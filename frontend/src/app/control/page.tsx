'use client'

import React, { useState, useEffect } from 'react'
import { toast } from 'react-hot-toast'
import { CheckCircle, XCircle, DollarSign, Clock, ArrowLeft } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { buildApiUrl, API_CONFIG } from '@/config/api'
import { authFetch } from '@/lib/authFetch';

const formatCurrency = (amount: number) => {
  return new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(amount)
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('de-DE')
}

interface Invoice {
  id: string
  rechnungsnummer?: string
  file_path?: string
  lieferant?: string
  status?: string
  approval_status?: string
  skonto_datum?: string
  skonto_prozent?: string
  rechnungsbetrag?: string
  skonto_decision?: string
  skonto_decided_by?: string
  skonto_decided_at?: string
  actual_skonto_savings?: number
  skonto_amount?: number
  skonto_due_date?: string
}

export default function InvoiceControlPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [processingActions, setProcessingActions] = useState<Set<string>>(new Set())
  const router = useRouter()

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

  const getInvoiceDisplayName = (invoice: Invoice): string => {
    if (invoice.rechnungsnummer && invoice.rechnungsnummer !== 'Nicht eingegeben') {
      return invoice.rechnungsnummer
    }
    if (invoice.file_path) {
      const filename = invoice.file_path.split('/').pop() || 'Unknown'
      return filename.endsWith('.pdf') ? filename.slice(0, -4) : filename
    }
    return 'Rechnung ohne Nummer'
  }

  const getStatusDisplay = (invoice: Invoice): string => {
    if (invoice.status === 'approved_by_bauleiter') return 'Genehmigt'
    if (invoice.status === 'rejected_by_bauleiter') return 'Abgelehnt'
    if (invoice.status === 'in_review_by_bauleiter') return 'Bei Bauleiter'
    if (invoice.approval_status === 'approved') return 'Genehmigt'
    if (invoice.approval_status === 'rejected') return 'Abgelehnt'
    return 'Offen'
  }

  const getSkontoStatusDisplay = (invoice: any) => {
    if (invoice.skonto_decision === 'taken') {
      return (
        <span className="text-green-600 bg-green-100 px-2 py-1 rounded-full text-sm">
          ✓ Skonto genommen ({formatCurrency(invoice.actual_skonto_savings || 0)})
        </span>
      )
    } else if (invoice.skonto_decision === 'missed') {
      return (
        <span className="text-red-600 bg-red-100 px-2 py-1 rounded-full text-sm">
          ✗ Skonto verpasst
        </span>
      )
    } else if ((invoice.skonto_due_date || invoice.skonto_datum) && (invoice.skonto_amount || invoice.skonto_prozent)) {
      const now = new Date()
      const skontoDate = new Date(invoice.skonto_due_date || invoice.skonto_datum)
      const isExpired = now > skontoDate
      
      if (isExpired) {
        return (
          <span className="text-orange-600 bg-orange-100 px-2 py-1 rounded-full text-sm">
            ⚠ Skonto abgelaufen ({formatDate(invoice.skonto_due_date || invoice.skonto_datum)})
          </span>
        )
      } else {
        const amount = invoice.skonto_amount || (parseFloat(invoice.rechnungsbetrag || '0') * parseFloat(invoice.skonto_prozent || '0') / 100)
        return (
          <span className="text-blue-600 bg-blue-100 px-2 py-1 rounded-full text-sm">
            ⏳ Skonto verfügbar bis {formatDate(invoice.skonto_due_date || invoice.skonto_datum)} ({formatCurrency(amount)})
          </span>
        )
      }
    }
    return null
  }

  const handleAction = async (invoiceId: string, action: 'approve' | 'reject' | 'skonto_take' | 'skonto_skip') => {
    if (processingActions.has(invoiceId)) return

    setProcessingActions(prev => new Set(prev).add(invoiceId))
    
    try {
      let endpoint = ''
      let method = 'PUT'
      let body = {}

      switch (action) {
        case 'approve':
          endpoint = `/api/invoices/${invoiceId}/approve`
          body = { decision: 'approved', decided_by: 'control_panel' }
          break
        case 'reject':
          endpoint = `/api/invoices/${invoiceId}/reject`
          body = { decision: 'rejected', decided_by: 'control_panel' }
          break
        case 'skonto_take':
          endpoint = `/api/invoices/${invoiceId}`
          body = { skonto_decision: 'taken' }
          break
        case 'skonto_skip':
          endpoint = `/api/invoices/${invoiceId}`
          body = { skonto_decision: 'missed' }
          break
      }

      const response = await authFetch(buildApiUrl(endpoint), {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      })

      if (!response.ok) {
        throw new Error(`Action failed: ${response.statusText}`)
      }

      const result = await response.json()
      
      if (result.success) {
        // Show immediate toast notification
        let successMessage = ''
        switch (action) {
          case 'approve':
            successMessage = '✅ Rechnung genehmigt'
            break
          case 'reject':
            successMessage = '❌ Rechnung abgelehnt'
            break
          case 'skonto_take':
            successMessage = '💰 Skonto genommen'
            break
          case 'skonto_skip':
            successMessage = '⏭️ Skonto übersprungen'
            break
        }
        toast.success(successMessage)
        
        // Refresh invoice list to show updated status
        await fetchInvoices()
      } else {
        throw new Error(result.error || 'Unknown error')
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Aktion fehlgeschlagen'
      toast.error(errorMessage)
    } finally {
      setProcessingActions(prev => {
        const newSet = new Set(prev)
        newSet.delete(invoiceId)
        return newSet
      })
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="bg-white p-8 rounded-xl shadow-lg max-w-md w-full text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <h2 className="text-xl font-semibold text-gray-800 mb-2">
            Rechnungen werden geladen...
          </h2>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="glass-card rounded-xl p-6 mb-6 border-0 shadow-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => router.push('/dashboard')}
                className="flex items-center space-x-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
              >
                <ArrowLeft className="h-4 w-4" />
                <span>Zurück zum Dashboard</span>
              </button>
              <div>
                <h1 className="text-3xl font-bold gradient-text">Rechnungssteuerung</h1>
                <p className="text-gray-600">Genehmigung und Skonto-Entscheidungen</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-500">Gesamt: {invoices.length} Rechnungen</p>
            </div>
          </div>
        </div>

        {error && (
          <div className="glass-card rounded-xl p-6 mb-6 border-l-4 border-red-500 bg-red-50">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Invoice Control List */}
        <div className="glass-card rounded-xl border-0 shadow-lg overflow-hidden">
          {invoices.length === 0 ? (
            <div className="p-12 text-center">
              <h3 className="text-xl font-semibold text-gray-800 mb-2">Keine Rechnungen verfügbar</h3>
              <p className="text-gray-600">Es sind derzeit keine Rechnungen zur Bearbeitung verfügbar.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Rechnung
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Lieferant
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Skonto Status
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Genehmigung
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Skonto Aktionen
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {invoices.map((invoice) => {
                    const isProcessing = processingActions.has(invoice.id)
                    return (
                      <tr key={invoice.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="font-medium text-gray-900">
                            {getInvoiceDisplayName(invoice)}
                          </div>
                          {invoice.rechnungsbetrag && (
                            <div className="text-sm text-gray-500">
                              {invoice.rechnungsbetrag} EUR
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900">
                            {invoice.lieferant || 'Nicht verfügbar'}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-800">
                            {getStatusDisplay(invoice)}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex flex-col space-y-1">
                            {getSkontoStatusDisplay(invoice)}
                            {invoice.skonto_datum && invoice.skonto_prozent && !invoice.skonto_decision && (
                              <div className="text-xs text-gray-500">
                                {invoice.skonto_prozent}% bis {new Date(invoice.skonto_datum).toLocaleDateString('de-DE')}
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex space-x-2">
                            <button
                              onClick={() => handleAction(invoice.id, 'approve')}
                              disabled={isProcessing}
                              className="flex items-center space-x-1 px-3 py-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white rounded-lg transition-colors text-sm"
                            >
                              <CheckCircle className="h-4 w-4" />
                              <span>Genehmigen</span>
                            </button>
                            <button
                              onClick={() => handleAction(invoice.id, 'reject')}
                              disabled={isProcessing}
                              className="flex items-center space-x-1 px-3 py-1 bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white rounded-lg transition-colors text-sm"
                            >
                              <XCircle className="h-4 w-4" />
                              <span>Ablehnen</span>
                            </button>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {invoice.skonto_datum && invoice.skonto_prozent ? (
                            <div className="flex space-x-2">
                              <button
                                onClick={() => handleAction(invoice.id, 'skonto_take')}
                                disabled={isProcessing || invoice.skonto_decision === 'taken'}
                                className="flex items-center space-x-1 px-3 py-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded-lg transition-colors text-sm"
                              >
                                <DollarSign className="h-4 w-4" />
                                <span>Nehmen</span>
                              </button>
                              <button
                                onClick={() => handleAction(invoice.id, 'skonto_skip')}
                                disabled={isProcessing || invoice.skonto_decision === 'missed'}
                                className="flex items-center space-x-1 px-3 py-1 bg-gray-600 hover:bg-gray-700 disabled:bg-gray-400 text-white rounded-lg transition-colors text-sm"
                              >
                                <Clock className="h-4 w-4" />
                                <span>Überspringen</span>
                              </button>
                            </div>
                          ) : (
                            <span className="text-sm text-gray-500">Kein Skonto verfügbar</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
      
    </div>
  )
}
