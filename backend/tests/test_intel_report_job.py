from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, db, table_name: str, operation: str = "select", values=None):
        self.db = db
        self.table_name = table_name
        self.operation = operation
        self.values = values or {}
        self.filters: dict[str, str] = {}

    def select(self, *_args, **_kwargs):
        self.operation = "select"
        return self

    def update(self, values):
        self.operation = "update"
        self.values = values
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def single(self):
        return self

    def execute(self):
        if self.table_name == "intel_report_purchases":
            purchase_id = self.filters.get("id")
            if self.operation == "update":
                self.db.updates.append(dict(self.values))
                self.db.purchases[purchase_id].update(self.values)
                return FakeResult([self.db.purchases[purchase_id]])
            row = self.db.purchases.get(purchase_id)
            return FakeResult(row)

        if self.table_name == "profiles":
            return FakeResult(self.db.profiles.get(self.filters.get("id")))

        raise AssertionError(f"unexpected table {self.table_name}")


class FakeBucket:
    def __init__(self, upload_error: Exception | None = None):
        self.upload_error = upload_error
        self.upload_calls = []
        self.signed_calls = []

    def upload(self, **kwargs):
        self.upload_calls.append(kwargs)
        if self.upload_error:
            raise self.upload_error
        return {"path": kwargs["path"]}

    def create_signed_url(self, **kwargs):
        self.signed_calls.append(kwargs)
        return {"signedURL": f"https://storage.test/{kwargs['path']}?token=signed"}


class FakeStorage:
    def __init__(self, bucket: FakeBucket):
        self.bucket = bucket

    def from_(self, bucket_name):
        assert bucket_name == "intel-reports"
        return self.bucket


class FakeSupabase:
    def __init__(
        self,
        purchase: dict,
        profile: dict | None = None,
        bucket: FakeBucket | None = None,
    ):
        self.purchases = {purchase["id"]: dict(purchase)}
        self.profiles = {purchase["user_id"]: profile or {
            "email": "ana@example.com",
            "full_name": "Ana Cliente",
        }}
        self.storage = FakeStorage(bucket or FakeBucket())
        self.updates: list[dict] = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def _purchase(**overrides):
    base = {
        "id": "purchase-001",
        "user_id": "user-001",
        "product_type": "cnpj",
        "entity_key": "12345678000195",
        "status": "pending",
        "pdf_url": None,
        "stripe_payment_intent_id": "pi_123",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_generate_intel_report_success_uploads_updates_ready_and_emails():
    from jobs.queue.jobs import generate_intel_report

    db = FakeSupabase(_purchase())
    pdf_bytes = b"%PDF-1.4 smartlic"

    with patch("supabase_client.get_supabase", return_value=db), \
         patch("jobs.queue.jobs._generate_cnpj_report_pdf", new=AsyncMock(return_value=pdf_bytes)), \
         patch("email_service.send_intel_report_ready", return_value="email-123") as mock_email, \
         patch("analytics_events.track_event") as mock_track:
        result = await generate_intel_report({}, "purchase-001")

    assert result["status"] == "ready"
    assert db.purchases["purchase-001"]["status"] == "ready"
    assert db.purchases["purchase-001"]["pdf_url"].startswith("https://storage.test/purchase-001.pdf")
    assert db.storage.bucket.upload_calls == [{
        "path": "purchase-001.pdf",
        "file": pdf_bytes,
        "file_options": {"content-type": "application/pdf", "upsert": "false"},
    }]
    mock_email.assert_called_once()
    mock_track.assert_called_once()


@pytest.mark.asyncio
async def test_generate_intel_report_third_failure_marks_failed_and_refunds():
    from jobs.queue.jobs import generate_intel_report

    db = FakeSupabase(_purchase())

    with patch("supabase_client.get_supabase", return_value=db), \
         patch("jobs.queue.jobs._generate_cnpj_report_pdf", new=AsyncMock(side_effect=RuntimeError("pdf failed"))), \
         patch("stripe.Refund.create", return_value=SimpleNamespace(id="re_123")) as mock_refund, \
         patch("email_service.send_email_async") as mock_failed_email:
        result = await generate_intel_report({"job_try": 3}, "purchase-001")

    assert result["status"] == "failed"
    assert result["refunded"] is True
    assert db.purchases["purchase-001"]["status"] == "failed"
    mock_refund.assert_called_once()
    mock_failed_email.assert_called_once()


@pytest.mark.asyncio
async def test_generate_intel_report_duplicate_storage_upload_is_idempotent():
    from jobs.queue.jobs import generate_intel_report

    bucket = FakeBucket(upload_error=RuntimeError("resource already exists"))
    db = FakeSupabase(_purchase(), bucket=bucket)

    with patch("supabase_client.get_supabase", return_value=db), \
         patch("jobs.queue.jobs._generate_cnpj_report_pdf", new=AsyncMock(return_value=b"%PDF duplicate")), \
         patch("email_service.send_intel_report_ready", return_value="email-123"):
        result = await generate_intel_report({}, "purchase-001")

    assert result["status"] == "ready"
    assert db.purchases["purchase-001"]["status"] == "ready"
    assert len(bucket.upload_calls) == 1
    assert len(bucket.signed_calls) == 1


def test_worker_settings_registers_generate_intel_report():
    from jobs.queue.config import WorkerSettings

    assert any(fn.__name__ == "generate_intel_report" for fn in WorkerSettings.functions)
