DROP INDEX IF EXISTS idx_leads_pending_email;
ALTER TABLE public.leads
  DROP COLUMN IF EXISTS email_sent_at,
  DROP COLUMN IF EXISTS email_message_id,
  DROP COLUMN IF EXISTS email_status;
