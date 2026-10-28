"""
Folder Watcher Service for automatic invoice processing.
Monitors specified directories for new PDF files and automatically uploads them.
"""
import os
import asyncio
import logging
import uuid
import time
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

if TYPE_CHECKING:
    from watchdog.observers import Observer as ObserverType

from services.upload_service import upload_service, FileData, UploadSource
from services.database import db_service

logger = logging.getLogger(__name__)

class WatcherStatus(Enum):
    """Status of the folder watcher"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

class NotificationType(Enum):
    """Types of file processing notifications"""
    FILE_DETECTED = "file_detected"
    PROCESSING_STARTED = "processing_started"
    UPLOAD_SUCCESS = "upload_success"
    UPLOAD_FAILED = "upload_failed"
    VALIDATION_FAILED = "validation_failed"

@dataclass
class FileNotification:
    """Notification about file processing event"""
    id: str
    type: NotificationType
    filename: str
    file_path: str
    timestamp: str
    message: str
    error: Optional[str] = None
    invoice_id: Optional[str] = None
    file_size: Optional[int] = None
    watch_config_id: Optional[str] = None

@dataclass
class WatchConfig:
    """Configuration for a watched folder"""
    id: str
    folder_path: str
    pattern: str = "*.pdf"
    enabled: bool = True
    recursive: bool = False
    cooldown_seconds: int = 5  # Prevent duplicate processing
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    last_scan: Optional[str] = None
    files_processed: int = 0

@dataclass
class WatcherStats:
    """Statistics for folder watcher"""
    total_files_processed: int = 0
    successful_uploads: int = 0
    failed_uploads: int = 0
    folders_watched: int = 0
    uptime_seconds: int = 0
    last_activity: Optional[str] = None

class InvoiceFileHandler(FileSystemEventHandler):
    """Handles file system events for invoice processing"""
    
    def __init__(self, folder_watcher_service, watch_config: WatchConfig):
        super().__init__()
        self.folder_watcher = folder_watcher_service
        self.watch_config = watch_config
        self.processed_files: Set[str] = set()
        self.processing_queue: Dict[str, float] = {}  # file_path -> timestamp
        
    def on_created(self, event):
        """Handle file creation events"""
        if not event.is_directory:
            self._handle_file_event(event.src_path, "created")
    
    def on_modified(self, event):
        """Handle file modification events (sometimes files are written in chunks)"""
        if not event.is_directory:
            self._handle_file_event(event.src_path, "modified")

    def on_deleted(self, event):
        """Forget a file once it leaves the folder, so a new file at that path is processed"""
        if not event.is_directory:
            self.processed_files.discard(event.src_path)

    def on_moved(self, event):
        """Treat a move out as a delete and a move in (e.g. a finished download) as a new file"""
        if not event.is_directory:
            self.processed_files.discard(event.src_path)
            watched = os.path.realpath(self.watch_config.folder_path)
            if os.path.realpath(event.dest_path).startswith(watched + os.sep):
                self._handle_file_event(event.dest_path, "moved")
    
    def _handle_file_event(self, file_path: str, event_type: str):
        """Process file system events with enhanced validation"""
        try:
            # Convert to Path object for easier handling
            path = Path(file_path)
            
            # Check if it's a PDF file
            if not path.suffix.lower() == '.pdf':
                logger.debug(f"Ignoring non-PDF file: {file_path}")
                return
            
            # Check if file exists (might be deleted quickly)
            if not path.exists():
                logger.warning(f"File no longer exists: {file_path}")
                return
            
            # Prevent duplicate processing with cooldown
            current_time = time.time()
            if file_path in self.processing_queue:
                last_processed = self.processing_queue[file_path]
                if current_time - last_processed < self.watch_config.cooldown_seconds:
                    logger.debug(f"Skipping {file_path} - still in cooldown period")
                    return
            
            # Enhanced filename validation before processing
            filename = path.name
            filename_pattern = r'^(\d{8})_([^_]+)_([^_]+)_(.+)\.pdf$'
            
            if not re.match(filename_pattern, filename):
                logger.warning(f"❌ Invalid filename pattern: {filename}")
                self.folder_watcher._add_notification(FileNotification(
                    id=str(uuid.uuid4()),
                    type=NotificationType.VALIDATION_FAILED,
                    filename=filename,
                    file_path=file_path,
                    timestamp=datetime.now().isoformat(),
                    message=f"❌ Ungültiger Dateiname: {filename}",
                    error=f"Dateiname entspricht nicht dem Muster: EINGANGSDATUM_PROJEKT_GEWERK_LIEFERANT.pdf\n"
                          f"Beispiel: 20250704_OMEGA_ELEKTRO_Mueller.pdf",
                    watch_config_id=self.watch_config.id
                ))
                return
            
            # Check if file was already processed successfully
            if file_path in self.processed_files:
                logger.debug(f"File already processed successfully: {file_path}")
                return
            
            # Add to processing queue
            self.processing_queue[file_path] = current_time
            
            # Clean up old entries from processing queue
            cutoff_time = current_time - (self.watch_config.cooldown_seconds * 2)
            self.processing_queue = {
                k: v for k, v in self.processing_queue.items() 
                if v > cutoff_time
            }
            
            logger.info(f"📁 Detected {event_type} event for PDF: {file_path}")
            logger.info(f"📋 Filename validation passed: {filename}")
            
            # Send file detected notification
            self.folder_watcher._add_notification(FileNotification(
                id=str(uuid.uuid4()),
                type=NotificationType.FILE_DETECTED,
                filename=path.name,
                file_path=file_path,
                timestamp=datetime.now().isoformat(),
                message=f"📁 Neue PDF-Datei erkannt: {path.name}",
                watch_config_id=self.watch_config.id
            ))
            
            # Use thread-safe approach to schedule processing
            try:
                # Get the event loop from the main thread
                if hasattr(self.folder_watcher, '_event_loop') and self.folder_watcher._event_loop:
                    # Schedule coroutine to run in the main event loop
                    future = asyncio.run_coroutine_threadsafe(
                        self._process_file_async(file_path), 
                        self.folder_watcher._event_loop
                    )
                    logger.info(f"⚡ Scheduled async processing for: {file_path}")
                else:
                    # No event loop available, add to pending queue
                    logger.warning(f"⚠️ No event loop available, queuing file: {file_path}")
                    self.folder_watcher._pending_files.add(file_path)
            except Exception as e:
                logger.error(f"❌ Error scheduling file processing: {e}")
                # Fallback: add to pending queue
                self.folder_watcher._pending_files.add(file_path)
            
        except Exception as e:
            logger.error(f"❌ Error handling file event for {file_path}: {str(e)}")
            # Send error notification
            try:
                filename = Path(file_path).name if file_path else "unknown"
                self.folder_watcher._add_notification(FileNotification(
                    id=str(uuid.uuid4()),
                    type=NotificationType.UPLOAD_FAILED,
                    filename=filename,
                    file_path=file_path,
                    timestamp=datetime.now().isoformat(),
                    message=f"❌ Fehler beim Verarbeiten der Datei: {filename}",
                    error=str(e),
                    watch_config_id=self.watch_config.id
                ))
            except Exception as notify_error:
                logger.error(f"Failed to send error notification: {notify_error}")
    
    async def _process_file_async(self, file_path: str):
        """Asynchronously process detected file with enhanced error handling"""
        path = Path(file_path)
        notification_id = str(uuid.uuid4())
        
        try:
            # Send processing started notification
            self.folder_watcher._add_notification(FileNotification(
                id=notification_id,
                type=NotificationType.PROCESSING_STARTED,
                filename=path.name,
                file_path=file_path,
                timestamp=datetime.now().isoformat(),
                message=f"🔄 Verarbeitung gestartet: {path.name}",
                watch_config_id=self.watch_config.id
            ))
            
            # Wait a bit to ensure file is fully written
            await asyncio.sleep(3)  # Increased wait time for better stability
            
            # Check if file still exists and is readable
            if not path.exists():
                logger.warning(f"File no longer exists: {file_path}")
                self.folder_watcher._add_notification(FileNotification(
                    id=str(uuid.uuid4()),
                    type=NotificationType.UPLOAD_FAILED,
                    filename=path.name,
                    file_path=file_path,
                    timestamp=datetime.now().isoformat(),
                    message=f"❌ Datei nicht mehr vorhanden: {path.name}",
                    error="Die Datei wurde gelöscht oder ist nicht mehr verfügbar",
                    watch_config_id=self.watch_config.id
                ))
                return
            
            # Check file size and readability
            try:
                file_size = path.stat().st_size
                if file_size == 0:
                    logger.warning(f"File is empty: {file_path}")
                    self.folder_watcher._add_notification(FileNotification(
                        id=str(uuid.uuid4()),
                        type=NotificationType.VALIDATION_FAILED,
                        filename=path.name,
                        file_path=file_path,
                        timestamp=datetime.now().isoformat(),
                        message=f"❌ Validierungsfehler: {path.name}",
                        error="Die Datei ist leer (0 Bytes)",
                        watch_config_id=self.watch_config.id
                    ))
                    return
                
                logger.info(f"📊 File size check passed: {path.name} ({file_size} bytes)")
                
            except OSError as e:
                logger.error(f"Cannot access file stats {file_path}: {str(e)}")
                self.folder_watcher._add_notification(FileNotification(
                    id=str(uuid.uuid4()),
                    type=NotificationType.UPLOAD_FAILED,
                    filename=path.name,
                    file_path=file_path,
                    timestamp=datetime.now().isoformat(),
                    message=f"❌ Dateizugriffsfehler: {path.name}",
                    error=f"Datei-Eigenschaften können nicht gelesen werden: {str(e)}",
                    watch_config_id=self.watch_config.id
                ))
                return
            
            # Read file content
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                    
                logger.info(f"📖 File read successfully: {path.name} ({len(content)} bytes)")
                
            except (IOError, PermissionError) as e:
                error_msg = f"Datei konnte nicht gelesen werden: {str(e)}"
                logger.error(f"Cannot read file {file_path}: {str(e)}")
                self.folder_watcher._add_notification(FileNotification(
                    id=str(uuid.uuid4()),
                    type=NotificationType.UPLOAD_FAILED,
                    filename=path.name,
                    file_path=file_path,
                    timestamp=datetime.now().isoformat(),
                    message=f"❌ Lesefehler: {path.name}",
                    error=error_msg,
                    watch_config_id=self.watch_config.id
                ))
                return
            
            # Double-check content is not empty after reading
            if len(content) == 0:
                error_msg = "Die Datei ist leer nach dem Lesen"
                logger.warning(f"File content is empty after reading: {file_path}")
                self.folder_watcher._add_notification(FileNotification(
                    id=str(uuid.uuid4()),
                    type=NotificationType.VALIDATION_FAILED,
                    filename=path.name,
                    file_path=file_path,
                    timestamp=datetime.now().isoformat(),
                    message=f"❌ Validierungsfehler: {path.name}",
                    error=error_msg,
                    watch_config_id=self.watch_config.id
                ))
                return
            
            # Create FileData for upload service
            file_data = FileData(
                content=content,
                filename=path.name,
                content_type="application/pdf",
                file_size=len(content),
                source=UploadSource.FOLDER_WATCHER,
                source_metadata={
                    "folder_path": str(path.parent),
                    "original_path": file_path,
                    "detected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "watch_config_id": self.watch_config.id,
                    "event_type": "folder_watcher_auto"
                }
            )
            
            logger.info(f"📤 Starting upload process for: {path.name}")
            
            # Upload using common upload service
            result = await upload_service.upload_file(file_data)
            
            if result.success:
                logger.info(f"✅ Successfully uploaded {path.name} from folder watcher")
                logger.info(f"   📋 Invoice ID: {result.invoice_id}")
                logger.info(f"   🔗 Storage URL: {result.url}")
                
                # Send success notification
                self.folder_watcher._add_notification(FileNotification(
                    id=str(uuid.uuid4()),
                    type=NotificationType.UPLOAD_SUCCESS,
                    filename=path.name,
                    file_path=file_path,
                    timestamp=datetime.now().isoformat(),
                    message=f"✅ Upload erfolgreich: {path.name}",
                    invoice_id=result.invoice_id,
                    file_size=result.file_size,
                    watch_config_id=self.watch_config.id
                ))
                
                # Update statistics
                self.folder_watcher.stats.successful_uploads += 1
                self.folder_watcher.stats.total_files_processed += 1
                self.folder_watcher.stats.last_activity = time.strftime("%Y-%m-%d %H:%M:%S")
                self.watch_config.files_processed += 1
                
                # Mark as processed
                self.processed_files.add(file_path)
                
                logger.info(f"📈 Stats updated - Total: {self.folder_watcher.stats.total_files_processed}, "
                           f"Success: {self.folder_watcher.stats.successful_uploads}")
                
            else:
                logger.error(f"❌ Failed to upload {path.name}: {result.error}")
                
                # Determine notification type based on error
                notification_type = NotificationType.UPLOAD_FAILED
                error_message = result.error or "Unbekannter Fehler"
                
                # Check if it's a validation error (enhanced detection)
                validation_keywords = [
                    "dateiname", "muster", "pattern", "filename", "format", 
                    "pdf", "dateityp", "filetype", "zu groß", "too large",
                    "leer", "empty", "existiert bereits", "already exists", 
                    "duplicate", "duplikat", "ähnliche", "similar", "ungültig"
                ]
                
                if error_message and any(keyword in error_message.lower() for keyword in validation_keywords):
                    notification_type = NotificationType.VALIDATION_FAILED
                    logger.warning(f"🔍 Validation error detected: {error_message}")
                else:
                    logger.error(f"💥 Upload error: {error_message}")
                
                # Send failure notification with specific error
                self.folder_watcher._add_notification(FileNotification(
                    id=str(uuid.uuid4()),
                    type=notification_type,
                    filename=path.name,
                    file_path=file_path,
                    timestamp=datetime.now().isoformat(),
                    message=f"{'❌ Validierungsfehler' if notification_type == NotificationType.VALIDATION_FAILED else '💥 Upload fehlgeschlagen'}: {path.name}",
                    error=error_message,
                    watch_config_id=self.watch_config.id
                ))
                
                self.folder_watcher.stats.failed_uploads += 1
                logger.info(f"📉 Failed uploads count: {self.folder_watcher.stats.failed_uploads}")
                
        except Exception as e:
            logger.error(f"💥 Error processing file {file_path}: {str(e)}")
            
            # Send generic error notification
            self.folder_watcher._add_notification(FileNotification(
                id=str(uuid.uuid4()),
                type=NotificationType.UPLOAD_FAILED,
                filename=path.name,
                file_path=file_path,
                timestamp=datetime.now().isoformat(),
                message=f"💥 Verarbeitungsfehler: {path.name}",
                error=f"Unerwarteter Fehler: {str(e)}",
                watch_config_id=self.watch_config.id
            ))
            
            self.folder_watcher.stats.failed_uploads += 1

class FolderWatcherService:
    """Main folder watcher service"""
    
    def __init__(self):
        self.status = WatcherStatus.STOPPED
        self.watch_configs: Dict[str, WatchConfig] = {}
        self.observers: Dict[str, Any] = {}  # Observer instances
        self.handlers: Dict[str, InvoiceFileHandler] = {}
        self.stats = WatcherStats()
        self.start_time: Optional[float] = None
        self._lock = asyncio.Lock()
        self._pending_files: Set[str] = set()  # Files queued for processing
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None  # Main event loop reference
        
        # Notification system
        self._notifications: List[FileNotification] = []
        self._max_notifications = 100  # Keep last 100 notifications
    
    def _add_notification(self, notification: FileNotification):
        """Add a new notification to the list"""
        self._notifications.append(notification)
        
        # Keep only the most recent notifications
        if len(self._notifications) > self._max_notifications:
            self._notifications = self._notifications[-self._max_notifications:]
        
        logger.info(f"📋 Notification: {notification.message}")
    
    def get_notifications(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent notifications"""
        recent_notifications = self._notifications[-limit:] if limit else self._notifications
        return [
            {
                "id": notif.id,
                "type": notif.type.value,
                "filename": notif.filename,
                "file_path": notif.file_path,
                "timestamp": notif.timestamp,
                "message": notif.message,
                "error": notif.error,
                "invoice_id": notif.invoice_id,
                "file_size": notif.file_size,
                "watch_config_id": notif.watch_config_id
            }
            for notif in reversed(recent_notifications)  # Most recent first
        ]
    
    def clear_notifications(self):
        """Clear all notifications"""
        self._notifications.clear()
        logger.info("📋 All notifications cleared")

    async def add_watch_folder(self, folder_path: str, pattern: str = "*.pdf", 
                             recursive: bool = False, enabled: bool = True) -> Tuple[bool, str, Optional[str]]:
        """
        Add a folder to watch for new files
        Returns (success, config_id, error_message)
        """
        try:
            # Validate folder path with better normalization
            import os
            
            # Normalize the path to handle any path resolution issues
            normalized_path = os.path.abspath(os.path.expanduser(folder_path))
            path = Path(normalized_path)
            
            if not path.exists():
                return False, "", f"Folder does not exist: {folder_path}"
            
            if not path.is_dir():
                return False, "", f"Path is not a directory: {folder_path}"
            
            # Check if folder is already being watched
            resolved_path = str(path.resolve())
            
            for config in self.watch_configs.values():
                if config.folder_path == resolved_path:
                    return False, "", f"Folder is already being watched: {folder_path}"
            
            # Create watch configuration
            config_id = str(uuid.uuid4())
            watch_config = WatchConfig(
                id=config_id,
                folder_path=resolved_path,
                pattern=pattern,
                enabled=enabled,
                recursive=recursive
            )
            
            self.watch_configs[config_id] = watch_config
            
            # If watcher is running, start watching this folder immediately
            if self.status == WatcherStatus.RUNNING and enabled:
                await self._start_watching_folder(config_id)
            
            logger.info(f"Added watch folder: {folder_path} (ID: {config_id})")
            return True, config_id, None
            
        except Exception as e:
            logger.error(f"Error adding watch folder {folder_path}: {str(e)}")
            return False, "", str(e)
    
    async def remove_watch_folder(self, config_id: str) -> Tuple[bool, Optional[str]]:
        """
        Remove a folder from watching
        Returns (success, error_message)
        """
        try:
            if config_id not in self.watch_configs:
                return False, f"Watch configuration not found: {config_id}"
            
            # Stop watching this folder if currently active
            if config_id in self.observers:
                await self._stop_watching_folder(config_id)
            
            # Remove configuration
            config = self.watch_configs.pop(config_id)
            logger.info(f"Removed watch folder: {config.folder_path}")
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error removing watch folder {config_id}: {str(e)}")
            return False, str(e)
    
    async def start_watcher(self) -> Tuple[bool, Optional[str]]:
        """
        Start the folder watcher service
        Returns (success, error_message)
        """
        async with self._lock:
            try:
                if self.status == WatcherStatus.RUNNING:
                    return True, None  # Already running
                
                if self.status == WatcherStatus.STARTING:
                    return False, "Watcher is already starting"
                
                self.status = WatcherStatus.STARTING
                self.start_time = time.time()
                
                # Store reference to current event loop for thread-safe async processing
                try:
                    self._event_loop = asyncio.get_running_loop()
                    logger.info("Event loop reference stored for async processing")
                except RuntimeError:
                    logger.warning("No running event loop found")
                    self._event_loop = None
                
                logger.info("Starting folder watcher service...")
                
                # Start watching all enabled folders
                for config_id, config in self.watch_configs.items():
                    if config.enabled:
                        await self._start_watching_folder(config_id)
                
                self.status = WatcherStatus.RUNNING
                self.stats.folders_watched = len([c for c in self.watch_configs.values() if c.enabled])
                
                logger.info(f"Folder watcher started successfully - watching {self.stats.folders_watched} folders")
                return True, None
                
            except Exception as e:
                self.status = WatcherStatus.ERROR
                logger.error(f"Error starting folder watcher: {str(e)}")
                return False, str(e)
    
    async def stop_watcher(self) -> Tuple[bool, Optional[str]]:
        """
        Stop the folder watcher service
        Returns (success, error_message)
        """
        async with self._lock:
            try:
                if self.status == WatcherStatus.STOPPED:
                    return True, None  # Already stopped
                
                if self.status == WatcherStatus.STOPPING:
                    return False, "Watcher is already stopping"
                
                self.status = WatcherStatus.STOPPING
                
                logger.info("Stopping folder watcher service...")
                
                # Stop all observers
                for config_id in list(self.observers.keys()):
                    await self._stop_watching_folder(config_id)
                
                self.status = WatcherStatus.STOPPED
                self.start_time = None
                
                logger.info("Folder watcher stopped successfully")
                return True, None
                
            except Exception as e:
                self.status = WatcherStatus.ERROR
                logger.error(f"Error stopping folder watcher: {str(e)}")
                return False, str(e)
    
    async def _start_watching_folder(self, config_id: str):
        """Start watching a specific folder"""
        try:
            config = self.watch_configs[config_id]
            
            # Create file handler
            handler = InvoiceFileHandler(self, config)
            self.handlers[config_id] = handler
            
            # Create and start observer
            observer = Observer()
            observer.schedule(handler, config.folder_path, recursive=config.recursive)
            observer.start()
            
            self.observers[config_id] = observer
            config.last_scan = time.strftime("%Y-%m-%d %H:%M:%S")
            
            logger.info(f"Started watching folder: {config.folder_path}")
            
        except Exception as e:
            logger.error(f"Error starting watch for folder {config_id}: {str(e)}")
            # Clean up on error
            if config_id in self.observers:
                self.observers[config_id].stop()
                del self.observers[config_id]
            if config_id in self.handlers:
                del self.handlers[config_id]
    
    async def _stop_watching_folder(self, config_id: str):
        """Stop watching a specific folder"""
        try:
            if config_id in self.observers:
                observer = self.observers[config_id]
                observer.stop()
                observer.join(timeout=5)  # Wait up to 5 seconds
                del self.observers[config_id]
            
            if config_id in self.handlers:
                del self.handlers[config_id]
            
            if config_id in self.watch_configs:
                config = self.watch_configs[config_id]
                logger.info(f"Stopped watching folder: {config.folder_path}")
                
        except Exception as e:
            logger.error(f"Error stopping watch for folder {config_id}: {str(e)}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current watcher status and statistics"""
        # Update uptime
        if self.start_time and self.status == WatcherStatus.RUNNING:
            self.stats.uptime_seconds = int(time.time() - self.start_time)
        
        return {
            "status": self.status.value,
            "uptime_seconds": self.stats.uptime_seconds,
            "folders_watched": len([c for c in self.watch_configs.values() if c.enabled]),
            "total_folders_configured": len(self.watch_configs),
            "statistics": {
                "total_files_processed": self.stats.total_files_processed,
                "successful_uploads": self.stats.successful_uploads,
                "failed_uploads": self.stats.failed_uploads,
                "last_activity": self.stats.last_activity
            },
            "watch_configs": [
                {
                    "id": config.id,
                    "folder_path": config.folder_path,
                    "pattern": config.pattern,
                    "enabled": config.enabled,
                    "recursive": config.recursive,
                    "files_processed": config.files_processed,
                    "last_scan": config.last_scan,
                    "created_at": config.created_at,
                    "is_watching": config.id in self.observers
                }
                for config in self.watch_configs.values()
            ]
        }
    
    def get_watch_folders(self) -> List[Dict[str, Any]]:
        """Get list of configured watch folders"""
        return [
            {
                "id": config.id,
                "folder_path": config.folder_path,
                "pattern": config.pattern,
                "enabled": config.enabled,
                "recursive": config.recursive,
                "files_processed": config.files_processed,
                "last_scan": config.last_scan,
                "created_at": config.created_at,
                "is_watching": config.id in self.observers
            }
            for config in self.watch_configs.values()
        ]
    
    async def enable_watch_folder(self, config_id: str) -> Tuple[bool, Optional[str]]:
        """Enable watching for a specific folder"""
        try:
            if config_id not in self.watch_configs:
                return False, f"Watch configuration not found: {config_id}"
            
            config = self.watch_configs[config_id]
            config.enabled = True
            
            # If watcher is running, start watching this folder
            if self.status == WatcherStatus.RUNNING and config_id not in self.observers:
                await self._start_watching_folder(config_id)
            
            logger.info(f"Enabled watch folder: {config.folder_path}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error enabling watch folder {config_id}: {str(e)}")
            return False, str(e)
    
    async def disable_watch_folder(self, config_id: str) -> Tuple[bool, Optional[str]]:
        """Disable watching for a specific folder"""
        try:
            if config_id not in self.watch_configs:
                return False, f"Watch configuration not found: {config_id}"
            
            config = self.watch_configs[config_id]
            config.enabled = False
            
            # Stop watching this folder if currently active
            if config_id in self.observers:
                await self._stop_watching_folder(config_id)
            
            logger.info(f"Disabled watch folder: {config.folder_path}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error disabling watch folder {config_id}: {str(e)}")
            return False, str(e)

    async def process_pending_files(self) -> int:
        """Process any files that were queued due to async processing issues"""
        if not self._pending_files:
            return 0
        
        processed_count = 0
        pending_copy = self._pending_files.copy()
        self._pending_files.clear()
        
        for file_path in pending_copy:
            try:
                # Find the handler for this file based on its path
                for config_id, handler in self.handlers.items():
                    config = self.watch_configs[config_id]
                    if file_path.startswith(config.folder_path):
                        await handler._process_file_async(file_path)
                        processed_count += 1
                        break
                else:
                    logger.warning(f"No handler found for pending file: {file_path}")
            except Exception as e:
                logger.error(f"Error processing pending file {file_path}: {e}")
        
        if processed_count > 0:
            logger.info(f"Processed {processed_count} pending files")
        
        return processed_count

    async def scan_existing_files(self, config_id: str) -> Dict[str, Any]:
        """
        Scan existing files in a watched folder for processing
        This helps catch files that were added while the watcher was offline
        """
        if config_id not in self.watch_configs:
            return {"success": False, "error": "Watch configuration not found"}
        
        config = self.watch_configs[config_id]
        scan_results = {
            "success": True,
            "folder_path": config.folder_path,
            "files_found": 0,
            "files_processed": 0,
            "files_skipped": 0,
            "errors": []
        }
        
        try:
            folder_path = Path(config.folder_path)
            if not folder_path.exists():
                return {"success": False, "error": f"Folder does not exist: {config.folder_path}"}
            
            # Find all PDF files
            pdf_files = list(folder_path.glob("*.pdf"))
            scan_results["files_found"] = len(pdf_files)
            
            logger.info(f"🔍 Scanning existing files in {config.folder_path}: found {len(pdf_files)} PDF files")
            
            for pdf_file in pdf_files:
                try:
                    file_path = str(pdf_file)
                    
                    # Skip if already processed
                    if config_id in self.handlers:
                        handler = self.handlers[config_id]
                        if file_path in handler.processed_files:
                            scan_results["files_skipped"] += 1
                            continue
                    
                    # Check filename pattern
                    filename_pattern = r'^(\d{8})_([^_]+)_([^_]+)_(.+)\.pdf$'
                    if not re.match(filename_pattern, pdf_file.name):
                        logger.warning(f"⚠️ Skipping file with invalid pattern: {pdf_file.name}")
                        scan_results["errors"].append(f"Invalid filename pattern: {pdf_file.name}")
                        scan_results["files_skipped"] += 1
                        continue
                    
                    # Check if database has this file already
                    if db_service.is_available:
                        duplicate_result = db_service.check_duplicate_by_filename(pdf_file.name)
                        if duplicate_result.get("success") and duplicate_result.get("duplicate_found"):
                            logger.info(f"🔍 File already exists in database: {pdf_file.name}")
                            scan_results["files_skipped"] += 1
                            continue
                    
                    # Process the file
                    logger.info(f"🔄 Processing existing file: {pdf_file.name}")
                    
                    # Simulate file detection event
                    if config_id in self.handlers:
                        handler = self.handlers[config_id]
                        await handler._process_file_async(file_path)
                        scan_results["files_processed"] += 1
                    else:
                        scan_results["errors"].append(f"No handler available for config {config_id}")
                    
                except Exception as file_error:
                    error_msg = f"Error processing {pdf_file.name}: {str(file_error)}"
                    logger.error(error_msg)
                    scan_results["errors"].append(error_msg)
            
            # Update scan timestamp
            config.last_scan = time.strftime("%Y-%m-%d %H:%M:%S")
            
            logger.info(f"📊 Scan completed - Found: {scan_results['files_found']}, "
                       f"Processed: {scan_results['files_processed']}, "
                       f"Skipped: {scan_results['files_skipped']}, "
                       f"Errors: {len(scan_results['errors'])}")
            
            return scan_results
            
        except Exception as e:
            logger.error(f"❌ Error during folder scan: {str(e)}")
            return {"success": False, "error": str(e)}

# Global service instance
folder_watcher_service = FolderWatcherService()
