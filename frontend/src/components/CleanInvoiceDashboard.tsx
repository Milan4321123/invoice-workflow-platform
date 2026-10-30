'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { toast, Toaster } from 'react-hot-toast'
import { 
  FileText, 
  Edit3, 
  Trash2, 
  Calendar, 
  DollarSign, 
  Building, 
  User,
  AlertTriangle,
  CheckCircle,
  Clock,
  RefreshCw,
  Search,
  X
} from 'lucide-react'
import FolderWatcherWidget from './FolderWatcherWidget'
import DeleteConfirmationDialog from './DeleteConfirmationDialog'
import InvoiceMobileCard from './InvoiceMobileCard'
import { buildApiUrl, API_CONFIG } from '@/config/api'
import { authFetch } from '@/lib/authFetch';

interface CleanInvoice {
  id: string
  file_name: string
  url: string
  file_path?: string
  status: 'pending' | 'uploaded' | 'edited' | 'pending_email' | 'edit_completed' | 'in_review_by_bauleiter' | 'approved_by_bauleiter' | 'rejected_by_bauleiter' | 'completed' | 'error'
  file_size: number
  created_at: string
  e_rechnung_format?: string | null
  
  // Manual Review Status
  review_status?: 'pending' | 'under_review' | 'completed_review' | 'needs_attention'
  reviewed_by?: string
  reviewed_at?: string
  review_notes?: string
  
  // German Business Fields
  rechnungsempfaenger?: string
  rechnungssteller?: string
  rechnungssteller_label?: string
  rechnungsempfaenger_label?: string
  projekt_label?: string
  gewerk_label?: string
  weiter_berechnen_an_label?: string
  projekt?: string
  gewerk?: string
  rechnungsbetrag?: number
  rechnungseingang?: string
  faelligkeit?: string
  skonto_datum?: string
  skonto_prozent?: number
  rechnungsart?: string
  kfw_anrechenbare_kosten?: boolean
  rechnungspruefung?: string
  weiter_berechnen_an?: string
}

export default function CleanInvoiceDashboard() {
  const [invoices, setInvoices] = useState<CleanInvoice[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [deleteDialog, setDeleteDialog] = useState<{
    isOpen: boolean
    invoiceId: string
    fileName: string
    uploadSource: 'drag-drop' | 'folder-watcher' | 'manual' | 'unknown'
  }>({
    isOpen: false,
    invoiceId: '',
    fileName: '',
    uploadSource: 'unknown'
  })
  const [deleteAllDialog, setDeleteAllDialog] = useState<{
    isOpen: boolean
  }>({
    isOpen: false
  })

  useEffect(() => {
    fetchInvoices()
  }, [])

  const fetchInvoices = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await authFetch(buildApiUrl(API_CONFIG.ENDPOINTS.INVOICES.BASE))
      
      if (!response.ok) {
        throw new Error(`Failed to fetch invoices: ${response.statusText}`)
      }
      
      const data = await response.json()
      setInvoices(data.invoices || [])
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load invoices'
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  const deleteInvoice = async (id: string, filename: string) => {
    try {
      const response = await authFetch(buildApiUrl(API_CONFIG.ENDPOINTS.INVOICES.DELETE(id)), {
        method: 'DELETE'
      })

      if (!response.ok) {
        throw new Error('Rechnung konnte nicht gelöscht werden')
      }

      // Parse the enhanced deletion response
      const result = await response.json()
      
      // Create detailed success message based on what was cleaned up
      let successMessage = `Rechnung "${filename}" erfolgreich gelöscht`
      
      if (result.details?.skonto_data_cleaned) {
        successMessage += ' (inkl. Skonto-Daten)'
      }
      
      if (result.details?.storage_cleaned) {
        successMessage += ' • Datei aus Speicher entfernt'
      }

      toast.success(successMessage)
      
      // Log deletion details for debugging
      console.log('Invoice deletion completed:', {
        invoice_id: result.invoice_id,
        filename: result.filename,
        skonto_cleaned: result.details?.skonto_data_cleaned || false,
        storage_cleaned: result.details?.storage_cleaned || false,
        file_path: result.details?.file_path
      })
      
      await fetchInvoices() // Refresh the list
      
      // Close delete dialog
      setDeleteDialog({
        isOpen: false,
        invoiceId: '',
        fileName: '',
        uploadSource: 'unknown'
      })
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Rechnung konnte nicht gelöscht werden'
      toast.error(errorMessage)
    }
  }

  const deleteAllInvoices = async () => {
    try {
      toast.loading('Alle Rechnungen werden gelöscht...', { id: 'delete-all' })
      
      const response = await authFetch(buildApiUrl(API_CONFIG.ENDPOINTS.INVOICES.DELETE_ALL), {
        method: 'DELETE'
      })

      if (!response.ok) {
        throw new Error('Rechnungen konnten nicht gelöscht werden')
      }

      const result = await response.json()
      
      // Create comprehensive success message
      const summary = result.summary || {}
      let successMessage = `✅ Alle Rechnungen erfolgreich gelöscht!\n\n`
      successMessage += `📊 Zusammenfassung:\n`
      successMessage += `• ${summary.total_deleted || 0} Rechnungen gelöscht\n`
      successMessage += `• ${summary.skonto_data_cleaned || 0} Skonto-Datensätze bereinigt\n`
      successMessage += `• ${summary.storage_files_cleaned || 0} Dateien aus Speicher entfernt`
      
      if (summary.failed_deletions > 0) {
        successMessage += `\n⚠️ ${summary.failed_deletions} Löschungen fehlgeschlagen`
      }

      toast.success(successMessage, { 
        id: 'delete-all',
        duration: 8000,
        style: {
          maxWidth: '500px',
          whiteSpace: 'pre-line'
        }
      })
      
      // Log deletion details for debugging
      console.log('Bulk deletion completed:', result)
      
      await fetchInvoices() // Refresh the list
      
      // Close delete all dialog
      setDeleteAllDialog({ isOpen: false })
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Rechnungen konnten nicht gelöscht werden'
      toast.error(errorMessage, { id: 'delete-all' })
    }
  }

  const openDeleteAllDialog = () => {
    if (invoices.length === 0) {
      toast.error('Keine Rechnungen zum Löschen vorhanden')
      return
    }
    setDeleteAllDialog({ isOpen: true })
  }

  const closeDeleteAllDialog = () => {
    setDeleteAllDialog({ isOpen: false })
  }

  const sendToBauleiter = async (invoice: CleanInvoice) => {
    try {
      // Get Bauleiter email from user
      const bauleiterEmail = prompt(
        `Rechnung "${invoice.file_name}" an Bauleiter senden.\n\nBitte geben Sie die E-Mail-Adresse des Bauleiters ein:`
      );
      
      if (!bauleiterEmail) {
        toast.error("Abgebrochen: Bauleiter E-Mail ist erforderlich");
        return;
      }
      
      // Validate email format
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(bauleiterEmail)) {
        toast.error("Ungültige E-Mail-Adresse");
        return;
      }
      
      // Use the new send-to-bauleiter endpoint for better status tracking
      const requestData = {
        bauleiter_email: bauleiterEmail,
        sent_by: "dashboard_user",
        editor_name: "Dashboard User",
        editor_email: "dashboard_user@company.de",
        changes_summary: [
          {
            field: "Status",
            old_value: "Bearbeitung abgeschlossen", 
            new_value: "An Bauleiter gesendet",
            timestamp: new Date().toLocaleString('de-DE')
          }
        ]
      };

      const response = await authFetch(buildApiUrl(`/api/invoices/${invoice.id}/send-to-bauleiter`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      });

      if (!response.ok) {
        throw new Error(`Senden fehlgeschlagen: ${response.statusText}`);
      }

      const result = await response.json();
      
      // Show success message with email status
      if (result.email_sent && result.email_provider === 'demo') {
        toast.success(`📁 Demo-Modus: E-Mail an ${bauleiterEmail} wurde nicht versendet, sondern in backend/outbox gespeichert.`, { duration: 6000 });
        await fetchInvoices();
      } else if (result.email_sent) {
        toast.success(`✅ E-Mail erfolgreich an ${bauleiterEmail} gesendet!`);
        // Refresh the list to show updated status
        await fetchInvoices();
      } else {
        toast.error(`❌ E-Mail konnte nicht gesendet werden: ${result.email_error || 'Unbekannter Fehler'}`);
      }
      
    } catch (err) {
      console.error('Error sending to Bauleiter:', err);
      toast.error(`Fehler beim Senden: ${err instanceof Error ? err.message : 'Unbekannter Fehler'}`);
    }
  }

  const openDeleteDialog = (invoice: CleanInvoice) => {
    // Detect upload source from file_path or other indicators
    let uploadSource: 'drag-drop' | 'folder-watcher' | 'manual' | 'unknown' = 'unknown'
    
    if (invoice.file_path) {
      if (invoice.file_path.startsWith('folder_watcher/')) {
        uploadSource = 'folder-watcher'
      } else if (invoice.file_path.startsWith('manual/')) {
        uploadSource = 'manual'
      } else {
        uploadSource = 'drag-drop'
      }
    }
    
    setDeleteDialog({
      isOpen: true,
      invoiceId: invoice.id,
      fileName: invoice.file_name,
      uploadSource
    })
  }

  const closeDeleteDialog = () => {
    setDeleteDialog({
      isOpen: false,
      invoiceId: '',
      fileName: '',
      uploadSource: 'unknown'
    })
  }

  const handleDeleteConfirm = async () => {
    await deleteInvoice(deleteDialog.invoiceId, deleteDialog.fileName)
  }

  const getStatusColor = (status: string | undefined): string => {
    switch (status) {
      case 'completed': return 'text-green-600 bg-green-50'
      case 'processing': return 'text-blue-600 bg-blue-50'
      case 'error': return 'text-red-600 bg-red-50'
      default: return 'text-gray-600 bg-gray-50'
    }
  }

  const getReviewStatusColor = (reviewStatus: string | undefined): string => {
    switch (reviewStatus) {
      case 'completed_review': return 'text-green-600 bg-green-50'
      case 'under_review': return 'text-blue-600 bg-blue-50'
      case 'needs_attention': return 'text-yellow-600 bg-yellow-50'
      case null:
      case undefined:
      case 'pending': return 'text-orange-600 bg-orange-50'
      default: return 'text-gray-600 bg-gray-50'
    }
  }

  const getReviewStatusLabel = (reviewStatus: string | undefined): string => {
    switch (reviewStatus) {
      case 'completed_review': return 'Abgeschlossen'
      case 'under_review': return 'In Bearbeitung'
      case 'needs_attention': return 'Aufmerksamkeit erforderlich'
      case null:
      case undefined:
      case 'pending': return 'Erfassung/Prüfung'
      default: return reviewStatus || 'Unbekannt'
    }
  }

  const getWorkflowStatusColor = (status: string | undefined, reviewStatus: string | undefined): string => {
    // Enhanced 5-stage workflow with Bauleiter approval
    if (status === 'approved_by_bauleiter') {
      return 'text-green-600 bg-green-50'  // Final approval
    } else if (status === 'rejected_by_bauleiter') {
      return 'text-red-600 bg-red-50'      // Rejected by Bauleiter
    } else if (status === 'in_review_by_bauleiter') {
      return 'text-purple-600 bg-purple-50' // With Bauleiter for approval
    } else if (status === 'completed' && reviewStatus === 'completed_review') {
      return 'text-green-600 bg-green-50'  // Ready for Bauleiter
    } else if (status === 'edited' && reviewStatus === 'under_review') {
      return 'text-blue-600 bg-blue-50'    // In editing
    } else {
      return 'text-orange-600 bg-orange-50' // Not started
    }
  }

  const getWorkflowStatusLabel = (status: string | undefined, reviewStatus: string | undefined): string => {
    // Enhanced 5-stage workflow with Bauleiter approval
    if (status === 'approved_by_bauleiter') {
      return 'Von Bauleiter genehmigt'
    } else if (status === 'rejected_by_bauleiter') {
      return 'Von Bauleiter abgelehnt'
    } else if (status === 'in_review_by_bauleiter') {
      return 'Bei Bauleiter zur Prüfung'
    } else if (status === 'completed' && reviewStatus === 'completed_review') {
      return 'Bereit für Bauleiter'
    } else if (status === 'edited' && reviewStatus === 'under_review') {
      return 'In Bearbeitung'
    } else {
      return 'Nicht begonnen'
    }
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const formatDate = (dateString: string): string => {
    if (!dateString) return 'Nicht verfügbar'
    try {
      // Handle different date formats
      const date = new Date(dateString)
      if (isNaN(date.getTime())) {
        // Try parsing as DD.MM.YYYY or DD-MM-YYYY
        const parts = dateString.split(/[.-]/)
        if (parts.length === 3) {
          const day = parseInt(parts[0])
          const month = parseInt(parts[1]) - 1 // Month is 0-indexed
          const year = parseInt(parts[2])
          if (year > 1900 && month >= 0 && month < 12 && day >= 1 && day <= 31) {
            return new Date(year, month, day).toLocaleDateString('de-DE', {
              year: 'numeric',
              month: '2-digit',
              day: '2-digit'
            })
          }
        }
        return dateString // Return as-is if can't parse
      }
      return date.toLocaleDateString('de-DE', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      })
    } catch {
      return dateString
    }
  }

  const formatCurrency = (amount: number | undefined): string => {
    if (!amount) return '---'
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'EUR'
    }).format(amount)
  }

  // Search filter function
  const filterInvoices = (invoices: CleanInvoice[], searchTerm: string): CleanInvoice[] => {
    if (!searchTerm.trim()) {
      return invoices
    }

    const term = searchTerm.toLowerCase().trim()
    return invoices.filter(invoice => {
      // Search in multiple fields
      const searchableFields = [
        invoice.file_name,
        invoice.rechnungsempfaenger,
        invoice.rechnungsempfaenger_label,
        invoice.rechnungssteller,
        invoice.rechnungssteller_label,
        invoice.projekt,
        invoice.projekt_label,
        invoice.gewerk,
        invoice.gewerk_label,
        invoice.rechnungsart,
        invoice.weiter_berechnen_an,
        invoice.weiter_berechnen_an_label,
        invoice.rechnungspruefung,
        invoice.status,
        invoice.review_status,
        // Convert number fields to strings for searching
        invoice.rechnungsbetrag?.toString(),
        invoice.skonto_prozent?.toString(),
        // Format dates for searching
        invoice.rechnungseingang,
        invoice.faelligkeit,
        invoice.skonto_datum,
        formatDate(invoice.created_at)
      ]

      return searchableFields.some(field => 
        field && field.toString().toLowerCase().includes(term)
      )
    })
  }

  // Get filtered invoices
  const filteredInvoices = filterInvoices(invoices, searchTerm)

  if (loading) {
    return (
      <div className="min-h-screen gradient-bg-light flex items-center justify-center">
        <div className="text-center glass-card rounded-2xl p-8 animate-fade-in">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-purple-600 mx-auto mb-4"></div>
          <h2 className="text-xl font-semibold gradient-text mb-2">Rechnungen werden geladen</h2>
          <p className="text-gray-600">Bitte warten...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen gradient-bg-light pt-16"> {/* Added pt-16 for fixed navigation */}
      <Toaster 
        position="top-right" 
        toastOptions={{
          style: {
            marginTop: '80px', // Push notifications below the fixed navigation
            zIndex: 9999, // Ensure toasts appear above all other elements
          },
          success: {
            style: {
              background: '#10B981',
              color: 'white',
              fontWeight: '500',
              boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
            },
            duration: 4000,
          },
          error: {
            style: {
              background: '#EF4444',
              color: 'white',
              fontWeight: '500',
              boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
            },
            duration: 5000,
          },
        }}
      />
      
      {/* Header */}
      <header className="glass-card border-0 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-gradient-to-r from-purple-600 to-blue-600 rounded-xl flex items-center justify-center shadow-lg animate-glow">
                <FileText className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold gradient-text">Rechnungsverwaltung</h1>
                <p className="text-gray-600">Verwalten und bearbeiten Sie Ihre Rechnungen</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <a 
                href="/bauleiter"
                className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-purple-700 text-white rounded-xl hover:from-purple-700 hover:to-purple-800 transition-all transform hover:scale-105 shadow-lg"
              >
                <span>👨‍💼</span>
                <span>Bauleiter Dashboard</span>
              </a>
              
              <Link 
                href="/control"
                className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-green-600 to-green-700 text-white rounded-xl hover:from-green-700 hover:to-green-800 transition-all transform hover:scale-105 shadow-lg"
              >
                <span>⚙️</span>
                <span>Control Panel</span>
              </Link>
              
              <button
                onClick={fetchInvoices}
                className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-xl hover:from-blue-700 hover:to-blue-800 transition-all transform hover:scale-105 shadow-lg"
              >
                <RefreshCw className="h-4 w-4" />
                <span>Aktualisieren</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-2 sm:px-4 lg:px-8 py-4 lg:py-8">

        {error && (
          <div className="mb-6 glass-card border border-red-200 rounded-xl p-4 animate-fade-in">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="h-5 w-5 text-red-600" />
              <span className="text-red-700 font-medium">{error}</span>
            </div>
          </div>
        )}

        {/* Invoice List - MOVED TO TOP */}
        <div className="glass-card border-0 shadow-xl rounded-xl overflow-hidden animate-fade-in">
          <div className="px-4 lg:px-6 py-4 border-b border-white/20 bg-gradient-to-r from-purple-50 to-blue-50">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between space-y-3 lg:space-y-0">
              <h2 className="text-lg font-semibold gradient-text">Rechnungen</h2>
              
              {/* Actions and Search */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center space-y-3 sm:space-y-0 sm:space-x-3">
                {/* Delete All Button */}
                {invoices.length > 0 && (
                  <button
                    onClick={openDeleteAllDialog}
                    className="flex items-center justify-center space-x-2 px-4 py-2 bg-gradient-to-r from-red-600 to-red-700 text-white rounded-lg hover:from-red-700 hover:to-red-800 transition-all transform hover:scale-105 shadow-lg text-sm font-medium"
                    title={`Alle ${invoices.length} Rechnungen löschen`}
                  >
                    <Trash2 className="h-4 w-4" />
                    <span>Alle löschen ({invoices.length})</span>
                  </button>
                )}
                
                {/* Search Input */}
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Search className="h-4 w-4 text-gray-400" />
                  </div>
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="Suchen... (Dateiname, Empfänger, Projekt, etc.)"
                    className="block w-64 pl-10 pr-10 py-2 border border-gray-300 rounded-lg text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent bg-white/90 backdrop-blur-sm"
                  />
                  {searchTerm && (
                    <button
                      onClick={() => setSearchTerm('')}
                      className="absolute inset-y-0 right-0 pr-3 flex items-center"
                    >
                      <X className="h-4 w-4 text-gray-400 hover:text-gray-600" />
                    </button>
                  )}
                </div>
                
                <div className="hidden lg:block text-sm text-gray-600 glass-dark px-3 py-1 rounded-full">
                  ← → Horizontal scrollen für alle Felder
                </div>
              </div>
            </div>
            
            {/* Search Results Summary */}
            {searchTerm && (
              <div className="mt-3 text-sm text-gray-600">
                {filteredInvoices.length === 0 ? (
                  <span className="text-orange-600">Keine Rechnungen gefunden für „{searchTerm}“</span>
                ) : (
                  <span>
                    {filteredInvoices.length} von {invoices.length} Rechnungen gefunden
                    {filteredInvoices.length !== invoices.length && (
                      <button
                        onClick={() => setSearchTerm('')}
                        className="ml-2 text-purple-600 hover:text-purple-800 underline"
                      >
                        Alle anzeigen
                      </button>
                    )}
                  </span>
                )}
              </div>
            )}
          </div>

          {filteredInvoices.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-16 h-16 bg-gradient-to-r from-gray-300 to-gray-400 rounded-xl flex items-center justify-center mx-auto mb-4">
                <FileText className="h-8 w-8 text-white" />
              </div>
              <h3 className="text-lg font-medium gradient-text mb-2">
                {searchTerm ? `Keine Rechnungen gefunden für "${searchTerm}"` : 'Keine Rechnungen gefunden'}
              </h3>
              <p className="text-gray-600">
                {searchTerm ? 'Versuchen Sie einen anderen Suchbegriff.' : 'Laden Sie Rechnungen hoch, um zu beginnen.'}
              </p>
            </div>
          ) : (
            <>
              {/* Mobile Card View */}
              <div className="lg:hidden">
                <div className="p-4 space-y-4">
                  {filteredInvoices.map((invoice) => (
                    <InvoiceMobileCard
                      key={invoice.id}
                      invoice={invoice}
                      onDelete={openDeleteDialog}
                      onSendToBauleiter={sendToBauleiter}
                      formatFileSize={formatFileSize}
                      getWorkflowStatusColor={getWorkflowStatusColor}
                      getWorkflowStatusLabel={getWorkflowStatusLabel}
                    />
                  ))}
                </div>
              </div>

              {/* Desktop Table View */}
              <div className="hidden lg:block overflow-x-auto">
                <table className="min-w-full divide-y divide-white/20" style={{ minWidth: '1800px' }}>
                  <thead className="glass-dark">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider min-w-[200px]">
                        Rechnungsdetails
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider min-w-[120px]">
                        Status
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider min-w-[150px]">
                      Rechnungsempfänger
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider min-w-[150px]">
                      Rechnungssteller
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider min-w-[120px]">
                      Projekt
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider min-w-[100px]">
                      Gewerk
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-700 uppercase tracking-wider min-w-[120px]">
                      Rechnungsbetrag
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider min-w-[120px]">
                      Rechnungseingang
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider min-w-[120px]">
                      Fälligkeit
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider min-w-[120px]">
                      Skonto Datum
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-700 uppercase tracking-wider min-w-[100px]">
                      Skonto %
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider min-w-[120px]">
                      Rechnungsart
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-700 uppercase tracking-wider min-w-[100px]">
                      KfW Kosten
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider min-w-[150px]">
                      Rechnungsprüfung
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider min-w-[150px]">
                      Weiter berechnen an
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-700 uppercase tracking-wider sticky right-0 glass-dark z-10 min-w-[160px]">
                      Aktionen
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10">
                  {filteredInvoices.map((invoice) => (
                    <tr key={invoice.id} className="hover:bg-white/5 transition-colors">
                      <td className="px-4 py-4 whitespace-nowrap min-w-[200px]">
                        <div className="flex items-center space-x-3 h-full">
                          <div className="w-8 h-8 bg-gradient-to-r from-gray-400 to-gray-500 rounded-lg flex items-center justify-center flex-shrink-0">
                            <FileText className="h-4 w-4 text-white" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-gray-900 break-words leading-tight" title={invoice.file_name}>
                              {invoice.file_name}
                            </div>
                            <div className="text-sm text-gray-600">
                              {formatFileSize(invoice.file_size)}
                            </div>
                            {invoice.e_rechnung_format && (
                              <span
                                className="mt-1 inline-block rounded bg-green-100 px-1.5 py-0.5 text-xs font-medium text-green-800"
                                title={invoice.e_rechnung_format}
                              >
                                E-Rechnung
                              </span>
                            )}
                            <div className="text-xs text-gray-500">
                              {new Date(invoice.created_at).toLocaleDateString('de-DE', {
                                year: 'numeric',
                                month: '2-digit',
                                day: '2-digit'
                              })}
                            </div>
                          </div>
                        </div>
                      </td>
                      
                      <td className="px-4 py-4 whitespace-nowrap min-w-[120px]">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getWorkflowStatusColor(invoice.status, invoice.review_status)}`}>
                          {getWorkflowStatusLabel(invoice.status, invoice.review_status)}
                        </span>
                      </td>
                      
                      <td className="px-4 py-4 whitespace-nowrap min-w-[150px]">
                        <div className="text-sm text-gray-900 truncate max-w-[130px]" title={invoice.rechnungsempfaenger_label || invoice.rechnungsempfaenger || ''}>
                          {invoice.rechnungsempfaenger_label || invoice.rechnungsempfaenger || '---'}
                        </div>
                      </td>
                      
                      <td className="px-4 py-4 whitespace-nowrap min-w-[150px]">
                        <div className="text-sm text-gray-900 truncate max-w-[130px]" title={invoice.rechnungssteller_label || invoice.rechnungssteller || ''}>
                          {invoice.rechnungssteller_label || invoice.rechnungssteller || '---'}
                        </div>
                      </td>
                      
                      <td className="px-4 py-4 whitespace-nowrap min-w-[120px]">
                        <div className="text-sm text-gray-900 truncate max-w-[100px]" title={invoice.projekt_label || invoice.projekt || ''}>
                          {invoice.projekt_label || invoice.projekt || '---'}
                        </div>
                      </td>
                      
                      <td className="px-4 py-4 whitespace-nowrap min-w-[100px]">
                        <div className="text-sm text-gray-900 truncate max-w-[80px]" title={invoice.gewerk_label || invoice.gewerk || ''}>
                          {invoice.gewerk_label || invoice.gewerk || '---'}
                        </div>
                      </td>
                      
                      <td className="px-4 py-4 whitespace-nowrap text-right min-w-[120px]">
                        <div className="text-sm font-medium text-gray-900">
                          {formatCurrency(invoice.rechnungsbetrag)}
                        </div>
                      </td>
                      
                      <td className="px-4 py-4 whitespace-nowrap min-w-[120px]">
                        <div className="text-sm text-gray-900">
                          {invoice.rechnungseingang ? formatDate(invoice.rechnungseingang) : '---'}
                        </div>
                      </td>
                      
                      <td className="px-4 py-4 whitespace-nowrap min-w-[120px]">
                        <div className="text-sm text-gray-900">
                          {invoice.faelligkeit ? formatDate(invoice.faelligkeit) : '---'}
                        </div>
                      </td>
                      
                      <td className="px-4 py-4 whitespace-nowrap min-w-[120px]">
                        <div className="text-sm text-gray-900">
                          {invoice.skonto_datum ? formatDate(invoice.skonto_datum) : '---'}
                        </div>
                      </td>
                      
                      <td className="px-4 py-4 whitespace-nowrap text-right min-w-[100px]">
                        <div className="text-sm text-gray-900">
                          {invoice.skonto_prozent ? `${invoice.skonto_prozent}%` : '---'}
                        </div>
                      </td>
                      
                      <td className="px-4 py-4 whitespace-nowrap min-w-[120px]">
                        <div className="text-sm text-gray-900 truncate max-w-[100px]" title={invoice.rechnungsart || ''}>
                          {invoice.rechnungsart || '---'}
                        </div>
                      </td>
                      
                      <td className="px-4 py-4 whitespace-nowrap text-center min-w-[100px]">
                        <div className="text-sm text-gray-900">
                          {invoice.kfw_anrechenbare_kosten ? (
                            <CheckCircle className="h-5 w-5 text-green-600 mx-auto" />
                          ) : (
                            <span className="text-gray-400">---</span>
                          )}
                        </div>
                      </td>
                      
                      <td className="px-4 py-4 whitespace-nowrap min-w-[150px]">
                        <div className="text-sm text-gray-900 truncate max-w-[130px]" title={invoice.rechnungspruefung || ''}>
                          {invoice.rechnungspruefung || '---'}
                        </div>
                      </td>
                      
                      <td className="px-4 py-4 whitespace-nowrap min-w-[150px]">
                        <div className="text-sm text-gray-900 truncate max-w-[130px]" title={invoice.weiter_berechnen_an_label || invoice.weiter_berechnen_an || ''}>
                          {invoice.weiter_berechnen_an_label || invoice.weiter_berechnen_an || '---'}
                        </div>
                      </td>
                      
                      <td className="px-4 py-4 whitespace-nowrap text-right text-sm font-medium sticky right-0 glass-card z-10 min-w-[220px]">
                        <div className="flex items-center justify-end space-x-2">
                          <Link
                            href={`/invoice-editor/${invoice.id}`}
                            className="flex items-center space-x-1 px-3 py-1 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg hover:from-blue-700 hover:to-blue-800 transition-all transform hover:scale-105 shadow-lg"
                          >
                            <Edit3 className="h-4 w-4" />
                            <span>Bearbeiten</span>
                          </Link>
                          
                          {/* Show "Send to Bauleiter" button for completed invoices that haven't been sent yet */}
                          {(invoice.status === 'completed' || invoice.review_status === 'completed_review') && 
                           !['in_review_by_bauleiter', 'approved_by_bauleiter', 'rejected_by_bauleiter'].includes(invoice.status || '') && (
                            <button
                              onClick={() => sendToBauleiter(invoice)}
                              className="flex items-center space-x-1 px-3 py-1 bg-gradient-to-r from-green-600 to-green-700 text-white rounded-lg hover:from-green-700 hover:to-green-800 transition-all transform hover:scale-105 shadow-lg"
                              title="Rechnung zur Genehmigung an Bauleiter senden"
                            >
                              <User className="h-4 w-4" />
                              <span>An Bauleiter</span>
                            </button>
                          )}
                          
                          <button
                            onClick={() => openDeleteDialog(invoice)}
                            className="flex items-center space-x-1 px-3 py-1 bg-gradient-to-r from-red-600 to-red-700 text-white rounded-lg hover:from-red-700 hover:to-red-800 transition-all transform hover:scale-105 shadow-lg"
                          >
                            <Trash2 className="h-4 w-4" />
                            <span>Löschen</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </>
          )}
        </div>

        {/* Enhanced Stats with Bauleiter Workflow - MOVED BELOW INVOICE TABLE */}
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-6 mb-8 mt-8">
          <div className="glass-card rounded-xl p-6 border-0 shadow-lg hover:shadow-xl transition-all transform hover:scale-105 animate-fade-in">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-blue-600 rounded-xl flex items-center justify-center">
                <FileText className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Rechnungen gesamt</p>
                <p className="text-2xl font-bold gradient-text">{invoices.length}</p>
              </div>
            </div>
          </div>

          <div className="glass-card rounded-xl p-6 border-0 shadow-lg hover:shadow-xl transition-all transform hover:scale-105 animate-fade-in">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 bg-gradient-to-r from-green-500 to-green-600 rounded-xl flex items-center justify-center">
                <CheckCircle className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Genehmigt</p>
                <p className="text-2xl font-bold gradient-text">
                  {invoices.filter(inv => inv.status === 'approved_by_bauleiter').length}
                </p>
              </div>
            </div>
          </div>

          <div className="glass-card rounded-xl p-6 border-0 shadow-lg hover:shadow-xl transition-all transform hover:scale-105 animate-fade-in">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 bg-gradient-to-r from-purple-500 to-purple-600 rounded-xl flex items-center justify-center">
                <Clock className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Bei Bauleiter</p>
                <p className="text-2xl font-bold gradient-text">
                  {invoices.filter(inv => inv.status === 'in_review_by_bauleiter').length}
                </p>
              </div>
            </div>
          </div>

          <div className="glass-card rounded-xl p-6 border-0 shadow-lg hover:shadow-xl transition-all transform hover:scale-105 animate-fade-in">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center">
                <Clock className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">In Bearbeitung</p>
                <p className="text-2xl font-bold gradient-text">
                  {invoices.filter(inv => 
                    (inv.status === 'edited' && inv.review_status === 'under_review') ||
                    (inv.status === 'completed' && inv.review_status === 'completed_review' && 
                     !['in_review_by_bauleiter', 'approved_by_bauleiter', 'rejected_by_bauleiter'].includes(inv.status || ''))
                  ).length}
                </p>
              </div>
            </div>
          </div>

          <div className="glass-card rounded-xl p-6 border-0 shadow-lg hover:shadow-xl transition-all transform hover:scale-105 animate-fade-in">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 bg-gradient-to-r from-orange-500 to-orange-600 rounded-xl flex items-center justify-center">
                <Clock className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Nicht begonnen</p>
                <p className="text-2xl font-bold gradient-text">
                  {invoices.filter(inv => 
                    !['completed', 'edited', 'in_review_by_bauleiter', 'approved_by_bauleiter', 'rejected_by_bauleiter'].includes(inv.status || '')
                  ).length}
                </p>
              </div>
            </div>
          </div>

          <div className="glass-card rounded-xl p-6 border-0 shadow-lg hover:shadow-xl transition-all transform hover:scale-105 animate-fade-in">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 bg-gradient-to-r from-purple-500 to-pink-600 rounded-xl flex items-center justify-center">
                <DollarSign className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Gesamtbetrag</p>
                <p className="text-2xl font-bold gradient-text">
                  {formatCurrency(
                    invoices.reduce((sum, inv) => sum + (inv.rechnungsbetrag || 0), 0)
                  )}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Folder Watcher Widget - MOVED BELOW STATS */}
        <div className="mb-8">
          <FolderWatcherWidget />
        </div>

        {/* Delete Confirmation Dialog */}
        <DeleteConfirmationDialog
          isOpen={deleteDialog.isOpen}
          fileName={deleteDialog.fileName}
          uploadSource={deleteDialog.uploadSource}
          onConfirm={handleDeleteConfirm}
          onCancel={closeDeleteDialog}
        />

        {/* Delete All Confirmation Dialog */}
        {deleteAllDialog.isOpen && (
          <div className="fixed inset-0 z-50 overflow-y-auto">
            <div className="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
              <div className="fixed inset-0 transition-opacity" aria-hidden="true">
                <div className="absolute inset-0 bg-gray-500 opacity-75"></div>
              </div>

              <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>

              <div className="inline-block align-bottom bg-white rounded-xl text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
                <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                  <div className="sm:flex sm:items-start">
                    <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-red-100 sm:mx-0 sm:h-10 sm:w-10">
                      <AlertTriangle className="h-6 w-6 text-red-600" />
                    </div>
                    <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                      <h3 className="text-lg leading-6 font-medium text-gray-900">
                        Alle Rechnungen löschen
                      </h3>
                      <div className="mt-2">
                        <p className="text-sm text-gray-500">
                          ⚠️ <strong>WARNUNG:</strong> Diese Aktion löscht <strong>ALLE {invoices.length} Rechnungen</strong> dauerhaft aus dem System!
                        </p>
                        <div className="mt-3 p-3 bg-red-50 rounded-lg border border-red-200">
                          <p className="text-sm text-red-700 font-medium">Diese Aktion wird:</p>
                          <ul className="mt-2 text-sm text-red-600 list-disc list-inside space-y-1">
                            <li>Alle Rechnungsdatensätze löschen</li>
                            <li>Alle Skonto-Daten bereinigen</li>
                            <li>Alle Dateien aus dem Speicher entfernen</li>
                            <li><strong>Kann NICHT rückgängig gemacht werden!</strong></li>
                          </ul>
                        </div>
                        <div className="mt-4">
                          <p className="text-sm text-gray-600">
                            Geben Sie <strong>„ALLE LÖSCHEN“</strong> ein, um zu bestätigen:
                          </p>
                          <input
                            type="text"
                            id="confirm-delete-all"
                            className="mt-2 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
                            placeholder="ALLE LÖSCHEN"
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && (e.target as HTMLInputElement).value === 'ALLE LÖSCHEN') {
                                deleteAllInvoices();
                              }
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                  <button
                    type="button"
                    className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:ml-3 sm:w-auto sm:text-sm transition-colors"
                    onClick={() => {
                      const input = document.getElementById('confirm-delete-all') as HTMLInputElement;
                      if (input?.value === 'ALLE LÖSCHEN') {
                        deleteAllInvoices();
                      } else {
                        toast.error('Bitte geben Sie „ALLE LÖSCHEN“ ein, um zu bestätigen');
                      }
                    }}
                  >
                    Alle Rechnungen löschen
                  </button>
                  <button
                    type="button"
                    className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm transition-colors"
                    onClick={closeDeleteAllDialog}
                  >
                    Abbrechen
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
