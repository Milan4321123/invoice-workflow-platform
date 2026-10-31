'use client';

import React, { useState, useEffect } from 'react';
import { getApiUrl } from '@/config/api';
import PDFViewer from './PDFViewerClean';
import CleanInvoiceForm, { GermanInvoiceFields } from './CleanInvoiceForm';
import { FileText, Eye, Edit3, AlertTriangle, CheckCircle, Monitor, FileInput, FileCode2, BadgeCheck, Lock } from 'lucide-react';
import { authFetch } from '@/lib/authFetch';
import { toast } from 'react-hot-toast';
import { useRouter } from 'next/navigation';
import { Notice } from './ui/Notice';
import { apiErrorMessage } from '@/lib/apiError';
import { useLanguage } from '@/i18n/LanguageContext';

interface InvoiceEditorDashboardProps {
  invoiceId: string;
  initialData?: {
    pdfUrl: string;
    fields: GermanInvoiceFields;
    filename?: string;
  };
}

export default function InvoiceEditorDashboard({ 
  invoiceId, 
  initialData 
}: InvoiceEditorDashboardProps) {
  const [pdfUrl, setPdfUrl] = useState<string>(initialData?.pdfUrl || '');
  const [fields, setFields] = useState<GermanInvoiceFields>(initialData?.fields || {});
  const [filename, setFilename] = useState<string>(initialData?.filename || '');
  const [mimeType, setMimeType] = useState<string | null>(null);
  const [eRechnungFormat, setERechnungFormat] = useState<string | null>(null);
  const [locked, setLocked] = useState(false);
  const [aiMode, setAiMode] = useState<'live' | 'offline' | null>(null);

  useEffect(() => {
    authFetch(`${getApiUrl()}/api/ai/status`)
      .then((r) => (r.ok ? r.json() : null))
      .then((status) => status && setAiMode(status.mode))
      .catch(() => setAiMode(null));
  }, []);
  const { locale, t } = useLanguage();
  const router = useRouter();
  const [retentionUntil, setRetentionUntil] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(!initialData);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isCompleting, setIsCompleting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);
  const [pdfNumPages, setPdfNumPages] = useState<number>(0);
  const [mobileView, setMobileView] = useState<'pdf' | 'form'>('pdf'); // For mobile toggle

  // Load invoice data if not provided initially
  useEffect(() => {
    if (!initialData && invoiceId) {
      loadInvoiceData();
    }
  }, [invoiceId, initialData]);

  const loadInvoiceData = async () => {
    try {
      setIsLoading(true);
      setError(null);

      // API call to load invoice data
      const apiUrl = getApiUrl();
      const response = await authFetch(`${apiUrl}/api/invoices/${invoiceId}/editor`);
      if (!response.ok) {
        throw new Error(`Rechnung konnte nicht geladen werden: ${response.statusText}`);
      }

      const data = await response.json();
      setPdfUrl(data.pdfUrl);
      setFields(data.fields || {});
      setFilename(data.filename || `Rechnung ${invoiceId}`);
      setMimeType(data.mimeType || null);
      setERechnungFormat(data.eRechnungFormat || null);
      setLocked(Boolean(data.locked));
      setRetentionUntil(data.retentionUntil || null);
    } catch (err) {
      console.error('Error loading invoice data:', err);
      setError(err instanceof Error ? err.message : 'Rechnungsdaten konnten nicht geladen werden');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFieldChange = (field: keyof GermanInvoiceFields, value: any) => {
    setFields(prev => ({
      ...prev,
      [field]: value
    }));
    setHasUnsavedChanges(true);
  };

  const handleSave = async (updatedFields: GermanInvoiceFields, quiet = false) => {
    try {
      setIsSaving(true);
      
      // API call to save invoice data with editor information for email notification
      const apiUrl = getApiUrl();
      
      // Prepare editor information for email notification
      const editorInfo = {
        editor_email: updatedFields.rechnungspruefung_email ,
        editor_name: "Rechnung Bearbeiter",
        changes_summary: [
          {
            field: "last_edited",
            old_value: new Date().toISOString(),
            new_value: "Rechnung wurde bearbeitet und gespeichert"
          }
        ]
      };

      const response = await authFetch(`${apiUrl}/api/invoices/${invoiceId}/editor`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          fields: updatedFields,
          editor_info: editorInfo
        }),
      });

      if (!response.ok) {
        throw new Error(await apiErrorMessage(response, `Speichern fehlgeschlagen: ${response.statusText}`));
      }

      const result = await response.json();
      setFields(updatedFields);
      setHasUnsavedChanges(false);
      
      if (!quiet) {
        toast.success(<Notice title={t('editor.saved')}
          text={result.email_sent ? t('editor.savedEmail', { email: editorInfo.editor_email ?? '' }) : undefined} />);
      }
      
      return true;
    } catch (err) {
      console.error('Error saving invoice:', err);
      // When completing, the caller reports the failure once
      if (!quiet) toast.error(<Notice title={t('editor.saveFailed')} text={err instanceof Error ? err.message : undefined} />);
      throw err;
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    // Reset to original data
    if (initialData) {
      setFields(initialData.fields);
    }
    setHasUnsavedChanges(false);
  };

  const handlePdfLoadSuccess = (numPages: number) => {
    setPdfNumPages(numPages);
  };

  const handlePdfLoadError = (error: any) => {
    console.error('PDF load error:', error);
    setError('PDF-Dokument konnte nicht geladen werden');
  };

  const handleComplete = async () => {
    try {
      setIsCompleting(true);
      
      // First save the current changes
      await handleSave(fields, true);
      
      // Mark as completed - no automatic email sending
      const apiUrl = getApiUrl();
      
      // Prepare completion data with editor info for completion email
      const completionData = {
        completion_info: {
          completed_by: fields.rechnungspruefung_email || "editor@company.de",
          completed_at: new Date().toISOString(),
          completion_notes: "Rechnung wurde vollständig bearbeitet - bereit für Bauleiter-Genehmigung über Dashboard"
        },
        editor_info: {
          editor_email: fields.rechnungspruefung_email || "editor@company.de",
          editor_name: fields.rechnungspruefung_email?.split('@')[0] || "Editor",
          changes_summary: [
            {
              field: "Status",
              old_value: "Bearbeitung",
              new_value: "Bearbeitung abgeschlossen - bereit für Bauleiter",
              timestamp: new Date().toLocaleString('de-DE')
            }
          ]
        }
      };

      const response = await authFetch(`${apiUrl}/api/invoices/${invoiceId}/complete`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(completionData),
      });

      if (!response.ok) {
        throw new Error(await apiErrorMessage(response, `Abschluss fehlgeschlagen: ${response.statusText}`));
      }

      const result = await response.json();
      
      toast.success(<Notice title={t('editor.completed')}
        text={[result.completion_email_sent ? t('editor.completedEmail') : '', t('editor.completedNext')].filter(Boolean).join(' ')} />,
        { duration: 6000 });
      // Client-side navigation keeps the notification visible on the dashboard
      router.push('/dashboard');
      
      return true;
    } catch (err) {
      console.error('Error completing invoice:', err);
      toast.error(<Notice title={t('editor.completeFailed')} text={err instanceof Error ? err.message : undefined} />);
      throw err;
    } finally {
      setIsCompleting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <h2 className="text-xl font-semibold text-gray-700 mb-2">Rechnungseditor wird geladen</h2>
          <p className="text-gray-500">Dokument wird vorbereitet...</p>
        </div>
      </div>
    );
  }

  if (error && !pdfUrl) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center max-w-md">
          <AlertTriangle className="h-16 w-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-700 mb-2">Fehler beim Laden der Rechnung</h2>
          <p className="text-gray-500 mb-4">{error}</p>
          <button
            onClick={loadInvoiceData}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Erneut versuchen
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen bg-white flex flex-col">
      {/* Minimal Header - Only for Mobile Toggle */}
      <header className="lg:hidden bg-white border-b border-gray-200 py-2 px-4">
        <div className="flex justify-center">
          <div className="flex bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setMobileView('pdf')}
              className={`flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                mobileView === 'pdf' 
                  ? 'bg-white text-blue-600 shadow-sm' 
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Monitor className="h-4 w-4" />
              <span>{t('editor.pdf')}</span>
            </button>
            <button
              onClick={() => setMobileView('form')}
              className={`flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                mobileView === 'form' 
                  ? 'bg-white text-blue-600 shadow-sm' 
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <FileInput className="h-4 w-4" />
              <span>{t('editor.form')}</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content - Clean Full-Screen Split */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* PDF Viewer - Full Height, Clean Display */}
        <div className={`lg:flex-1 lg:w-1/2 ${mobileView === 'pdf' ? 'flex' : 'hidden lg:flex'} flex-col bg-gray-900`}>
          <div className="flex-1 h-full">
            {mimeType === 'application/xml' ? (
              <div className="flex items-center justify-center h-full bg-gray-800 p-8">
                <div className="text-center text-gray-300 max-w-sm">
                  <FileCode2 className="h-16 w-16 mx-auto mb-4 text-gray-400" aria-hidden="true" />
                  <p className="text-lg font-medium text-white">{t('editor.xmlTitle')}</p>
                  <p className="text-sm mt-2">{t('editor.xmlBody')}</p>
                </div>
              </div>
            ) : pdfUrl ? (
              <PDFViewer
                pdfUrl={pdfUrl}
                onLoadSuccess={handlePdfLoadSuccess}
                onLoadError={handlePdfLoadError}
                className="h-full w-full"
              />
            ) : (
              <div className="flex items-center justify-center h-full bg-gray-800">
                <div className="text-center text-gray-400">
                  <FileText className="h-16 w-16 mx-auto mb-4" />
                  <p className="text-lg">{t('editor.noPdf')}</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Form Section - Clean, Focused Editing */}
        <div className={`lg:flex-1 lg:w-1/2 ${mobileView === 'form' ? 'flex' : 'hidden lg:flex'} flex-col bg-white`}>
          {locked && (
            <div role="note" className="flex items-start gap-3 border-b border-amber-200 bg-amber-50 px-6 py-3 text-sm text-amber-900">
              <Lock className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true" />
              <p>
                <span className="font-semibold">{t('editor.locked')}</span>{' '}
                {t('editor.lockedBody', {
                  date: retentionUntil ? new Date(retentionUntil).toLocaleDateString(locale === 'en' ? 'en-GB' : 'de-DE') : '—',
                })}
              </p>
            </div>
          )}
          {eRechnungFormat && (
            <div className="flex items-start gap-3 border-b border-green-200 bg-green-50 px-6 py-3 text-sm text-green-800">
              <BadgeCheck className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true" />
              <p>
                <span className="font-semibold">{t('editor.eInvoice', { format: eRechnungFormat })}</span>{' '}
                {t('editor.eInvoiceBody')}
              </p>
            </div>
          )}
          <div className="flex-1 h-full overflow-hidden">
            <CleanInvoiceForm
              invoiceId={invoiceId}
              readOnly={locked}
              aiExtraction={!eRechnungFormat && !locked && mimeType !== 'application/xml' ? { mode: aiMode } : null}
              fields={fields}
              onFieldChange={(fieldName: string, value: any) => handleFieldChange(fieldName as keyof GermanInvoiceFields, value)}
              onSave={() => handleSave(fields)}
              onComplete={handleComplete}
              isSaving={isSaving}
              isCompleting={isCompleting}
              className="h-full"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
