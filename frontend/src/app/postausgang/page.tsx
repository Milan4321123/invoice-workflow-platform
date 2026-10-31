'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { Inbox, Mail, RefreshCw } from 'lucide-react';
import { buildApiUrl } from '@/config/api';
import { authFetch } from '@/lib/authFetch';
import { apiErrorMessage } from '@/lib/apiError';
import { useLanguage } from '@/i18n/LanguageContext';
import { de, type MessageKey } from '@/i18n/messages';

interface OutboxMail { id: string; to?: string; subject?: string; type?: string; sent_at?: string }

/**
 * Demo mode only: the e-mails the platform "sent". The HTML is shown in a
 * sandboxed frame (no scripts); its links open in a new tab, so the approval
 * and Skonto pages can be tried for real.
 */
export default function OutboxPage() {
  const { locale, t } = useLanguage();
  const [mails, setMails] = useState<OutboxMail[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [html, setHtml] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const typeLabel = (type?: string) => {
    const key = `outbox.type.${type}` as MessageKey;
    return key in de ? t(key) : type || '';
  };

  const load = useCallback(async () => {
    setError(null);
    const response = await authFetch(buildApiUrl('/api/demo/outbox'));
    if (!response.ok) {
      setError(await apiErrorMessage(response, t('outbox.empty')));
      setMails([]);
      return;
    }
    const data = await response.json();
    setMails(data.emails);
    if (!selected && data.emails.length) setSelected(data.emails[0].id);
  }, [selected, t]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!selected) return;
    authFetch(buildApiUrl(`/api/demo/outbox/${selected}`))
      .then((r) => (r.ok ? r.text() : ''))
      // Links must leave the sandboxed frame: open them in a new tab
      .then((text) => setHtml(text.replace(/<head>/i, '<head><base target="_blank">')));
  }, [selected]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold text-gray-900">
            <Inbox className="h-6 w-6 text-blue-600" aria-hidden="true" />
            {t('outbox.title')}
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-gray-600">{t('outbox.subtitle')}</p>
        </div>
        <button type="button" onClick={load}
          className="inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50">
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          {t('outbox.refresh')}
        </button>
      </div>

      {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}

      <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <ul className="space-y-2" aria-label={t('outbox.title')}>
          {mails?.length === 0 && <li className="text-sm text-gray-600">{t('outbox.empty')}</li>}
          {mails?.map((mail) => (
            <li key={mail.id}>
              <button type="button" onClick={() => setSelected(mail.id)} aria-current={selected === mail.id ? 'true' : undefined}
                className={`w-full rounded-xl border p-3 text-left text-sm shadow-sm ${selected === mail.id ? 'border-blue-400 bg-blue-50' : 'border-gray-200 bg-white hover:border-blue-200'}`}>
                <span className="flex items-center gap-1.5 text-xs font-medium text-blue-700">
                  <Mail className="h-3.5 w-3.5" aria-hidden="true" />{typeLabel(mail.type)}
                </span>
                <span className="mt-1 block font-medium text-gray-900">{mail.subject}</span>
                <span className="mt-0.5 block text-xs text-gray-600">
                  {t('outbox.to')} {mail.to}
                  {mail.sent_at && ` · ${new Date(mail.sent_at).toLocaleString(locale === 'en' ? 'en-GB' : 'de-DE', { dateStyle: 'short', timeStyle: 'short' })}`}
                </span>
              </button>
            </li>
          ))}
        </ul>

        <div>
          {html ? (
            <>
              <iframe title={t('outbox.preview')} srcDoc={html} sandbox="allow-popups allow-popups-to-escape-sandbox"
                className="h-[75vh] w-full rounded-xl border border-gray-200 bg-white" />
              <p className="mt-2 text-xs text-gray-500">{t('outbox.linkHint')}</p>
            </>
          ) : (
            <p className="rounded-xl border border-dashed border-gray-300 bg-white/60 p-6 text-center text-sm text-gray-600">{t('outbox.select')}</p>
          )}
        </div>
      </div>
    </div>
  );
}
