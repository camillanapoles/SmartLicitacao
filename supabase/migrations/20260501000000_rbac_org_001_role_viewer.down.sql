-- RBAC-ORG-001 rollback: restore 'admin' role and original RLS policies.

ALTER TABLE public.organization_members
  DROP CONSTRAINT IF EXISTS organization_members_role_check;

ALTER TABLE public.organization_members
  ADD CONSTRAINT organization_members_role_check
  CHECK (role IN ('owner', 'admin', 'member'));

COMMENT ON COLUMN public.organization_members.role
  IS 'Role within the org: owner (full control), admin (manage members), member (read-only team access)';

-- Restore original RLS policies
DROP POLICY IF EXISTS "Org members can view organization"     ON public.organizations;
DROP POLICY IF EXISTS "Org owner can view all members"        ON public.organization_members;
DROP POLICY IF EXISTS "Org owner can insert members"          ON public.organization_members;
DROP POLICY IF EXISTS "Org owner can delete members"          ON public.organization_members;

CREATE POLICY "Org admins can view organization"
  ON public.organizations FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members om
      WHERE om.org_id = public.organizations.id
        AND om.user_id = auth.uid()
        AND om.role IN ('owner', 'admin')
        AND om.accepted_at IS NOT NULL
    )
  );

CREATE POLICY "Org owner/admin can view all members"
  ON public.organization_members FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members om
      WHERE om.org_id = public.organization_members.org_id
        AND om.user_id = auth.uid()
        AND om.role IN ('owner', 'admin')
        AND om.accepted_at IS NOT NULL
    )
  );

CREATE POLICY "Org owner/admin can insert members"
  ON public.organization_members FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.organization_members om
      WHERE om.org_id = public.organization_members.org_id
        AND om.user_id = auth.uid()
        AND om.role IN ('owner', 'admin')
        AND om.accepted_at IS NOT NULL
    )
    OR EXISTS (
      SELECT 1 FROM public.organizations o
      WHERE o.id = public.organization_members.org_id AND o.owner_id = auth.uid()
    )
  );

CREATE POLICY "Org owner/admin can delete members"
  ON public.organization_members FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members om
      WHERE om.org_id = public.organization_members.org_id
        AND om.user_id = auth.uid()
        AND om.role IN ('owner', 'admin')
        AND om.accepted_at IS NOT NULL
    )
    OR auth.uid() = user_id
  );
