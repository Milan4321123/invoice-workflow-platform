'use client';

import React from 'react';
import { Calculator } from 'lucide-react';
import type { GermanInvoiceFields } from '../CleanInvoiceForm';

interface TaxDetailsSectionProps {
  fields: GermanInvoiceFields;
  onFieldChange: (fieldName: string, value: any) => void;
}

const inputClass =
  'w-full px-3 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500';
const labelClass = 'block text-sm font-medium text-gray-700 mb-2';

const parseAmount = (value: string) => (value === '' ? '' : parseFloat(value));

/**
 * The invoice details §14 Abs. 4 UStG requires for input VAT deduction, plus
 * the construction-specific §13b UStG and §48b EStG fields.
 */
export default function TaxDetailsSection({ fields, onFieldChange }: TaxDetailsSectionProps) {
  const net = typeof fields.nettobetrag === 'number' ? fields.nettobetrag : undefined;
  const rate = fields.reverse_charge_13b ? 0 : typeof fields.ust_satz === 'number' ? fields.ust_satz : undefined;
  const canCalculate = net !== undefined && rate !== undefined;

  // Fill VAT and gross from net and rate; most invoices state those two clearly.
  const calculateFromNet = () => {
    if (!canCalculate) return;
    const vat = Math.round(net * rate) / 100;
    onFieldChange('ust_betrag', vat);
    onFieldChange('rechnungsbetrag', Math.round((net + vat) * 100) / 100);
  };

  return (
    <section aria-labelledby="tax-details-heading" className="mt-8 pt-6 border-t border-gray-200">
      <h3 id="tax-details-heading" className="text-base font-semibold text-gray-900">
        Steuerangaben
      </h3>
      <p className="text-sm text-gray-500 mb-5">
        Pflichtangaben für den Vorsteuerabzug nach §14 Abs. 4 UStG.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <label htmlFor="rechnungsnummer" className={labelClass}>Rechnungsnummer</label>
          <input
            id="rechnungsnummer"
            type="text"
            value={fields.rechnungsnummer || ''}
            onChange={(e) => onFieldChange('rechnungsnummer', e.target.value)}
            className={inputClass}
            placeholder="z. B. RE-2026-0815"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="rechnungsdatum" className={labelClass}>Rechnungsdatum</label>
            <input
              id="rechnungsdatum"
              type="date"
              value={fields.rechnungsdatum || ''}
              onChange={(e) => onFieldChange('rechnungsdatum', e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="leistungsdatum" className={labelClass}>Leistungsdatum</label>
            <input
              id="leistungsdatum"
              type="date"
              value={fields.leistungsdatum || ''}
              onChange={(e) => onFieldChange('leistungsdatum', e.target.value)}
              className={inputClass}
            />
          </div>
        </div>

        <div>
          <label htmlFor="nettobetrag" className={labelClass}>Nettobetrag</label>
          <div className="relative">
            <span aria-hidden="true" className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">€</span>
            <input
              id="nettobetrag"
              type="number"
              step="0.01"
              inputMode="decimal"
              value={fields.nettobetrag ?? ''}
              onChange={(e) => onFieldChange('nettobetrag', parseAmount(e.target.value))}
              className={`${inputClass} pl-8`}
              placeholder="0.00"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="ust_satz" className={labelClass}>USt-Satz</label>
            <select
              id="ust_satz"
              value={fields.reverse_charge_13b ? '0' : fields.ust_satz ?? ''}
              disabled={fields.reverse_charge_13b}
              onChange={(e) => onFieldChange('ust_satz', e.target.value === '' ? '' : Number(e.target.value))}
              className={`${inputClass} disabled:bg-gray-100`}
            >
              <option value="">Auswählen…</option>
              <option value="19">19 %</option>
              <option value="7">7 %</option>
              <option value="0">0 %</option>
            </select>
          </div>
          <div>
            <label htmlFor="ust_betrag" className={labelClass}>USt-Betrag</label>
            <div className="relative">
              <span aria-hidden="true" className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">€</span>
              <input
                id="ust_betrag"
                type="number"
                step="0.01"
                inputMode="decimal"
                value={fields.ust_betrag ?? ''}
                onChange={(e) => onFieldChange('ust_betrag', parseAmount(e.target.value))}
                className={`${inputClass} pl-8`}
                placeholder="0.00"
              />
            </div>
          </div>
        </div>

        <div className="lg:col-span-2">
          <button
            type="button"
            onClick={calculateFromNet}
            disabled={!canCalculate}
            className="inline-flex items-center gap-2 text-sm font-medium text-blue-700 hover:text-blue-800 disabled:text-gray-400 disabled:cursor-not-allowed"
          >
            <Calculator className="h-4 w-4" aria-hidden="true" />
            USt-Betrag und Rechnungsbetrag aus Netto berechnen
          </button>
        </div>

        <div>
          <label htmlFor="lieferant_ust_id" className={labelClass}>USt-IdNr. des Lieferanten</label>
          <input
            id="lieferant_ust_id"
            type="text"
            autoComplete="off"
            value={fields.lieferant_ust_id || ''}
            onChange={(e) => onFieldChange('lieferant_ust_id', e.target.value.toUpperCase())}
            className={`${inputClass} font-mono`}
            placeholder="DE123456789"
          />
        </div>

        <div>
          <label htmlFor="lieferant_steuernummer" className={labelClass}>
            Steuernummer <span className="font-normal text-gray-500">(falls keine USt-IdNr.)</span>
          </label>
          <input
            id="lieferant_steuernummer"
            type="text"
            autoComplete="off"
            value={fields.lieferant_steuernummer || ''}
            onChange={(e) => onFieldChange('lieferant_steuernummer', e.target.value)}
            className={`${inputClass} font-mono`}
            placeholder="12/345/67890"
          />
        </div>

        <div className="lg:col-span-2">
          <label htmlFor="lieferant_iban" className={labelClass}>IBAN des Lieferanten</label>
          <input
            id="lieferant_iban"
            type="text"
            autoComplete="off"
            value={fields.lieferant_iban || ''}
            onChange={(e) => onFieldChange('lieferant_iban', e.target.value.toUpperCase())}
            className={`${inputClass} font-mono`}
            placeholder="DE89 3704 0044 0532 0130 00"
          />
        </div>

        <div className="lg:col-span-2 flex items-start gap-3 p-4 bg-gray-50 rounded-lg">
          <input
            id="reverse_charge_13b"
            type="checkbox"
            checked={fields.reverse_charge_13b || false}
            onChange={(e) => {
              onFieldChange('reverse_charge_13b', e.target.checked);
              if (e.target.checked) onFieldChange('ust_satz', 0);
            }}
            aria-describedby="reverse_charge_13b_hint"
            className="mt-0.5 h-5 w-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
          />
          <div>
            <label htmlFor="reverse_charge_13b" className="text-sm font-medium text-gray-700">
              Steuerschuldnerschaft des Leistungsempfängers (§13b UStG)
            </label>
            <p id="reverse_charge_13b_hint" className="text-xs text-gray-500 mt-1">
              Bei Bauleistungen an Bauunternehmen: Der Lieferant weist keine USt aus, wir melden sie selbst an.
            </p>
          </div>
        </div>

        <div className="lg:col-span-2">
          <label htmlFor="freistellung_48b_gueltig_bis" className={labelClass}>
            Freistellungsbescheinigung (§48b EStG) gültig bis
          </label>
          <input
            id="freistellung_48b_gueltig_bis"
            type="date"
            value={fields.freistellung_48b_gueltig_bis || ''}
            onChange={(e) => onFieldChange('freistellung_48b_gueltig_bis', e.target.value)}
            aria-describedby="freistellung_hint"
            className={inputClass}
          />
          <p id="freistellung_hint" className="text-xs text-gray-500 mt-1">
            Ohne gültige Bescheinigung sind bei Bauleistungen 15 % Bauabzugsteuer einzubehalten.
          </p>
        </div>
      </div>
    </section>
  );
}
