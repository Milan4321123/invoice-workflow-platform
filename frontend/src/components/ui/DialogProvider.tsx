'use client';

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { AlertTriangle, HelpCircle, Mail } from 'lucide-react';
import { useT } from '@/i18n/LanguageContext';

/**
 * In-app replacement for window.confirm / window.prompt: same promise-based
 * flow, but in the product's design, with the native <dialog> element for
 * focus handling, Escape and screen readers.
 *
 *   const dialog = useDialog();
 *   if (!(await dialog.confirm({ title: 'Löschen?', tone: 'danger' }))) return;
 *   const email = await dialog.prompt({ title: 'An Bauleiter senden', inputType: 'email' });
 */

type Tone = 'default' | 'danger';

interface ConfirmOptions {
  title: string;
  message?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: Tone;
}

interface PromptOptions extends ConfirmOptions {
  label: string;
  inputType?: 'text' | 'email';
  placeholder?: string;
  defaultValue?: string;
  /** Return an error message to block submitting, or null if the value is fine */
  validate?: (value: string) => string | null;
}

type Request =
  | { kind: 'confirm'; options: ConfirmOptions; resolve: (ok: boolean) => void }
  | { kind: 'prompt'; options: PromptOptions; resolve: (value: string | null) => void };

interface DialogApi {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  prompt: (options: PromptOptions) => Promise<string | null>;
}

const DialogContext = createContext<DialogApi | null>(null);

export const isEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());

export function DialogProvider({ children }: { children: React.ReactNode }) {
  const t = useT();
  const [request, setRequest] = useState<Request | null>(null);
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const confirm = useCallback((options: ConfirmOptions) =>
    new Promise<boolean>((resolve) => setRequest({ kind: 'confirm', options, resolve })), []);
  const prompt = useCallback((options: PromptOptions) =>
    new Promise<string | null>((resolve) => {
      setValue(options.defaultValue ?? '');
      setRequest({ kind: 'prompt', options, resolve });
    }), []);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (request && !dialog.open) {
      setError(null);
      dialog.showModal();
      if (request.kind === 'prompt') setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [request]);

  const finish = (result: boolean | string | null) => {
    if (!request) return;
    if (request.kind === 'confirm') request.resolve(Boolean(result));
    else request.resolve(typeof result === 'string' ? result : null);
    setRequest(null);
    dialogRef.current?.close();
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (request?.kind === 'prompt') {
      const problem = request.options.validate?.(value) ?? null;
      if (problem) {
        setError(problem);
        inputRef.current?.focus();
        return;
      }
      finish(value.trim());
    } else {
      finish(true);
    }
  };

  const options = request?.options;
  const danger = options?.tone === 'danger';
  const Icon = request?.kind === 'prompt' ? Mail : danger ? AlertTriangle : HelpCircle;

  return (
    <DialogContext.Provider value={{ confirm, prompt }}>
      {children}
      <dialog
        ref={dialogRef}
        aria-labelledby="app-dialog-title"
        aria-describedby={options?.message ? 'app-dialog-message' : undefined}
        onCancel={(e) => { e.preventDefault(); finish(request?.kind === 'prompt' ? null : false); }}
        className="w-[min(28rem,calc(100vw-2rem))] rounded-2xl p-0 shadow-2xl backdrop:bg-gray-900/40 backdrop:backdrop-blur-[2px]"
      >
        {options && (
          <form onSubmit={submit} noValidate className="p-6">
            <div className="flex gap-4">
              <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${danger ? 'bg-red-100 text-red-600' : 'bg-blue-100 text-blue-600'}`}>
                <Icon className="h-5 w-5" aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <h2 id="app-dialog-title" className="text-base font-semibold text-gray-900">{options.title}</h2>
                {options.message && (
                  <div id="app-dialog-message" className="mt-1.5 text-sm leading-relaxed text-gray-600">{options.message}</div>
                )}
                {request?.kind === 'prompt' && (
                  <div className="mt-4">
                    <label htmlFor="app-dialog-input" className="block text-sm font-medium text-gray-700">
                      {request.options.label}
                    </label>
                    <input
                      ref={inputRef}
                      id="app-dialog-input"
                      type={request.options.inputType ?? 'text'}
                      value={value}
                      onChange={(e) => { setValue(e.target.value); setError(null); }}
                      placeholder={request.options.placeholder}
                      autoComplete={request.options.inputType === 'email' ? 'email' : 'off'}
                      aria-invalid={Boolean(error)}
                      aria-describedby={error ? 'app-dialog-error' : undefined}
                      className={`mt-1.5 w-full rounded-lg border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ${error ? 'border-red-400 focus:ring-red-500' : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500'}`}
                    />
                    {error && <p id="app-dialog-error" role="alert" className="mt-1.5 text-sm text-red-600">{error}</p>}
                  </div>
                )}
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button type="button" onClick={() => finish(request?.kind === 'prompt' ? null : false)}
                className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100">
                {options.cancelLabel ?? t('dialog.cancel')}
              </button>
              <button type="submit" autoFocus={request?.kind === 'confirm'}
                className={`rounded-lg px-4 py-2 text-sm font-semibold text-white shadow-sm ${danger ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'}`}>
                {options.confirmLabel ?? t('dialog.ok')}
              </button>
            </div>
          </form>
        )}
      </dialog>
    </DialogContext.Provider>
  );
}

export function useDialog(): DialogApi {
  const context = useContext(DialogContext);
  if (!context) throw new Error('useDialog must be used inside DialogProvider');
  return context;
}
