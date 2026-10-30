'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Copy, Loader2, Mail, X } from 'lucide-react';
import { buildApiUrl } from '@/config/api';
import { authFetch } from '@/lib/authFetch';
import { apiErrorMessage } from '@/lib/apiError';
import { useT } from '@/i18n/LanguageContext';

interface Draft { mode: 'live' | 'offline'; subject: string | null; body: string | null; reason?: string }

/** Drafts an e-mail asking the supplier for a corrected invoice. The user copies it; nothing is sent. */
export default function CorrectionDraftButton({ invoiceId }: { invoiceId: string }) {
  const t = useT();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (draft?.body) dialogRef.current?.showModal();
  }, [draft]);

  const open = async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await authFetch(buildApiUrl(`/api/invoices/${invoiceId}/ai-correction-request`), { method: 'POST' });
      if (!response.ok) throw new Error(await apiErrorMessage(response, t('ai.error')));
      const data: Draft = await response.json();
      if (!data.body) setError(data.reason || t('ai.error'));
      setDraft(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('ai.error'));
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    if (!draft?.body) return;
    await navigator.clipboard.writeText(`${draft.subject}\n\n${draft.body}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <>
      <button type="button" onClick={open} disabled={busy}
        className="mt-4 inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-800 hover:bg-gray-50 disabled:opacity-60">
        {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Mail className="h-4 w-4" aria-hidden="true" />}
        {t('correction.button')}
      </button>
      {error && <p role="alert" className="mt-2 text-sm text-gray-600">{error}</p>}

      <dialog ref={dialogRef} aria-labelledby="correction-title" onClose={() => setDraft(null)}
        className="w-full max-w-2xl rounded-xl p-0 shadow-2xl backdrop:bg-black/40">
        {draft?.body && (
          <div className="p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 id="correction-title" className="text-lg font-semibold text-gray-900">{t('correction.heading')}</h2>
                <p className="text-xs text-gray-500">
                  {draft.mode === 'live' ? t('ai.badgeLive') : t('ai.badgeOffline')} · {t('correction.notSent')}
                </p>
              </div>
              <button type="button" onClick={() => dialogRef.current?.close()} aria-label={t('correction.close')}
                className="rounded p-1 text-gray-500 hover:bg-gray-100">
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            <label htmlFor="correction-subject" className="mt-4 block text-sm font-medium text-gray-700">{t('correction.subject')}</label>
            <input id="correction-subject" defaultValue={draft.subject ?? ''} onChange={(e) => setDraft({ ...draft, subject: e.target.value })}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
            <label htmlFor="correction-body" className="mt-3 block text-sm font-medium text-gray-700">{t('correction.body')}</label>
            <textarea id="correction-body" defaultValue={draft.body} rows={14} onChange={(e) => setDraft({ ...draft, body: e.target.value })}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm" />
            <div className="mt-4 flex justify-end">
              <button type="button" onClick={copy}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                <Copy className="h-4 w-4" aria-hidden="true" />
                {copied ? t('correction.copied') : t('correction.copy')}
              </button>
            </div>
          </div>
        )}
      </dialog>
    </>
  );
}
