-- =====================================================================
-- COMPLETE SUPABASE SETUP SQL FOR OCR INVOICE PROCESSOR
-- Run this entire script in your NEW company Supabase SQL Editor
-- =====================================================================

-- 1. CREATE TRIGGER FUNCTION (needed for auto-updating timestamps)
-- =====================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';

-- =====================================================================
-- 2. USERS TABLE (Authentication)
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.users (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  username VARCHAR(50) NOT NULL UNIQUE,
  hashed_password TEXT NOT NULL,
  email VARCHAR(255),
  full_name VARCHAR(255),
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  CONSTRAINT users_pkey PRIMARY KEY (id),
  CONSTRAINT users_username_key UNIQUE (username)
) TABLESPACE pg_default;

-- Users table indexes
CREATE INDEX IF NOT EXISTS idx_users_username ON public.users USING btree (username) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users USING btree (email) TABLESPACE pg_default;

-- Users table trigger
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================================
-- 3. MAIN INVOICES TABLE (Core invoice data)
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.invoices_clean (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  file_name VARCHAR(255) NOT NULL,
  file_path VARCHAR(500),
  file_size INTEGER,
  mime_type VARCHAR(100),
  rechnungsempfaenger VARCHAR(255),
  rechnungssteller VARCHAR(255),
  projekt VARCHAR(255),
  gewerk VARCHAR(255),
  weiter_berechnen_an VARCHAR(255),
  rechnungsbetrag NUMERIC(10, 2),
  kfw_anrechenbare_kosten BOOLEAN DEFAULT false,
  rechnungseingang DATE,
  faelligkeit DATE,
  skonto_datum DATE,
  skonto_prozent NUMERIC(5, 2),
  rechnungsart VARCHAR(100),
  rechnungspruefung VARCHAR(255),
  status VARCHAR(50) DEFAULT 'pending'::VARCHAR,
  ocr_status VARCHAR(50) DEFAULT 'pending'::VARCHAR,
  ocr_text TEXT,
  raw_ocr_data JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  review_status TEXT,
  reviewed_by TEXT,
  reviewed_at TIMESTAMP WITH TIME ZONE,
  review_notes TEXT,
  editor_email VARCHAR(255),
  editor_name VARCHAR(255),
  edit_completed_at TIMESTAMP WITH TIME ZONE,
  edit_bericht_sent_at TIMESTAMP WITH TIME ZONE,
  bauleiter_email VARCHAR(255),
  bauleiter_review_sent_at TIMESTAMP WITH TIME ZONE,
  approval_status VARCHAR(50) DEFAULT 'pending'::VARCHAR,
  approved_at TIMESTAMP WITH TIME ZONE,
  approval_method VARCHAR(50),
  change_summary JSONB,
  email_logs JSONB,
  skonto_reminder_sent BOOLEAN DEFAULT false,
  skonto_reminder_sent_at TIMESTAMP WITH TIME ZONE,
  skonto_decision VARCHAR(20) DEFAULT 'pending'::VARCHAR,
  actual_skonto_savings NUMERIC(10, 2),
  -- §14 UStG / §13b UStG / §48 EStG (see database/migrations/004_invoice_tax_fields.sql)
  rechnungsnummer VARCHAR(100),
  rechnungsdatum DATE,
  leistungsdatum DATE,
  nettobetrag NUMERIC(12, 2),
  ust_satz NUMERIC(5, 2),
  ust_betrag NUMERIC(12, 2),
  lieferant_ust_id VARCHAR(20),
  lieferant_steuernummer VARCHAR(30),
  lieferant_iban VARCHAR(34),
  reverse_charge_13b BOOLEAN NOT NULL DEFAULT false,
  freistellung_48b_gueltig_bis DATE,
  e_rechnung_format VARCHAR(60), -- see database/migrations/005_e_rechnung_format.sql
  CONSTRAINT invoices_clean_pkey PRIMARY KEY (id),
  CONSTRAINT check_approval_status CHECK (
    (approval_status)::text = ANY (
      ARRAY[
        'pending'::text,
        'approved'::text,
        'rejected'::text
      ]
    )
  ),
  CONSTRAINT check_review_status CHECK (
    review_status = ANY (
      ARRAY[
        'pending'::text,
        'under_review'::text,
        'completed_review'::text,
        'needs_attention'::text
      ]
    )
  ),
  CONSTRAINT check_skonto_decision CHECK (
    (skonto_decision)::text = ANY (
      (
        ARRAY[
          'pending'::VARCHAR,
          'taken'::VARCHAR,
          'missed'::VARCHAR,
          'not_applicable'::VARCHAR
        ]
      )::text[]
    )
  ),
  CONSTRAINT check_status CHECK (
    (status)::text = ANY (
      ARRAY[
        'pending'::text,
        'uploaded'::text,
        'edited'::text,
        'pending_email'::text,
        'edit_completed'::text,
        'in_review_by_bauleiter'::text,
        'approved_by_bauleiter'::text,
        'rejected_by_bauleiter'::text,
        'completed'::text,
        'error'::text
      ]
    )
  )
) TABLESPACE pg_default;

-- Invoices table indexes
CREATE INDEX IF NOT EXISTS idx_invoices_status ON public.invoices_clean USING btree (status) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_invoices_approval_status ON public.invoices_clean USING btree (approval_status) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_skonto_reminders ON public.invoices_clean USING btree (skonto_datum, skonto_reminder_sent) TABLESPACE pg_default
WHERE (skonto_datum IS NOT NULL);
CREATE INDEX IF NOT EXISTS idx_invoices_supplier_number ON public.invoices_clean USING btree (rechnungssteller, rechnungsnummer) TABLESPACE pg_default
WHERE (rechnungsnummer IS NOT NULL);

-- =====================================================================
-- 4. APPROVAL TOKENS TABLE (Email link security)
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.approval_tokens (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  token_hash VARCHAR(255) NOT NULL,
  invoice_id UUID NOT NULL,
  action VARCHAR(20) NOT NULL,
  user_email VARCHAR(255) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
  used_at TIMESTAMP WITH TIME ZONE,
  used_by_ip VARCHAR(45),
  is_revoked BOOLEAN DEFAULT false,
  nonce VARCHAR(255) NOT NULL,
  CONSTRAINT approval_tokens_pkey PRIMARY KEY (id),
  CONSTRAINT approval_tokens_token_hash_key UNIQUE (token_hash),
  CONSTRAINT approval_tokens_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES invoices_clean (id) ON DELETE CASCADE
) TABLESPACE pg_default;

-- Approval tokens indexes
CREATE INDEX IF NOT EXISTS idx_approval_tokens_invoice_id ON public.approval_tokens USING btree (invoice_id) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_approval_tokens_expires_at ON public.approval_tokens USING btree (expires_at) TABLESPACE pg_default;

-- =====================================================================
-- 5. EMAIL AUDIT LOG TABLE (Email tracking)
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.email_audit_log (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  invoice_id UUID NOT NULL,
  email_type VARCHAR(50) NOT NULL,
  recipient_email VARCHAR(255) NOT NULL,
  subject TEXT NOT NULL,
  sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  send_success BOOLEAN NOT NULL,
  provider_message_id VARCHAR(255),
  provider_response JSONB,
  template_used VARCHAR(100),
  email_size_bytes INTEGER,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  CONSTRAINT email_audit_log_pkey PRIMARY KEY (id),
  CONSTRAINT email_audit_log_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES invoices_clean (id) ON DELETE CASCADE
) TABLESPACE pg_default;

-- Email audit log indexes
CREATE INDEX IF NOT EXISTS idx_email_audit_invoice_id ON public.email_audit_log USING btree (invoice_id) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_email_audit_sent_at ON public.email_audit_log USING btree (sent_at) TABLESPACE pg_default;

-- =====================================================================
-- 6. DROPDOWN OPTIONS TABLE (UI dropdowns)
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.dropdown_options (
  id BIGSERIAL NOT NULL,
  field_name TEXT NOT NULL,
  value TEXT NOT NULL,
  label TEXT NOT NULL,
  is_default BOOLEAN DEFAULT false,
  sort_order INTEGER DEFAULT 1,
  is_active BOOLEAN DEFAULT true,
  metadata JSONB DEFAULT '{}'::JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  CONSTRAINT dropdown_options_pkey PRIMARY KEY (id),
  CONSTRAINT dropdown_options_field_name_value_key UNIQUE (field_name, value)
) TABLESPACE pg_default;

-- Dropdown options indexes
CREATE INDEX IF NOT EXISTS dropdown_options_field_name_idx ON public.dropdown_options USING btree (field_name) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS dropdown_options_is_active_idx ON public.dropdown_options USING btree (is_active) TABLESPACE pg_default;

-- =====================================================================
-- 7. GEWERK LIST TABLE (German construction trades)
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.gewerk_list (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  code VARCHAR(10) NOT NULL,
  name VARCHAR(200) NOT NULL,
  parent_code VARCHAR(10),
  sort_order INTEGER DEFAULT 0,
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  CONSTRAINT gewerk_list_pkey PRIMARY KEY (id),
  CONSTRAINT gewerk_list_code_key UNIQUE (code)
) TABLESPACE pg_default;

-- =====================================================================
-- 8. SECURITY EVENTS TABLE (Audit trail for approval links)
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.security_events (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  event_type VARCHAR(100) NOT NULL,
  ip_address VARCHAR(45),
  user_email VARCHAR(255),
  invoice_id UUID,
  event_data JSONB,
  risk_level VARCHAR(20) DEFAULT 'low',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  CONSTRAINT security_events_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_security_events_invoice_id ON public.security_events USING btree (invoice_id) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_security_events_created_at ON public.security_events USING btree (created_at) TABLESPACE pg_default;

-- Skonto scheduler run history (see database/migrations/003_skonto_scheduler_runs.sql)
CREATE TABLE IF NOT EXISTS public.skonto_scheduler_runs (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMP WITH TIME ZONE,
  trigger VARCHAR(20) NOT NULL,
  invoices_in_window INTEGER NOT NULL DEFAULT 0,
  reminders_due INTEGER NOT NULL DEFAULT 0,
  reminders_sent INTEGER NOT NULL DEFAULT 0,
  errors JSONB NOT NULL DEFAULT '[]'::JSONB,
  dry_run BOOLEAN NOT NULL DEFAULT false,
  CONSTRAINT skonto_scheduler_runs_pkey PRIMARY KEY (id),
  CONSTRAINT check_scheduler_trigger CHECK (trigger IN ('startup', 'interval', 'manual'))
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_skonto_scheduler_runs_started_at ON public.skonto_scheduler_runs USING btree (started_at DESC) TABLESPACE pg_default;

-- Invoice change log (see database/migrations/006_invoice_audit_log.sql)

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


-- =====================================================================
-- 9. STORAGE BUCKETS (private: PDFs are only served via signed URLs)
-- =====================================================================

INSERT INTO storage.buckets (id, name, public) VALUES
('invoices', 'invoices', false),
('folderwatcher', 'folderwatcher', false),
('manual-invoices', 'manual-invoices', false)
ON CONFLICT (id) DO NOTHING;

-- =====================================================================
-- 10. INSERT DEFAULT DATA (Required for app to work)
-- =====================================================================

-- NOTE: Default admin user will be created automatically by the application
-- based on environment variables (ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL)
-- This provides better security than hardcoded credentials

-- Insert sample dropdown options for project field
INSERT INTO dropdown_options (field_name, value, label, is_default, sort_order, is_active) VALUES
('projekt', 'project1', 'Bauprojekt 1', true, 1, true),
('projekt', 'project2', 'Bauprojekt 2', false, 2, true),
('projekt', 'project3', 'Bauprojekt 3', false, 3, true)
ON CONFLICT (field_name, value) DO NOTHING;

-- Insert sample dropdown options for gewerk field
INSERT INTO dropdown_options (field_name, value, label, is_default, sort_order, is_active) VALUES
('gewerk', 'elektro', 'Elektroinstallation', false, 1, true),
('gewerk', 'sanitaer', 'Sanitärinstallation', false, 2, true),
('gewerk', 'heizung', 'Heizungsinstallation', false, 3, true),
('gewerk', 'maler', 'Malerarbeiten', false, 4, true)
ON CONFLICT (field_name, value) DO NOTHING;

-- Insert sample gewerk list items
INSERT INTO gewerk_list (code, name, sort_order) VALUES
('E001', 'Elektroinstallation', 1),
('S001', 'Sanitärinstallation', 2),
('H001', 'Heizungsinstallation', 3),
('M001', 'Malerarbeiten', 4)
ON CONFLICT (code) DO NOTHING;

-- =====================================================================
-- 11. ROW LEVEL SECURITY
-- =====================================================================

-- RLS on, no policies: the public anon key can read nothing. The backend
-- connects with the service-role key (SUPA_KEY), which bypasses RLS, so
-- all data access goes through the API.
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices_clean ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE dropdown_options ENABLE ROW LEVEL SECURITY;
ALTER TABLE gewerk_list ENABLE ROW LEVEL SECURITY;
ALTER TABLE security_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE skonto_scheduler_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_audit_log ENABLE ROW LEVEL SECURITY;

-- =====================================================================
-- SETUP COMPLETE!
-- =====================================================================
-- Next steps:
-- 1. Put the project URL and the service_role key into .env
--    (SUPA_URL, SUPA_KEY and SUPA_SERVICE_ROLE_KEY)
-- 2. Start the backend; it creates the admin user from ADMIN_* variables
-- =====================================================================
