"""Schemas added during PARITY-BE-FE-001 Pass 2.

These models are intentionally permissive — every field is `Optional`,
extra keys are tolerated. The goal of Pass 2 is to expose the OpenAPI
*shape* so `frontend/app/api-types.generated.ts` stops collapsing to
`{[k: string]: unknown}`. Tightening individual schemas (e.g.
`OrganizationDashboardResponse`) is deliberately deferred to follow-up
work so that this PR cannot strip keys silently from existing handlers.

Convention:
    * `BaseModel` with `model_config = ConfigDict(extra="allow")` so the
      handler can keep returning extra dynamic keys without breaking
      validation.
    * `Optional[...] = None` for every field — never `extra="forbid"`
      on a response model.

See `docs/adr/ADR-PARITY-BE-FE-001-response-model-mandatory.md` for the
full policy.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Generic permissive envelopes
# ---------------------------------------------------------------------------

class _PermissiveBase(BaseModel):
    """Base model that tolerates extra keys (response-side only)."""

    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# auth_check.py — pre-signup validation responses
# ---------------------------------------------------------------------------

class CheckEmailResponse(_PermissiveBase):
    """STORY-258 AC15: Pre-signup email validation response."""

    available: bool
    disposable: bool
    corporate: bool


class CheckPhoneResponse(_PermissiveBase):
    """STORY-258 AC11-AC12: Pre-signup phone uniqueness response."""

    available: bool


# ---------------------------------------------------------------------------
# health.py — system / status / cache health responses
# ---------------------------------------------------------------------------

class SystemHealthResponse(_PermissiveBase):
    """GTM-STAB-008 AC3: Component-level health (overall + components).

    Permissive — `health.get_system_health()` can grow new components
    over time (Redis metrics, queue, sources) and existing callers
    just see additional keys.
    """

    status: Optional[str] = None
    overall: Optional[str] = None
    timestamp: Optional[str] = None


class PublicStatusResponse(_PermissiveBase):
    """STORY-316 AC3: Public per-source status snapshot."""

    overall: Optional[str] = None
    timestamp: Optional[str] = None


class IncidentEntry(_PermissiveBase):
    """One incident record from the public status timeline."""

    id: Optional[str] = None
    occurred_at: Optional[str] = None
    severity: Optional[str] = None
    summary: Optional[str] = None


class IncidentsResponse(_PermissiveBase):
    """STORY-316 AC13: Recent incidents wrapper."""

    incidents: List[IncidentEntry] = []


class UptimeHistoryEntry(_PermissiveBase):
    """One day of uptime data."""

    date: Optional[str] = None
    uptime_pct: Optional[float] = None


class UptimeHistoryResponse(_PermissiveBase):
    """STORY-316 AC12: Daily uptime history wrapper."""

    history: List[UptimeHistoryEntry] = []


class BackgroundTasksHealthResponse(_PermissiveBase):
    """DEBT-014 SYS-006: TaskRegistry health snapshot (shape varies)."""

    status: Optional[str] = None


class SourceHealthEntry(_PermissiveBase):
    """Per-source health state."""

    enabled: Optional[bool] = None
    status: Optional[str] = None
    available: Optional[bool] = None


class SourcesHealthMapResponse(_PermissiveBase):
    """UX-428 AC5: { sources: { code: SourceHealthEntry } }."""

    sources: Dict[str, SourceHealthEntry] = {}


class CacheLevelHealth(_PermissiveBase):
    """Per-level cache health (supabase / redis / local)."""

    status: Optional[str] = None
    latency_ms: Optional[int] = None
    last_error: Optional[str] = None


class CacheDegradationInfo(_PermissiveBase):
    """B-03/AC9 cache degradation aggregates."""

    degraded_keys_count: Optional[int] = None
    avg_fail_streak: Optional[float] = None
    keys_with_failures: Optional[int] = None
    priority_distribution: Optional[Dict[str, int]] = None
    error: Optional[str] = None


class CacheHealthResponse(_PermissiveBase):
    """UX-303 AC7: Cache health envelope across all levels."""

    timestamp: Optional[str] = None
    overall: Optional[str] = None
    supabase: Optional[CacheLevelHealth] = None
    redis: Optional[CacheLevelHealth] = None
    local: Optional[CacheLevelHealth] = None
    degradation: Optional[CacheDegradationInfo] = None


class SitemapMvCheck(_PermissiveBase):
    """Per-MV status entry for the sitemap health endpoint."""

    status: Optional[str] = None  # "ok" | "empty" | "error"
    count: Optional[int] = None
    error: Optional[str] = None


class SitemapHealthResponse(_PermissiveBase):
    """SEO-SITEMAP-TELEMETRY-001: Health envelope for sitemap materialized views.

    Returns per-MV status (ok/empty/error) and overall status (ok/degraded).
    HTTP 200 when all MVs are ok; HTTP 503 when any MV is empty or errored.
    """

    status: Optional[str] = None  # "ok" | "degraded"
    timestamp: Optional[str] = None
    checks: Optional[Dict[str, SitemapMvCheck]] = None


# ---------------------------------------------------------------------------
# organizations.py — multi-tenant org responses
# ---------------------------------------------------------------------------

class OrganizationResponse(_PermissiveBase):
    """One organization row + denormalized fields the API may add."""

    id: Optional[str] = None
    name: Optional[str] = None
    owner_id: Optional[str] = None
    plan_id: Optional[str] = None
    seats_used: Optional[int] = None
    created_at: Optional[str] = None


class OrganizationMembershipResponse(_PermissiveBase):
    """`/organizations/me` returns membership + org info."""

    organization_id: Optional[str] = None
    role: Optional[str] = None
    organization: Optional[OrganizationResponse] = None


class OrganizationInviteResponse(_PermissiveBase):
    """POST /organizations/{org_id}/invite response."""

    invite_id: Optional[str] = None
    invite_token: Optional[str] = None
    invite_url: Optional[str] = None
    expires_at: Optional[str] = None


class OrganizationAcceptResponse(_PermissiveBase):
    """POST /organizations/{org_id}/accept response."""

    organization_id: Optional[str] = None
    role: Optional[str] = None
    success: Optional[bool] = None


class OrganizationMemberRemovedResponse(_PermissiveBase):
    """DELETE /organizations/{org_id}/members/{user_id} response."""

    success: Optional[bool] = None
    removed_user_id: Optional[str] = None


class OrganizationDashboardResponse(_PermissiveBase):
    """Aggregated dashboard for an org (extends over time)."""

    organization_id: Optional[str] = None
    members_count: Optional[int] = None
    seats_used: Optional[int] = None
    pipeline_count: Optional[int] = None
    searches_30d: Optional[int] = None


class OrganizationLogoUpdatedResponse(_PermissiveBase):
    """PUT /organizations/{org_id}/logo response."""

    success: Optional[bool] = None
    logo_url: Optional[str] = None


# ---------------------------------------------------------------------------
# partners.py — partner program responses
# ---------------------------------------------------------------------------

class PartnerDashboardResponse(_PermissiveBase):
    """AC14: Partner self-service dashboard payload."""

    partner_id: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = None
    referrals: Optional[List[Dict[str, Any]]] = None
    revenue: Optional[Dict[str, Any]] = None


class PartnerSummary(_PermissiveBase):
    """One partner row in the admin list."""

    id: Optional[str] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    status: Optional[str] = None
    contact_email: Optional[str] = None
    revenue_share_pct: Optional[float] = None
    referrals_total: Optional[int] = None
    referrals_active: Optional[int] = None
    monthly_share: Optional[float] = None


class PartnersListResponse(_PermissiveBase):
    """AC10: Admin partners list wrapper."""

    partners: List[PartnerSummary] = []


class PartnerCreateResponse(_PermissiveBase):
    """AC11: Newly-created partner row."""

    id: Optional[str] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    status: Optional[str] = None


class PartnerReferralEntry(_PermissiveBase):
    """One partner referral record."""

    id: Optional[str] = None
    user_id: Optional[str] = None
    converted_at: Optional[str] = None
    churned_at: Optional[str] = None
    monthly_revenue: Optional[float] = None
    revenue_share_amount: Optional[float] = None


class PartnerReferralsResponse(_PermissiveBase):
    """AC12: Admin partner referrals wrapper."""

    referrals: List[PartnerReferralEntry] = []


class PartnerRevenueResponse(_PermissiveBase):
    """AC13: Partner revenue share for a given month."""

    partner_id: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    total_revenue: Optional[float] = None
    revenue_share_amount: Optional[float] = None


# ---------------------------------------------------------------------------
# trial_emails.py — admin preview / test send / webhook
# ---------------------------------------------------------------------------

class TrialEmailWebhookResponse(_PermissiveBase):
    """AC11: Resend webhook ack — `{status: "processed"|"skipped"|"ignored"}`."""

    status: Optional[str] = None
    event_type: Optional[str] = None


class TrialEmailPreviewItem(_PermissiveBase):
    """AC15: One template preview entry."""

    number: Optional[int] = None
    day: Optional[int] = None
    type: Optional[str] = None
    subject: Optional[str] = None
    html: Optional[str] = None
    error: Optional[str] = None


class TrialEmailTestSendResponse(_PermissiveBase):
    """AC14: Admin test-send response."""

    status: Optional[str] = None
    email_id: Optional[str] = None
    to: Optional[str] = None
    type: Optional[str] = None
    subject: Optional[str] = None


# ---------------------------------------------------------------------------
# slo.py — admin SLO dashboard
# ---------------------------------------------------------------------------

class SloDashboardResponse(_PermissiveBase):
    """STORY-299 AC7-AC9: SLO compliance + alerts + definitions."""

    compliance: Optional[str] = None
    slos: Optional[Dict[str, Any]] = None
    alerts: Optional[List[Dict[str, Any]]] = None
    firing_count: Optional[int] = None
    slo_definitions: Optional[Dict[str, Any]] = None
    recording_rules: Optional[Any] = None
    sentry_alerts: Optional[Any] = None


class SloAlertsResponse(_PermissiveBase):
    """STORY-299: Current alert evaluation snapshot."""

    alerts: Optional[List[Dict[str, Any]]] = None
    firing_count: Optional[int] = None


# ---------------------------------------------------------------------------
# search_status.py — search timeline / results / zero-match / cancel
# ---------------------------------------------------------------------------

class SearchTimelineResponse(_PermissiveBase):
    """`GET /search/{id}/timeline` — list of progress events."""

    search_id: Optional[str] = None
    events: Optional[List[Dict[str, Any]]] = None


class SearchResultsResponse(_PermissiveBase):
    """`GET /buscar-results/{id}` and `/search/{id}/results` — full envelope."""

    search_id: Optional[str] = None
    licitacoes: Optional[List[Dict[str, Any]]] = None
    resumo: Optional[Dict[str, Any]] = None
    total: Optional[int] = None


class SearchZeroMatchResponse(_PermissiveBase):
    """`GET /search/{id}/zero-match` — zero-match LLM decisions."""

    search_id: Optional[str] = None
    zero_matches: Optional[List[Dict[str, Any]]] = None


class SearchActionResponse(_PermissiveBase):
    """Generic ack for `regenerate-excel`, `retry`, `cancel`."""

    search_id: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# pipeline.py — write responses (item create/update/delete)
# ---------------------------------------------------------------------------

class PipelineItemResponse(_PermissiveBase):
    """One pipeline item (kanban card)."""

    id: Optional[str] = None
    user_id: Optional[str] = None
    licitacao_id: Optional[str] = None
    stage: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    version: Optional[int] = None


class PipelineDeletedResponse(_PermissiveBase):
    """DELETE /pipeline/{id} response."""

    success: Optional[bool] = None
    deleted_id: Optional[str] = None


# ---------------------------------------------------------------------------
# alerts.py — patch / delete alert responses
# ---------------------------------------------------------------------------

class AlertEntryResponse(_PermissiveBase):
    """One alert row."""

    id: Optional[str] = None
    user_id: Optional[str] = None
    name: Optional[str] = None
    enabled: Optional[bool] = None
    setor: Optional[str] = None
    ufs: Optional[List[str]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AlertDeletedResponse(_PermissiveBase):
    """DELETE /alerts/{id} response."""

    success: Optional[bool] = None
    deleted_id: Optional[str] = None


# ---------------------------------------------------------------------------
# notifications / metrics / sessions / observatorio / billing extras
# ---------------------------------------------------------------------------

class NewBidsCountClearedResponse(_PermissiveBase):
    """DELETE /new-bids-count response."""

    success: Optional[bool] = None
    cleared: Optional[bool] = None


class DiscardRateResponse(_PermissiveBase):
    """GET /metrics/discard-rate snapshot."""

    discard_rate: Optional[float] = None
    period_days: Optional[int] = None
    total_searches: Optional[int] = None
    discarded: Optional[int] = None


class BillingPortalResponse(_PermissiveBase):
    """POST /billing-portal — Stripe customer portal session url."""

    portal_url: Optional[str] = None
    url: Optional[str] = None


class SubscriptionStatusResponse(_PermissiveBase):
    """GET /subscription/status — current plan + period info."""

    status: Optional[str] = None
    plan_id: Optional[str] = None
    activated_at: Optional[str] = None
    current_period_end: Optional[str] = None
    cancel_at_period_end: Optional[bool] = None
    trial_end: Optional[str] = None


class ObservatorioCsvAck(_PermissiveBase):
    """`/observatorio/relatorio/{mes}/{ano}/csv` non-streaming ack (shape may vary)."""

    status: Optional[str] = None
    url: Optional[str] = None


class SitemapCacheRefreshResponse(_PermissiveBase):
    """POST /admin/sitemap-cache/refresh response."""

    status: Optional[str] = None
    total_combos: Optional[int] = None
    threshold: Optional[int] = None


# ---------------------------------------------------------------------------
# user.py — admin trial exit surveys / data export
# ---------------------------------------------------------------------------

class TrialExitSurveyEntry(_PermissiveBase):
    """One trial exit survey response row."""

    id: Optional[str] = None
    user_id: Optional[str] = None
    reason: Optional[str] = None
    feedback: Optional[str] = None
    created_at: Optional[str] = None


class TrialExitSurveysReasonCount(_PermissiveBase):
    """One {reason, count} aggregation row."""

    reason: Optional[str] = None
    count: Optional[int] = None


class TrialExitSurveysResponse(_PermissiveBase):
    """GET /admin/trial-exit-surveys: aggregated reason counts."""

    total: Optional[int] = None
    by_reason: Optional[List[TrialExitSurveysReasonCount]] = None
    surveys: Optional[List[TrialExitSurveyEntry]] = None


# ---------------------------------------------------------------------------
# stats_public.py — public stats embed/badge already typed; nothing here.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# auth_email.py — validate signup email
# ---------------------------------------------------------------------------

class ValidateSignupEmailResponse(_PermissiveBase):
    """POST /validate-signup-email response."""

    valid: Optional[bool] = None
    available: Optional[bool] = None
    disposable: Optional[bool] = None
    corporate: Optional[bool] = None
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# feature_flags.py — experiments list (currently untyped)
# ---------------------------------------------------------------------------

class ExperimentsListResponse(_PermissiveBase):
    """GET /experiments — list of experiment definitions."""

    experiments: Optional[List[Dict[str, Any]]] = None


# ---------------------------------------------------------------------------
# intel_reports.py — download (returns file stream → response_model=None used in route).
# nothing here; placeholder marker.
# ---------------------------------------------------------------------------
