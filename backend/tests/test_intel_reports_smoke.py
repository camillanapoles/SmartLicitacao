"""Smoke tests para Intel Reports — validação de go-live (#825).

Cobre os gaps não presentes em test_intel_report_billing.py e test_intel_report_job.py:

1. Segurança: download sem auth → 401
2. Segurança: status sem auth → 401
3. Segurança: usuário B não acessa download de usuário A → 403
4. Segurança: usuário B não acessa status de usuário A → 403
5. Download retorna 400 quando status != "ready"
6. Download funciona end-to-end com PDF bytes via httpx mock
7. Cancelamento Stripe (checkout.session.expired) não cria row em intel_report_purchases
8. Bucket "intel-reports" é validado no WorkerSettings

Testes complementares (NÃO duplicar) em:
- test_intel_report_billing.py — schema, checkout route, webhook idempotência, payment_failed
- test_intel_report_job.py — geração do job, upload, email, refund na 3ª falha, WorkerSettings
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# Helpers compartilhados
# ─────────────────────────────────────────────────────────────────────────────

USER_A = {"id": "user-a-uuid-0001", "email": "usera@smartlic.tech", "role": "authenticated"}
USER_B = {"id": "user-b-uuid-0002", "email": "userb@smartlic.tech", "role": "authenticated"}


def _build_intel_app(user: dict | None = None) -> FastAPI:
    """Monta app isolado com apenas o router intel_reports."""
    from auth import require_auth
    from routes.intel_reports import router

    app = FastAPI()
    app.include_router(router, prefix="/v1")

    if user is not None:
        async def _fake_auth():
            return user
        app.dependency_overrides[require_auth] = _fake_auth

    return app


def _mock_sb_execute_single(data: dict | None):
    """Retorna AsyncMock que simula sb_execute retornando um único objeto."""
    mock = AsyncMock()
    mock.return_value = MagicMock(data=data)
    return mock


# ─────────────────────────────────────────────────────────────────────────────
# 1. Segurança — endpoints exigem autenticação (401)
# ─────────────────────────────────────────────────────────────────────────────

class TestDownloadRequiresAuth:
    """Sem override de auth, os endpoints devem rejeitar requisições não autenticadas."""

    def _unauthenticated_client(self) -> TestClient:
        from routes.intel_reports import router
        from auth import require_auth
        from fastapi import HTTPException

        app = FastAPI()
        app.include_router(router, prefix="/v1")

        # Simula require_auth levantando 401
        async def _raise_401():
            raise HTTPException(status_code=401, detail="Not authenticated")

        app.dependency_overrides[require_auth] = _raise_401
        return TestClient(app, raise_server_exceptions=False)

    def test_download_without_auth_returns_401(self):
        client = self._unauthenticated_client()
        resp = client.get("/v1/intel-reports/some-purchase-id/download")
        assert resp.status_code == 401

    def test_status_without_auth_returns_401(self):
        client = self._unauthenticated_client()
        resp = client.get("/v1/intel-reports/some-purchase-id")
        assert resp.status_code == 401

    def test_list_without_auth_returns_401(self):
        client = self._unauthenticated_client()
        resp = client.get("/v1/intel-reports/")
        assert resp.status_code == 401

    def test_checkout_without_auth_returns_401(self):
        client = self._unauthenticated_client()
        resp = client.post("/v1/intel-reports/checkout", json={
            "product_type": "cnpj",
            "entity_key": "12345678000195",
        })
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# 2. Segurança — ownership: usuário B não acessa dados de usuário A (403)
# ─────────────────────────────────────────────────────────────────────────────

class TestCrossUserAccessForbidden:
    """Usuário B não pode acessar purchase de usuário A — deve receber 403, não 404."""

    # Compra pertence a USER_A
    PURCHASE_OF_A = {
        "id": "purchase-of-a-001",
        "user_id": USER_A["id"],
        "status": "ready",
        "pdf_url": "https://storage.example.com/user-a/purchase-of-a-001.pdf?token=signed",
    }

    def test_user_b_gets_403_on_download_of_user_a_purchase(self):
        """GET /{id}/download de usuário B para compra de usuário A → 403."""
        # Autentica como USER_B
        app = _build_intel_app(user=USER_B)
        client = TestClient(app, raise_server_exceptions=False)

        # sb_execute retorna a compra de USER_A (existe no banco mas dono é A)
        with patch("routes.intel_reports.sb_execute", _mock_sb_execute_single(self.PURCHASE_OF_A)):
            resp = client.get(f"/v1/intel-reports/{self.PURCHASE_OF_A['id']}/download")

        assert resp.status_code == 403, (
            f"Esperado 403 (acesso negado), obtido {resp.status_code}. "
            "O endpoint deve distinguir '404 não existe' de '403 não é seu'."
        )

    def test_user_b_gets_403_on_status_of_user_a_purchase(self):
        """GET /{id} de usuário B para compra de usuário A → 403."""
        purchase_with_expires = {
            **self.PURCHASE_OF_A,
            "expires_at": "2026-12-31T23:59:59Z",
        }
        app = _build_intel_app(user=USER_B)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("routes.intel_reports.sb_execute", _mock_sb_execute_single(purchase_with_expires)):
            resp = client.get(f"/v1/intel-reports/{self.PURCHASE_OF_A['id']}")

        assert resp.status_code == 403

    def test_user_a_can_access_own_purchase(self):
        """GET /{id} de usuário A para sua própria compra → 200."""
        purchase = {
            "id": "purchase-of-a-001",
            "user_id": USER_A["id"],
            "status": "pending",
            "pdf_url": None,
            "expires_at": None,
        }
        app = _build_intel_app(user=USER_A)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("routes.intel_reports.sb_execute", _mock_sb_execute_single(purchase)):
            resp = client.get("/v1/intel-reports/purchase-of-a-001")

        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_nonexistent_purchase_returns_404(self):
        """GET /{id} de compra inexistente → 404."""
        app = _build_intel_app(user=USER_A)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("routes.intel_reports.sb_execute", _mock_sb_execute_single(None)):
            resp = client.get("/v1/intel-reports/nonexistent-id")

        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 3. Download: status != "ready" → 400
# ─────────────────────────────────────────────────────────────────────────────

class TestDownloadStatusGuard:
    """Download só deve funcionar quando status == 'ready'."""

    @pytest.mark.parametrize("status", ["pending", "generating", "failed"])
    def test_download_non_ready_status_returns_400(self, status: str):
        purchase = {
            "id": "purchase-a-001",
            "user_id": USER_A["id"],
            "status": status,
            "pdf_url": None,
        }
        app = _build_intel_app(user=USER_A)
        client = TestClient(app, raise_server_exceptions=False)

        with patch("routes.intel_reports.sb_execute", _mock_sb_execute_single(purchase)):
            resp = client.get("/v1/intel-reports/purchase-a-001/download")

        assert resp.status_code == 400, (
            f"Status '{status}' deveria retornar 400, obtido {resp.status_code}"
        )
        assert status in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# 4. Download end-to-end: PDF retornado via streaming (mock httpx)
# ─────────────────────────────────────────────────────────────────────────────

class TestDownloadEndToEnd:
    """Download com compra ready retorna PDF válido (bytes) via streaming."""

    PDF_BYTES = b"%PDF-1.4 smartlic-test-fixture"

    READY_PURCHASE = {
        "id": "purchase-a-ready",
        "user_id": USER_A["id"],
        "status": "ready",
        "pdf_url": "https://storage.example.com/signed?token=abc",
    }

    def test_download_ready_purchase_returns_pdf(self):
        app = _build_intel_app(user=USER_A)
        client = TestClient(app, raise_server_exceptions=False)

        # Mock httpx.AsyncClient para evitar chamada real ao storage
        mock_response = MagicMock()
        mock_response.content = self.PDF_BYTES
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch("routes.intel_reports.sb_execute", _mock_sb_execute_single(self.READY_PURCHASE)), \
             patch("httpx.AsyncClient", return_value=mock_http_client):
            resp = client.get("/v1/intel-reports/purchase-a-ready/download")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "attachment" in resp.headers.get("content-disposition", "")
        assert resp.content == self.PDF_BYTES

    def test_download_pdf_starts_with_pdf_magic_bytes(self):
        """PDF retornado começa com %PDF (magic bytes do formato PDF)."""
        app = _build_intel_app(user=USER_A)
        client = TestClient(app, raise_server_exceptions=False)

        mock_response = MagicMock()
        mock_response.content = self.PDF_BYTES
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch("routes.intel_reports.sb_execute", _mock_sb_execute_single(self.READY_PURCHASE)), \
             patch("httpx.AsyncClient", return_value=mock_http_client):
            resp = client.get("/v1/intel-reports/purchase-a-ready/download")

        assert resp.content[:4] == b"%PDF"

    def test_download_storage_unavailable_returns_502(self):
        """Falha ao buscar PDF do storage → 502 (não expõe detalhes internos)."""
        import httpx

        app = _build_intel_app(user=USER_A)
        client = TestClient(app, raise_server_exceptions=False)

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "404 not found",
                request=MagicMock(),
                response=MagicMock(status_code=404),
            )
        )

        with patch("routes.intel_reports.sb_execute", _mock_sb_execute_single(self.READY_PURCHASE)), \
             patch("httpx.AsyncClient", return_value=mock_http_client):
            resp = client.get("/v1/intel-reports/purchase-a-ready/download")

        assert resp.status_code == 502


# ─────────────────────────────────────────────────────────────────────────────
# 5. Cancelamento Stripe: nenhuma row em intel_report_purchases
# ─────────────────────────────────────────────────────────────────────────────

class TestStripeCheckoutCancellation:
    """
    Quando o usuário cancela o Stripe Checkout (checkout.session.expired ou
    checkout sem mode=payment+product_type), nenhuma row deve ser inserida em
    intel_report_purchases.

    O comportamento é garantido pelo dispatcher: o handler Intel Report só é
    chamado para mode=payment com metadata.product_type presente.
    A ausência de checkout.session.expired handler é o comportamento esperado
    (no-op do lado do SmartLic — Stripe não processa pagamento, sem fulfillment).
    """

    @pytest.mark.asyncio
    async def test_subscription_mode_does_not_create_intel_report_purchase(self):
        """
        checkout.session.completed mode=subscription NÃO cria row em intel_report_purchases.
        Complementar ao TestCheckoutHandlerModeBranching em test_intel_report_billing.py.
        """
        from webhooks.handlers.checkout import handle_checkout_session_completed

        session = MagicMock()
        session.get = lambda key, default=None: {
            "mode": "subscription",  # NOT payment
            "metadata": {"plan_id": "smartlic_pro"},
            "payment_status": "paid",
            "subscription": "sub_test",
            "customer": "cus_test",
        }.get(key, default)
        event = MagicMock()
        event.data = MagicMock()
        event.data.object = session

        sb = MagicMock()
        intel_chain = MagicMock()
        sb.table.return_value = intel_chain

        with patch("webhooks.handlers.checkout.handle_intel_report_checkout_completed",
                   new_callable=AsyncMock) as mock_intel, \
             patch("webhooks.handlers.checkout.resolve_user_id", return_value=None):
            await handle_checkout_session_completed(sb, event)

        # Handler intel nunca chamado → nenhum insert em intel_report_purchases
        mock_intel.assert_not_called()

    @pytest.mark.asyncio
    async def test_payment_mode_without_product_type_not_dispatched_to_intel(self):
        """
        checkout.session.completed mode=payment sem metadata.product_type
        (por ex: Founders Plan) NÃO aciona handle_intel_report_checkout_completed.
        """
        from webhooks.handlers.checkout import handle_checkout_session_completed

        session = MagicMock()
        session.get = lambda key, default=None: {
            "mode": "payment",
            "metadata": {"source": "founding"},  # sem product_type
            "payment_status": "paid",
        }.get(key, default)
        event = MagicMock()
        event.data = MagicMock()
        event.data.object = session

        sb = MagicMock()

        with patch("webhooks.handlers.checkout.handle_intel_report_checkout_completed",
                   new_callable=AsyncMock) as mock_intel, \
             patch("webhooks.handlers.founding.mark_founding_lead_completed"):
            await handle_checkout_session_completed(sb, event)

        mock_intel.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# 6. Infra: bucket "intel-reports" referenciado no job
# ─────────────────────────────────────────────────────────────────────────────

class TestIntelReportInfra:
    """
    Valida pré-requisitos de infra que podem ser checados em tempo de módulo.
    Complementar ao test_worker_settings_registers_generate_intel_report em test_intel_report_job.py.
    """

    def test_job_uses_intel_reports_bucket(self):
        """O job ARQ referencia o bucket 'intel-reports' no upload."""
        import ast
        import pathlib

        jobs_path = pathlib.Path(__file__).parent.parent / "jobs" / "queue" / "jobs.py"
        source = jobs_path.read_text()

        assert "intel-reports" in source, (
            "O bucket 'intel-reports' deve estar referenciado em jobs/queue/jobs.py. "
            "Verifique a função _upload_intel_report_pdf."
        )

    def test_generate_intel_report_is_in_worker_functions(self):
        """generate_intel_report está registrado em WorkerSettings.functions.

        Nota: após wrapping pelo ARQ, as funções são objetos arq.Function.
        Verificamos via repr/str ou pelo nome do coroutine subjacente.
        O test_intel_report_job.py faz a asserção canônica via fn.__name__.
        """
        from jobs.queue.config import WorkerSettings

        # ARQ wraps functions in Function objects; check via string representation
        functions_repr = repr(WorkerSettings.functions)
        assert "generate_intel_report" in functions_repr, (
            "generate_intel_report deve estar em WorkerSettings.functions para o worker processar jobs de Intel Report. "
            f"WorkerSettings.functions repr: {functions_repr[:200]}"
        )

    def test_intel_report_prices_match_expected_values(self):
        """Preços do Intel Report: CNPJ=R$197 (19700 centavos), Setor/UF=R$147 (14700 centavos)."""
        from schemas.intel_report import INTEL_REPORT_PRICES

        assert INTEL_REPORT_PRICES["cnpj"] == 19700, "CNPJ report deve custar R$197 (19700 centavos)"
        assert INTEL_REPORT_PRICES["sector_uf"] == 14700, "Setor/UF report deve custar R$147 (14700 centavos)"
