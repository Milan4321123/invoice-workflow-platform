'use client';

import React, { useState } from 'react';
import { AlertTriangle, Loader2, Sparkles } from 'lucide-react';
import { buildApiUrl } from '@/config/api';
import { authFetch } from '@/lib/authFetch';
import { apiErrorMessage } from '@/lib/apiError';
import { useT } from '@/i18n/LanguageContext';
import type { MessageKey } from '@/i18n/messages';

type Confidence = 'high' | 'medium' | 'low';
interface Suggestion { value: unknown; confidence: Confidence; source_text: string; check?: string }
interface ExtractionResult {
  mode: 'live' | 'offline';
  fields: Record<string, Suggestion>;
  warnings: string[];
  suspicious_instructions: string | null;
}

const CONFIDENCE_STYLE: Record<Confidence, string> = {
  high: 'bg-green-100 text-green-800',
  medium: 'bg-amber-100 text-amber-800',
  low: 'bg-red-100 text-red-800',
};

/**
 * Reads a PDF invoice and shows suggested values. Nothing is saved: the user
 * picks values, they go into the form, and the normal save records them.
 */
export default function AiExtractionPanel({ invoiceId, aiMode, onApply }: {
  invoiceId: string;
  aiMode: 'live' | 'offline' | null;
  onApply: (field: string, value: unknown) => void;
}) {
  const t = useT();
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await authFetch(buildApiUrl(`/api/invoices/${invoiceId}/ai-extract`), { method: 'POST' });
      if (!response.ok) throw new Error(await apiErrorMessage(response, t('ai.error')));
      const data: ExtractionResult = await response.json();
      setResult(data);
      // Preselect what the rules didn't flag
      setSelected(new Set(Object.entries(data.fields).filter(([, s]) => s.confidence !== 'low').map(([k]) => k)));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('ai.error'));
    } finally {
      setBusy(false);
    }
  };

  const apply = () => {
    if (!result) return;
    selected.forEach((field) => onApply(field, result.fields[field].value));
    setResult(null);
  };

  return (
    <section aria-label={t('extract.heading')} className="mb-6 rounded-xl border border-purple-200 bg-purple-50/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={run}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-60"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Sparkles className="h-4 w-4" aria-hidden="true" />}
          {busy ? t('extract.running') : aiMode === 'live' ? t('extract.button') : t('extract.buttonOffline')}
        </button>
        {result && (
          <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${result.mode === 'live' ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-700'}`}>
            {result.mode === 'live' ? t('ai.badgeLive') : t('ai.badgeOffline')}
          </span>
        )}
      </div>

      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}

      {result && (
        <div className="mt-4">
          <h3 className="text-sm font-semibold text-gray-900">{t('extract.heading')}</h3>
          <p className="text-xs text-gray-600">{t('extract.hint')}</p>

          {result.suspicious_instructions && (
            <div role="alert" className="mt-3 flex gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              <AlertTriangle className="h-5 w-5 shrink-0" aria-hidden="true" />
              <p>{t('extract.suspicious')} <q lang="de">{result.suspicious_instructions}</q></p>
            </div>
          )}
          {result.warnings.length > 0 && (
            <ul className="mt-3 list-disc pl-5 text-sm text-amber-800">
              {result.warnings.map((w) => <li key={w}>{w}</li>)}
            </ul>
          )}

          {Object.keys(result.fields).length === 0 ? (
            <p className="mt-3 text-sm text-gray-600">{t('extract.none')}</p>
          ) : (
            <ul className="mt-3 divide-y divide-purple-100 rounded-lg bg-white">
              {Object.entries(result.fields).map(([field, s]) => (
                <li key={field} className="flex items-start gap-3 px-3 py-2 text-sm">
                  <input
                    id={`suggest-${field}`}
                    type="checkbox"
                    checked={selected.has(field)}
                    onChange={(e) => {
                      const next = new Set(selected);
                      if (e.target.checked) next.add(field); else next.delete(field);
                      setSelected(next);
                    }}
                    className="mt-1 h-4 w-4 rounded border-gray-300 text-purple-600"
                  />
                  <label htmlFor={`suggest-${field}`} className="min-w-0 flex-1">
                    <span className="font-mono text-xs text-gray-500">{field}</span>{' '}
                    <span className="font-medium text-gray-900">{String(s.value)}</span>{' '}
                    <span className={`rounded px-1.5 py-0.5 text-xs ${CONFIDENCE_STYLE[s.confidence]}`}>
                      {t(`extract.confidence.${s.confidence}` as MessageKey)}
                    </span>
                    {s.check && <span className="ml-1 text-xs text-red-700">({s.check})</span>}
                    {s.source_text && (
                      <span className="block truncate text-xs text-gray-500" title={s.source_text}>
                        {t('extract.readFrom')}: „{s.source_text}“
                      </span>
                    )}
                  </label>
                </li>
              ))}
            </ul>
          )}

          {selected.size > 0 && (
            <button type="button" onClick={apply}
              className="mt-3 rounded-lg border border-purple-300 bg-white px-4 py-2 text-sm font-medium text-purple-800 hover:bg-purple-50">
              {t('extract.applySelected')} ({selected.size})
            </button>
          )}
        </div>
      )}
    </section>
  );
}
