-- Details an invoice needs for input VAT deduction (§14 Abs. 4 UStG) and for
-- the construction tax rules (§13b UStG, §48 EStG). All nullable: invoices
-- already in the system stay valid and show up as incomplete in the check.

ALTER TABLE public.invoices_clean
  ADD COLUMN IF NOT EXISTS rechnungsnummer VARCHAR(100),
  ADD COLUMN IF NOT EXISTS rechnungsdatum DATE,
  ADD COLUMN IF NOT EXISTS leistungsdatum DATE,
  ADD COLUMN IF NOT EXISTS nettobetrag NUMERIC(12, 2),
  ADD COLUMN IF NOT EXISTS ust_satz NUMERIC(5, 2),
  ADD COLUMN IF NOT EXISTS ust_betrag NUMERIC(12, 2),
  ADD COLUMN IF NOT EXISTS lieferant_ust_id VARCHAR(20),
  ADD COLUMN IF NOT EXISTS lieferant_steuernummer VARCHAR(30),
  ADD COLUMN IF NOT EXISTS lieferant_iban VARCHAR(34),
  ADD COLUMN IF NOT EXISTS reverse_charge_13b BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS freistellung_48b_gueltig_bis DATE;

-- Same supplier + same invoice number = probably paid twice
CREATE INDEX IF NOT EXISTS idx_invoices_supplier_number
  ON public.invoices_clean (rechnungssteller, rechnungsnummer)
  WHERE rechnungsnummer IS NOT NULL;
