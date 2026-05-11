"""
Tests for WebhookHandler ABC base + registry (REF-MON-002).

Coverage:
- WebhookHandler.handle() invokes process() exactly once for a new event.
- WebhookHandler.handle() skips process() on idempotency replay (2nd call
  with same key returns immediately, no double side-effect).
- HANDLERS_REGISTRY is populated by the @webhook_handler decorator.
- idempotency_key() default returns event.id; subclass override works.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest

from webhooks.handlers._base import (
    HANDLERS_REGISTRY,
    WebhookHandler,
    webhook_handler,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(event_id: str = "evt_test_base_001", event_type: str = "test.event"):
    event = Mock()
    event.id = event_id
    event.type = event_type
    event.data = Mock()
    event.data.object = {"id": event_id}
    return event


class _UpsertResult:
    def __init__(self, data):
        self.data = data


def _make_sb(claim_results: list):
    """Build a mock Supabase client where each call to
    sb.table('stripe_webhook_events').upsert(...).execute() returns the next
    item from ``claim_results`` (a list of _UpsertResult).
    """
    iterator = iter(claim_results)

    def _execute_side_effect(*args, **kwargs):
        return next(iterator)

    table_mock = MagicMock()
    table_mock.upsert.return_value.execute.side_effect = _execute_side_effect

    sb = MagicMock()
    sb.table.return_value = table_mock
    return sb


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_populated_by_decorator():
    """@webhook_handler must instantiate the class and register it."""

    sentinel_type = "test.registry.populated"

    @webhook_handler(sentinel_type)
    class _Handler(WebhookHandler):
        event_type = sentinel_type

        async def process(self, sb, event):
            return None

    assert sentinel_type in HANDLERS_REGISTRY
    assert isinstance(HANDLERS_REGISTRY[sentinel_type], _Handler)

    # cleanup so we don't pollute the global registry for other tests
    del HANDLERS_REGISTRY[sentinel_type]


def test_decorator_rejects_non_subclass():
    with pytest.raises(TypeError):

        @webhook_handler("test.not.a.subclass")
        class _NotAHandler:  # noqa: D401
            pass


# ---------------------------------------------------------------------------
# idempotency_key
# ---------------------------------------------------------------------------


def test_idempotency_key_default_returns_event_id():
    class _H(WebhookHandler):
        event_type = "x"

        async def process(self, sb, event):
            pass

    h = _H()
    event = _make_event(event_id="evt_KEY_abc")
    assert h.idempotency_key(event) == "evt_KEY_abc"


def test_idempotency_key_override():
    class _H(WebhookHandler):
        event_type = "x"

        def idempotency_key(self, event):
            return event.data.object["id"] + ":custom"

        async def process(self, sb, event):
            pass

    h = _H()
    event = _make_event(event_id="evt_outer")
    event.data.object = {"id": "biz_inner"}
    assert h.idempotency_key(event) == "biz_inner:custom"


# ---------------------------------------------------------------------------
# handle() template method — idempotency replay
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_runs_process_once_for_new_event():
    """First call: upsert returns data (claimed), process() must run."""

    calls = []

    class _H(WebhookHandler):
        event_type = "test.new.event"

        async def process(self, sb, event):
            calls.append(event.id)

    sb = _make_sb([_UpsertResult([{"id": "evt_new_001"}])])
    h = _H()
    event = _make_event(event_id="evt_new_001", event_type="test.new.event")

    await h.handle(sb, event)

    assert calls == ["evt_new_001"], "process() should run exactly once for a new event"


@pytest.mark.asyncio
async def test_handle_skips_process_on_replay():
    """Second call with same key: upsert returns empty data (ON CONFLICT),
    process() must NOT run.
    """

    calls = []

    class _H(WebhookHandler):
        event_type = "test.replay.event"

        async def process(self, sb, event):
            calls.append(event.id)

    # Two sequential events with same id:
    # - 1st claim: returns data (new) → process runs
    # - 2nd claim: returns empty (duplicate) → process skipped
    sb = _make_sb(
        [
            _UpsertResult([{"id": "evt_replay_001"}]),
            _UpsertResult([]),  # ON CONFLICT DO NOTHING — empty result
        ]
    )
    h = _H()
    event = _make_event(event_id="evt_replay_001", event_type="test.replay.event")

    await h.handle(sb, event)
    await h.handle(sb, event)

    assert calls == ["evt_replay_001"], (
        "process() must run once across 2 deliveries of the same event_id "
        f"(got {calls})"
    )


@pytest.mark.asyncio
async def test_handle_proceeds_when_idempotency_claim_raises():
    """If the DB claim raises, fail open and still process (dispatcher is the
    authoritative gate; in-handler claim is best-effort).
    """

    calls = []

    class _H(WebhookHandler):
        event_type = "test.failopen.event"

        async def process(self, sb, event):
            calls.append(event.id)

    sb = MagicMock()
    # Make the upsert.execute() raise
    sb.table.return_value.upsert.return_value.execute.side_effect = RuntimeError("db down")

    h = _H()
    event = _make_event(event_id="evt_failopen_001", event_type="test.failopen.event")

    await h.handle(sb, event)

    assert calls == ["evt_failopen_001"], (
        "process() must still run when idempotency claim raises (fail-open)"
    )


@pytest.mark.asyncio
async def test_handle_skips_process_when_idempotency_key_empty_but_claim_returns_empty():
    """Edge: if idempotency_key returns empty string, we cannot dedup —
    process() should still run (allow path).
    """

    calls = []

    class _H(WebhookHandler):
        event_type = "test.empty.key"

        def idempotency_key(self, event):
            return ""

        async def process(self, sb, event):
            calls.append("ran")

    sb = MagicMock()
    h = _H()
    await h.handle(sb, _make_event())

    assert calls == ["ran"]
    # sb.table should not have been called (no claim attempted on empty key)
    sb.table.assert_not_called()
