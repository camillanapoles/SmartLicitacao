ALTER TABLE public.leads
  ADD COLUMN IF NOT EXISTS email_sent_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS email_message_id TEXT,
  ADD COLUMN IF NOT EXISTS email_status TEXT DEFAULT 'pending';

COMMENT ON COLUMN public.leads.email_sent_at IS 'Timestamp quando o lead magnet foi enviado. NULL = pendente.';
COMMENT ON COLUMN public.leads.email_message_id IS 'Resend message ID para rastreamento de entrega/bounce';
COMMENT ON COLUMN public.leads.email_status IS 'Status do envio: pending, sent, failed, bounced, quota_exceeded';

CREATE INDEX IF NOT EXISTS idx_leads_pending_email
  ON public.leads (captured_at)
  WHERE email_sent_at IS NULL AND email_status = 'pending';
