'use client';

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { de, en, type MessageKey } from './messages';

export type Locale = 'de' | 'en';

const dictionaries = { de, en } as const;
const STORAGE_KEY = 'locale';

interface LanguageContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey, values?: Record<string, string | number>) => string;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>('de');

  // Saved choice first, otherwise the browser language; German by default
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === 'de' || saved === 'en') {
        setLocaleState(saved);
        return;
      }
    } catch {
      // storage blocked: fall through to the browser language
    }
    if (navigator.language?.toLowerCase().startsWith('en')) setLocaleState('en');
  }, []);

  // Screen readers pick pronunciation from <html lang>
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // the choice just won't be remembered
    }
  }, []);

  const t = useCallback(
    (key: MessageKey, values?: Record<string, string | number>) => {
      const text: string = dictionaries[locale][key] ?? de[key];
      return values ? text.replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? `{${name}}`)) : text;
    },
    [locale],
  );

  return <LanguageContext.Provider value={{ locale, setLocale, t }}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error('useLanguage must be used inside LanguageProvider');
  return context;
}

export const useT = () => useLanguage().t;
