'use client';

import React, { useState } from 'react';
import { History } from 'lucide-react';
import { getApiUrl } from '@/config/api';
import { authFetch } from '@/lib/authFetch';
import { useLanguage } from '@/i18n/LanguageContext';
import { de, type MessageKey } from '@/i18n/messages';

interface AuditEntry {
  seq: number;
  action: string;
  actor: string;
  changes: Record<string, { old: unknown; new: unknown }>;
  recorded_at: string;
}

const formatValue = (value: unknown) =>
  value === null || value === undefined || value === '' ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value);

/**
 * Who changed what and when (GoBD: changes must stay traceable).
 * Loaded when the user opens the section.
 */
export default function AuditHistory({ invoiceId }: { invoiceId: string }) {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [failed, setFailed] = useState(false);
  const { locale, t } = useLanguage();
  const actionLabel = (action: string) => {
    const key = `history.action.${action}` as MessageKey;
    return key in de ? t(key) : action;
  };

  const load = async () => {
    try {
      const response = await authFetch(`${getApiUrl()}/api/invoices/${invoiceId}/audit-log`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setEntries([...data.entries].reverse());
      setFailed(false);
    } catch {
      setFailed(true);
    }
  };

  return (
    <details
      className="mt-8 pt-6 border-t border-gray-200 group"
      onToggle={(e) => {
        if ((e.target as HTMLDetailsElement).open) load();
      }}
    >
      <summary className="flex cursor-pointer items-center gap-2 text-base font-semibold text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded">
        <History className="h-4 w-4 text-gray-500" aria-hidden="true" />
        {t('history.heading')}
      </summary>

      <div className="mt-4">
        {failed && <p className="text-sm text-gray-500">{t('history.failed')}</p>}
        {!failed && entries === null && <p className="text-sm text-gray-500">{t('history.loading')}</p>}
        {entries?.length === 0 && <p className="text-sm text-gray-500">{t('history.empty')}</p>}

        {entries && entries.length > 0 && (
          <ol className="space-y-4">
            {entries.map((entry) => (
              <li key={entry.seq} className="text-sm">
                <p className="text-gray-900">
                  <span className="font-medium">{actionLabel(entry.action)}</span>
                  <span className="text-gray-500">
                    {' '}· {entry.actor} ·{' '}
                    <time dateTime={entry.recorded_at}>
                      {new Date(entry.recorded_at).toLocaleString(locale === 'en' ? 'en-GB' : 'de-DE', { dateStyle: 'medium', timeStyle: 'short' })}
                    </time>
                  </span>
                </p>
                {Object.keys(entry.changes).length > 0 && (
                  <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs text-gray-600">
                    {Object.entries(entry.changes).map(([field, change]) => (
                      <React.Fragment key={field}>
                        <dt className="font-mono">{field}</dt>
                        <dd>
                          <span className="line-through text-gray-400">{formatValue(change.old)}</span>
                          {' → '}
                          <span className="text-gray-800">{formatValue(change.new)}</span>
                        </dd>
                      </React.Fragment>
                    ))}
                  </dl>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
    </details>
  );
}
