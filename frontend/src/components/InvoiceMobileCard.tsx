'use client'

import React from 'react'
import Link from 'next/link'
import { 
  FileText, 
  Edit3, 
  Trash2, 
  Calendar, 
  DollarSign, 
  Building, 
  User,
  CheckCircle,
  Clock,
  AlertTriangle
} from 'lucide-react'

interface CleanInvoice {
  id: string
  file_name: string
  url: string
  file_path?: string
  status: 'pending' | 'uploaded' | 'edited' | 'pending_email' | 'edit_completed' | 'in_review_by_bauleiter' | 'approved_by_bauleiter' | 'rejected_by_bauleiter' | 'completed' | 'error'
  file_size: number
  created_at: string
  
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

interface InvoiceMobileCardProps {
  invoice: CleanInvoice
  onDelete: (invoice: CleanInvoice) => void
  onSendToBauleiter: (invoice: CleanInvoice) => void
  formatFileSize: (size: number) => string
  getWorkflowStatusColor: (status: string | undefined, reviewStatus: string | undefined) => string
  getWorkflowStatusLabel: (status: string | undefined, reviewStatus: string | undefined) => string
}

export default function InvoiceMobileCard({ 
  invoice, 
  onDelete, 
  onSendToBauleiter, 
  formatFileSize,
  getWorkflowStatusColor,
  getWorkflowStatusLabel
}: InvoiceMobileCardProps) {
  
  const formatCurrency = (amount: number | undefined): string => {
    if (amount === undefined || amount === null) return '---'
    return `€${amount.toLocaleString('de-DE', { minimumFractionDigits: 2 })}`
  }

  const formatDate = (dateString: string | undefined): string => {
    if (!dateString) return '---'
    return new Date(dateString).toLocaleDateString('de-DE')
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-4 space-y-4 border border-gray-200 hover:shadow-lg transition-shadow">
      {/* Header with file info and status */}
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-3 flex-1 min-w-0">
          <div className="w-12 h-12 bg-gradient-to-r from-gray-400 to-gray-500 rounded-lg flex items-center justify-center flex-shrink-0">
            <FileText className="h-6 w-6 text-white" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold text-gray-900 break-words leading-tight">
              {invoice.file_name}
            </div>
            <div className="text-xs text-gray-600 flex items-center space-x-2">
              <span>{formatFileSize(invoice.file_size)}</span>
              <span>•</span>
              <span>{new Date(invoice.created_at).toLocaleDateString('de-DE')}</span>
            </div>
          </div>
        </div>
        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full flex-shrink-0 ml-2 ${getWorkflowStatusColor(invoice.status, invoice.review_status)}`}>
          {getWorkflowStatusLabel(invoice.status, invoice.review_status)}
        </span>
      </div>

      {/* Key invoice details */}
      <div className="space-y-3">
        {/* Amount and dates - most important info */}
        <div className="grid grid-cols-2 gap-3">
          {invoice.rechnungsbetrag && (
            <div className="bg-blue-50 rounded-lg p-3">
              <div className="flex items-center space-x-2">
                <DollarSign className="h-4 w-4 text-blue-600" />
                <span className="text-xs text-blue-600 font-medium">Betrag</span>
              </div>
              <div className="text-sm font-bold text-blue-900 mt-1">
                {formatCurrency(invoice.rechnungsbetrag)}
              </div>
            </div>
          )}
          
          {invoice.faelligkeit && (
            <div className="bg-orange-50 rounded-lg p-3">
              <div className="flex items-center space-x-2">
                <Calendar className="h-4 w-4 text-orange-600" />
                <span className="text-xs text-orange-600 font-medium">Fälligkeit</span>
              </div>
              <div className="text-sm font-bold text-orange-900 mt-1">
                {formatDate(invoice.faelligkeit)}
              </div>
            </div>
          )}
        </div>

        {/* Business details */}
        <div className="space-y-2 text-sm">
          {invoice.rechnungssteller && (
            <div className="flex items-start justify-between">
              <span className="text-gray-600 text-xs">Rechnungssteller:</span>
              <span className="text-gray-900 font-medium text-right truncate ml-2 max-w-[60%]" title={invoice.rechnungssteller_label || invoice.rechnungssteller}>
                {invoice.rechnungssteller_label || invoice.rechnungssteller}
              </span>
            </div>
          )}
          
          {invoice.rechnungsempfaenger && (
            <div className="flex items-start justify-between">
              <span className="text-gray-600 text-xs">Empfänger:</span>
              <span className="text-gray-900 font-medium text-right truncate ml-2 max-w-[60%]" title={invoice.rechnungsempfaenger_label || invoice.rechnungsempfaenger}>
                {invoice.rechnungsempfaenger_label || invoice.rechnungsempfaenger}
              </span>
            </div>
          )}
          
          {invoice.projekt && (
            <div className="flex items-start justify-between">
              <span className="text-gray-600 text-xs">Projekt:</span>
              <span className="text-gray-900 font-medium text-right truncate ml-2 max-w-[60%]" title={invoice.projekt_label || invoice.projekt}>
                {invoice.projekt_label || invoice.projekt}
              </span>
            </div>
          )}

          {invoice.gewerk && (
            <div className="flex items-start justify-between">
              <span className="text-gray-600 text-xs">Gewerk:</span>
              <span className="text-gray-900 font-medium text-right truncate ml-2 max-w-[60%]" title={invoice.gewerk_label || invoice.gewerk}>
                {invoice.gewerk_label || invoice.gewerk}
              </span>
            </div>
          )}

          {/* Skonto information if available */}
          {invoice.skonto_datum && invoice.skonto_prozent && (
            <div className="bg-green-50 rounded-lg p-2 mt-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-green-600 font-medium">Skonto bis {formatDate(invoice.skonto_datum)}</span>
                <span className="text-green-900 font-bold">{invoice.skonto_prozent}%</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex space-x-2 pt-2 border-t border-gray-200">
        <Link
          href={`/invoice-editor/${invoice.id}`}
          className="flex-1 bg-gradient-to-r from-blue-500 to-purple-600 text-white px-3 py-2.5 rounded-lg text-sm font-medium hover:from-blue-600 hover:to-purple-700 transition-all duration-200 flex items-center justify-center space-x-2 shadow-md hover:shadow-lg"
        >
          <Edit3 className="h-4 w-4" />
          <span>Bearbeiten</span>
        </Link>

        {/* Show "Send to Bauleiter" button for completed invoices that haven't been sent yet */}
        {(invoice.status === 'completed' || invoice.review_status === 'completed_review') && 
         !['in_review_by_bauleiter', 'approved_by_bauleiter', 'rejected_by_bauleiter'].includes(invoice.status || '') && (
          <button
            onClick={() => onSendToBauleiter(invoice)}
            className="bg-gradient-to-r from-green-500 to-green-600 text-white px-3 py-2.5 rounded-lg text-sm font-medium hover:from-green-600 hover:to-green-700 transition-all duration-200 flex items-center justify-center space-x-1 shadow-md hover:shadow-lg"
            title="Rechnung zur Genehmigung an Bauleiter senden"
          >
            <User className="h-4 w-4" />
            <span className="hidden sm:inline">Bauleiter</span>
          </button>
        )}
        
        <button
          onClick={() => onDelete(invoice)}
          className="bg-red-500 text-white px-3 py-2.5 rounded-lg text-sm font-medium hover:bg-red-600 transition-colors flex items-center justify-center shadow-md hover:shadow-lg"
          title="Rechnung löschen"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
