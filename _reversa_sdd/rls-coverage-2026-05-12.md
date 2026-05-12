# RLS Coverage Audit — `public` schema

- **Generated:** 2026-05-12 17:34 UTC
- **Project ref:** `fqqyovlzdzimiwfofdjk`
- **Total tables:** 62
- **Compliant (RLS on + ≥1 policy):** 61
- **Documented exempt (`-- rls-exempt:`):** 1
- **Failing:** 0
- **Coverage:** 100.0%

Source: ADR-RLS-MANDATORY-001 (`docs/adr/ADR-RLS-MANDATORY-001-policy.md`).
Generator: `backend/scripts/audit_rls_coverage.py` (RLS-AUDIT-001 / #969).

## ❌ RLS disabled (failing)

_None._

## ❌ RLS enabled but no policies (failing — effectively closed to non-bypass roles, gap on intent)

_None._

## ⚠️ Documented exemptions (`-- rls-exempt:` in migrations)

| Table | RLS | Policies | Detail |
|-------|-----|---------:|--------|
| `auth_attempts` | on | 0 | auth_attempts — service-role only table, no anon/authenticated access needed. |

## ✅ Compliant (RLS on + ≥1 policy)

| Table | RLS | Policies | Detail |
|-------|-----|---------:|--------|
| `admin_billing_audit_log` | on | 2 | `admin_billing_audit_log_service_all` (ALL → service_role); `admin_billing_audit_log_no_public_read` (SELECT → anon,authenticated) |
| `alert_preferences` | on | 4 | `update_alert_preferences_owner` (UPDATE → public); `all_alert_preferences_service` (ALL → service_role); `insert_alert_preferences_owner` (INSERT → public); `select_alert_preferences_owner` (SELECT → public) |
| `alert_runs` | on | 2 | `select_alert_runs_owner` (SELECT → public); `all_alert_runs_service` (ALL → service_role) |
| `alert_sent_items` | on | 2 | `select_alert_sent_items_owner` (SELECT → public); `all_alert_sent_items_service` (ALL → service_role) |
| `alerts` | on | 5 | `all_alerts_service` (ALL → service_role); `update_alerts_owner` (UPDATE → public); `select_alerts_owner` (SELECT → public); `insert_alerts_owner` (INSERT → public); `delete_alerts_owner` (DELETE → public) |
| `app_config` | on | 1 | `Service role full access on app_config` (ALL → public) |
| `audit_events` | on | 2 | `select_audit_events_admin` (SELECT → public); `all_audit_events_service` (ALL → service_role) |
| `billing_reconciliation_runs` | on | 2 | `billing_reconciliation_runs_no_public_read` (SELECT → anon,authenticated); `billing_reconciliation_runs_service_all` (ALL → service_role) |
| `classification_feedback` | on | 5 | `select_classification_feedback_owner` (SELECT → public); `update_classification_feedback_owner` (UPDATE → public); `all_classification_feedback_service` (ALL → service_role); `delete_classification_feedback_owner` (DELETE → public); `insert_classification_feedback_owner` (INSERT → public) |
| `cnae_setor_mapping` | on | 2 | `cnae_admin_write` (ALL → authenticated); `cnae_public_read` (SELECT → public) |
| `cnae_setores` | on | 1 | `cnae_setores_read_authenticated` (SELECT → authenticated) |
| `conversations` | on | 4 | `insert_conversations_owner` (INSERT → public); `select_conversations_owner` (SELECT → public); `update_conversations_admin` (UPDATE → public); `all_conversations_service` (ALL → service_role) |
| `enriched_entities` | on | 2 | `enriched_entities_read_all` (SELECT → public); `enriched_entities_service_write` (ALL → public) |
| `export_time_saved_survey` | on | 3 | `User can read own surveys` (SELECT → public); `User can insert own surveys` (INSERT → public); `Service role full access on export surveys` (ALL → public) |
| `founding_leads` | on | 2 | `founding_leads_admin_read` (SELECT → public); `founding_leads_service_write` (ALL → public) |
| `founding_policy` | on | 2 | `founding_policy_public_read` (SELECT → public); `founding_policy_service_write` (ALL → public) |
| `founding_policy_audit_log` | on | 1 | `founding_policy_audit_service_write` (ALL → public) |
| `google_sheets_exports` | on | 4 | `all_google_sheets_exports_service` (ALL → service_role); `update_google_sheets_exports_owner` (UPDATE → public); `select_google_sheets_exports_owner` (SELECT → public); `insert_google_sheets_exports_owner` (INSERT → public) |
| `gsc_metrics` | on | 2 | `admin_read_gsc_metrics` (SELECT → public); `service_write_gsc_metrics` (ALL → public) |
| `health_checks` | on | 1 | `all_health_checks_service` (ALL → service_role) |
| `incidents` | on | 1 | `all_incidents_service` (ALL → service_role) |
| `indice_municipal` | on | 2 | `indice_municipal_public_read` (SELECT → public); `indice_municipal_service_write` (ALL → service_role) |
| `ingestion_checkpoints` | on | 2 | `select_ingestion_checkpoints_authenticated` (SELECT → authenticated); `all_ingestion_checkpoints_service` (ALL → service_role) |
| `ingestion_runs` | on | 2 | `select_ingestion_runs_authenticated` (SELECT → authenticated); `all_ingestion_runs_service` (ALL → service_role) |
| `intel_report_purchases` | on | 4 | `irp_service_update` (UPDATE → service_role); `irp_service_select` (SELECT → service_role); `irp_service_insert` (INSERT → service_role); `irp_owner_select` (SELECT → authenticated) |
| `leads` | on | 2 | `leads_anon_insert` (INSERT → public); `leads_service_all` (ALL → public) |
| `messages` | on | 4 | `insert_messages_authenticated` (INSERT → public); `select_messages_authenticated` (SELECT → public); `update_messages_owner` (UPDATE → public); `all_messages_service` (ALL → service_role) |
| `mfa_recovery_attempts` | on | 1 | `all_mfa_recovery_attempts_service` (ALL → service_role) |
| `mfa_recovery_codes` | on | 2 | `select_mfa_recovery_codes_owner` (SELECT → authenticated); `all_mfa_recovery_codes_service` (ALL → service_role) |
| `monthly_quota` | on | 2 | `all_monthly_quota_service` (ALL → service_role); `select_monthly_quota_owner` (SELECT → public) |
| `organization_members` | on | 8 | `delete_organization_members_admin` (DELETE → public); `select_organization_members_admin` (SELECT → public); `select_organization_members_self` (SELECT → public); `Org members can view all members` (SELECT → public); `Org owner can delete members` (DELETE → public); `Org owner can insert members` (INSERT → public); `all_organization_members_service` (ALL → service_role); `insert_organization_members_admin` (INSERT → public) |
| `organizations` | on | 6 | `Org members can view organization` (SELECT → public); `all_organizations_service` (ALL → service_role); `insert_organizations_owner` (INSERT → public); `select_organizations_admin` (SELECT → public); `select_organizations_owner` (SELECT → public); `update_organizations_owner` (UPDATE → public) |
| `partner_referrals` | on | 3 | `select_partner_referrals_partner` (SELECT → public); `all_partner_referrals_admin` (ALL → public); `all_partner_referrals_service` (ALL → service_role) |
| `partners` | on | 3 | `all_partners_admin` (ALL → public); `select_partners_self` (SELECT → public); `all_partners_service` (ALL → service_role) |
| `pipeline_items` | on | 5 | `update_pipeline_items_owner` (UPDATE → public); `all_pipeline_items_service` (ALL → service_role); `delete_pipeline_items_owner` (DELETE → public); `insert_pipeline_items_owner` (INSERT → public); `select_pipeline_items_owner` (SELECT → public) |
| `plan_billing_periods` | on | 2 | `select_plan_billing_periods_public` (SELECT → anon,authenticated); `all_plan_billing_periods_service` (ALL → service_role) |
| `plan_features` | on | 1 | `select_plan_features_public` (SELECT → public) |
| `plans` | on | 2 | `plans_service_write` (ALL → service_role); `plans_select_all` (SELECT → public) |
| `plans_audit` | on | 1 | `plans_audit_service_all` (ALL → service_role) |
| `pncp_raw_bids` | on | 4 | `insert_pncp_raw_bids_service` (INSERT → service_role); `delete_pncp_raw_bids_service` (DELETE → service_role); `select_pncp_raw_bids_authenticated` (SELECT → authenticated); `update_pncp_raw_bids_service` (UPDATE → service_role) |
| `pncp_supplier_contracts` | on | 2 | `psc_service_write` (ALL → public); `psc_public_read` (SELECT → public) |
| `profiles` | on | 5 | `insert_profiles_owner` (INSERT → authenticated); `all_profiles_service` (ALL → service_role); `profiles_update_own` (UPDATE → public); `profiles_select_own` (SELECT → public); `insert_profiles_service` (INSERT → service_role) |
| `reconciliation_log` | on | 2 | `all_reconciliation_log_service` (ALL → service_role); `select_reconciliation_log_admin` (SELECT → public) |
| `referrals` | on | 3 | `referrals_insert_own` (INSERT → authenticated); `referrals_select_own` (SELECT → authenticated); `referrals_service_all` (ALL → service_role) |
| `report_leads` | on | 1 | `report_leads_service_all` (ALL → service_role) |
| `saved_filter_presets` | on | 4 | `Users can update own presets` (UPDATE → public); `Users can delete own presets` (DELETE → public); `Users can insert own presets` (INSERT → public); `Users can read own presets` (SELECT → public) |
| `search_results_cache` | on | 2 | `select_search_results_cache_owner` (SELECT → public); `Service role full access on search_results_cache` (ALL → service_role) |
| `search_results_store` | on | 2 | `all_search_results_store_service` (ALL → service_role); `select_search_results_store_owner` (SELECT → public) |
| `search_sessions` | on | 3 | `sessions_select_own` (SELECT → public); `all_search_sessions_service` (ALL → service_role); `sessions_insert_own` (INSERT → public) |
| `search_state_transitions` | on | 2 | `all_search_state_transitions_service` (ALL → service_role); `Users can read own transitions` (SELECT → public) |
| `seo_coverage_manifest` | on | 1 | `Public read coverage manifest` (SELECT → public) |
| `seo_metrics` | on | 2 | `seo_metrics_service_write` (ALL → service_role); `seo_metrics_select` (SELECT → authenticated) |
| `shared_analyses` | on | 2 | `users_insert_own_shares` (INSERT → public); `anyone_can_read_shares` (SELECT → public) |
| `stripe_webhook_events` | on | 4 | `webhook_events_select_admin` (SELECT → authenticated); `insert_stripe_webhook_events_service` (INSERT → service_role); `select_stripe_webhook_events_admin` (SELECT → authenticated); `select_stripe_webhook_events_service` (SELECT → service_role) |
| `trial_email_dlq` | on | 1 | `trial_email_dlq_service_only` (ALL → public) |
| `trial_email_log` | on | 1 | `select_trial_email_log_owner` (SELECT → public) |
| `trial_exit_surveys` | on | 2 | `users_insert_own_survey` (INSERT → public); `admin_read_surveys` (SELECT → public) |
| `trial_extensions` | on | 2 | `Service role full access` (ALL → public); `Users read own extensions` (SELECT → public) |
| `user_email_actions` | on | 2 | `service_role_select` (SELECT → service_role); `service_role_insert` (INSERT → service_role) |
| `user_oauth_tokens` | on | 4 | `update_user_oauth_tokens_owner` (UPDATE → public); `select_user_oauth_tokens_owner` (SELECT → public); `delete_user_oauth_tokens_owner` (DELETE → public); `all_user_oauth_tokens_service` (ALL → service_role) |
| `user_subscriptions` | on | 2 | `Service role can manage subscriptions` (ALL → service_role); `subscriptions_select_own` (SELECT → public) |
