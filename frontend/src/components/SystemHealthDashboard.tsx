'use client';

import React, { useState, useEffect } from 'react';
import { authFetch } from '@/lib/authFetch';

interface HealthComponent {
  status: 'healthy' | 'degraded' | 'error';
  response_time_ms?: number;
  error?: string;
  total_invoices?: number;
  connection?: string;
  config?: Record<string, string>;
  available_endpoints?: string[];
  write_access?: boolean;
  bucket?: string;
  // Service-specific properties
  service?: string;
  timestamp?: number;
  checks?: Record<string, {
    status: string;
    details: string;
  }>;
}

interface SystemHealth {
  timestamp: string;
  overall_status: 'healthy' | 'degraded' | 'error';
  components: {
    database?: HealthComponent;
    storage?: HealthComponent;
    environment?: HealthComponent;
    api_endpoints?: HealthComponent;
    filesystem?: HealthComponent;
  };
}

const statusColors = {
  healthy: 'glass-card text-green-700 border-green-200',
  degraded: 'glass-card text-yellow-700 border-yellow-200',
  error: 'glass-card text-red-700 border-red-200'
};

const statusIcons = {
  healthy: '✅',
  degraded: '⚠️',
  error: '❌'
};

export default function SystemHealthDashboard() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchHealth = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Use the Next.js API route as a proxy to avoid CORS issues
      const response = await authFetch('/api/system-health');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setHealth(data);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Fehler beim Laden des Systemstatus');
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const renderComponent = (name: string, component: HealthComponent) => {
    return (
      <div key={name} className="glass-card rounded-xl shadow-xl p-6 border-l-4 border-purple-500 hover:shadow-2xl transition-all transform hover:scale-[1.02] animate-fade-in">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold gradient-text capitalize flex items-center gap-2">
            {name.replace('_', ' ')}
          </h3>
          <span className={`px-3 py-1 rounded-full text-sm font-medium border shadow-lg ${statusColors[component.status]}`}>
            {statusIcons[component.status]} {
              component.status === 'healthy' ? 'GESUND' :
              component.status === 'degraded' ? 'BEEINTRÄCHTIGT' :
              component.status === 'error' ? 'FEHLER' :
              (component.status as string).toUpperCase()
            }
          </span>
        </div>
      
      <div className="space-y-2">
        {component.response_time_ms !== undefined && (
          <div className="flex justify-between">
            <span className="text-gray-700">Response Time:</span>
            <span className={`font-mono ${component.response_time_ms > 1000 ? 'text-red-600' : 'text-green-600'}`}>
              {component.response_time_ms}ms
            </span>
          </div>
        )}
        
        {component.total_invoices !== undefined && (
          <div className="flex justify-between">
            <span className="text-gray-700">Total Invoices:</span>
            <span className="font-mono gradient-text">{component.total_invoices}</span>
          </div>
        )}
        
        {component.connection && (
          <div className="flex justify-between">
            <span className="text-gray-700">Verbindung:</span>
            <span className="font-mono gradient-text">{component.connection}</span>
          </div>
        )}
        
        {component.bucket && (
          <div className="flex justify-between">
            <span className="text-gray-700">Bucket:</span>
            <span className="font-mono gradient-text">{component.bucket}</span>
          </div>
        )}
        
        {component.write_access !== undefined && (
          <div className="flex justify-between">
            <span className="text-gray-700">Schreibzugriff:</span>
            <span className={`font-mono ${component.write_access ? 'text-green-600' : 'text-red-600'}`}>
              {component.write_access ? 'Ja' : 'Nein'}
            </span>
          </div>
        )}
        
        {component.config && (
          <div className="mt-3">
            <span className="text-gray-700 text-sm">Configuration:</span>
            <div className="mt-1 space-y-1">
              {Object.entries(component.config).map(([key, value]) => (
                <div key={key} className="flex justify-between text-sm">
                  <span className="text-gray-600">{key}:</span>
                  <span className={`font-mono $                    {value === 'configured' ? 'text-green-600' : 'text-red-600'}`}>
                    {value === 'configured' ? 'konfiguriert' : value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {component.available_endpoints && (
          <div className="mt-3">
            <span className="text-gray-700 text-sm">Available Endpoints:</span>
            <div className="mt-1 flex flex-wrap gap-1">
              {component.available_endpoints.map((endpoint) => (
                <span key={endpoint} className="glass-card text-gray-700 px-2 py-1 rounded text-xs font-mono border border-gray-200 shadow-sm">
                  {endpoint}
                </span>
              ))}
            </div>
          </div>
        )}
        
        {component.service && (
          <div className="flex justify-between">
            <span className="text-gray-700">Service:</span>
            <span className="font-mono text-blue-600">{component.service}</span>
          </div>
        )}
        
        {component.checks && (
          <div className="mt-3">
            <span className="text-gray-700 text-sm">Health Checks:</span>
            <div className="mt-2 space-y-2">
              {Object.entries(component.checks).map(([checkName, checkData]) => (
                <div key={checkName} className="glass-card rounded-lg p-2 border border-white/20 shadow-lg">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-sm font-medium text-gray-800">
                      {checkName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </span>
                    <span className={`px-2 py-1 text-xs rounded glass-card border ${
                      checkData.status === 'healthy' ? 'border-green-200 text-green-800' :
                      checkData.status === 'unhealthy' ? 'border-red-200 text-red-800' :
                      'border-yellow-200 text-yellow-800'
                    }`}>
                      {checkData.status}
                    </span>
                  </div>
                  <p className="text-xs text-gray-700">{checkData.details}</p>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {component.error && (
          <div className="mt-3 p-3 glass-card border border-red-200 rounded-xl shadow-lg">
            <span className="text-red-600 text-sm font-medium">Fehler:</span>
            <p className="text-red-700 text-sm mt-1 font-mono">{component.error}</p>
          </div>
        )}
      </div>
    </div>
  );
};

  if (loading && !health) {
    return (
      <div className="min-h-screen gradient-bg-light flex items-center justify-center">
        <div className="text-center glass-card rounded-2xl p-8 animate-fade-in">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto mb-4"></div>
          <p className="gradient-text">Systemstatus wird geladen...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen gradient-bg-light py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold gradient-text">Systemstatus Dashboard</h1>
              <p className="text-gray-700 mt-2">Überwachen Sie den Zustand und Status aller Systemkomponenten</p>
            </div>
            <button
              onClick={fetchHealth}
              disabled={loading}
              className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 disabled:from-blue-400 disabled:to-blue-500 text-white px-4 py-2 rounded-xl flex items-center gap-2 transition-all transform hover:scale-105 shadow-lg"
            >
              {loading ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              ) : (
                '🔄'
              )}
              Aktualisieren
            </button>
          </div>
          
          {lastUpdated && (
            <p className="text-sm text-gray-600 mt-2">
              Last updated: {lastUpdated.toLocaleString()}
            </p>
          )}
        </div>

        {error && (
          <div className="mb-8 glass-card border border-red-200 rounded-xl p-6 animate-fade-in">
            <div className="flex">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-gradient-to-r from-red-500 to-red-600 rounded-lg flex items-center justify-center">
                  <span className="text-white text-lg">❌</span>
                </div>
              </div>
              <div className="ml-4">
                <h3 className="text-lg font-medium text-red-800 mb-2">Systemstatus kann nicht abgerufen werden</h3>
                <div className="text-sm text-red-700 space-y-2">
                  <p className="font-mono bg-red-50 p-2 rounded-lg border border-red-200">
                    {error}
                  </p>
                  <div className="space-y-1">
                    <p><strong>Mögliche Ursachen:</strong></p>
                    <ul className="list-disc list-inside space-y-1 text-red-600">
                      <li>Backend-Server läuft nicht (erwartet unter: <code className="bg-red-50 px-1 rounded">http://localhost:8000</code>)</li>
                      <li>Netzwerkverbindungsprobleme</li>
                      <li>API-Endpunkt-Konfigurationsfehler</li>
                      <li>Backend-Health-Endpunkt nicht verfügbar</li>
                    </ul>
                  </div>
                  <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <p className="text-blue-800 text-sm">
                      <strong>💡 Quick fix:</strong> Make sure the backend server is running by executing:
                    </p>
                    <code className="block mt-1 bg-gray-800 text-green-400 p-2 rounded text-xs font-mono">
                      cd backend && python main.py
                    </code>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {health && (
          <>
            <div className="mb-8 glass-card rounded-xl shadow-xl p-6 animate-fade-in">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold gradient-text">Gesamtsystemstatus</h2>
                <span className={`px-4 py-2 rounded-full text-lg font-medium border shadow-lg ${statusColors[health.overall_status]}`}>
                  {statusIcons[health.overall_status]} {
                    health.overall_status === 'healthy' ? 'GESUND' :
                    health.overall_status === 'degraded' ? 'BEEINTRÄCHTIGT' :
                    health.overall_status === 'error' ? 'FEHLER' :
                    (health.overall_status as string).toUpperCase()
                  }
                </span>
              </div>
              <p className="text-gray-700 text-sm mt-2">
                Geprüft am: {new Date(health.timestamp).toLocaleString()}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {Object.entries(health.components).map(([name, component]) =>
                renderComponent(name, component)
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
