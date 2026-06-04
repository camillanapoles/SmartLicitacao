"""Tests for post-purchase email templates — CONV-011b-2.

Validates all three step templates (delivery, followup, reengagement) with
each delivery_type variant (pdf, csv, email) and edge cases.
"""

from __future__ import annotations

from templates.emails.post_purchase import (
    _price_display,
    _download_button,
    _upsell_box,
    render_post_purchase_delivery,
    render_post_purchase_followup,
    render_post_purchase_reengagement,
)


# ---------------------------------------------------------------------------
# _price_display
# ---------------------------------------------------------------------------


class TestPriceDisplay:
    def test_integer_reais(self):
        assert _price_display(4700) == "R$47"

    def test_decimal_reais(self):
        assert _price_display(2990) == "R$29,90"

    def test_zero(self):
        assert _price_display(0) == "R$0"

    def test_large_value(self):
        assert _price_display(497000) == "R$4.970"


# ---------------------------------------------------------------------------
# _download_button
# ---------------------------------------------------------------------------


class TestDownloadButton:
    def test_renders_download_link(self):
        result = _download_button("https://example.com/file.pdf")
        assert "Baixar agora" in result
        assert "https://example.com/file.pdf" in result

    def test_custom_label(self):
        result = _download_button("https://x.com/f.csv", label="Baixar novamente")
        assert "Baixar novamente" in result


# ---------------------------------------------------------------------------
# _upsell_box
# ---------------------------------------------------------------------------


class TestUpsellBox:
    def test_empty_when_no_product(self):
        result = _upsell_box(upsell_product_name=None)
        assert result == ""

    def test_renders_product_name(self):
        result = _upsell_box(upsell_product_name="Mapa de Subcontratação")
        assert "Mapa de Subcontratação" in result

    def test_renders_price_when_provided(self):
        result = _upsell_box(
            upsell_product_name="Mapa", upsell_product_price=9700
        )
        assert "R$97" in result

    def test_renders_cta_url(self):
        result = _upsell_box(
            upsell_product_name="Mapa",
            upsell_url="https://smartlic.tech/produtos?sku=mapa",
        )
        assert "https://smartlic.tech/produtos?sku=mapa" in result


# ---------------------------------------------------------------------------
# render_post_purchase_delivery
# ---------------------------------------------------------------------------


class TestRenderDelivery:
    def test_pdf_delivery_with_download(self):
        subject, html = render_post_purchase_delivery(
            user_name="João",
            product_name="Relatório de Oportunidade",
            product_sku="relatorio-oportunidade",
            delivery_type="pdf",
            download_url="https://example.com/dl/abc.pdf",
        )
        assert "Relatório de Oportunidade" in subject
        assert "Baixar agora" in html
        assert "https://example.com/dl/abc.pdf" in html
        assert "expira em 30 dias" in html
        assert "João" in html
        # Transactional — no unsubscribe
        assert "Cancelar inscrição" not in html

    def test_csv_delivery_with_download(self):
        subject, html = render_post_purchase_delivery(
            user_name="Maria",
            product_name="Exportação CSV",
            product_sku="export-csv",
            delivery_type="csv",
            download_url="https://example.com/dl/xyz.csv",
        )
        assert "Baixar agora" in html

    def test_email_delivery_no_download_button(self):
        subject, html = render_post_purchase_delivery(
            user_name="Ana",
            product_name="Alerta Semanal",
            product_sku="alerta-semanal",
            delivery_type="email",
            download_url=None,
        )
        assert "foi ativado com sucesso" in html
        assert "Baixar agora" not in html

    def test_unknown_delivery_type_fallback(self):
        subject, html = render_post_purchase_delivery(
            user_name="Test",
            product_name="Produto X",
            product_sku="prod-x",
            delivery_type="unknown",
            download_url=None,
        )
        assert "processado com sucesso" in html

    def test_setor_personalized_cta(self):
        _, html = render_post_purchase_delivery(
            user_name="João",
            product_name="Relatório",
            product_sku="rel",
            delivery_type="pdf",
            download_url="https://x.com/f.pdf",
            setor="ti-software",
        )
        assert "setor=ti-software" in html

    def test_html_escape_user_name(self):
        _, html = render_post_purchase_delivery(
            user_name='João <script>alert("xss")</script>',
            product_name="Relatório",
            product_sku="rel",
            delivery_type="pdf",
            download_url="https://x.com/f.pdf",
        )
        assert "<script>alert" not in html


# ---------------------------------------------------------------------------
# render_post_purchase_followup
# ---------------------------------------------------------------------------


class TestRenderFollowup:
    def test_basic_followup(self):
        subject, html = render_post_purchase_followup(
            user_name="João",
            product_name="Relatório de Oportunidade",
            product_sku="relatorio-oportunidade",
        )
        assert "Relatório de Oportunidade" in subject
        assert "João" in html
        assert "Testar SmartLic grátis" in html
        # Followup is promotional (is_transactional=False) — unsubscribe_url
        # not yet wired; unsubscribe section not rendered without the URL.
        assert "Cancelar inscrição" not in html

    def test_with_upsell(self):
        _, html = render_post_purchase_followup(
            user_name="João",
            product_name="Relatório",
            product_sku="rel",
            upsell_product_name="Mapa de Subcontratação",
            upsell_product_price=9700,
            upsell_product_url="https://smartlic.tech/produtos?sku=mapa",
        )
        assert "Mapa de Subcontratação" in html
        assert "R$97" in html

    def test_without_upsell_no_box(self):
        _, html = render_post_purchase_followup(
            user_name="João",
            product_name="Relatório",
            product_sku="rel",
        )
        assert "💡 Quer ir além?" not in html

    def test_trial_url_includes_utm(self):
        _, html = render_post_purchase_followup(
            user_name="João",
            product_name="Relatório",
            product_sku="rel",
        )
        assert "utm_source=post_purchase" in html
        assert "utm_campaign=followup_48h" in html
        assert "utm_content=rel" in html


# ---------------------------------------------------------------------------
# render_post_purchase_reengagement
# ---------------------------------------------------------------------------


class TestRenderReengagement:
    def test_with_download_url(self):
        subject, html = render_post_purchase_reengagement(
            user_name="João",
            product_name="Relatório",
            product_sku="rel",
            download_url="https://example.com/dl/abc.pdf",
        )
        assert "ainda está disponível" in subject
        assert "Baixar novamente" in html
        assert "https://example.com/dl/abc.pdf" in html
        assert "última mensagem desta sequência" in html

    def test_without_download_url(self):
        _, html = render_post_purchase_reengagement(
            user_name="Maria",
            product_name="Alerta Semanal",
            product_sku="alerta-semanal",
            download_url=None,
        )
        assert "Baixar novamente" not in html
        assert "continua ativo" in html

    def test_with_upsell(self):
        _, html = render_post_purchase_reengagement(
            user_name="João",
            product_name="Relatório",
            product_sku="rel",
            upsell_product_name="Mapa Completo",
            upsell_product_price=14700,
            upsell_product_url="https://smartlic.tech/produtos?sku=mapa",
        )
        assert "Mapa Completo" in html
        assert "R$147" in html

    def test_last_message_notice(self):
        _, html = render_post_purchase_reengagement(
            user_name="Test",
            product_name="Relatório",
            product_sku="rel",
        )
        assert "última mensagem" in html
