-- One row per Skonto reminder check, so the scheduler's work survives restarts
-- and can be shown in the Prüfbericht.

CREATE TABLE IF NOT EXISTS public.skonto_scheduler_runs (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMP WITH TIME ZONE,
  trigger VARCHAR(20) NOT NULL,                -- startup | interval | manual
  invoices_in_window INTEGER NOT NULL DEFAULT 0, -- Skonto due within the reminder window
  reminders_due INTEGER NOT NULL DEFAULT 0,      -- reached a new urgency level
  reminders_sent INTEGER NOT NULL DEFAULT 0,
  errors JSONB NOT NULL DEFAULT '[]'::JSONB,
  dry_run BOOLEAN NOT NULL DEFAULT false,
  CONSTRAINT skonto_scheduler_runs_pkey PRIMARY KEY (id),
  CONSTRAINT check_scheduler_trigger CHECK (trigger IN ('startup', 'interval', 'manual'))
);

CREATE INDEX IF NOT EXISTS idx_skonto_scheduler_runs_started_at
  ON public.skonto_scheduler_runs (started_at DESC);

-- Only the backend (service-role key) reads and writes this table
ALTER TABLE public.skonto_scheduler_runs ENABLE ROW LEVEL SECURITY;
