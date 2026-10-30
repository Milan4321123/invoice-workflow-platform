'use client';

import { Languages } from 'lucide-react';
import { useLanguage } from '@/i18n/LanguageContext';

/** Toggles between German and English. Labelled in the language it switches to. */
export default function LanguageSwitcher({ className = '' }: { className?: string }) {
  const { locale, setLocale, t } = useLanguage();
  const next = locale === 'de' ? 'en' : 'de';

  return (
    <button
      type="button"
      onClick={() => setLocale(next)}
      aria-label={t('app.switchTo')}
      title={t('app.switchTo')}
      className={`inline-flex items-center gap-1.5 rounded-lg px-2 py-2 text-sm font-medium text-gray-700 hover:bg-white/50 ${className}`}
    >
      <Languages className="h-4 w-4" aria-hidden="true" />
      <span lang={next}>{next.toUpperCase()}</span>
    </button>
  );
}
