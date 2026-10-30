import Link from 'next/link';

/** Impressum and privacy notice must be reachable from every page, logged in or not. */
export default function LegalFooter() {
  return (
    <footer className="relative z-10 border-t border-gray-200/60 py-4 text-center text-xs text-gray-500">
      <nav aria-label="Rechtliches" className="flex justify-center gap-4">
        <Link href="/impressum" className="hover:text-gray-800 underline-offset-2 hover:underline">Impressum</Link>
        <Link href="/datenschutz" className="hover:text-gray-800 underline-offset-2 hover:underline">Datenschutz</Link>
      </nav>
    </footer>
  );
}
