-- B2GOPS-002: Rollback workspace_documents schema + RPCs
--
-- Order: DROP FUNCTION before DROP TABLE (functions depend on tables at
-- runtime, but DROP TABLE CASCADE handles function dependency at the
-- Postgres level). We drop functions explicitly first for clarity and safety.

DROP FUNCTION IF EXISTS public.ops_insert_document(TEXT, TEXT, TEXT, TEXT, BIGINT, TEXT, TEXT, DATE, TEXT[]);
DROP FUNCTION IF EXISTS public.ops_check_expiring_certidoes(INTEGER);
DROP FUNCTION IF EXISTS public.ops_list_documents(TEXT, TEXT);

DROP POLICY IF EXISTS "Users can CRUD own documents" ON public.workspace_documents;

DROP TABLE IF EXISTS public.workspace_documents CASCADE;
