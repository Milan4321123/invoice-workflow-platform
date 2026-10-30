"""
Common upload service for invoice files.
Handles file upload logic shared between drag & drop and folder watcher.
Clean implementation without external processing dependencies.
"""
import os
import re
import uuid
import datetime
import logging
from typing import Dict, Any, Optional, Tuple, Union, BinaryIO
from dataclasses import dataclass
from enum import Enum

from services.database import db_service
from services.e_invoice import EInvoice, EInvoiceError, parse_pdf, parse_xml

logger = logging.getLogger(__name__)

class UploadSource(Enum):
    """Source of the upload"""
    DRAG_DROP = "drag_drop"
    FOLDER_WATCHER = "folder_watcher"
    MANUAL = "manual"

@dataclass
class UploadResult:
    """Result of file upload operation"""
    success: bool
    invoice_id: Optional[str] = None
    filename: Optional[str] = None
    url: Optional[str] = None
    file_size: Optional[int] = None
    error: Optional[str] = None
    source: Optional[UploadSource] = None
    storage_path: Optional[str] = None
    e_invoice_format: Optional[str] = None
    rejected: bool = False  # the file itself is not acceptable (400), as opposed to a server error

@dataclass
class FileData:
    """Container for file data and metadata"""
    content: bytes
    filename: str
    content_type: str
    file_size: int
    source: UploadSource
    source_metadata: Optional[Dict[str, Any]] = None

class UploadService:
    """Centralized upload service for invoice files"""
    
    # Filename pattern validation following German business convention:
    # FIXED Pattern: EINGANGSDATUM_PROJEKT_GEWERK_LIEFERANT.pdf
    # - EINGANGSDATUM: YYYYMMDD (8 digits - receipt date)
    # - PROJEKT: Project identifier (letters, numbers, hyphens, periods)
    # - GEWERK: Trade/work type (letters, numbers, hyphens, periods)  
    # - LIEFERANT: Supplier name (letters, numbers, hyphens, periods)
    # Must be exactly 4 parts separated by underscores
    # Supports German characters (ä, ö, ü, ß) and international characters
    FILENAME_PATTERN = r'^\d{8}_[A-Za-z0-9äöüÄÖÜß][A-Za-z0-9äöüÄÖÜß.\-]*_[A-Za-z0-9äöüÄÖÜß][A-Za-z0-9äöüÄÖÜß.\-]*_[A-Za-z0-9äöüÄÖÜß][A-Za-z0-9äöüÄÖÜß.\-]*\.(pdf|xml)$'
    
    # PDF (scan or ZUGFeRD/Factur-X) or bare XML (XRechnung)
    SUPPORTED_CONTENT_TYPES = {"application/pdf", "application/xml", "text/xml"}
    XML_CONTENT_TYPES = {"application/xml", "text/xml"}
    
    # Max file size (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    def __init__(self):
        # Use separate buckets for different upload sources
        self.buckets = {
            UploadSource.DRAG_DROP: "invoices",
            UploadSource.FOLDER_WATCHER: "folderwatcher", 
            UploadSource.MANUAL: "manual-invoices"
        }
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to prevent path traversal and XSS attacks
        """
        if not filename:
            return "unknown.pdf"
        
        # Remove path traversal attempts
        filename = os.path.basename(filename)
        
        # Remove or replace dangerous characters
        # Keep only alphanumeric, dots, dashes, underscores
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        
        # Remove multiple dots that could be used for traversal
        filename = re.sub(r'\.{2,}', '.', filename)
        
        # Keep .pdf or .xml (e-invoice), anything else becomes .pdf
        if not filename.lower().endswith(('.pdf', '.xml')):
            filename = filename + '.pdf'
        
        # Limit length
        if len(filename) > 255:
            name_part, extension = filename[:-4][:250], filename[-4:]
            filename = name_part + extension
        
        return filename
    
    def validate_file(self, file_data: FileData) -> Tuple[bool, Optional[str]]:
        """
        Validate file content and metadata with comprehensive duplicate checking
        Returns (is_valid, error_message)
        """
        # Step 1: Basic file validation
        if file_data.file_size == 0:
            return False, "Die Datei ist leer"
        
        if file_data.file_size > self.MAX_FILE_SIZE:
            return False, f"Datei ist zu groß. Maximum: {self.MAX_FILE_SIZE // (1024*1024)}MB"
        
        if file_data.content_type not in self.SUPPORTED_CONTENT_TYPES:
            return False, "Nur PDF-Dateien oder E-Rechnungen (XML) sind erlaubt"
        
        # Step 2: Enhanced filename pattern validation
        if not re.match(self.FILENAME_PATTERN, file_data.filename):
            if file_data.source == UploadSource.FOLDER_WATCHER:
                return False, f"❌ Dateiname '{file_data.filename}' entspricht nicht dem erforderlichen Muster:\n" \
                             f"   Format: EINGANGSDATUM_PROJEKT_GEWERK_LIEFERANT.pdf (oder .xml)\n" \
                             f"   Beispiel: 20250704_OMEGA_ELEKTRO_Mueller.pdf\n" \
                             f"   - EINGANGSDATUM: 8 Ziffern (JJJJMMTT)\n" \
                             f"   - PROJEKT: Projektname ohne Unterstriche\n" \
                             f"   - GEWERK: Gewerkebezeichnung\n" \
                             f"   - LIEFERANT: Lieferantenname"
            else:
                return False, "Dateiname muss dem Muster folgen: EINGANGSDATUM_PROJEKT_GEWERK_LIEFERANT.pdf (oder .xml)"
        
        # Step 3: Enhanced duplicate checking for folder watcher
        if file_data.source == UploadSource.FOLDER_WATCHER and db_service.is_available:
            
            # 3a: Check for exact filename duplicates
            duplicate_result = db_service.check_duplicate_by_filename(file_data.filename)
            if duplicate_result.get("success") and duplicate_result.get("duplicate_found"):
                existing_file = duplicate_result.get("existing_file", {})
                return False, f"🚫 DUPLIKAT ERKANNT: Eine Datei mit dem Namen '{file_data.filename}' " \
                             f"existiert bereits!\n" \
                             f"   Ursprünglich hochgeladen: {existing_file.get('created_at', 'unbekannt')}\n" \
                             f"   Dateigröße: {existing_file.get('file_size', 'unbekannt')} Bytes\n" \
                             f"   Invoice ID: {existing_file.get('id', 'unbekannt')}"
            
            # 3b: Check for content similarity (same project/gewerk/lieferant)
            similarity_result = db_service.check_duplicate_by_content_similarity(
                file_data.filename, file_data.file_size, tolerance_bytes=2048
            )
            if similarity_result.get("success") and similarity_result.get("duplicate_found"):
                similar_files = similarity_result.get("similar_files", [])
                if similar_files:
                    file_info = []
                    for similar_file in similar_files[:3]:  # Show max 3 similar files
                        file_info.append(f"   • {similar_file.get('file_name', 'unbekannt')} "
                                       f"({similar_file.get('created_at', 'unbekannt')})")
                    
                    return False, f"⚠️ ÄHNLICHE DATEIEN GEFUNDEN: Es existieren bereits ähnliche Rechnungen " \
                                 f"für dasselbe Projekt/Gewerk:\n" + "\n".join(file_info) + \
                                 f"\n   Bitte prüfen Sie, ob diese Rechnung bereits erfasst wurde."
            
            # 3c: Handle database errors more strictly for folder watcher
            if not duplicate_result.get("success"):
                return False, f"❌ FEHLER BEI DUPLIKATSPRÜFUNG: {duplicate_result.get('error', 'Unbekannter Fehler')}\n" \
                             f"   Aus Sicherheitsgründen wird der Upload blockiert."
        
        # Step 4: Basic duplicate checking for manual uploads
        elif db_service.is_available:
            try:
                response = db_service.client.table("invoices_clean").select("id,file_name,created_at").eq("file_name", file_data.filename).execute()
                if response.data and len(response.data) > 0:
                    existing_file = response.data[0]
                    logger.warning(f"Duplicate file detected: {file_data.filename} (existing ID: {existing_file['id']})")
                    return False, f"Eine Datei mit dem Namen '{file_data.filename}' existiert bereits " \
                                 f"(hochgeladen am {existing_file.get('created_at', 'unbekannt')})"
            except Exception as e:
                logger.error(f"Error checking for duplicate files: {e}")
                # For manual uploads, we log but don't fail completely
                logger.warning(f"Could not check for duplicate files: {e}")
        else:
            logger.warning("Database service not available - cannot check for duplicates")
            if file_data.source == UploadSource.FOLDER_WATCHER:
                return False, "❌ Datenbank nicht verfügbar - Duplikatsprüfung nicht möglich. " \
                             "Upload aus Sicherheitsgründen blockiert."
        
        return True, None
    
    def read_e_invoice(self, file_data: FileData) -> Tuple[Optional[EInvoice], Optional[str]]:
        """
        Structured invoice data, if the file carries any. Returns (e_invoice, error).
        A bare XML upload must be a readable e-invoice; a PDF without embedded
        XML is an ordinary scanned invoice.
        """
        if file_data.content_type in self.XML_CONTENT_TYPES:
            try:
                return parse_xml(file_data.content), None
            except EInvoiceError as e:
                return None, f"Keine lesbare E-Rechnung: {e}"
        try:
            return parse_pdf(file_data.content), None
        except EInvoiceError as e:
            # The PDF itself is still a valid invoice copy; fields are entered by hand
            logger.warning(f"Embedded invoice XML in {file_data.filename} is unreadable: {e}")
            return None, None

    def generate_storage_path(self, filename: str, source: UploadSource) -> str:
        """
        Generate storage path based on source and filename
        For database storage, we include bucket prefix to help with PDF URL construction
        """
        if source == UploadSource.FOLDER_WATCHER:
            return f"folder_watcher/{filename}"
        elif source == UploadSource.MANUAL:
            return f"manual/{filename}"
        else:  # DRAG_DROP
            return filename  # No prefix for drag-drop (default)
    async def upload_to_storage(self, file_data: FileData, storage_path: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Upload file to Supabase storage using the appropriate bucket
        Returns (success, public_url, error_message)
        """
        if not db_service.is_available:
            raise Exception("Database service not available")

        try:
            # Get the appropriate bucket for this upload source
            bucket_name = self.buckets[file_data.source]
            
            # Extract just the filename for storage (remove any prefix)
            filename = storage_path.split('/')[-1] if '/' in storage_path else storage_path
            
            # Upload file to the source-specific bucket using just the filename
            db_service.client.storage.from_(bucket_name).upload(filename, file_data.content)
            
            # Get public URL from the specific bucket
            public_url = db_service.client.storage.from_(bucket_name).get_public_url(filename)
            
            return True, public_url, None
            
        except Exception as e:
            logger.error(f"Storage upload failed to bucket '{bucket_name}': {str(e)}")
            return False, None, str(e)
    
    def create_invoice_record(self, file_data: FileData, storage_path: str, 
                            public_url: str, invoice_id: str,
                            e_invoice: Optional[EInvoice] = None) -> Tuple[bool, Optional[str]]:
        """
        Create invoice record in database (clean, no OCR dependencies)
        Returns (success, error_message)
        """
        try:
            # Prepare base database record using exact schema field names
            invoice_data = {
                "id": invoice_id,
                "file_name": file_data.filename,
                "file_path": storage_path,
                "file_size": file_data.file_size,
                "mime_type": file_data.content_type,
                "status": "uploaded"  # Use valid status value instead of "nicht_begonnen"
                # Note: upload_source removed as column doesn't exist in current schema
                # created_at and updated_at will be auto-generated by database default
            }
            if e_invoice:
                # Values from the XML are exact; the editor still shows them for review
                invoice_data.update(e_invoice.invoice_fields())
                invoice_data["e_rechnung_format"] = e_invoice.format
            # Create invoice record in database using clean database service
            if db_service.is_available:
                logger.info(f"🔍 Database available, creating invoice record for {invoice_id}")
                create_result = db_service.create_invoice(invoice_data)
                logger.info(f"🔍 Database create result: {create_result}")
                
                if not create_result.get("success"):
                    error_msg = create_result.get("error", "Unknown database error")
                    logger.warning(f"Failed to save invoice to database: {error_msg}")
                    return False, error_msg
                else:
                    logger.info(f"✅ Invoice saved successfully: {invoice_id}")
            else:
                logger.warning(f"Database unavailable - invoice record not persisted: {invoice_id}")
            
            return True, None
            
        except Exception as e:
            logger.error(f"Database record creation failed: {str(e)}")
            return False, str(e)
    
    def _process_field_value(self, value: str, data_type: str) -> Any:
        """
        Process field value based on expected data type
        """
        if not value or value == "":
            return None
            
        try:
            if data_type == "numeric":
                # Extract numeric value from strings like "1,234.56 EUR" or "€1,234.56"
                import re
                # Remove currency symbols and extract numbers
                numeric_match = re.search(r'[\d,]+\.?\d*', str(value))
                if numeric_match:
                    numeric_str = numeric_match.group().replace(',', '')
                    return float(numeric_str) if '.' in numeric_str else int(numeric_str)
                return None
                
            elif data_type == "date":
                # Handle various date formats
                if isinstance(value, str):
                    # Try to parse common date formats
                    from datetime import datetime
                    date_formats = [
                        "%Y-%m-%d",
                        "%d.%m.%Y",
                        "%d/%m/%Y",
                        "%m/%d/%Y",
                        "%Y-%m-%d %H:%M:%S"
                    ]
                    for fmt in date_formats:
                        try:
                            parsed_date = datetime.strptime(value, fmt)
                            return parsed_date.date().isoformat()
                        except ValueError:
                            continue
                    # If no format matches, return as-is
                    return value
                return value
                
            else:  # text or default
                return str(value).strip()
                
        except Exception as e:
            logger.warning(f"Failed to process field value '{value}' as {data_type}: {e}")
            return None
    
    async def upload_file(self, file_data: FileData) -> UploadResult:
        """
        Main upload method that orchestrates the entire upload process
        """
        try:
            # Step 1: Sanitize filename
            safe_filename = self.sanitize_filename(file_data.filename)
            file_data.filename = safe_filename
            
            # Step 2: Validate file
            is_valid, validation_error = self.validate_file(file_data)
            if not is_valid:
                return UploadResult(
                    success=False,
                    error=validation_error,
                    source=file_data.source,
                    rejected=True
                )
            
            # Step 2b: Read structured data from XRechnung / ZUGFeRD
            e_invoice, e_invoice_error = self.read_e_invoice(file_data)
            if e_invoice_error:
                return UploadResult(success=False, error=e_invoice_error, source=file_data.source, rejected=True)

            # Step 3: Generate storage path
            storage_path = self.generate_storage_path(safe_filename, file_data.source)
            
            # Step 4: Upload to storage
            upload_success, public_url, upload_error = await self.upload_to_storage(file_data, storage_path)
            if not upload_success:
                return UploadResult(
                    success=False,
                    error=f"Storage upload failed: {upload_error}",
                    source=file_data.source
                )
            
            # Step 5: Generate invoice ID
            invoice_id = str(uuid.uuid4())
            
            # Step 6: Create database record
            db_success, db_error = self.create_invoice_record(
                file_data, storage_path, public_url, invoice_id, e_invoice
            )
            if not db_success:
                # Log error but don't fail the upload completely
                logger.warning(f"Database record creation failed: {db_error}")
            
            # Step 7: Return success result
            return UploadResult(
                success=True,
                invoice_id=invoice_id,
                filename=safe_filename,
                url=public_url,
                file_size=file_data.file_size,
                source=file_data.source,
                storage_path=storage_path,
                e_invoice_format=e_invoice.format if e_invoice else None
            )
            
        except Exception as e:
            logger.error(f"Upload process failed: {str(e)}")
            return UploadResult(
                success=False,
                error=f"Upload failed: {str(e)}",
                source=file_data.source
            )

# Global instance
upload_service = UploadService()
