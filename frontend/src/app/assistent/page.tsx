'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Bot, Check, ExternalLink, Loader2, RotateCcw, Send, Sparkles, Wrench, X } from 'lucide-react';
import { buildApiUrl } from '@/config/api';
import { authFetch } from '@/lib/authFetch';
import { apiErrorMessage } from '@/lib/apiError';
import { useT } from '@/i18n/LanguageContext';
import type { MessageKey } from '@/i18n/messages';

interface Citation { citation: string; quote: string; source: string }
interface TraceStep { tool: string; ok: boolean }
interface Proposal { invoice_id: string; file_name: string; field: string; old_value: unknown; new_value: string; reason: string }
interface AgentAnswer {
  mode: 'live' | 'offline';
  answer: string;
  citations: Citation[];
  trace: TraceStep[];
  proposals: Proposal[];
  history: unknown[];
  usage: { input_tokens: number; output_tokens: number; cost_usd: number } | null;
}
type Turn = { role: 'user'; text: string } | { role: 'assistant'; data: AgentAnswer };

const NUMBER_FIELDS = new Set(['nettobetrag', 'ust_satz', 'ust_betrag', 'rechnungsbetrag', 'skonto_prozent']);
const EXAMPLES: MessageKey[] = ['ai.example1', 'ai.example2', 'ai.example3', 'ai.example4'];

function ProposalCard({ proposal }: { proposal: Proposal }) {
  const t = useT();
  const [state, setState] = useState<'open' | 'applying' | 'applied' | 'rejected'>('open');
  const [error, setError] = useState<string | null>(null);

  // Applying goes through the normal update route: GoBD lock and audit log apply,
  // and the change is recorded under the user who clicked, not the AI.
  const apply = async () => {
    setState('applying');
    setError(null);
    const value = NUMBER_FIELDS.has(proposal.field) ? Number(proposal.new_value) : proposal.new_value;
    const response = await authFetch(buildApiUrl(`/api/invoices/${proposal.invoice_id}`), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [proposal.field]: value }),
    });
    if (response.ok) {
      setState('applied');
    } else {
      setError(await apiErrorMessage(response, t('ai.error')));
      setState('open');
    }
  };

  return (
    <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
      <p className="font-medium text-amber-900">{t('ai.proposal')}: {proposal.file_name}</p>
      <p className="mt-1 text-amber-900">
        <span className="font-mono">{proposal.field}</span>:{' '}
        <span className="line-through text-amber-700">{String(proposal.old_value ?? '—')}</span> → <strong>{proposal.new_value}</strong>
      </p>
      <p className="mt-1 text-amber-800">{proposal.reason}</p>
      {error && <p role="alert" className="mt-2 text-red-700">{error}</p>}
      <div className="mt-2 flex gap-2">
        {state === 'applied' && <span className="inline-flex items-center gap-1 text-green-700"><Check className="h-4 w-4" aria-hidden="true" />{t('ai.applied')}</span>}
        {state === 'rejected' && <span className="text-gray-600">{t('ai.rejected')}</span>}
        {(state === 'open' || state === 'applying') && (
          <>
            <button type="button" onClick={apply} disabled={state === 'applying'}
              className="rounded-md bg-amber-600 px-3 py-1 font-medium text-white hover:bg-amber-700 disabled:opacity-60">
              {t('ai.apply')}
            </button>
            <button type="button" onClick={() => setState('rejected')}
              className="rounded-md px-3 py-1 font-medium text-amber-900 hover:bg-amber-100">
              {t('ai.reject')}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function AssistantMessage({ data }: { data: AgentAnswer }) {
  const t = useT();
  return (
    <div className="flex gap-3">
      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-r from-purple-600 to-blue-600">
        <Bot className="h-4 w-4 text-white" aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1 rounded-2xl rounded-tl-sm bg-white p-4 shadow-sm">
        <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${data.mode === 'live' ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-700'}`}>
          {data.mode === 'live' ? t('ai.badgeLive') : t('ai.badgeOffline')}
        </span>
        <p className="mt-2 whitespace-pre-line text-gray-900">{data.answer}</p>

        {data.trace.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-gray-600">
            <Wrench className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="sr-only">{t('ai.toolsUsed')}:</span>
            {data.trace.map((step, i) => (
              <span key={i} className={`rounded px-1.5 py-0.5 font-mono ${step.ok ? 'bg-gray-100' : 'bg-red-50 text-red-700'}`}>{step.tool}</span>
            ))}
          </div>
        )}

        {data.citations.length > 0 && (
          <details className="mt-3 text-sm">
            <summary className="cursor-pointer font-medium text-gray-700">{t('ai.sources')} ({data.citations.length})</summary>
            <ul className="mt-2 space-y-2">
              {data.citations.map((c, i) => (
                <li key={i} className="border-l-2 border-purple-200 pl-3">
                  <p className="font-medium text-gray-800">
                    {c.citation}{' '}
                    {c.source.startsWith('http') && (
                      <a href={c.source} target="_blank" rel="noreferrer" aria-label={`${c.citation} – gesetze-im-internet.de`}
                        className="inline-flex items-center text-blue-700 hover:underline">
                        <ExternalLink className="h-3 w-3" aria-hidden="true" />
                      </a>
                    )}
                  </p>
                  <blockquote lang="de" className="text-gray-600">„{c.quote}“</blockquote>
                </li>
              ))}
            </ul>
          </details>
        )}

        {data.proposals.map((proposal, i) => <ProposalCard key={i} proposal={proposal} />)}

        {data.usage && (
          <p className="mt-3 text-xs text-gray-500">
            {t('ai.usage', { tokens: data.usage.input_tokens + data.usage.output_tokens, cost: data.usage.cost_usd.toFixed(4) })}
          </p>
        )}
      </div>
    </div>
  );
}

export default function AssistantPage() {
  const t = useT();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [history, setHistory] = useState<unknown[]>([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<'live' | 'offline' | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    authFetch(buildApiUrl('/api/ai/status'))
      .then((r) => (r.ok ? r.json() : null))
      .then((status) => status && setMode(status.mode))
      .catch(() => setMode(null));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns, busy]);

  const ask = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setTurns((prev) => [...prev, { role: 'user', text: trimmed }]);
    setQuestion('');
    setBusy(true);
    setError(null);
    try {
      const response = await authFetch(buildApiUrl('/api/ai/agent'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // The history goes back unchanged; the server only ever appends to it
        body: JSON.stringify({ question: trimmed, history }),
      });
      if (!response.ok) throw new Error(await apiErrorMessage(response, t('ai.error')));
      const data: AgentAnswer = await response.json();
      setHistory(data.history);
      setTurns((prev) => [...prev, { role: 'assistant', data }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('ai.error'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-3xl flex-col px-4 py-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold text-gray-900">
            <Sparkles className="h-6 w-6 text-purple-600" aria-hidden="true" />
            {t('ai.title')}
          </h1>
          <p className="mt-1 text-sm text-gray-600">{t('ai.subtitle')}</p>
        </div>
        {turns.length > 0 && (
          <button type="button" onClick={() => { setTurns([]); setHistory([]); }}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-gray-700 hover:bg-white/60">
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            {t('ai.newChat')}
          </button>
        )}
      </div>

      {mode && (
        <p role="note" className={`mt-4 rounded-lg border px-4 py-3 text-sm ${mode === 'live' ? 'border-purple-200 bg-purple-50 text-purple-900' : 'border-gray-200 bg-white/70 text-gray-700'}`}>
          {mode === 'live' ? t('ai.disclosureLive') : t('ai.disclosureOffline')}
        </p>
      )}

      <div className="mt-6 space-y-5" aria-live="polite">
        {turns.length === 0 && (
          <div>
            <p className="text-sm font-medium text-gray-700">{t('ai.examples')}</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {EXAMPLES.map((key) => (
                <button key={key} type="button" onClick={() => ask(t(key))}
                  className="rounded-xl border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-800 shadow-sm hover:border-purple-300">
                  {t(key)}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((turn, i) =>
          turn.role === 'user' ? (
            <div key={i} className="flex justify-end">
              <p className="max-w-[85%] rounded-2xl rounded-tr-sm bg-gradient-to-r from-purple-600 to-blue-600 px-4 py-2 text-white">{turn.text}</p>
            </div>
          ) : (
            <AssistantMessage key={i} data={turn.data} />
          ),
        )}

        {busy && (
          <p className="flex items-center gap-2 text-sm text-gray-600">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            {t('ai.thinking')}
          </p>
        )}
        {error && (
          <p role="alert" className="flex items-center gap-2 text-sm text-red-700">
            <X className="h-4 w-4" aria-hidden="true" />
            {error}
          </p>
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); ask(question); }}
        className="sticky bottom-4 mt-6 flex gap-2 rounded-2xl border border-gray-200 bg-white p-2 shadow-lg"
      >
        <label htmlFor="assistant-question" className="sr-only">{t('ai.placeholder')}</label>
        <input
          id="assistant-question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t('ai.placeholder')}
          autoComplete="off"
          className="min-w-0 flex-1 rounded-xl px-3 py-2 focus:outline-none"
        />
        <button type="submit" disabled={busy || question.trim().length < 2}
          className="inline-flex items-center gap-1.5 rounded-xl bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50">
          <Send className="h-4 w-4" aria-hidden="true" />
          {t('ai.send')}
        </button>
      </form>
    </div>
  );
}
