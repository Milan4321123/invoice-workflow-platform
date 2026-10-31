'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { AlertCircle, CheckCircle2, ExternalLink, HardHat, Loader2, XCircle } from 'lucide-react';
import { buildApiUrl } from '@/config/api';
import { authFetch } from '@/lib/authFetch';
import { apiErrorMessage } from '@/lib/apiError';
import { useLanguage } from '@/i18n/LanguageContext';
import { useDialog } from '@/components/ui/DialogProvider';

interface Invoice {
  id: string;
  file_name: string;
  rechnungssteller?: string;
  rechnungsnummer?: string;
  rechnungsbetrag?: number;
  rechnungseingang?: string;
  faelligkeit?: string;
  projekt_label?: string;
  projekt?: string;
  gewerk_label?: string;
  gewerk?: string;
  bauleiter_email?: string;
  reviewed_by?: string;
  reviewed_at?: string;
  review_notes?: string;
  status: string;
}

interface Check { status: 'ok' | 'warnings' | 'errors'; error_count: number }

function DecisionCard({ invoice, onDecided }: { invoice: Invoice; onDecided: () => void }) {
  const { locale, t } = useLanguage();
  const [check, setCheck] = useState<Check | null>(null);
  const [mode, setMode] = useState<'idle' | 'rejecting' | 'busy'>('idle');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const dialog = useDialog();
  const money = (v?: number) => (v ?? 0).toLocaleString(locale === 'en' ? 'en-GB' : 'de-DE', { style: 'currency', currency: 'EUR' });
  const day = (v?: string) => (v ? new Date(v).toLocaleDateString(locale === 'en' ? 'en-GB' : 'de-DE') : '—');

  // The site manager approves the work; showing the tax check avoids approving a defective invoice by accident
  useEffect(() => {
    authFetch(buildApiUrl(`/api/invoices/${invoice.id}/compliance-check`), { method: 'POST' })
      .then((r) => (r.ok ? r.json() : null))
      .then(setCheck)
      .catch(() => setCheck(null));
  }, [invoice.id]);

  const decide = async (decision: 'approve' | 'reject') => {
    if (decision === 'approve' && check && check.error_count > 0 && !(await dialog.confirm({
      title: t('site.approve'),
      message: t('site.approveWithErrors', { count: check.error_count }),
      confirmLabel: t('site.approve'),
      tone: 'danger',
    }))) {
      return;
    }
    setMode('busy');
    setError(null);
    const response = await authFetch(buildApiUrl(`/api/invoices/${invoice.id}/${decision}`), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes }),
    });
    if (response.ok) {
      onDecided();
    } else {
      setError(await apiErrorMessage(response, t('site.failed')));
      setMode(decision === 'reject' ? 'rejecting' : 'idle');
    }
  };

  return (
    <li className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold text-gray-900">
            {invoice.rechnungssteller || invoice.file_name}
            {invoice.rechnungsnummer && <span className="font-normal text-gray-600"> · {invoice.rechnungsnummer}</span>}
          </h3>
          <p className="mt-1 text-sm text-gray-600">
            {invoice.projekt_label || invoice.projekt || '—'} · {invoice.gewerk_label || invoice.gewerk || '—'}
          </p>
          <p className="mt-1 text-sm text-gray-600">
            {t('site.received')} {day(invoice.rechnungseingang)} · {t('site.due')} {day(invoice.faelligkeit)}
          </p>
        </div>
        <p className="text-xl font-semibold text-gray-900">{money(invoice.rechnungsbetrag)}</p>
      </div>

      {check && (
        <p className={`mt-3 flex items-center gap-1.5 text-sm ${check.error_count ? 'text-red-700' : 'text-green-700'}`}>
          {check.error_count
            ? <AlertCircle className="h-4 w-4" aria-hidden="true" />
            : <CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
          {check.error_count ? t('site.checkErrors', { count: check.error_count }) : t('site.checkOk')}
        </p>
      )}

      {mode === 'rejecting' || (mode === 'busy' && notes) ? (
        <div className="mt-4">
          <label htmlFor={`reason-${invoice.id}`} className="block text-sm font-medium text-gray-700">{t('site.reason')}</label>
          <textarea id={`reason-${invoice.id}`} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)}
            placeholder={t('site.reasonPlaceholder')} required aria-required="true"
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-red-500 focus:ring-2 focus:ring-red-500" />
        </div>
      ) : null}

      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {mode === 'rejecting' ? (
          <>
            <button type="button" onClick={() => decide('reject')} disabled={!notes.trim()}
              className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">
              {t('site.confirmReject')}
            </button>
            <button type="button" onClick={() => { setMode('idle'); setNotes(''); }}
              className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100">
              {t('site.cancel')}
            </button>
          </>
        ) : (
          <>
            <button type="button" onClick={() => decide('approve')} disabled={mode === 'busy'}
              className="inline-flex items-center gap-1.5 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50">
              {mode === 'busy' ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
              {t('site.approve')}
            </button>
            <button type="button" onClick={() => setMode('rejecting')} disabled={mode === 'busy'}
              className="inline-flex items-center gap-1.5 rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50">
              <XCircle className="h-4 w-4" aria-hidden="true" />
              {t('site.reject')}
            </button>
          </>
        )}
        <Link href={`/invoice-editor/${invoice.id}`}
          className="ml-auto inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:underline">
          {t('site.open')} <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </div>
    </li>
  );
}

/**
 * The site manager's queue: invoices whose work they have to confirm. Approval is
 * the factual check ("was it built as invoiced"); the tax check is shown alongside.
 */
export default function BauleiterPage() {
  const { locale, t } = useLanguage();
  const [email, setEmail] = useState('');
  const [pending, setPending] = useState<Invoice[] | null>(null);
  const [recent, setRecent] = useState<Invoice[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const query = email.trim() ? `?bauleiter_email=${encodeURIComponent(email.trim())}` : '';
      const [pendingRes, approvedRes, rejectedRes] = await Promise.all([
        authFetch(buildApiUrl(`/api/invoices/pending-approval${query}`)),
        authFetch(buildApiUrl('/api/invoices/by-status/approved_by_bauleiter')),
        authFetch(buildApiUrl('/api/invoices/by-status/rejected_by_bauleiter')),
      ]);
      if (!pendingRes.ok) throw new Error(await apiErrorMessage(pendingRes, t('site.failed')));
      setPending((await pendingRes.json()).pending_approvals);
      const decided = [
        ...(approvedRes.ok ? (await approvedRes.json()).invoices : []),
        ...(rejectedRes.ok ? (await rejectedRes.json()).invoices : []),
      ].sort((a: Invoice, b: Invoice) => (b.reviewed_at || '').localeCompare(a.reviewed_at || ''));
      setRecent(decided.slice(0, 10));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('site.failed'));
      setPending([]);
    }
  }, [email, t]);

  useEffect(() => {
    const timer = setTimeout(load, 300);
    return () => clearTimeout(timer);
  }, [load]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <h1 className="flex items-center gap-2 text-2xl font-semibold text-gray-900">
        <HardHat className="h-6 w-6 text-amber-600" aria-hidden="true" />
        {t('site.title')}
      </h1>
      <p className="mt-1 text-sm text-gray-600">{t('site.subtitle')}</p>

      <div className="mt-6 max-w-md">
        <label htmlFor="site-manager-email" className="block text-sm font-medium text-gray-700">{t('site.filter')}</label>
        <input id="site-manager-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
          placeholder={t('site.filterPlaceholder')} autoComplete="email"
          className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500" />
      </div>

      {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}

      <section aria-labelledby="pending-heading" className="mt-8">
        <h2 id="pending-heading" className="text-lg font-semibold text-gray-900">
          {t('site.pending')}{pending ? ` (${pending.length})` : ''}
        </h2>
        {pending === null ? (
          <p className="mt-3 text-sm text-gray-500">{t('site.loading')}</p>
        ) : pending.length === 0 ? (
          <p className="mt-3 rounded-xl border border-dashed border-gray-300 bg-white/60 p-6 text-center text-sm text-gray-600">{t('site.none')}</p>
        ) : (
          <ul className="mt-3 space-y-4">
            {pending.map((invoice) => <DecisionCard key={invoice.id} invoice={invoice} onDecided={load} />)}
          </ul>
        )}
      </section>

      <section aria-labelledby="recent-heading" className="mt-10">
        <h2 id="recent-heading" className="text-lg font-semibold text-gray-900">{t('site.recent')}</h2>
        {recent.length === 0 ? (
          <p className="mt-3 text-sm text-gray-500">{t('site.noneRecent')}</p>
        ) : (
          <ul className="mt-3 divide-y divide-gray-200 rounded-xl border border-gray-200 bg-white">
            {recent.map((invoice) => (
              <li key={invoice.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
                <span className="min-w-0">
                  <span className="font-medium text-gray-900">{invoice.rechnungssteller || invoice.file_name}</span>
                  {invoice.rechnungsnummer && <span className="text-gray-600"> · {invoice.rechnungsnummer}</span>}
                  {invoice.review_notes && <span className="block text-gray-500">„{invoice.review_notes}“</span>}
                </span>
                <span className={`rounded px-2 py-0.5 text-xs font-medium ${invoice.status === 'approved_by_bauleiter' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                  {invoice.status === 'approved_by_bauleiter' ? t('site.approved') : t('site.rejected')}
                  {invoice.reviewed_by && ` · ${invoice.reviewed_by}`}
                  {invoice.reviewed_at && ` · ${new Date(invoice.reviewed_at).toLocaleDateString(locale === 'en' ? 'en-GB' : 'de-DE')}`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
