'use client';

import React, { useEffect, useState } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, Info, Loader2, type LucideIcon } from 'lucide-react';
import { getApiUrl } from '@/config/api';
import { authFetch } from '@/lib/authFetch';
import type { GermanInvoiceFields } from '../CleanInvoiceForm';
import { useT } from '@/i18n/LanguageContext';
import type { MessageKey } from '@/i18n/messages';

type Severity = 'error' | 'warning' | 'info';

interface Finding {
  code: string;
  severity: Severity;
  field: string | null;
  message: string;
  legal_ref: string | null;
}

interface ComplianceReport {
  status: 'ok' | 'warnings' | 'errors';
  error_count: number;
  warning_count: number;
  findings: Finding[];
}

const severityStyle: Record<Severity, { icon: LucideIcon; className: string; label: MessageKey }> = {
  error: { icon: AlertCircle, className: 'text-red-600', label: 'check.error' },
  warning: { icon: AlertTriangle, className: 'text-amber-600', label: 'check.warning' },
  info: { icon: Info, className: 'text-blue-600', label: 'check.info' },
};

const CHECK_DELAY_MS = 600;

/**
 * Live result of the backend's §14 UStG / §13b UStG / §48 EStG check.
 * Sends the unsaved form values, so problems show up while the user types.
 */
export default function ComplianceChecklist({ invoiceId, fields }: { invoiceId: string; fields: GermanInvoiceFields }) {
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [failed, setFailed] = useState(false);
  const t = useT();

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setIsChecking(true);
      try {
        const response = await authFetch(`${getApiUrl()}/api/invoices/${invoiceId}/compliance-check`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(fields),
          signal: controller.signal,
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        setReport(await response.json());
        setFailed(false);
      } catch (error) {
        if ((error as Error).name !== 'AbortError') setFailed(true);
      } finally {
        setIsChecking(false);
      }
    }, CHECK_DELAY_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [invoiceId, fields]);

  const headline = !report
    ? t('check.pending')
    : report.status === 'ok'
      ? t('check.ok')
      : report.status === 'errors'
        ? t('check.errors', { count: report.error_count })
        : t('check.warnings', { count: report.warning_count });

  const HeadlineIcon = report?.status === 'ok' ? CheckCircle2 : report?.status === 'errors' ? AlertCircle : AlertTriangle;
  const headlineColor =
    report?.status === 'ok' ? 'text-green-700' : report?.status === 'errors' ? 'text-red-700' : 'text-amber-700';

  return (
    <section aria-labelledby="compliance-heading" className="mt-8 pt-6 border-t border-gray-200">
      <div className="flex items-center justify-between mb-3">
        <h3 id="compliance-heading" className="text-base font-semibold text-gray-900">
          {t('check.heading')}
        </h3>
        {isChecking && <Loader2 className="h-4 w-4 animate-spin text-gray-400" aria-label={t('check.running')} />}
      </div>

      <div role="status" aria-live="polite">
        {failed ? (
          <p className="text-sm text-gray-500">{t('check.unavailable')}</p>
        ) : (
          <p className={`flex items-center gap-2 text-sm font-medium ${report ? headlineColor : 'text-gray-500'}`}>
            {report && <HeadlineIcon className="h-5 w-5" aria-hidden="true" />}
            {headline}
          </p>
        )}
      </div>

      {report && report.findings.length > 0 && (
        <ul className="mt-4 space-y-3">
          {report.findings.map((finding) => {
            const { icon: Icon, className, label } = severityStyle[finding.severity];
            return (
              <li key={`${finding.code}-${finding.field}`} className="flex gap-3 text-sm">
                <Icon className={`h-4 w-4 mt-0.5 shrink-0 ${className}`} aria-hidden="true" />
                <div>
                  <span className="sr-only">{t(label)}: </span>
                  <span className="text-gray-800">{finding.message}</span>
                  {finding.legal_ref && (
                    <span className="ml-2 inline-block rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
                      {finding.legal_ref}
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
