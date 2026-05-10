"""
STORY-321 AC17: Tests for trial email templates — 6 emails.

Tests each template renders correctly, contains expected content,
handles zero stats, and includes unsubscribe links.
"""


from templates.emails.trial import (
    render_trial_welcome_email,
    render_trial_engagement_email,
    render_trial_paywall_alert_email,
    render_trial_value_email,
    render_trial_last_day_email,
    render_trial_last_day_card_email,
    render_trial_expired_email,
    _format_brl,
    _stats_block,
    _unsubscribe_block,
    _preheader,
)


SAMPLE_STATS = {
    "searches_count": 12,
    "opportunities_found": 47,
    "total_value_estimated": 2_350_000,
    "pipeline_items_count": 8,
    "sectors_searched": ["software", "medicamentos", "construcao"],
}

ZERO_STATS = {
    "searches_count": 0,
    "opportunities_found": 0,
    "total_value_estimated": 0,
    "pipeline_items_count": 0,
    "sectors_searched": [],
}

UNSUB_URL = "https://api.smartlic.tech/v1/trial-emails/unsubscribe?user_id=test&token=abc"


# ============================================================================
# Helpers
# ============================================================================

class TestFormatBrl:
    """Test Brazilian Real formatting helper."""

    def test_millions(self):
        assert "M" in _format_brl(2_500_000)
        assert "2.5M" in _format_brl(2_500_000)

    def test_thousands(self):
        assert "k" in _format_brl(150_000)
        assert "150k" in _format_brl(150_000)

    def test_small_value(self):
        result = _format_brl(500)
        assert "500" in result
        assert "R$" in result

    def test_zero(self):
        result = _format_brl(0)
        assert "R$" in result


class TestStatsBlock:
    """Test stats block rendering."""

    def test_renders_with_stats(self):
        html = _stats_block(SAMPLE_STATS)
        assert "12" in html
        assert "47" in html
        assert "2.4M" in html or "2.3M" in html

    def test_shows_pipeline_when_enabled(self):
        html = _stats_block(SAMPLE_STATS, show_pipeline=True)
        assert "8" in html
        assert "pipeline" in html.lower()

    def test_empty_stats_safe(self):
        html = _stats_block({})
        assert "0" in html


class TestUnsubscribeBlock:
    """Test unsubscribe block rendering."""

    def test_renders_when_url_provided(self):
        html = _unsubscribe_block(UNSUB_URL)
        assert "unsubscribe" in html
        assert "trial" in html.lower()

    def test_empty_when_no_url(self):
        html = _unsubscribe_block("")
        assert html == ""


class TestPreheader:
    """Test preheader text rendering."""

    def test_renders_hidden_div(self):
        html = _preheader("Test preheader text")
        assert "display:none" in html
        assert "Test preheader text" in html

    def test_empty_string(self):
        html = _preheader("")
        assert "display:none" in html


# ============================================================================
# Email #1 — Day 0: Welcome
# ============================================================================

class TestWelcomeEmail:
    """AC17: Email #1 — Day 0: Welcome."""

    def test_renders_without_error(self):
        html = render_trial_welcome_email("Joao")
        assert "<!DOCTYPE html>" in html

    def test_contains_user_name(self):
        html = render_trial_welcome_email("Maria Silva")
        assert "Maria Silva" in html

    def test_contains_welcome_message(self):
        html = render_trial_welcome_email("Test")
        assert "Bem-vindo" in html

    def test_contains_14_day_trial_mention(self):
        html = render_trial_welcome_email("Test")
        assert "14 dias" in html

    def test_contains_3_steps(self):
        """AC7: Welcome email has 3 steps."""
        html = render_trial_welcome_email("Test")
        assert "1." in html
        assert "2." in html
        assert "3." in html

    def test_contains_buscar_cta(self):
        html = render_trial_welcome_email("Test")
        assert "/buscar" in html
        assert "primeira análise" in html.lower()

    def test_contains_preheader(self):
        html = render_trial_welcome_email("Test")
        assert "display:none" in html

    def test_contains_unsubscribe_link(self):
        html = render_trial_welcome_email("Test", unsubscribe_url=UNSUB_URL)
        assert "unsubscribe" in html

    def test_is_not_transactional(self):
        html = render_trial_welcome_email("Test", unsubscribe_url=UNSUB_URL)
        assert "Cancelar" in html or "unsubscribe" in html


# ============================================================================
# Email #2 — Day 3: Engagement
# ============================================================================

class TestEngagementEmail:
    """EMAIL-TRIAL-006 (#1005) Day 3: founder-led "tá fazendo sentido?"."""

    def test_renders_with_stats(self):
        html = render_trial_engagement_email("Joao", SAMPLE_STATS)
        assert "<!DOCTYPE html>" in html

    def test_founder_signature_present(self):
        """Day 3 is founder-led — signed Tiago, not Equipe SmartLic."""
        html = render_trial_engagement_email("Test", SAMPLE_STATS)
        assert "Tiago" in html

    def test_question_subject_in_body(self):
        """Belgray-style direct question hook."""
        html = render_trial_engagement_email("Test", SAMPLE_STATS)
        assert "fazendo sentido" in html.lower()

    def test_contains_buscar_link(self):
        html = render_trial_engagement_email("Test", SAMPLE_STATS)
        assert "/buscar" in html

    def test_founders_link_in_ps(self):
        """Soft cross-sell — Founders link in PS, not primary CTA."""
        html = render_trial_engagement_email("Test", SAMPLE_STATS)
        assert "/fundadores" in html
        assert "997" in html
        assert "P.S." in html

    def test_empty_stats_safe(self):
        html = render_trial_engagement_email("Test", {})
        assert "<!DOCTYPE html>" in html

    def test_unsubscribe_url_passed(self):
        html = render_trial_engagement_email("Test", SAMPLE_STATS, unsubscribe_url=UNSUB_URL)
        assert "unsubscribe" in html

    def test_contains_preheader(self):
        html = render_trial_engagement_email("Test", SAMPLE_STATS)
        assert "display:none" in html


# ============================================================================
# Email #3 — Day 7: Paywall Alert (NEW)
# ============================================================================

class TestPaywallAlertEmail:
    """EMAIL-TRIAL-006 (#1005) Day 7: pricing comparison + Founders cross-sell."""

    def test_renders_without_error(self):
        html = render_trial_paywall_alert_email("Joao", SAMPLE_STATS)
        assert "<!DOCTYPE html>" in html

    def test_pricing_table_present(self):
        """Day 7 shows the math: R$397/mes vs R$997 vitalício."""
        html = render_trial_paywall_alert_email("Test", SAMPLE_STATS)
        assert "397" in html
        assert "997" in html
        assert "4.764" in html  # annual total — Belgray "show me the money"

    def test_founders_cross_sell_primary(self):
        """Day 7 primary CTA is Plano Fundadores."""
        html = render_trial_paywall_alert_email("Test", SAMPLE_STATS)
        assert "/fundadores" in html
        assert "Vitalício" in html or "vitalício" in html

    def test_pro_mensal_secondary(self):
        """Pro mensal is the secondary CTA — still present."""
        html = render_trial_paywall_alert_email("Test", SAMPLE_STATS)
        assert "/planos" in html

    def test_founder_signature_present(self):
        html = render_trial_paywall_alert_email("Test", SAMPLE_STATS)
        assert "Tiago" in html

    def test_seats_remaining_when_provided(self):
        """When seats_remaining > 0, scarcity copy uses concrete number."""
        html = render_trial_paywall_alert_email("Test", SAMPLE_STATS, seats_remaining=12)
        assert "12 vagas" in html

    def test_seats_fallback_when_none(self):
        """Without counter (API fallback) → generic 'vagas limitadas' copy."""
        html = render_trial_paywall_alert_email("Test", SAMPLE_STATS, seats_remaining=None)
        assert "limitadas" in html.lower() or "vitalícias" in html

    def test_empty_stats_safe(self):
        html = render_trial_paywall_alert_email("Test", {})
        assert "<!DOCTYPE html>" in html

    def test_contains_preheader(self):
        html = render_trial_paywall_alert_email("Test", SAMPLE_STATS)
        assert "display:none" in html

    def test_unsubscribe(self):
        html = render_trial_paywall_alert_email("Test", SAMPLE_STATS, unsubscribe_url=UNSUB_URL)
        assert "unsubscribe" in html


# ============================================================================
# Email #4 — Day 10: Valor Acumulado (NEW)
# ============================================================================

class TestValueEmail:
    """EMAIL-TRIAL-006 (#1005) Day 10: Chaperon open loop + Founders cross-sell."""

    def test_renders_without_error(self):
        html = render_trial_value_email("Joao", SAMPLE_STATS)
        assert "<!DOCTYPE html>" in html

    def test_chaperon_open_loop(self):
        """Day 10 uses 'terceira opção' open loop (Chaperon)."""
        html = render_trial_value_email("Test", SAMPLE_STATS)
        assert "terceira opção" in html

    def test_founders_cross_sell_primary(self):
        """Day 10 primary CTA is Plano Fundadores."""
        html = render_trial_value_email("Test", SAMPLE_STATS)
        assert "/fundadores" in html
        assert "997" in html

    def test_pro_mensal_secondary(self):
        html = render_trial_value_email("Test", SAMPLE_STATS)
        assert "/planos" in html

    def test_founder_signature_present(self):
        html = render_trial_value_email("Test", SAMPLE_STATS)
        assert "Tiago" in html

    def test_seats_remaining_when_provided(self):
        html = render_trial_value_email("Test", SAMPLE_STATS, seats_remaining=8)
        assert "8 vagas" in html

    def test_seats_fallback_when_none(self):
        """Without counter → generic copy, no broken {placeholder} in copy text.

        Only checks that template-style placeholders (e.g. {seats_remaining})
        don't leak into the rendered body — CSS rules in <style> blocks
        legitimately contain `{`, so we strip them before scanning.
        """
        html = render_trial_value_email("Test", SAMPLE_STATS, seats_remaining=None)
        import re
        # Strip <style>...</style> blocks; they legitimately contain CSS braces
        body_text = re.sub(r"<style>.*?</style>", "", html, flags=re.DOTALL)
        # Also strip inline style="..." attributes which may carry CSS
        body_text = re.sub(r'style="[^"]*"', "", body_text)
        assert "{seats" not in body_text
        assert "{vagas" not in body_text
        assert "vagas" in html.lower()

    def test_days_remaining_default(self):
        """Default days_remaining=4 (Day 10 trial → 4 days left)."""
        html = render_trial_value_email("Test", SAMPLE_STATS)
        assert "4 dias" in html

    def test_progress_recap_when_value(self):
        """Shows opportunities mapped count when there is usage."""
        html = render_trial_value_email("Test", SAMPLE_STATS)
        assert "47" in html  # opps count

    def test_empty_stats_safe(self):
        html = render_trial_value_email("Test", {})
        assert "<!DOCTYPE html>" in html

    def test_contains_preheader(self):
        html = render_trial_value_email("Test", SAMPLE_STATS)
        assert "display:none" in html

    def test_unsubscribe(self):
        html = render_trial_value_email("Test", SAMPLE_STATS, unsubscribe_url=UNSUB_URL)
        assert "unsubscribe" in html


# ============================================================================
# Email #5 — Day 13: Last Day
# ============================================================================

class TestLastDayEmail:
    """EMAIL-TRIAL-006 (#1005) Day 13 (legacy branch): vira abóbora + 3-col comparison."""

    def test_renders_without_error(self):
        html = render_trial_last_day_email("Joao", SAMPLE_STATS)
        assert "<!DOCTYPE html>" in html

    def test_pumpkin_hook(self):
        """Belgray-style headline: trial 'vira abóbora'."""
        html = render_trial_last_day_email("Test", SAMPLE_STATS)
        assert "abóbora" in html

    def test_three_column_comparison(self):
        """Day 13 shows 3 options side-by-side: cancelar / Pro / Vitalício."""
        html = render_trial_last_day_email("Test", SAMPLE_STATS)
        assert "Cancelar" in html
        assert "Pro mensal" in html
        assert "Vitalício" in html
        # All three prices visible
        assert "R$ 0" in html
        assert "397" in html
        assert "997" in html

    def test_mentions_tomorrow(self):
        html = render_trial_last_day_email("Test", {})
        assert "Amanhã" in html or "amanhã" in html

    def test_founders_cross_sell_block(self):
        """Day 13 has Founders cross-sell block."""
        html = render_trial_last_day_email("Test", SAMPLE_STATS)
        assert "/fundadores" in html

    def test_no_card_charge_language(self):
        """Legacy branch: user has NO card. Must say no charge tomorrow."""
        html = render_trial_last_day_email("Test", SAMPLE_STATS)
        assert "ninguém vai cobrar" in html or "Sem cartão" in html

    def test_founder_signature_present(self):
        html = render_trial_last_day_email("Test", SAMPLE_STATS)
        assert "Tiago" in html

    def test_empty_stats_safe(self):
        html = render_trial_last_day_email("Test", {})
        assert "<!DOCTYPE html>" in html

    def test_contains_preheader(self):
        html = render_trial_last_day_email("Test", SAMPLE_STATS)
        assert "display:none" in html

    def test_seats_remaining_when_provided(self):
        html = render_trial_last_day_email("Test", SAMPLE_STATS, seats_remaining=3)
        assert "3 vagas" in html


# ============================================================================
# Email #5b — Day 13 card-branch: First-charge-tomorrow compliance notice
# (STORY-CONV-003c AC1)
# ============================================================================

SAMPLE_CANCEL_URL = "https://smartlic.tech/conta/cancelar-trial?token=eyJ.sample.jwt"


class TestLastDayCardEmail:
    """STORY-CONV-003c AC1: Email #5b — Day 13 for card-rollout cohort."""

    def _render(self, user_name="Ana", stats=None, cancel_url=SAMPLE_CANCEL_URL):
        return render_trial_last_day_card_email(
            user_name=user_name,
            stats=stats if stats is not None else SAMPLE_STATS,
            charge_date_display="amanhã, 21/04",
            plan_name="SmartLic Pro",
            amount_display="R$ 397/mês",
            cancel_url=cancel_url,
        )

    def test_renders_without_error(self):
        assert "<!DOCTYPE html>" in self._render()

    def test_mentions_auto_charge(self):
        html = self._render()
        assert "cartão" in html or "cartao" in html.replace("ã", "a")
        assert "R$ 397" in html

    def test_cta_is_cancel(self):
        """AC1 compliance: CTA is CANCEL, not 'Assinar agora' (card branch auto-converts)."""
        html = self._render()
        assert "Cancelar minha trial" in html
        # MUST NOT contain the legacy scarcity CTA
        assert "Assinar agora" not in html

    def test_cancel_link_is_embedded(self):
        html = self._render()
        assert SAMPLE_CANCEL_URL in html

    def test_mentions_tomorrow(self):
        html = self._render()
        assert "Amanhã" in html or "amanhã" in html

    def test_does_not_say_access_expires(self):
        """Critical: card-branch users do NOT lose access — the trial auto-converts.
        Legacy copy 'seu acesso expira' must NOT appear for this cohort."""
        html = self._render(stats=ZERO_STATS)
        assert "acesso expira" not in html

    def test_headline_with_stats_shows_opportunities(self):
        html = self._render(stats=SAMPLE_STATS)
        # 47 opportunities from SAMPLE_STATS
        assert "47" in html

    def test_empty_stats_neutral_headline(self):
        html = self._render(stats=ZERO_STATS)
        # Neutral variant — still valid compliance notice
        assert "<!DOCTYPE html>" in html
        assert "Cancelar minha trial" in html
        assert "R$ 397" in html

    def test_preheader_present(self):
        assert "display:none" in self._render()

    def test_token_validity_note_present(self):
        """48h TTL of the JWT is disclosed to the user."""
        html = self._render()
        assert "48 horas" in html or "48h" in html

    def test_signature(self):
        """Brand sign-off present."""
        html = self._render()
        assert "Equipe SmartLic" in html


class TestLastDayCardBranchDispatch:
    """STORY-CONV-003c AC1: dispatch layer must branch on has_payment_method."""

    def test_render_email_uses_card_variant_when_flag_set(self, monkeypatch):
        from services import trial_email_sequence

        captured = {}

        def fake_card(**kwargs):
            captured["variant"] = "card"
            captured["cancel_url"] = kwargs.get("cancel_url")
            return "<html>CARD</html>"

        def fake_legacy(user_name, stats, unsubscribe_url="", seats_remaining=None):
            captured["variant"] = "legacy"
            return "<html>LEGACY</html>"

        # Patch imports inside _render_email via the trial module (local import)
        monkeypatch.setattr(
            "templates.emails.trial.render_trial_last_day_card_email", fake_card
        )
        monkeypatch.setattr(
            "templates.emails.trial.render_trial_last_day_email", fake_legacy
        )
        # Avoid reaching JWT secret config in this unit test
        monkeypatch.setattr(
            "services.trial_cancel_token.create_cancel_trial_token",
            lambda uid: "test.jwt.token",
        )

        subject, html = trial_email_sequence._render_email(
            email_type="last_day",
            user_name="Ana",
            stats=SAMPLE_STATS,
            user_id="user-abc-123",
            has_payment_method=True,
            user_created_at="2026-04-07T10:00:00Z",
        )

        assert captured["variant"] == "card"
        assert "test.jwt.token" in captured["cancel_url"]
        assert "SmartLic Pro" in subject

    def test_render_email_uses_legacy_variant_when_flag_unset(self, monkeypatch):
        from services import trial_email_sequence

        captured = {}

        def fake_card(**kwargs):
            captured["variant"] = "card"
            return "<html>CARD</html>"

        def fake_legacy(user_name, stats, unsubscribe_url="", seats_remaining=None):
            captured["variant"] = "legacy"
            return "<html>LEGACY</html>"

        monkeypatch.setattr(
            "templates.emails.trial.render_trial_last_day_card_email", fake_card
        )
        monkeypatch.setattr(
            "templates.emails.trial.render_trial_last_day_email", fake_legacy
        )

        subject, html = trial_email_sequence._render_email(
            email_type="last_day",
            user_name="Ana",
            stats=SAMPLE_STATS,
            has_payment_method=False,
        )

        assert captured["variant"] == "legacy"

    def test_token_mint_failure_falls_back_to_plain_url(self, monkeypatch):
        """Token minting MUST NOT break the send loop — fall back gracefully."""
        from services import trial_email_sequence

        captured_kwargs = {}

        def fake_card(**kwargs):
            captured_kwargs.update(kwargs)
            return "<html>CARD</html>"

        monkeypatch.setattr(
            "templates.emails.trial.render_trial_last_day_card_email", fake_card
        )

        def broken_mint(uid):
            raise RuntimeError("jwt_secret_missing")

        monkeypatch.setattr(
            "services.trial_cancel_token.create_cancel_trial_token", broken_mint
        )

        subject, html = trial_email_sequence._render_email(
            email_type="last_day",
            user_name="Ana",
            stats=SAMPLE_STATS,
            user_id="user-abc-123",
            has_payment_method=True,
        )

        # Fallback URL still produced — no token param
        assert "/conta/cancelar-trial" in captured_kwargs["cancel_url"]
        assert "token=" not in captured_kwargs["cancel_url"]


class TestFormatChargeDateDisplay:
    """STORY-CONV-003c AC1 helper: trial_end = created_at + 14d."""

    def test_parses_iso_8601_z_suffix(self):
        from services.trial_email_sequence import _format_charge_date_display

        # 2026-04-07 + 14d = 2026-04-21
        assert _format_charge_date_display("2026-04-07T10:00:00Z") == "amanhã, 21/04"

    def test_parses_iso_8601_offset(self):
        from services.trial_email_sequence import _format_charge_date_display

        assert _format_charge_date_display("2026-04-07T10:00:00+00:00") == "amanhã, 21/04"

    def test_falls_back_on_none(self):
        from services.trial_email_sequence import _format_charge_date_display

        assert _format_charge_date_display(None) == "amanhã"

    def test_falls_back_on_garbage(self):
        from services.trial_email_sequence import _format_charge_date_display

        assert _format_charge_date_display("not-an-iso-timestamp") == "amanhã"


# ============================================================================
# Email #6 — Day 16: Expired
# ============================================================================

class TestExpiredEmail:
    """EMAIL-TRIAL-006 (#1005) Day 16 (lapsed): "Errei algo?" founder-led ask."""

    def test_renders_without_error(self):
        html = render_trial_expired_email("Joao", SAMPLE_STATS)
        assert "<!DOCTYPE html>" in html

    def test_errei_algo_question(self):
        """Founder-led headline: 'Errei algo?'."""
        html = render_trial_expired_email("Test", SAMPLE_STATS)
        assert "Errei algo" in html

    def test_invites_one_line_reply(self):
        """Founder asks for 1-line response — primary engagement, not CTA."""
        html = render_trial_expired_email("Test", SAMPLE_STATS)
        assert "1 linha" in html or "uma linha" in html.lower()

    def test_mentions_data_saved(self):
        html = render_trial_expired_email("Test", SAMPLE_STATS)
        assert "30 dias" in html

    def test_coupon_in_ps(self):
        """Day 16 keeps TRIAL_COMEBACK_20 cupom — but in PS, not primary CTA."""
        html = render_trial_expired_email(
            "Test", SAMPLE_STATS,
            coupon_checkout_url="https://smartlic.tech/planos?coupon=TRIAL_COMEBACK_20",
        )
        assert "TRIAL_COMEBACK_20" in html
        assert "coupon=TRIAL_COMEBACK_20" in html
        assert "20% off" in html.lower()
        assert "P.S." in html

    def test_founders_cross_sell_in_ps(self):
        """Day 16 PS also offers Founders alternative."""
        html = render_trial_expired_email("Test", SAMPLE_STATS)
        assert "/fundadores" in html
        assert "997" in html

    def test_founder_signature_present(self):
        html = render_trial_expired_email("Test", SAMPLE_STATS)
        assert "Tiago" in html

    def test_zero_usage_renders(self):
        """Without prior activity still renders without crash."""
        html = render_trial_expired_email("Test", ZERO_STATS)
        assert "<!DOCTYPE html>" in html
        assert "Errei algo" in html

    def test_empty_stats_safe(self):
        html = render_trial_expired_email("Test", {})
        assert "<!DOCTYPE html>" in html

    def test_contains_preheader(self):
        html = render_trial_expired_email("Test", SAMPLE_STATS)
        assert "display:none" in html

    def test_progress_recap_when_opps(self):
        """When user had activity, recap shows opp count."""
        html = render_trial_expired_email("Test", {
            "opportunities_found": 30,
            "pipeline_items_count": 5,
        })
        assert "30" in html
        assert "5" in html


# ============================================================================
# CRIT-044 AC11: Verify legacy cron job is removed
# ============================================================================

class TestLegacyCronRemoved:
    """CRIT-044 AC11: Verify legacy STORY-266 trial reminder system is fully removed."""

    def test_check_trial_reminders_removed(self):
        import cron_jobs
        assert not hasattr(cron_jobs, "check_trial_reminders")

    def test_trial_email_milestones_removed(self):
        import cron_jobs
        assert not hasattr(cron_jobs, "TRIAL_EMAIL_MILESTONES")

    def test_start_trial_reminder_task_removed(self):
        import cron_jobs
        assert not hasattr(cron_jobs, "start_trial_reminder_task")

    def test_new_system_still_exists(self):
        import cron_jobs
        assert hasattr(cron_jobs, "start_trial_sequence_task")

    def test_new_system_respects_feature_flag(self):
        from services.trial_email_sequence import process_trial_emails
        import inspect
        source = inspect.getsource(process_trial_emails)
        assert "TRIAL_EMAILS_ENABLED" in source

    def test_new_system_checks_marketing_emails_enabled(self):
        from services.trial_email_sequence import process_trial_emails
        import inspect
        source = inspect.getsource(process_trial_emails)
        assert "marketing_emails_enabled" in source
