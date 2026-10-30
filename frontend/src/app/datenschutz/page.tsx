import { COMPANY } from '@/config/company';

export const metadata = { title: 'Datenschutzhinweise' };

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="mt-8">
    <h2 className="text-base font-semibold text-gray-900">{title}</h2>
    <div className="mt-2 space-y-2 leading-relaxed">{children}</div>
  </section>
);

/**
 * Information under Art. 13 DSGVO for the people who use the platform:
 * staff in accounts payable, site managers who approve invoices, and
 * suppliers whose details appear on invoices.
 */
export default function DatenschutzPage() {
  return (
    <article lang="de" className="mx-auto max-w-2xl px-4 py-12 text-gray-800">
      <h1 className="text-2xl font-semibold text-gray-900">Datenschutzhinweise</h1>
      <p className="mt-2 text-sm text-gray-500">Für Beschäftigte, freigebende Bauleitungen und Lieferanten</p>

      <Section title="1. Verantwortlicher">
        <address className="not-italic">
          {COMPANY.name}, {COMPANY.street}, {COMPANY.city}<br />
          E-Mail: {COMPANY.email}
        </address>
        <p>Ansprechpartner für Datenschutz: {COMPANY.privacyContact}</p>
      </Section>

      <Section title="2. Welche Daten wir wofür verarbeiten">
        <dl className="space-y-4">
          <div>
            <dt className="font-medium">Rechnungsdaten</dt>
            <dd>
              Angaben auf Eingangsrechnungen, darunter Name, Anschrift, Steuernummer und Bankverbindung von
              Lieferanten, sowie wer eine Rechnung geprüft und freigegeben hat. Zweck: Prüfung, Zahlung und
              gesetzliche Aufbewahrung. Rechtsgrundlage: Art. 6 Abs. 1 lit. b und lit. c DSGVO i. V. m. § 147 AO,
              § 257 HGB.
            </dd>
          </div>
          <div>
            <dt className="font-medium">Benutzerkonto</dt>
            <dd>
              Benutzername, Name, E-Mail-Adresse und ein Passwort-Hash (nie das Passwort selbst). Zweck: Anmeldung
              und Zuordnung von Arbeitsschritten. Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO.
            </dd>
          </div>
          <div>
            <dt className="font-medium">Freigabe per E-Mail-Link</dt>
            <dd>
              E-Mail-Adresse, Zeitpunkt und IP-Adresse beim Aufruf des Links. Zweck: Nachvollziehbarkeit der
              Freigabe und Schutz vor Missbrauch. Rechtsgrundlage: Art. 6 Abs. 1 lit. c DSGVO (Belegfunktion)
              und lit. f (berechtigtes Interesse an der Sicherheit des Freigabeverfahrens).
            </dd>
          </div>
          <div>
            <dt className="font-medium">Änderungsprotokoll</dt>
            <dd>
              Wer wann welche Angabe einer Rechnung geändert hat. Zweck: Unveränderbarkeit und
              Nachvollziehbarkeit nach den GoBD. Rechtsgrundlage: Art. 6 Abs. 1 lit. c DSGVO i. V. m. § 146 AO.
            </dd>
          </div>
        </dl>
      </Section>

      <Section title="3. Speicherdauer">
        <ul className="list-disc pl-5 space-y-1">
          <li>Rechnungen und das zugehörige Änderungsprotokoll: 8 Jahre ab Ende des Eingangsjahres (§ 147 AO).</li>
          <li>IP-Adressen aus Freigabe-Links und Sicherheitsereignissen: 30 Tage.</li>
          <li>Benutzerkonten: bis zur Deaktivierung. Danach werden Name und E-Mail-Adresse entfernt.</li>
          <li>
            In Server-Protokollen werden E-Mail-Adressen und IBANs automatisch unkenntlich gemacht.
          </li>
        </ul>
      </Section>

      <Section title="4. Empfänger und Auftragsverarbeiter">
        <p>
          Wir setzen Dienstleister ein, die Daten nur nach unserer Weisung verarbeiten (Art. 28 DSGVO):
          Datenbank und Dateiablage (Supabase, Rechenzentrum in der EU), Hosting der Anwendung sowie einen
          E-Mail-Versanddienst für Freigabe- und Skonto-Benachrichtigungen. Sitzt ein Dienstleister außerhalb der
          EU, stützt sich die Übermittlung auf einen Angemessenheitsbeschluss (z. B. EU-US Data Privacy Framework)
          oder Standardvertragsklauseln (Art. 45, 46 DSGVO). Die konkreten Anbieter nennt das Verzeichnis von
          Verarbeitungstätigkeiten des Unternehmens.
        </p>
      </Section>

      <Section title="5. Cookies, Tracking und externe Inhalte">
        <p>
          Die Anwendung setzt keine Analyse- oder Werbe-Cookies und bindet keine Tracking-Dienste ein. Für die
          Anmeldung wird ein Sitzungstoken im lokalen Speicher des Browsers abgelegt. Das ist für den Dienst
          unbedingt erforderlich und braucht keine Einwilligung (§ 25 Abs. 2 Nr. 2 TDDDG). Schriftarten und die
          PDF-Anzeige werden von unserem eigenen Server geladen, nicht von Drittanbietern.
        </p>
      </Section>

      <Section title="6. Keine automatisierten Entscheidungen">
        <p>
          Die Pflichtangabenprüfung zeigt Hinweise an. Ob eine Rechnung freigegeben oder bezahlt wird,
          entscheiden immer Menschen (Art. 22 DSGVO).
        </p>
      </Section>

      <Section title="7. Ihre Rechte">
        <p>
          Sie haben das Recht auf Auskunft (Art. 15), Berichtigung (Art. 16), Löschung (Art. 17), Einschränkung
          der Verarbeitung (Art. 18), Datenübertragbarkeit (Art. 20) und Widerspruch (Art. 21). Daten, die wir
          gesetzlich aufbewahren müssen, löschen wir erst nach Ablauf der Frist; bis dahin verwenden wir sie nur
          noch zu diesem Zweck. Wenden Sie sich dazu an {COMPANY.privacyContact}.
        </p>
        <p>
          Sie können sich außerdem bei einer Datenschutz-Aufsichtsbehörde beschweren (Art. 77 DSGVO), zum
          Beispiel bei der für den Sitz des Unternehmens zuständigen Landesbehörde.
        </p>
      </Section>
    </article>
  );
}
