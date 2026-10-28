'use client';

import React, { useState, useEffect } from 'react';
import { AlertCircle, TrendingUp, Clock, CheckCircle, XCircle, Filter, Download, RefreshCw, Mail, ThumbsUp, ThumbsDown, Settings, Play, Pause, Zap, Timer } from 'lucide-react';

interface SkontoMetrics {
  totalInvoices: number;
  totalSkontoAmount: number;
  capturedSkonto: number;
  missedSkonto: number;
  pendingReview: number;
  successRate: number;
}

interface SkontoInvoice {
  id: string;
  invoiceNumber: string;
  vendor: string;
  amount: number;
  skontoRate: number;
  skontoAmount: number;
  skontoDeadline: string;
  status: 'captured' | 'missed' | 'pending' | 'expired';
  processedDate?: string;
  daysRemaining?: number;
  reminderSent?: boolean;
}

interface SchedulerStatus {
  enabled: boolean;
  is_running: boolean;
  stats: {
    total_runs: number;
    total_reminders_sent: number;
    total_errors: number;
    last_error: string | null;
  };
  last_run: string | null;
  next_run: string | null;
}

export default function PrufberichtPage() {
  const [metrics, setMetrics] = useState<SkontoMetrics | null>(null);
  const [invoices, setInvoices] = useState<SkontoInvoice[]>([]);
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      console.log('🚀 Starting fetchData...');
      setLoading(true);
      
      // Fetch real data from Skonto API endpoints
      console.log('📡 Making API calls...');
      const [metricsResponse, opportunitiesResponse, schedulerResponse] = await Promise.all([
        fetch('/api/skonto/dashboard/summary'),
        fetch('/api/skonto/dashboard/opportunities?urgency=all&limit=200'), // Max limit is 200
        fetch('/api/skonto/scheduler/status')
      ]);
      
      console.log('📊 API responses received:', {
        metrics: metricsResponse.status,
        opportunities: opportunitiesResponse.status,
        scheduler: schedulerResponse.status
      });

      if (!metricsResponse.ok || !opportunitiesResponse.ok) {
        throw new Error('Failed to fetch Skonto data');
      }

      const metricsData = await metricsResponse.json();
      const opportunitiesData = await opportunitiesResponse.json();
      
      // Fetch scheduler status (non-critical)
      let schedulerData = null;
      if (schedulerResponse.ok) {
        const schedulerResult = await schedulerResponse.json();
        schedulerData = schedulerResult.scheduler_status;
      }

      console.log('📊 Metrics data:', metricsData);
      console.log('📋 Opportunities data:', opportunitiesData);

      // Transform API data to match our interface
      const transformedMetrics: SkontoMetrics = {
        totalInvoices: metricsData.total_opportunities || 0,
        totalSkontoAmount: metricsData.total_potential_savings || 0,
        capturedSkonto: 0, // Will be calculated from transformed invoices
        missedSkonto: 0,   // Will be calculated from transformed invoices
        pendingReview: metricsData.open_count || 0,
        successRate: metricsData.success_rate || 0
      };

      // Transform opportunities data to match our interface
      const transformedInvoices: SkontoInvoice[] = opportunitiesData.map((opportunity: any) => {
        const skontoAmount = opportunity.potential_savings || 0;
        let status: 'captured' | 'missed' | 'pending' | 'expired' = 'pending';
        
        // Determine status based on skonto_decision from backend
        const skontoDecision = opportunity.skonto_decision;
        if (skontoDecision === 'taken') {
          status = 'captured';
        } else if (skontoDecision === 'missed') {
          status = 'missed';
        } else if (opportunity.days_until_expiry < 0) {
          status = 'expired';
        } else {
          status = 'pending';
        }

        return {
          id: opportunity.id,
          invoiceNumber: opportunity.invoice_number || 'N/A',
          vendor: opportunity.supplier || 'N/A', // This uses rechnungssteller from backend
          amount: opportunity.amount || 0,
          skontoRate: opportunity.skonto_percentage || 0,
          skontoAmount: skontoAmount,
          skontoDeadline: opportunity.skonto_date || '',
          status: status,
          daysRemaining: opportunity.days_until_expiry || 0,
          processedDate: opportunity.processed_date,
          reminderSent: opportunity.reminder_sent || false
        };
      });

      // Calculate captured and missed amounts from transformed invoices
      transformedMetrics.capturedSkonto = transformedInvoices
        .filter(invoice => invoice.status === 'captured')
        .reduce((total, invoice) => total + invoice.skontoAmount, 0);
      
      transformedMetrics.missedSkonto = transformedInvoices
        .filter(invoice => invoice.status === 'missed')
        .reduce((total, invoice) => total + invoice.skontoAmount, 0);

      setMetrics(transformedMetrics);
      setInvoices(transformedInvoices);
      setSchedulerStatus(schedulerData);
      setError(null);
      
    } catch (error) {
      console.error('❌ Error fetching Skonto data:', error);
      console.error('❌ Error details:', error);
      setError('Fehler beim Laden der Skonto-Daten');
    } finally {
      console.log('✅ fetchData completed, setting loading to false');
      setLoading(false);
    }
  };

  // Action handlers for Skonto management
  const handleSendReminder = async (invoiceId: string) => {
    try {
      setActionLoading(invoiceId);
      const response = await fetch(`/api/invoices/${invoiceId}/send-skonto-reminder`, {
        method: 'POST',
      });
      
      if (response.ok) {
        const result = await response.json();
        alert(result.email_provider === 'demo'
          ? '📁 Demo-Modus: Die Erinnerung wurde nicht versendet, sondern in backend/outbox gespeichert.'
          : '✅ Erinnerung erfolgreich gesendet!');
        // Refresh data after action
        await fetchData();
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Fehler beim Senden der Erinnerung');
      }
    } catch (error) {
      console.error('Error sending reminder:', error);
      alert('Fehler beim Senden der Erinnerung: ' + (error as Error).message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleMarkAsTaken = async (invoiceId: string) => {
    try {
      setActionLoading(invoiceId);
      const response = await fetch(`/api/invoices/${invoiceId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          skonto_decision: 'taken'
        }),
      });
      
      if (response.ok) {
        // Refresh data after action
        await fetchData();
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Fehler beim Markieren als genutzt');
      }
    } catch (error) {
      console.error('Error marking as taken:', error);
      alert('Fehler beim Markieren als genutzt: ' + (error as Error).message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleMarkAsMissed = async (invoiceId: string) => {
    try {
      setActionLoading(invoiceId);
      const response = await fetch(`/api/invoices/${invoiceId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          skonto_decision: 'missed'
        }),
      });
      
      if (response.ok) {
        // Refresh data after action
        await fetchData();
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Fehler beim Markieren als verpasst');
      }
    } catch (error) {
      console.error('Error marking as missed:', error);
      alert('Fehler beim Markieren als verpasst: ' + (error as Error).message);
    } finally {
      setActionLoading(null);
    }
  };

  useEffect(() => {
    console.log('🔄 useEffect triggered, calling fetchData...');
    
    // Add a simple timeout to test if useEffect is working
    setTimeout(() => {
      console.log('⏰ Timeout executed, now calling fetchData...');
      fetchData();
    }, 1000);
  }, []);

  const filteredInvoices = invoices.filter(invoice => {
    const matchesStatus = filterStatus === 'all' || invoice.status === filterStatus;
    const matchesSearch = 
      invoice.invoiceNumber.toLowerCase().includes(searchTerm.toLowerCase()) ||
      invoice.vendor.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const getStatusBadge = (status: string) => {
    const statusConfig = {
      captured: { bgColor: 'glass-card border-green-200', textColor: 'text-green-700', icon: CheckCircle },
      missed: { bgColor: 'glass-card border-red-200', textColor: 'text-red-700', icon: XCircle },
      pending: { bgColor: 'glass-card border-yellow-200', textColor: 'text-yellow-700', icon: Clock },
      expired: { bgColor: 'glass-card border-gray-200', textColor: 'text-gray-700', icon: AlertCircle }
    };
    
    const config = statusConfig[status as keyof typeof statusConfig];
    const Icon = config.icon;
    
    return (
      <span className={`inline-flex items-center gap-1 rounded-xl px-2.5 py-0.5 text-xs font-semibold border shadow-sm ${config.bgColor} ${config.textColor}`}>
        <Icon className="h-3 w-3" />
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen gradient-bg-light relative overflow-hidden">
        <div className="flex items-center justify-center min-h-screen">
          <div className="glass-card p-8 text-center animate-pulse rounded-xl border shadow">
            <div className="flex items-center justify-center space-x-2">
              <RefreshCw className="h-6 w-6 animate-spin text-purple-600" />
              <span className="text-lg font-medium text-gray-700">Lade Skonto-Bericht...</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen gradient-bg-light relative overflow-hidden">
        {/* Floating Background Elements */}
        <div className="absolute top-20 left-10 w-32 h-32 bg-red-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-float"></div>
        <div className="absolute bottom-20 right-20 w-40 h-40 bg-orange-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-float" style={{ animationDelay: '2s' }}></div>
        
        <div className="flex items-center justify-center min-h-screen">
          <div className="glass-card p-8 text-center max-w-md rounded-xl border shadow">
            <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-800 mb-2">Fehler beim Laden des Berichts</h2>
            <p className="text-gray-600 mb-4">{error}</p>
            <button 
              onClick={() => window.location.reload()} 
              className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors"
            >
              Erneut versuchen
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen gradient-bg-light relative overflow-hidden">
      {/* Floating Background Elements */}
      <div className="absolute top-20 left-10 w-32 h-32 bg-purple-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-float"></div>
      <div className="absolute top-40 right-20 w-40 h-40 bg-blue-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-float" style={{ animationDelay: '2s' }}></div>
      <div className="absolute bottom-20 left-1/3 w-36 h-36 bg-pink-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-float" style={{ animationDelay: '4s' }}></div>
      <div className="absolute top-1/2 right-10 w-28 h-28 bg-yellow-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-float" style={{ animationDelay: '1s' }}></div>

      <div className="relative z-10 pt-20 pb-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto px-2 sm:px-4 lg:px-8">
          {/* Header Section */}
          <div className="mb-8">
            <div className="glass-card p-6 border-0 shadow-xl rounded-xl">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between">
                <div>
                  <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-600 via-blue-600 to-indigo-600 bg-clip-text text-transparent mb-2">
                    Skonto Prüfbericht
                  </h1>
                  <p className="text-gray-600">
                    Umfassende Analyse von Skonto-Möglichkeiten und Leistung
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 mt-4 md:mt-0">
                  <span className="inline-flex items-center rounded-md px-2.5 py-0.5 text-xs font-semibold bg-gradient-to-r from-green-100 to-green-200 text-green-700 border border-green-300">
                    <TrendingUp className="h-3 w-3 mr-1" />
                    Echtzeit-Analysen
                  </span>
                  <span className="inline-flex items-center rounded-md px-2.5 py-0.5 text-xs font-semibold bg-gradient-to-r from-blue-100 to-blue-200 text-blue-700 border border-blue-300">
                    <Clock className="h-3 w-3 mr-1" />
                    Automatisch aktualisiert
                  </span>
                  {/* Scheduler Status Indicator */}
                  {schedulerStatus && (
                    <span className={`inline-flex items-center rounded-md px-2.5 py-0.5 text-xs font-semibold border ${
                      schedulerStatus.enabled && schedulerStatus.is_running
                        ? 'bg-gradient-to-r from-green-100 to-green-200 text-green-700 border-green-300'
                        : 'bg-gradient-to-r from-red-100 to-red-200 text-red-700 border-red-300'
                    }`}>
                      {schedulerStatus.enabled && schedulerStatus.is_running ? (
                        <Play className="h-3 w-3 mr-1" />
                      ) : (
                        <Pause className="h-3 w-3 mr-1" />
                      )}
                      Erinnerungs-Scheduler {schedulerStatus.enabled && schedulerStatus.is_running ? 'Aktiv' : 'Inaktiv'}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Filters and Controls - MOVED TO TOP */}
          <div className="glass-card border-0 shadow-lg mb-6 rounded-xl">
            <div className="p-6">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div className="flex flex-col md:flex-row gap-4 flex-1">
                  <div className="flex items-center gap-2">
                    <Filter className="h-4 w-4 text-gray-500" />
                    <span className="text-sm font-medium text-gray-700">Nach Status filtern:</span>
                    <select 
                      value={filterStatus} 
                      onChange={(e) => setFilterStatus(e.target.value)}
                      className="w-40 bg-white/50 border border-white/20 rounded-md px-3 py-1 text-sm"
                    >
                      <option value="all">Alle Status</option>
                      <option value="captured">Genutzt</option>
                      <option value="missed">Verpasst</option>
                      <option value="pending">Ausstehend</option>
                      <option value="expired">Abgelaufen</option>
                    </select>
                  </div>
                  
                  <input
                    placeholder="Rechnungen oder Lieferanten suchen..."
                    value={searchTerm}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchTerm(e.target.value)}
                    className="max-w-xs bg-white/50 border border-white/20 rounded-md px-3 py-1 text-sm placeholder:text-gray-500"
                  />
                </div>
                
                <button className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white shadow-lg px-4 py-2 rounded-md text-sm font-medium transition-colors inline-flex items-center gap-2">
                  <Download className="h-4 w-4" />
                  Export Report
                </button>
              </div>
            </div>
          </div>

          {/* Scheduler Statistics */}
          {schedulerStatus && (
            <div className="glass-card border-0 shadow-lg mb-6 rounded-xl">
              <div className="p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Settings className="h-5 w-5 text-gray-600" />
                  <h3 className="text-lg font-semibold text-gray-800">Automatisches Erinnerungssystem</h3>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="text-center p-3 bg-white/30 rounded-lg">
                    <div className="text-lg font-bold text-gray-900">{schedulerStatus.stats.total_runs}</div>
                    <div className="text-xs text-gray-600">Gesamte Prüfungen</div>
                  </div>
                  <div className="text-center p-3 bg-white/30 rounded-lg">
                    <div className="text-lg font-bold text-green-600">{schedulerStatus.stats.total_reminders_sent}</div>
                    <div className="text-xs text-gray-600">Erinnerungen gesendet</div>
                  </div>
                  <div className="text-center p-3 bg-white/30 rounded-lg">
                    <div className="text-lg font-bold text-blue-600">
                      {schedulerStatus.last_run ? new Date(schedulerStatus.last_run).toLocaleDateString() : 'Nie'}
                    </div>
                    <div className="text-xs text-gray-600">Letzte Prüfung</div>
                  </div>
                  <div className="text-center p-3 bg-white/30 rounded-lg">
                    <div className="text-lg font-bold text-purple-600">
                      {schedulerStatus.next_run ? new Date(schedulerStatus.next_run).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : 'Nicht geplant'}
                    </div>
                    <div className="text-xs text-gray-600">Nächste Prüfung</div>
                  </div>
                </div>
                {schedulerStatus.stats.total_errors > 0 && (
                  <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
                    <div className="text-sm text-red-700">
                      ⚠️ {schedulerStatus.stats.total_errors} Fehler erkannt. Überprüfen Sie die System-Logs.
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Invoices Table - MOVED TO TOP */}
          <div className="glass-card border-0 shadow-xl rounded-xl mb-8">
            <div className="border-b border-white/20 p-6">
              <h3 className="text-xl font-semibold text-gray-800">
                Skonto-Rechnungsdetails ({filteredInvoices.length} Rechnungen)
              </h3>
            </div>
            <div className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                    <tr>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rechnung</th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Lieferant</th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Betrag</th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Skonto</th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Frist</th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Erinnerung</th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Aktionen</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {filteredInvoices.map((invoice, index) => (
                      <tr 
                        key={invoice.id} 
                        className="hover:bg-white/50 transition-colors duration-200"
                        style={{ animationDelay: `${index * 0.1}s` }}
                      >
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900">{invoice.invoiceNumber}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900">{invoice.vendor}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900">€{invoice.amount.toLocaleString()}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900">
                            {invoice.skontoRate}% (€{invoice.skontoAmount.toLocaleString()})
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900">
                            {new Date(invoice.skontoDeadline).toLocaleDateString()}
                            {invoice.daysRemaining !== undefined && (
                              <div className={`text-xs ${invoice.daysRemaining > 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {invoice.daysRemaining > 0 ? `${invoice.daysRemaining} Tage verbleibend` : `${Math.abs(invoice.daysRemaining)} Tage überfällig`}
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {getStatusBadge(invoice.status)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium ${
                            invoice.reminderSent 
                              ? 'bg-green-50 text-green-700 border border-green-200' 
                              : 'bg-gray-50 text-gray-500 border border-gray-200'
                          }`}>
                            <Mail className="h-3 w-3" />
                            {invoice.reminderSent ? 'Gesendet' : 'Nicht gesendet'}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            {invoice.status === 'pending' && !invoice.reminderSent && (
                              <button
                                onClick={() => handleSendReminder(invoice.id)}
                                disabled={actionLoading === invoice.id}
                                className="bg-blue-600 hover:bg-blue-700 text-white shadow-lg px-3 py-1 rounded-md text-xs font-medium transition-colors inline-flex items-center gap-1 disabled:opacity-50"
                              >
                                {actionLoading === invoice.id ? (
                                  <RefreshCw className="h-3 w-3 animate-spin" />
                                ) : (
                                  <Mail className="h-3 w-3" />
                                )}
                                Erinnerung senden
                              </button>
                            )}
                            
                            {(invoice.status === 'pending' || invoice.status === 'expired') && (
                              <>
                                <button
                                  onClick={() => handleMarkAsTaken(invoice.id)}
                                  disabled={actionLoading === invoice.id}
                                  className="bg-green-600 hover:bg-green-700 text-white shadow-lg px-3 py-1 rounded-md text-xs font-medium transition-colors inline-flex items-center gap-1 disabled:opacity-50"
                                >
                                  {actionLoading === invoice.id ? (
                                    <RefreshCw className="h-3 w-3 animate-spin" />
                                  ) : (
                                    <ThumbsUp className="h-3 w-3" />
                                  )}
                                  Genutzt
                                </button>
                                <button
                                  onClick={() => handleMarkAsMissed(invoice.id)}
                                  disabled={actionLoading === invoice.id}
                                  className="bg-red-600 hover:bg-red-700 text-white shadow-lg px-3 py-1 rounded-md text-xs font-medium transition-colors inline-flex items-center gap-1 disabled:opacity-50"
                                >
                                  {actionLoading === invoice.id ? (
                                    <RefreshCw className="h-3 w-3 animate-spin" />
                                  ) : (
                                    <ThumbsDown className="h-3 w-3" />
                                  )}
                                  Verpasst
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Metrics Section - MOVED BELOW TABLE */}
          {metrics && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6 mb-8">
              <div className="glass-card border-0 shadow-lg hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 rounded-xl">                  <div className="p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-600 mb-1">Rechnungen gesamt</p>
                        <p className="text-2xl font-bold text-gray-900">{metrics.totalInvoices.toLocaleString()}</p>
                      </div>
                      <div className="h-12 w-12 bg-gradient-to-r from-blue-500 to-blue-600 rounded-lg flex items-center justify-center">
                        <AlertCircle className="h-6 w-6 text-white" />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="glass-card border-0 shadow-lg hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 rounded-xl">
                  <div className="p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-600 mb-1">Skonto gesamt</p>
                        <p className="text-2xl font-bold text-gray-900">€{metrics.totalSkontoAmount.toLocaleString()}</p>
                      </div>
                      <div className="h-12 w-12 bg-gradient-to-r from-purple-500 to-purple-600 rounded-lg flex items-center justify-center">
                        <TrendingUp className="h-6 w-6 text-white" />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="glass-card border-0 shadow-lg hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 rounded-xl">
                  <div className="p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-600 mb-1">Erfasst</p>
                        <p className="text-2xl font-bold text-green-600">€{metrics.capturedSkonto.toLocaleString()}</p>
                      </div>
                      <div className="h-12 w-12 bg-gradient-to-r from-green-500 to-green-600 rounded-lg flex items-center justify-center">
                        <CheckCircle className="h-6 w-6 text-white" />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="glass-card border-0 shadow-lg hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 rounded-xl">
                  <div className="p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-600 mb-1">Verpasst</p>
                        <p className="text-2xl font-bold text-red-600">€{metrics.missedSkonto.toLocaleString()}</p>
                      </div>
                      <div className="h-12 w-12 bg-gradient-to-r from-red-500 to-red-600 rounded-lg flex items-center justify-center">
                        <XCircle className="h-6 w-6 text-white" />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="glass-card border-0 shadow-lg hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 rounded-xl">
                  <div className="p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-600 mb-1">Ausstehend</p>
                        <p className="text-2xl font-bold text-yellow-600">{metrics.pendingReview}</p>
                      </div>
                      <div className="h-12 w-12 bg-gradient-to-r from-yellow-500 to-yellow-600 rounded-lg flex items-center justify-center">
                        <Clock className="h-6 w-6 text-white" />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="glass-card border-0 shadow-lg hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 rounded-xl">
                  <div className="p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-600 mb-1">Erfolgsquote</p>
                        <p className="text-2xl font-bold text-gray-900">{metrics.successRate.toFixed(0)}%</p>
                      </div>
                      <div className="h-12 w-12 bg-gradient-to-r from-indigo-500 to-indigo-600 rounded-lg flex items-center justify-center">
                        <Clock className="h-6 w-6 text-white" />
                      </div>
                    </div>
                  </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
