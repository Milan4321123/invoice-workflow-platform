-- Append-only change log for invoices (GoBD Rz. 58 ff.: changes stay traceable).
-- Written by backend/services/audit.py. Each row hashes its content together
-- with the previous row's hash, so editing an old row breaks the chain.

CREATE TABLE IF NOT EXISTS public.invoice_audit_log (
  seq BIGINT PRIMARY KEY,                 -- gapless order of the hash chain
  invoice_id UUID NOT NULL,               -- no foreign key: entries outlive deleted invoices
  action VARCHAR(40) NOT NULL,
  actor VARCHAR(255) NOT NULL,
  changes JSONB NOT NULL DEFAULT '{}'::JSONB,
  recorded_at TEXT NOT NULL,              -- exact string that was hashed
  prev_hash CHAR(64) NOT NULL,
  entry_hash CHAR(64) NOT NULL UNIQUE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoice_audit_log_invoice ON public.invoice_audit_log (invoice_id, seq);

-- Rows can be added, never changed or removed
CREATE OR REPLACE FUNCTION public.reject_audit_log_change()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'invoice_audit_log is append-only (GoBD); % is not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS invoice_audit_log_no_update_delete ON public.invoice_audit_log;
CREATE TRIGGER invoice_audit_log_no_update_delete
  BEFORE UPDATE OR DELETE ON public.invoice_audit_log
  FOR EACH ROW EXECUTE FUNCTION public.reject_audit_log_change();

DROP TRIGGER IF EXISTS invoice_audit_log_no_truncate ON public.invoice_audit_log;
CREATE TRIGGER invoice_audit_log_no_truncate
  BEFORE TRUNCATE ON public.invoice_audit_log
  FOR EACH STATEMENT EXECUTE FUNCTION public.reject_audit_log_change();

ALTER TABLE public.invoice_audit_log ENABLE ROW LEVEL SECURITY;
