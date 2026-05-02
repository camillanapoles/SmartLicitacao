-- RBAC-ORG-001: Replace 'admin' role with 'viewer' in organization_members.
-- Hierarchy: owner (3) > member (2) > viewer (1).
-- Table was empty at migration time (no admin rows to migrate).

-- ============================================================================
-- 1. CHECK constraint: swap 'admin' for 'viewer'
-- ============================================================================

ALTER TABLE public.organization_members
  DROP CONSTRAINT IF EXISTS organization_members_role_check;

ALTER TABLE public.organization_members
  ADD CONSTRAINT organization_members_role_check
  CHECK (role IN ('owner', 'member', 'viewer'));

COMMENT ON COLUMN public.organization_members.role
  IS 'Role within org: owner (full control, rank 3), member (team access, rank 2), viewer (read-only, rank 1)';

-- ============================================================================
-- 2. RLS policies: replace 'admin' references with 'owner' (only owners manage)
-- ============================================================================

-- organizations table
DROP POLICY IF EXISTS "Org admins can view organization" ON public.organizations;

CREATE POLICY "Org members can view organization"
  ON public.organizations
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members om
      WHERE om.org_id  = public.organizations.id
        AND om.user_id = auth.uid()
        AND om.accepted_at IS NOT NULL
    )
  );

-- organization_members table — view policy
DROP POLICY IF EXISTS "Org owner/admin can view all members" ON public.organization_members;

CREATE POLICY "Org owner can view all members"
  ON public.organization_members
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members om
      WHERE om.org_id  = public.organization_members.org_id
        AND om.user_id = auth.uid()
        AND om.role    = 'owner'
        AND om.accepted_at IS NOT NULL
    )
  );

-- organization_members table — insert policy
DROP POLICY IF EXISTS "Org owner/admin can insert members" ON public.organization_members;

CREATE POLICY "Org owner can insert members"
  ON public.organization_members
  FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.organization_members om
      WHERE om.org_id  = public.organization_members.org_id
        AND om.user_id = auth.uid()
        AND om.role    = 'owner'
        AND om.accepted_at IS NOT NULL
    )
    OR
    -- Allow owner to add the first member row (bootstrap: owner adds themselves)
    EXISTS (
      SELECT 1 FROM public.organizations o
      WHERE o.id       = public.organization_members.org_id
        AND o.owner_id = auth.uid()
    )
  );

-- organization_members table — delete policy
DROP POLICY IF EXISTS "Org owner/admin can delete members" ON public.organization_members;

CREATE POLICY "Org owner can delete members"
  ON public.organization_members
  FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members om
      WHERE om.org_id  = public.organization_members.org_id
        AND om.user_id = auth.uid()
        AND om.role    = 'owner'
        AND om.accepted_at IS NOT NULL
    )
    OR
    -- Users can remove themselves (leave org)
    auth.uid() = user_id
  );

DO $$
BEGIN
  RAISE NOTICE 'RBAC-ORG-001: role CHECK updated (admin → viewer), RLS policies updated';
END $$;
