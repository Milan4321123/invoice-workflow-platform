'use client';

import Link from 'next/link';
import { useT } from '@/i18n/LanguageContext';

/** Impressum and privacy notice must be reachable from every page, logged in or not. */
export default function LegalFooter() {
  const t = useT();
  return (
    <footer className="relative z-10 border-t border-gray-200/60 py-4 text-center text-xs text-gray-500">
      <nav aria-label={t('footer.label')} className="flex justify-center gap-4">
        <Link href="/impressum" className="hover:text-gray-800 underline-offset-2 hover:underline">{t('footer.imprint')}</Link>
        <Link href="/datenschutz" className="hover:text-gray-800 underline-offset-2 hover:underline">{t('footer.privacy')}</Link>
      </nav>
    </footer>
  );
}
