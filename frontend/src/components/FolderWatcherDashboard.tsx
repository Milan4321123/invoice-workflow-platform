'use client'

import React, { useState, useEffect } from 'react'
import { toast } from 'react-hot-toast'
import { getApiUrl } from '@/config/api'
import { 
  FolderIcon, 
  PlayIcon, 
  StopIcon, 
  PlusIcon, 
  TrashIcon,
  EyeIcon,
  EyeSlashIcon,
  CogIcon,
  DocumentIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline'
import { authFetch } from '@/lib/authFetch';

// Types for Folder Watcher
interface WatchFolder {
  id: string
  folder_path: string
  pattern: string
  enabled: boolean
  recursive: boolean
  files_processed: number
  last_scan: string | null
  created_at: string
  is_watching: boolean
}

interface WatcherStatus {
  status: 'stopped' | 'starting' | 'running' | 'stopping' | 'error'
  uptime_seconds: number
  folders_watched: number
  total_folders_configured: number
  statistics: {
    total_files_processed: number
    successful_uploads: number
    failed_uploads: number
    last_activity: string | null
  }
}

interface WatcherStatistics {
  status: string
  uptime_seconds: number
  uptime_formatted: string
  folders: {
    watched: number
    total_configured: number
    active: number
  }
  processing: {
    total_files_processed: number
    successful_uploads: number
    failed_uploads: number
    last_activity: string | null
  }
  watch_configs: WatchFolder[]
}

export function FolderWatcherDashboard() {
  const [watcherStatus, setWatcherStatus] = useState<WatcherStatus | null>(null)
  const [watchFolders, setWatchFolders] = useState<WatchFolder[]>([])
  const [statistics, setStatistics] = useState<WatcherStatistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  // Add folder modal state
  const [showAddModal, setShowAddModal] = useState(false)
  const [newFolderPath, setNewFolderPath] = useState('')
  const [newFolderPattern, setNewFolderPattern] = useState('*.pdf')
  const [newFolderRecursive, setNewFolderRecursive] = useState(false)

  // Fetch watcher status
  const fetchWatcherStatus = async () => {
    try {
      const apiUrl = getApiUrl()
      const response = await authFetch(`${apiUrl}/api/folder-watcher/status`)
      if (response.ok) {
        const data = await response.json()
        setWatcherStatus(data)
      } else {
        console.error('Failed to fetch watcher status')
      }
    } catch (error) {
      console.error('Error fetching watcher status:', error)
    }
  }

  // Fetch watch folders
  const fetchWatchFolders = async () => {
    try {
      const apiUrl = getApiUrl()
      const response = await authFetch(`${apiUrl}/api/folder-watcher/folders`)
      if (response.ok) {
        const data = await response.json()
        setWatchFolders(data)
      } else {
        console.error('Failed to fetch watch folders')
      }
    } catch (error) {
      console.error('Error fetching watch folders:', error)
    }
  }

  // Fetch detailed statistics
  const fetchStatistics = async () => {
    try {
      const apiUrl = getApiUrl()
      const response = await authFetch(`${apiUrl}/api/folder-watcher/statistics`)
      if (response.ok) {
        const data = await response.json()
        setStatistics(data)
      } else {
        console.error('Failed to fetch statistics')
      }
    } catch (error) {
      console.error('Error fetching statistics:', error)
    }
  }

  // Load all data
  const loadData = async () => {
    setLoading(true)
    await Promise.all([
      fetchWatcherStatus(),
      fetchWatchFolders(),
      fetchStatistics()
    ])
    setLoading(false)
  }

  // Start watcher service
  const startWatcher = async () => {
    setActionLoading('start')
    try {
      const apiUrl = getApiUrl()
      const response = await authFetch(`${apiUrl}/api/folder-watcher/start`, {
        method: 'POST'
      })
      
      if (response.ok) {
        toast.success('Ordnerüberwachung erfolgreich gestartet')
        await loadData()
      } else {
        const error = await response.json()
        toast.error(`Fehler beim Starten der Überwachung: ${error.detail}`)
      }
    } catch (error) {
      toast.error('Fehler beim Starten der Ordnerüberwachung')
      console.error('Start watcher error:', error)
    } finally {
      setActionLoading(null)
    }
  }

  // Stop watcher service
  const stopWatcher = async () => {
    setActionLoading('stop')
    try {
      const apiUrl = getApiUrl()
      const response = await authFetch(`${apiUrl}/api/folder-watcher/stop`, {
        method: 'POST'
      })
      
      if (response.ok) {
        toast.success('Ordnerüberwachung erfolgreich gestoppt')
        await loadData()
      } else {
        const error = await response.json()
        toast.error(`Fehler beim Stoppen der Überwachung: ${error.detail}`)
      }
    } catch (error) {
      toast.error('Fehler beim Stoppen der Ordnerüberwachung')
      console.error('Stop watcher error:', error)
    } finally {
      setActionLoading(null)
    }
  }

  // Add new watch folder
  const addWatchFolder = async () => {
    if (!newFolderPath.trim()) {
      toast.error('Bitte geben Sie einen Ordnerpfad ein')
      return
    }

    setActionLoading('add')
    try {
      const apiUrl = getApiUrl()
      const response = await authFetch(`${apiUrl}/api/folder-watcher/folders`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          folder_path: newFolderPath.trim(),
          pattern: newFolderPattern.trim() || '*.pdf',
          recursive: newFolderRecursive,
          enabled: true
        })
      })

      if (response.ok) {
        const result = await response.json()
        toast.success(`Added watch folder: ${result.folder_path}`)
        setShowAddModal(false)
        setNewFolderPath('')
        setNewFolderPattern('*.pdf')
        setNewFolderRecursive(false)
        await loadData()
      } else {
        const error = await response.json()
        toast.error(`Fehler beim Hinzufügen des Ordners: ${error.detail}`)
      }
    } catch (error) {
      toast.error('Fehler beim Hinzufügen des Überwachungsordners')
      console.error('Add folder error:', error)
    } finally {
      setActionLoading(null)
    }
  }

  // Remove watch folder
  const removeWatchFolder = async (folderId: string, folderPath: string) => {
    if (!confirm(`Sind Sie sicher, dass Sie den Überwachungsordner entfernen möchten:\n${folderPath}`)) {
      return
    }

    setActionLoading(`remove-${folderId}`)
    try {
      const apiUrl = getApiUrl()
      const response = await authFetch(`${apiUrl}/api/folder-watcher/folders/${folderId}`, {
        method: 'DELETE'
      })

      if (response.ok) {
        toast.success('Überwachungsordner erfolgreich entfernt')
        await loadData()
      } else {
        const error = await response.json()
        toast.error(`Fehler beim Entfernen des Ordners: ${error.detail}`)
      }
    } catch (error) {
      toast.error('Fehler beim Entfernen des Überwachungsordners')
      console.error('Remove folder error:', error)
    } finally {
      setActionLoading(null)
    }
  }

  // Toggle folder enable/disable
  const toggleFolderEnabled = async (folderId: string, currentlyEnabled: boolean) => {
    const action = currentlyEnabled ? 'disable' : 'enable'
    setActionLoading(`${action}-${folderId}`)

    try {
      const apiUrl = getApiUrl()
      const response = await authFetch(`${apiUrl}/api/folder-watcher/folders/${folderId}/${action}`, {
        method: 'POST'
      })

      if (response.ok) {
        toast.success(`Folder ${action}d successfully`)
        await loadData()
      } else {
        const error = await response.json()
        toast.error(`Failed to ${action} folder: ${error.detail}`)
      }
    } catch (error) {
      toast.error(`Error ${action}ing folder`)
      console.error(`${action} folder error:`, error)
    } finally {
      setActionLoading(null)
    }
  }

  // Format uptime
  const formatUptime = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`
    if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60)
      const remainingSeconds = seconds % 60
      return `${minutes}m ${remainingSeconds}s`
    }
    const hours = Math.floor(seconds / 3600)
    const remainingMinutes = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${remainingMinutes}m`
  }

  // Status badge component
  const StatusBadge = ({ status }: { status: string }) => {
    const getStatusColor = () => {
      switch (status) {
        case 'running': return 'bg-green-100 text-green-800 border-green-200'
        case 'stopped': return 'bg-gray-100 text-gray-800 border-gray-200'
        case 'starting': return 'bg-yellow-100 text-yellow-800 border-yellow-200'
        case 'stopping': return 'bg-orange-100 text-orange-800 border-orange-200'
        case 'error': return 'bg-red-100 text-red-800 border-red-200'
        default: return 'bg-gray-100 text-gray-800 border-gray-200'
      }
    }

    const getStatusIcon = () => {
      switch (status) {
        case 'running': return <CheckCircleIcon className="w-4 h-4" />
        case 'stopped': return <StopIcon className="w-4 h-4" />
        case 'starting': case 'stopping': return <ClockIcon className="w-4 h-4" />
        case 'error': return <XCircleIcon className="w-4 h-4" />
        default: return <InformationCircleIcon className="w-4 h-4" />
      }
    }

    return (
      <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusColor()}`}>
        {getStatusIcon()}
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    )
  }

  // Load data on component mount and set up refresh interval
  useEffect(() => {
    loadData()
    
    // Refresh data every 10 seconds when watcher is running
    const interval = setInterval(() => {
      if (watcherStatus?.status === 'running') {
        loadData()
      }
    }, 10000)

    return () => clearInterval(interval)
  }, [watcherStatus?.status])

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="space-y-4">
            <div className="h-24 bg-gray-200 rounded"></div>
            <div className="h-32 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <FolderIcon className="w-8 h-8 text-blue-600" />
            Folder Watcher
          </h1>
          <p className="text-gray-600 mt-1">
            Ordner für automatische Rechnungsverarbeitung überwachen
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            disabled={loading}
            className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors"
          >
            Refresh
          </button>
          
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center gap-2"
          >
            <PlusIcon className="w-4 h-4" />
            Ordner hinzufügen
          </button>
        </div>
      </div>

      {/* Service Status Card */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Service Status</h2>
          {watcherStatus && <StatusBadge status={watcherStatus.status} />}
        </div>

        {watcherStatus && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-gray-900">
                {watcherStatus.folders_watched}
              </div>
              <div className="text-sm text-gray-600">Aktive Ordner</div>
            </div>
            
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-green-600">
                {watcherStatus.statistics.successful_uploads}
              </div>
              <div className="text-sm text-gray-600">Erfolgreiche Uploads</div>
            </div>
            
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-red-600">
                {watcherStatus.statistics.failed_uploads}
              </div>
              <div className="text-sm text-gray-600">Fehlgeschlagene Uploads</div>
            </div>
            
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-blue-600">
                {formatUptime(watcherStatus.uptime_seconds)}
              </div>
              <div className="text-sm text-gray-600">Betriebszeit</div>
            </div>
          </div>
        )}

        <div className="flex gap-2">
          {watcherStatus?.status === 'running' ? (
            <button
              onClick={stopWatcher}
              disabled={actionLoading === 'stop'}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-400 text-white rounded-lg transition-colors flex items-center gap-2"
            >
              <StopIcon className="w-4 h-4" />
              {actionLoading === 'stop' ? 'Stoppe...' : 'Überwachung stoppen'}
            </button>
          ) : (
            <button
              onClick={startWatcher}
              disabled={actionLoading === 'start'}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white rounded-lg transition-colors flex items-center gap-2"
            >
              <PlayIcon className="w-4 h-4" />
              {actionLoading === 'start' ? 'Starte...' : 'Überwachung starten'}
            </button>
          )}
        </div>
      </div>

      {/* Watch Folders List */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Watch Folders</h2>
          <p className="text-gray-600 text-sm mt-1">
            Ordner, die auf neue Rechnungsdateien überwacht werden
          </p>
        </div>

        <div className="divide-y divide-gray-200">
          {watchFolders.length === 0 ? (
            <div className="p-12 text-center">
              <FolderIcon className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">Keine Ordner konfiguriert</h3>
              <p className="text-gray-600 mb-4">
                Fügen Sie Ordner hinzu, um die automatische Rechnungsverarbeitung zu überwachen
              </p>
              <button
                onClick={() => setShowAddModal(true)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center gap-2 mx-auto"
              >
                <PlusIcon className="w-4 h-4" />
                Ersten Ordner hinzufügen
              </button>
            </div>
          ) : (
            watchFolders.map((folder) => (
              <div key={folder.id} className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <FolderIcon className="w-5 h-5 text-gray-400" />
                      <code className="bg-gray-100 px-2 py-1 rounded text-sm font-mono">
                        {folder.folder_path}
                      </code>
                      {folder.is_watching && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                          Watching
                        </span>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-4 text-sm text-gray-600">
                      <span>Pattern: <code className="bg-gray-100 px-1 rounded">{folder.pattern}</code></span>
                      <span>Files processed: <strong>{folder.files_processed}</strong></span>
                      {folder.recursive && <span className="text-blue-600">Recursive</span>}
                      {folder.last_scan && (
                        <span>Last scan: {new Date(folder.last_scan).toLocaleString()}</span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 ml-4">
                    <button
                      onClick={() => toggleFolderEnabled(folder.id, folder.enabled)}
                      disabled={actionLoading === `${folder.enabled ? 'disable' : 'enable'}-${folder.id}`}
                      className={`p-2 rounded-lg transition-colors ${
                        folder.enabled 
                          ? 'text-green-600 hover:bg-green-50' 
                          : 'text-gray-400 hover:bg-gray-50'
                      }`}
                      title={folder.enabled ? 'Überwachung deaktivieren' : 'Überwachung aktivieren'}
                    >
                      {folder.enabled ? (
                        <EyeIcon className="w-4 h-4" />
                      ) : (
                        <EyeSlashIcon className="w-4 h-4" />
                      )}
                    </button>

                    <button
                      onClick={() => removeWatchFolder(folder.id, folder.folder_path)}
                      disabled={actionLoading === `remove-${folder.id}`}
                      className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      title="Remove folder"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Add Folder Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Add Watch Folder</h3>
              <p className="text-gray-600 text-sm mt-1">
                Configure a new folder to monitor for invoices
              </p>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Folder Path *
                </label>
                <input
                  type="text"
                  value={newFolderPath}
                  onChange={(e) => setNewFolderPath(e.target.value)}
                  placeholder="/path/to/invoice/folder"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  File Pattern
                </label>
                <input
                  type="text"
                  value={newFolderPattern}
                  onChange={(e) => setNewFolderPattern(e.target.value)}
                  placeholder="*.pdf"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Pattern to match files (e.g., *.pdf, invoice*.pdf)
                </p>
              </div>

              <div>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={newFolderRecursive}
                    onChange={(e) => setNewFolderRecursive(e.target.checked)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">
                    Monitor subfolders recursively
                  </span>
                </label>
              </div>
            </div>

            <div className="p-6 border-t border-gray-200 flex gap-2 justify-end">
              <button
                onClick={() => {
                  setShowAddModal(false)
                  setNewFolderPath('')
                  setNewFolderPattern('*.pdf')
                  setNewFolderRecursive(false)
                }}
                className="px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
              >
                Abbrechen
              </button>
              <button
                onClick={addWatchFolder}
                disabled={actionLoading === 'add' || !newFolderPath.trim()}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg transition-colors"
              >
                {actionLoading === 'add' ? 'Hinzufügen...' : 'Ordner hinzufügen'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
