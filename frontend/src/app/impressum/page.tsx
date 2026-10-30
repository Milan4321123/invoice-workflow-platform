import { COMPANY } from '@/config/company';

export const metadata = { title: 'Impressum' };

/** Provider identification under §5 DDG (formerly §5 TMG). */
export default function ImpressumPage() {
  return (
    <article className="mx-auto max-w-2xl px-4 py-12 text-gray-800">
      <h1 className="text-2xl font-semibold text-gray-900">Impressum</h1>

      <section className="mt-8">
        <h2 className="text-base font-semibold">Angaben gemäß § 5 DDG</h2>
        <address className="mt-2 not-italic leading-relaxed">
          {COMPANY.name}<br />
          {COMPANY.street}<br />
          {COMPANY.city}
        </address>
      </section>

      <section className="mt-6">
        <h2 className="text-base font-semibold">Vertreten durch</h2>
        <p className="mt-2">{COMPANY.representative}</p>
      </section>

      <section className="mt-6">
        <h2 className="text-base font-semibold">Kontakt</h2>
        <p className="mt-2">
          Telefon: {COMPANY.phone}<br />
          E-Mail: {COMPANY.email}
        </p>
      </section>

      <section className="mt-6">
        <h2 className="text-base font-semibold">Registereintrag und Umsatzsteuer</h2>
        <p className="mt-2">
          {COMPANY.register}<br />
          Umsatzsteuer-Identifikationsnummer gemäß § 27a UStG: {COMPANY.vatId}
        </p>
      </section>
    </article>
  );
}
