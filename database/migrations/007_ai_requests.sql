-- One row per live call to the AI provider: which feature, model, tokens and
-- estimated cost. No prompts or answers are stored (DSGVO data minimisation).
CREATE TABLE IF NOT EXISTS public.ai_requests (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  feature VARCHAR(40) NOT NULL,
  model VARCHAR(60) NOT NULL,
  actor VARCHAR(255),
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_requests_created_at ON public.ai_requests (created_at DESC);

ALTER TABLE public.ai_requests ENABLE ROW LEVEL SECURITY;
