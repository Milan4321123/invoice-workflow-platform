-- Which e-invoice standard an invoice arrived in, e.g. "XRechnung 3.0 (UBL)" or
-- "ZUGFeRD/Factur-X (EN 16931)". NULL for scanned paper or plain PDF invoices.
ALTER TABLE public.invoices_clean
  ADD COLUMN IF NOT EXISTS e_rechnung_format VARCHAR(60);
