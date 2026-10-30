'use client';

import React, { useState } from 'react';
import { Download, ShieldCheck, Trash2 } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { buildApiUrl } from '@/config/api';
import { authFetch } from '@/lib/authFetch';
import { apiErrorMessage } from '@/lib/apiError';

interface ErasureReport {
  geloescht: Record<string, number>;
  aufbewahrt: { kategorie: string; anzahl: number | null; grund: string; aufbewahrt_bis: string | null }[];
}

/**
 * Handles requests from people who want to know what is stored about them
 * or have it erased (Art. 15, 17, 20 DSGVO). Answer within one month.
 */
export default function DatenschutzAnfragenPage() {
  const [email, setEmail] = useState('');
  const [confirmErase, setConfirmErase] = useState(false);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<ErasureReport | null>(null);

  const exportData = async () => {
    setBusy(true);
    try {
      const response = await authFetch(buildApiUrl(`/api/privacy/subject-access?email=${encodeURIComponent(email)}`));
      if (!response.ok) throw new Error(await apiErrorMessage(response, 'Auskunft fehlgeschlagen'));
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = 'dsgvo-auskunft.json';
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Auskunft fehlgeschlagen');
    } finally {
      setBusy(false);
    }
  };

  const erase = async () => {
    setBusy(true);
    try {
      const response = await authFetch(buildApiUrl('/api/privacy/erasure'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, confirm: true }),
      });
      if (!response.ok) throw new Error(await apiErrorMessage(response, 'Löschung fehlgeschlagen'));
      setReport(await response.json());
      setConfirmErase(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Löschung fehlgeschlagen');
    } finally {
      setBusy(false);
    }
  };

  const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="flex items-center gap-2 text-2xl font-semibold text-gray-900">
        <ShieldCheck className="h-6 w-6 text-blue-600" aria-hidden="true" />
        Datenschutz-Anfragen
      </h1>
      <p className="mt-2 text-sm text-gray-600">
        Auskunft (Art. 15, 20 DSGVO) und Löschung (Art. 17 DSGVO) für eine E-Mail-Adresse. Anfragen sind innerhalb
        eines Monats zu beantworten. Jede Bearbeitung wird protokolliert.
      </p>

      <div className="mt-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <label htmlFor="subject-email" className="block text-sm font-medium text-gray-700">
          E-Mail-Adresse der betroffenen Person
        </label>
        <input
          id="subject-email"
          type="email"
          autoComplete="off"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            setReport(null);
          }}
          className="mt-2 w-full rounded-lg border border-gray-300 px-3 py-3 focus:border-blue-500 focus:ring-2 focus:ring-blue-500"
          placeholder="name@firma.de"
        />

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={exportData}
            disabled={!validEmail || busy}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            Auskunft als JSON herunterladen
          </button>
          <button
            type="button"
            onClick={() => setConfirmErase(true)}
            disabled={!validEmail || busy}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-400"
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            Daten löschen
          </button>
        </div>

        {confirmErase && (
          <div role="alertdialog" aria-labelledby="erase-title" className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4">
            <p id="erase-title" className="text-sm font-medium text-red-800">Daten zu {email} löschen?</p>
            <p className="mt-1 text-sm text-red-700">
              Benutzerkonto, E-Mail-Versandprotokoll, Freigabe-Links und Sicherheitsereignisse werden
              pseudonymisiert. Angaben, die zu aufbewahrungspflichtigen Belegen gehören, bleiben bis Fristende erhalten.
            </p>
            <div className="mt-3 flex gap-3">
              <button
                type="button"
                onClick={erase}
                disabled={busy}
                className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
              >
                Endgültig löschen
              </button>
              <button
                type="button"
                onClick={() => setConfirmErase(false)}
                className="rounded-lg px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-white"
              >
                Abbrechen
              </button>
            </div>
          </div>
        )}
      </div>

      {report && (
        <section aria-labelledby="report-title" className="mt-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 id="report-title" className="text-base font-semibold text-gray-900">Ergebnis</h2>
          <h3 className="mt-4 text-sm font-medium text-gray-700">Gelöscht oder pseudonymisiert</h3>
          <ul className="mt-2 space-y-1 text-sm text-gray-700">
            {Object.entries(report.geloescht).map(([category, count]) => (
              <li key={category}>{category}: {count}</li>
            ))}
          </ul>
          <h3 className="mt-6 text-sm font-medium text-gray-700">Aufbewahrt (gesetzliche Pflicht)</h3>
          <ul className="mt-2 space-y-3 text-sm text-gray-700">
            {report.aufbewahrt.map((item) => (
              <li key={item.kategorie}>
                <span className="font-medium">{item.kategorie}</span>
                {item.anzahl !== null && <> ({item.anzahl})</>}
                {item.aufbewahrt_bis && <> bis {new Date(item.aufbewahrt_bis).toLocaleDateString('de-DE')}</>}
                <p className="text-gray-500">{item.grund}</p>
              </li>
            ))}
          </ul>
          <p className="mt-6 text-xs text-gray-500">
            Teilen Sie der Person dieses Ergebnis mit, einschließlich der Gründe für die Aufbewahrung.
          </p>
        </section>
      )}
    </div>
  );
}
