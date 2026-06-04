"""jobs.queue.jobs — All ARQ job function implementations."""
from __future__ import annotations

import json
import logging
import time
import asyncio
from datetime import datetime, timezone
from typing import Any

from supabase_client import sb_execute
from templates.emails.base import FRONTEND_URL

logger = logging.getLogger(__name__)

INTEL_REPORT_BUCKET = "intel-reports"
INTEL_REPORT_SIGNED_URL_TTL_SECONDS = 60 * 60 * 24 * 30
INTEL_REPORT_RETRY_BACKOFF_SECONDS = (30, 60, 120)


def _sentry_breadcrumb(message: str, **data: Any) -> None:
    try:
        import sentry_sdk
        sentry_sdk.add_breadcrumb(
            category="intel_report_job",
            message=message,
            level="info",
            data=data,
        )
    except Exception:
        pass


def _track_post_purchase_event(
    event_name: str,
    user_id: str,
    properties: dict | None = None,
) -> None:
    """Fire-and-forget Mixpanel event for post-purchase analytics (CONV-011b-3).

    Never raises — tracking failures are logged and must not block the main job.
    """
    try:
        from analytics_events import track_event

        track_event(
            event_name=event_name,
            properties={
                **(properties or {}),
                "user_id": user_id,
                "source": "post_purchase_sequence",
            },
        )
    except Exception as exc:
        logger.warning(
            "Failed to track post-purchase event %s for user=%s: %s",
            event_name, user_id, exc,
        )


async def _execute_supabase(query: Any, category: str = "read") -> Any:
    return await sb_execute(query, category=category)


def _first_row(result: Any) -> dict | None:
    data = getattr(result, "data", None)
    if isinstance(data, list):
        return data[0] if data else None
    return data if isinstance(data, dict) else None


def _signed_url_from_response(response: Any) -> str:
    if isinstance(response, dict):
        return (
            response.get("signedURL")
            or response.get("signedUrl")
            or response.get("signed_url")
            or response.get("url")
            or ""
        )
    return (
        getattr(response, "signedURL", "")
        or getattr(response, "signedUrl", "")
        or getattr(response, "signed_url", "")
        or getattr(response, "url", "")
    )


async def _fetch_intel_report_purchase(db: Any, purchase_id: str) -> dict | None:
    result = await _execute_supabase(
        db.table("intel_report_purchases")
        .select(
            "id, user_id, product_type, entity_key, status, pdf_url, "
            "stripe_payment_intent_id"
        )
        .eq("id", purchase_id)
        .single()
    )
    return _first_row(result)


async def _fetch_profile(db: Any, user_id: str) -> dict | None:
    result = await _execute_supabase(
        db.table("profiles")
        .select("email, full_name")
        .eq("id", user_id)
        .single()
    )
    return _first_row(result)


async def _update_intel_report_purchase(
    db: Any,
    purchase_id: str,
    values: dict[str, Any],
) -> None:
    payload = {
        **values,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await _execute_supabase(
            db.table("intel_report_purchases")
            .update(payload)
            .eq("id", purchase_id),
            category="write",
        )
    except Exception as exc:
        if "updated_at" not in str(exc):
            raise
        fallback_payload = dict(values)
        await _execute_supabase(
            db.table("intel_report_purchases")
            .update(fallback_payload)
            .eq("id", purchase_id),
            category="write",
        )


async def _generate_cnpj_report_pdf(db: Any, entity_key: str) -> bytes:
    result = await _execute_supabase(
        db.rpc(
            "cnpj_supplier_intel",
            {"p_cnpj": entity_key, "p_window_months": 36},
        ),
        category="rpc",
    )
    payload = getattr(result, "data", None)
    if not payload:
        raise ValueError("cnpj_supplier_intel returned no data")

    from pdf_generator_intel_report import generate_cnpj_report

    buffer = generate_cnpj_report(payload)
    return buffer.getvalue() if hasattr(buffer, "getvalue") else buffer.read()


async def _generate_sector_uf_report_pdf(db: Any, entity_key: str) -> bytes:
    try:
        from pdf_generator_sector_uf_report import generate_sector_uf_report
    except ImportError as exc:
        raise NotImplementedError("sector_uf report generator is not available") from exc

    buffer = generate_sector_uf_report(db=db, entity_key=entity_key)
    if asyncio.iscoroutine(buffer):
        buffer = await buffer
    return buffer.getvalue() if hasattr(buffer, "getvalue") else buffer.read()


async def _generate_intel_report_pdf(db: Any, purchase: dict) -> bytes:
    product_type = purchase.get("product_type")
    entity_key = purchase.get("entity_key") or ""
    if product_type == "cnpj":
        return await asyncio.wait_for(
            _generate_cnpj_report_pdf(db, entity_key),
            timeout=90,
        )
    if product_type == "sector_uf":
        return await asyncio.wait_for(
            _generate_sector_uf_report_pdf(db, entity_key),
            timeout=90,
        )
    raise ValueError(f"unsupported intel report product_type={product_type!r}")


def _is_duplicate_storage_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(token in message for token in ("already exists", "duplicate", "exists"))


async def _upload_intel_report_pdf(db: Any, purchase_id: str, user_id: str, pdf_bytes: bytes) -> str:
    """Upload PDF to Storage at {user_id}/{purchase_id}.pdf and return a 30-day signed URL.

    Path structure aligns with the Storage RLS policy that allows authenticated
    users to SELECT only files under their own {user_id}/ prefix
    (migration 20260507110000_create_intel_reports_bucket.sql).
    """
    def _upload_and_sign() -> str:
        storage = db.storage
        bucket = storage.from_(INTEL_REPORT_BUCKET)
        # Folder prefix ensures RLS policy "users_read_own_intel_reports" works correctly.
        path = f"{user_id}/{purchase_id}.pdf"
        try:
            bucket.upload(
                path=path,
                file=pdf_bytes,
                file_options={"content-type": "application/pdf", "upsert": "false"},
            )
        except Exception as exc:
            if not _is_duplicate_storage_error(exc):
                raise
            logger.info("Intel Report PDF already exists in storage: %s", path)

        signed_response = bucket.create_signed_url(
            path=path,
            expires_in=INTEL_REPORT_SIGNED_URL_TTL_SECONDS,
        )
        signed_url = _signed_url_from_response(signed_response)
        if not signed_url:
            raise RuntimeError("Supabase Storage returned empty signed URL")
        return signed_url

    return await asyncio.wait_for(asyncio.to_thread(_upload_and_sign), timeout=10)


def _intel_report_product_name(product_type: str) -> str:
    if product_type == "sector_uf":
        return "Relatório Setor/UF SmartLic"
    return "Raio-X do Concorrente SmartLic"


def _refund_intel_report_purchase(purchase: dict) -> bool:
    payment_intent = purchase.get("stripe_payment_intent_id")
    if not payment_intent:
        logger.warning("Intel Report refund skipped: purchase has no payment_intent")
        return False
    try:
        import os
        import stripe as stripe_lib

        stripe_lib.Refund.create(
            payment_intent=payment_intent,
            reason="requested_by_customer",
            metadata={
                "source": "intel_report_job",
                "purchase_id": purchase.get("id", ""),
            },
            api_key=os.getenv("STRIPE_SECRET_KEY") or None,
        )
        return True
    except Exception as exc:
        logger.error("Intel Report refund failed: purchase_id=%s error=%s", purchase.get("id"), exc)
        return False


def _send_intel_report_failed_email(profile: dict | None, purchase: dict) -> None:
    if not profile or not profile.get("email"):
        return
    try:
        from templates.emails.base import email_base
        from email_service import send_email_async

        body = """
        <h1 style="color: #333; font-size: 24px; margin: 0 0 16px;">
          Não conseguimos gerar seu relatório
        </h1>
        <p style="color: #555; font-size: 16px; line-height: 1.6;">
          Tivemos uma falha ao gerar o relatório comprado. Já iniciamos o
          reembolso automático e, se precisar, responda este email para falar
          com nosso suporte.
        </p>
        """
        send_email_async(
            to=profile["email"],
            subject="Não conseguimos gerar seu relatório — SmartLic",
            html=email_base(
                title="Não conseguimos gerar seu relatório — SmartLic",
                body_html=body,
                is_transactional=True,
            ),
            reply_to="tiago.sasaki@gmail.com",
            tags=[
                {"name": "category", "value": "intel_report"},
                {"name": "status", "value": "failed"},
                {"name": "purchase_id", "value": str(purchase.get("id", ""))[:32]},
            ],
        )
    except Exception:
        logger.exception("Intel Report failure email failed: purchase_id=%s", purchase.get("id"))


async def generate_intel_report(ctx: dict, purchase_id: str) -> dict:
    """Generate, upload, and deliver an Intel Report PDF for a paid purchase."""
    start = time.monotonic()
    attempt = int(ctx.get("job_try") or 1) if isinstance(ctx, dict) else 1

    from supabase_client import get_supabase
    from metrics import INTEL_REPORT_GENERATED

    db = get_supabase()
    _sentry_breadcrumb("lookup", purchase_id=purchase_id, attempt=attempt)
    purchase = await _fetch_intel_report_purchase(db, purchase_id)
    if not purchase:
        INTEL_REPORT_GENERATED.labels(product_type="unknown", status="failed").inc()
        return {"status": "not_found", "purchase_id": purchase_id}

    product_type = purchase.get("product_type") or "unknown"
    if purchase.get("status") == "ready" and purchase.get("pdf_url"):
        return {"status": "already_ready", "purchase_id": purchase_id}
    if purchase.get("status") != "pending":
        return {
            "status": "skipped",
            "purchase_id": purchase_id,
            "purchase_status": purchase.get("status"),
        }

    profile = await _fetch_profile(db, purchase.get("user_id", ""))

    try:
        await _update_intel_report_purchase(db, purchase_id, {"status": "generating"})

        _sentry_breadcrumb("generation", purchase_id=purchase_id, product_type=product_type)
        pdf_bytes = await _generate_intel_report_pdf(db, purchase)

        _sentry_breadcrumb(
            "upload",
            purchase_id=purchase_id,
            product_type=product_type,
            pdf_size_bytes=len(pdf_bytes),
        )
        signed_url = await _upload_intel_report_pdf(db, purchase_id, purchase.get("user_id", ""), pdf_bytes)

        await _update_intel_report_purchase(
            db,
            purchase_id,
            {"status": "ready", "pdf_url": signed_url},
        )

        _sentry_breadcrumb("email", purchase_id=purchase_id, product_type=product_type)
        if profile and profile.get("email"):
            from email_service import send_intel_report_ready

            send_intel_report_ready(
                user_email=profile["email"],
                name=profile.get("full_name") or profile["email"].split("@")[0],
                pdf_url=signed_url,
                product_name=_intel_report_product_name(product_type),
                purchase_id=purchase_id,
            )

        duration_ms = int((time.monotonic() - start) * 1000)
        INTEL_REPORT_GENERATED.labels(product_type=product_type, status="success").inc()
        try:
            from analytics_events import track_event
            track_event(
                "intel_report_generated",
                {
                    "user_id": purchase.get("user_id"),
                    "product_type": product_type,
                    "entity_key": purchase.get("entity_key"),
                    "generation_time_ms": duration_ms,
                    "pdf_size_bytes": len(pdf_bytes),
                },
            )
        except Exception:
            pass

        return {
            "status": "ready",
            "purchase_id": purchase_id,
            "product_type": product_type,
            "pdf_size_bytes": len(pdf_bytes),
            "generation_time_ms": duration_ms,
        }
    except Exception as exc:
        logger.error(
            "Intel Report generation failed: purchase_id=%s attempt=%s error=%s",
            purchase_id,
            attempt,
            exc,
            exc_info=True,
        )
        await _update_intel_report_purchase(db, purchase_id, {"status": "pending"})

        if attempt < 3:
            try:
                from arq import Retry
                raise Retry(defer=INTEL_REPORT_RETRY_BACKOFF_SECONDS[attempt - 1]) from exc
            except ImportError:
                raise exc

        await _update_intel_report_purchase(db, purchase_id, {"status": "failed"})
        INTEL_REPORT_GENERATED.labels(product_type=product_type, status="failed").inc()
        refunded = _refund_intel_report_purchase(purchase)
        if refunded:
            INTEL_REPORT_GENERATED.labels(product_type=product_type, status="refunded").inc()
        _send_intel_report_failed_email(profile, purchase)
        return {
            "status": "failed",
            "purchase_id": purchase_id,
            "product_type": product_type,
            "refunded": refunded,
            "error": str(exc),
        }


async def send_founders_welcome(ctx: dict, user_email: str, user_name: str) -> dict:
    """ARQ job: send founders welcome email + record is_founder in Mixpanel.

    Idempotency is enforced inside send_founders_welcome_email() via
    founding_leads.welcome_sent_at — safe to enqueue more than once.

    Args:
        ctx: ARQ worker context (unused, kept for ARQ signature compatibility).
        user_email: Founder email address (key in founding_leads).
        user_name: Display name from profiles.full_name or email prefix.

    Returns:
        Dict with status and email_id.
    """
    logger.info("send_founders_welcome: start email=%s", user_email)
    try:
        from email_service import send_founders_welcome_email

        email_id = send_founders_welcome_email(user_email=user_email, user_name=user_name)
    except Exception as exc:
        logger.error("send_founders_welcome: email send failed email=%s: %s", user_email, exc)
        return {"status": "error", "error": str(exc), "email_id": None}

    if email_id:
        # Mixpanel people.set — only after confirmed send, best-effort, never blocks the job
        try:
            import os
            if os.getenv("MIXPANEL_TOKEN", "").strip():
                from analytics_events import set_user_profile

                set_user_profile(user_email, {"is_founder": True, "plan": "founders"})
        except Exception as exc:
            logger.warning("send_founders_welcome: Mixpanel people.set failed: %s", exc)

        logger.info("send_founders_welcome: sent email_id=%s email=%s", email_id, user_email)
        return {"status": "sent", "email_id": email_id}

    logger.info("send_founders_welcome: skipped (already sent or no lead) email=%s", user_email)
    return {"status": "skipped", "email_id": None}


async def llm_summary_job(ctx: dict, search_id: str, licitacoes: list, sector_name: str, termos_busca: str | None = None, **kwargs) -> dict:
    from middleware import search_id_var, request_id_var
    search_id_var.set(search_id)
    request_id_var.set(kwargs.get("_trace_id", search_id))

    from llm import get_or_generate_resumo_cached, gerar_resumo_fallback
    from progress import get_tracker
    from jobs.queue.result_store import persist_job_result

    logger.info(f"[LLM Job] search_id={search_id}, bids={len(licitacoes)}, sector={sector_name}")
    _setor_id = kwargs.get("setor_id")
    try:
        # Issue #160: use Redis-cached wrapper; falls back to direct OpenAI call if Redis unavailable.
        resumo = await get_or_generate_resumo_cached(
            licitacoes,
            sector_name=sector_name,
            termos_busca=termos_busca,
            setor_id=_setor_id,
        )
    except Exception as e:
        logger.warning(f"[LLM Job] LLM failed ({type(e).__name__}), using fallback: {e}")
        resumo = gerar_resumo_fallback(licitacoes, sector_name=sector_name, termos_busca=termos_busca)

    resumo.total_oportunidades = len(licitacoes)
    resumo.valor_total = sum(lic.get("valorTotalEstimado", 0) or 0 for lic in licitacoes)
    from llm import _ground_truth_summary, recompute_temporal_alerts
    _ground_truth_summary(resumo)
    recompute_temporal_alerts(resumo, licitacoes)

    result_data = resumo.model_dump()
    await persist_job_result(search_id, "resumo_json", result_data)
    tracker = await get_tracker(search_id)
    if tracker:
        await tracker.emit("llm_ready", 85, "Resumo pronto", resumo=result_data)
    return result_data


async def excel_generation_job(ctx: dict, search_id: str, licitacoes: list, allow_excel: bool, **kwargs) -> dict:
    from middleware import search_id_var, request_id_var
    search_id_var.set(search_id)
    request_id_var.set(kwargs.get("_trace_id", search_id))

    from excel import create_excel
    from storage import upload_excel
    from progress import get_tracker
    from jobs.queue.result_store import persist_job_result, _update_results_excel_url

    logger.info(f"[Excel Job] search_id={search_id}, bids={len(licitacoes)}, allow={allow_excel}")

    if not allow_excel:
        result = {"excel_status": "skipped", "download_url": None}
        await persist_job_result(search_id, "excel_result", result)
        return result

    download_url = None
    try:
        excel_buffer = create_excel(licitacoes)
        storage_result = upload_excel(excel_buffer.read(), search_id)
        if storage_result:
            download_url = storage_result["signed_url"]
        else:
            logger.error("[Excel Job] Storage upload returned None")
    except Exception as e:
        logger.error(f"[Excel Job] Generation/upload failed: {e}", exc_info=True)

    excel_status = "ready" if download_url else "failed"
    result = {"excel_status": excel_status, "download_url": download_url}
    await persist_job_result(search_id, "excel_result", result)
    if download_url:
        await _update_results_excel_url(search_id, download_url)

    tracker = await get_tracker(search_id)
    if tracker:
        if download_url:
            await tracker.emit("excel_ready", 98, "Planilha pronta para download", download_url=download_url)
        else:
            await tracker.emit("excel_ready", 98, "Erro ao gerar planilha. Tente novamente.", excel_status="failed")
    return result


async def bid_analysis_job(ctx: dict, search_id: str, licitacoes: list, user_profile: dict | None = None, sector_name: str = "", **kwargs) -> dict:
    from middleware import search_id_var, request_id_var
    search_id_var.set(search_id)
    request_id_var.set(kwargs.get("_trace_id", search_id))
    from bid_analyzer import batch_analyze_bids
    from progress import get_tracker
    from jobs.queue.result_store import persist_job_result

    logger.info(f"[BidAnalysis Job] search_id={search_id}, bids={len(licitacoes)}, sector={sector_name}")
    try:
        result_data = [r.model_dump() for r in batch_analyze_bids(bids=licitacoes, user_profile=user_profile, sector_name=sector_name)]
    except Exception as e:
        logger.warning(f"[BidAnalysis Job] Failed ({type(e).__name__}): {e}")
        result_data = []

    await persist_job_result(search_id, "bid_analysis", result_data)
    tracker = await get_tracker(search_id)
    if tracker:
        await tracker.emit("bid_analysis_ready", 90, "Análise de editais pronta", bid_analysis=result_data)
    return {"status": "completed", "count": len(result_data)}


async def daily_digest_job(ctx: dict) -> dict:
    import uuid as _uuid
    from config import DIGEST_ENABLED, DIGEST_MAX_PER_EMAIL, DIGEST_BATCH_SIZE
    from metrics import DIGEST_EMAILS_SENT, DIGEST_JOB_DURATION

    cycle_id = str(_uuid.uuid4())[:8]
    start = time.monotonic()

    if not DIGEST_ENABLED:
        return {"status": "disabled", "cycle_id": cycle_id}

    stats = {"cycle_id": cycle_id, "users_queried": 0, "emails_sent": 0, "emails_failed": 0, "emails_skipped": 0}

    try:
        from supabase_client import get_supabase
        db = get_supabase()
    except Exception as e:
        logger.error(f"[Digest {cycle_id}] Supabase unavailable: {e}")
        return {"status": "db_unavailable", **stats}

    try:
        from services.digest_service import get_digest_eligible_users, build_digest_for_user, mark_digest_sent
        from templates.emails.digest import render_daily_digest_email
        from email_service import send_batch_email

        eligible = await get_digest_eligible_users(db)
        stats["users_queried"] = len(eligible)
        if not eligible:
            DIGEST_JOB_DURATION.observe(time.monotonic() - start)
            return {"status": "no_users", **stats}

        batch_messages = []
        user_ids_in_batch = []

        for user_prefs in eligible:
            user_id = user_prefs["user_id"]
            try:
                digest = await build_digest_for_user(user_id=user_id, db=db, max_items=DIGEST_MAX_PER_EMAIL)
                if not digest or not digest.get("email"):
                    stats["emails_skipped"] += 1
                    DIGEST_EMAILS_SENT.labels(status="skipped").inc()
                    continue
                html = render_daily_digest_email(user_name=digest["user_name"], opportunities=digest["opportunities"], stats=digest["stats"])
                batch_messages.append({"to": digest["email"], "subject": f"{digest['stats']['total_novas']} oportunidades no seu setor — SmartLic", "html": html, "tags": [{"name": "category", "value": "digest"}, {"name": "cycle_id", "value": cycle_id}]})
                user_ids_in_batch.append(user_id)
            except Exception as e:
                stats["emails_failed"] += 1
                DIGEST_EMAILS_SENT.labels(status="failed").inc()
                logger.warning(f"[Digest {cycle_id}] Failed to build digest for {user_id[:8]}: {e}")

        if not batch_messages:
            DIGEST_JOB_DURATION.observe(time.monotonic() - start)
            return {"status": "no_messages", **stats}

        for batch_start in range(0, len(batch_messages), DIGEST_BATCH_SIZE):
            batch_end = min(batch_start + DIGEST_BATCH_SIZE, len(batch_messages))
            batch_slice = batch_messages[batch_start:batch_end]
            batch_user_ids = user_ids_in_batch[batch_start:batch_end]
            result = send_batch_email(batch_slice, idempotency_key=f"digest-{cycle_id}-{batch_start}")
            if result is not None:
                stats["emails_sent"] += len(batch_slice)
                DIGEST_EMAILS_SENT.labels(status="success").inc(len(batch_slice))
                for uid in batch_user_ids:
                    await mark_digest_sent(uid, db)
            else:
                stats["emails_failed"] += len(batch_slice)
                DIGEST_EMAILS_SENT.labels(status="failed").inc(len(batch_slice))

    except Exception as e:
        logger.error(f"[Digest {cycle_id}] Unexpected error: {e}", exc_info=True)
        return {"status": "error", "error": str(e), **stats}

    duration_s = time.monotonic() - start
    stats["duration_ms"] = int(duration_s * 1000)
    DIGEST_JOB_DURATION.observe(duration_s)
    logger.info(json.dumps({"event": "digest_sent", **stats}))
    return {"status": "completed", **stats}


async def email_alerts_job(ctx: dict) -> dict:
    import uuid as _uuid
    from config import ALERTS_ENABLED, ALERTS_MAX_PER_EMAIL

    cycle_id = str(_uuid.uuid4())[:8]
    start = time.monotonic()

    if not ALERTS_ENABLED:
        return {"status": "disabled", "cycle_id": cycle_id}

    stats = {"cycle_id": cycle_id, "total_alerts": 0, "emails_sent": 0, "emails_failed": 0, "emails_skipped": 0}

    try:
        from supabase_client import get_supabase
        db = get_supabase()
    except Exception:
        return {"status": "db_unavailable", **stats}

    try:
        from services.alert_service import run_all_alerts, finalize_alert_send
        from templates.emails.alert_digest import render_alert_digest_email, get_alert_digest_subject
        from routes.alerts import get_alert_unsubscribe_url
        from email_service import send_email

        summary = await run_all_alerts(db)
        stats["total_alerts"] = summary["total_alerts"]
        stats["emails_skipped"] = summary["skipped"]

        if not summary["payloads"]:
            return {"status": "no_messages", **stats}

        for payload in summary["payloads"]:
            alert_id = payload["alert_id"]
            opps = payload["opportunities"][:ALERTS_MAX_PER_EMAIL]
            try:
                unsubscribe_url = get_alert_unsubscribe_url(alert_id)
                html = render_alert_digest_email(user_name=payload["full_name"], alert_name=payload["alert_name"], opportunities=opps, total_count=payload["total_count"], unsubscribe_url=unsubscribe_url)
                subject = get_alert_digest_subject(payload["total_count"], payload["alert_name"])
                result = send_email(to=payload["email"], subject=subject, html=html, tags=[{"name": "category", "value": "alert"}, {"name": "alert_id", "value": alert_id[:8]}, {"name": "cycle_id", "value": cycle_id}])
                if result:
                    stats["emails_sent"] += 1
                    await finalize_alert_send(alert_id, [o["id"] for o in opps if o.get("id")], db)
                else:
                    stats["emails_failed"] += 1
            except Exception as e:
                stats["emails_failed"] += 1
                logger.error(f"[Alerts {cycle_id}] Error sending alert {alert_id[:8]}: {e}")

    except Exception as e:
        logger.error(f"[Alerts {cycle_id}] Unexpected error: {e}", exc_info=True)
        return {"status": "error", "error": str(e), **stats}

    stats["duration_ms"] = int((time.monotonic() - start) * 1000)
    logger.info(json.dumps({"event": "alerts_sent", **stats}))
    return {"status": "completed", **stats}


async def reclassify_pending_bids_job(ctx: dict, search_id: str, sector_name: str = "", sector_id: str = "", attempt: int = 1, **kwargs) -> dict:
    from config import PENDING_REVIEW_MAX_RETRIES, PENDING_REVIEW_RETRY_DELAY
    from redis_pool import get_redis_pool
    from jobs.queue.result_store import _PENDING_REVIEW_KEY_PREFIX
    from job_queue import get_arq_pool

    logger.info(f"STORY-354: reclassify_pending_bids_job start (search_id={search_id}, attempt={attempt})")
    redis = await get_redis_pool()
    if redis is None:
        return {"status": "error", "reason": "redis_unavailable"}

    key = f"{_PENDING_REVIEW_KEY_PREFIX}{search_id}"
    try:
        raw = await redis.get(key)
        if not raw:
            return {"status": "skipped", "reason": "no_pending_bids"}
        data = json.loads(raw)
        bids = data["bids"]
    except Exception as e:
        logger.error(f"STORY-354: Failed to load pending bids: {e}")
        return {"status": "error", "reason": str(e)}

    if not bids:
        return {"status": "skipped", "reason": "empty_bids"}

    from llm_arbiter import classify_contract_primary_match
    from concurrent.futures import ThreadPoolExecutor, as_completed

    accepted = rejected = still_pending = 0

    def _classify_one(bid: dict) -> tuple:
        objeto = bid.get("objetoCompra", "")
        valor = float(bid.get("valorTotalEstimado") or bid.get("valorTotalHomologado") or 0)
        result = classify_contract_primary_match(objeto=objeto, valor=valor, setor_name=sector_name or None, prompt_level="zero_match", setor_id=sector_id or None, search_id=search_id)
        return bid, result

    try:
        with ThreadPoolExecutor(max_workers=5) as executor:
            for future in as_completed({executor.submit(_classify_one, bid): bid for bid in bids}):
                try:
                    bid, result = future.result()
                    if isinstance(result, dict) and result.get("pending_review"):
                        still_pending += 1
                    elif isinstance(result, dict) and result.get("is_primary"):
                        accepted += 1
                    else:
                        rejected += 1
                except Exception:
                    still_pending += 1
    except Exception as e:
        logger.error(f"STORY-354: Reclassification failed entirely: {e}")
        if attempt < PENDING_REVIEW_MAX_RETRIES:
            try:
                pool = await get_arq_pool()
                if pool:
                    await pool.enqueue_job("reclassify_pending_bids_job", search_id=search_id, sector_name=sector_name, sector_id=sector_id, attempt=attempt + 1, _defer_by=PENDING_REVIEW_RETRY_DELAY)
            except Exception as enq_err:
                logger.error(f"STORY-354: Failed to enqueue retry: {enq_err}")
        return {"status": "error", "reason": str(e)}

    logger.info(f"STORY-354: Reclassification complete: {accepted} accepted, {rejected} rejected, {still_pending} still pending (search_id={search_id})")

    if accepted + rejected > 0:
        from progress import get_tracker
        tracker = await get_tracker(search_id)
        if tracker:
            await tracker.emit_pending_review_complete(reclassified_count=accepted + rejected, accepted_count=accepted, rejected_count=rejected)

    if still_pending == 0:
        try:
            await redis.delete(key)
        except Exception:
            pass
    elif attempt < PENDING_REVIEW_MAX_RETRIES:
        try:
            pool = await get_arq_pool()
            if pool:
                await pool.enqueue_job("reclassify_pending_bids_job", search_id=search_id, sector_name=sector_name, sector_id=sector_id, attempt=attempt + 1, _defer_by=PENDING_REVIEW_RETRY_DELAY)
        except Exception as enq_err:
            logger.error(f"STORY-354: Failed to enqueue retry: {enq_err}")

    return {"status": "completed", "total": accepted + rejected + still_pending, "accepted": accepted, "rejected": rejected, "still_pending": still_pending}


async def classify_zero_match_job(ctx: dict, search_id: str, candidates: list[dict], setor: str, sector_name: str, custom_terms: list[str] | None = None, enqueued_at: float = 0, **kwargs) -> dict:
    from config import MAX_ZERO_MATCH_ITEMS, ZERO_MATCH_VALUE_RATIO, ZERO_MATCH_JOB_TIMEOUT_S, LLM_ZERO_MATCH_BATCH_SIZE, FILTER_ZERO_MATCH_BUDGET_S, LLM_FALLBACK_PENDING_ENABLED
    from metrics import ZERO_MATCH_JOB_DURATION, ZERO_MATCH_JOB_STATUS, ZERO_MATCH_JOB_QUEUE_TIME, ZERO_MATCH_CAP_APPLIED_TOTAL, ZERO_MATCH_POOL_SIZE
    from progress import get_tracker
    from jobs.queue.result_store import store_zero_match_results

    job_start = time.time()
    if enqueued_at > 0:
        ZERO_MATCH_JOB_QUEUE_TIME.observe(job_start - enqueued_at)

    total_candidates = len(candidates)

    # CRIT-058 AC4: Observe pool size before cap (always, for visibility).
    if total_candidates > 0:
        ZERO_MATCH_POOL_SIZE.observe(total_candidates)

    # CRIT-058 AC1+AC2: Apply cap with value-prioritized selection.
    # When the pool exceeds MAX_ZERO_MATCH_ITEMS, we sort by valor_estimado desc
    # and take the top-N (with ZERO_MATCH_VALUE_RATIO controlling how much of the
    # cap is filled by value vs. random sampling — currently always 1.0=all-by-value).
    # Items dropped by the cap are tagged as pending_review (zero_match_cap_exceeded).
    cap_applied = total_candidates > MAX_ZERO_MATCH_ITEMS
    if cap_applied:
        ZERO_MATCH_CAP_APPLIED_TOTAL.inc()

        def _parse_value(lic: dict) -> float:
            v = lic.get("valorTotalEstimado") or lic.get("valorEstimado") or 0
            if isinstance(v, str):
                try:
                    return float(v.replace(".", "").replace(",", "."))
                except ValueError:
                    return 0.0
            try:
                return float(v) if v else 0.0
            except (TypeError, ValueError):
                return 0.0

        # Stable sort by value desc — prioritizes high-value contracts.
        sorted_pool = sorted(candidates, key=_parse_value, reverse=True)

        # AC2: split between by-value and random remainder per ZERO_MATCH_VALUE_RATIO.
        # ratio>=1.0 -> all by value (default). ratio<1.0 reserves a slice for random
        # sampling from the remainder for diversity (deterministic per search_id).
        ratio = max(0.0, min(1.0, float(ZERO_MATCH_VALUE_RATIO)))
        n_by_value = int(MAX_ZERO_MATCH_ITEMS * ratio)
        n_random = MAX_ZERO_MATCH_ITEMS - n_by_value

        pool_to_classify = list(sorted_pool[:n_by_value])
        remainder = sorted_pool[n_by_value:]
        if n_random > 0 and remainder:
            import random as _random
            rng = _random.Random(search_id)  # deterministic per search_id
            sample_size = min(n_random, len(remainder))
            pool_to_classify.extend(rng.sample(remainder, sample_size))

        # Mark dropped items as pending_review (cap_exceeded).
        classified_ids = {id(item) for item in pool_to_classify}
        for lic in candidates:
            if id(lic) not in classified_ids:
                lic.update({
                    "_relevance_source": "pending_review",
                    "_pending_review": True,
                    "_pending_review_reason": "zero_match_cap_exceeded",
                    "_term_density": 0.0,
                    "_matched_terms": [],
                    "_confidence_score": 0,
                    "_llm_evidence": [],
                })
    else:
        pool_to_classify = list(candidates)

    will_classify = len(pool_to_classify)
    logger.info(
        f"CRIT-058/059: classify_zero_match_job start "
        f"(search_id={search_id}, candidates={total_candidates}, will_classify={will_classify}, cap_applied={cap_applied})"
    )

    tracker = await get_tracker(search_id)
    if tracker:
        await tracker.emit("zero_match_started", -1, f"Analisando {will_classify} oportunidades adicionais com IA...", candidates=total_candidates, will_classify=will_classify)

    from llm_arbiter import _classify_zero_match_batch as _classify_batch
    approved: list[dict] = []
    rejected_count = pending_count = classified = 0
    budget_start = time.time()
    # CRIT-058: count items deferred by cap into pending so the job result reflects
    # the full deferred surface (cap-deferred + budget/timeout-deferred).
    if cap_applied:
        pending_count += total_candidates - will_classify

    try:
        batch_items = []
        for lic in pool_to_classify:
            obj = lic.get("objetoCompra", "")
            val = lic.get("valorTotalEstimado") or lic.get("valorEstimado") or 0
            if isinstance(val, str):
                try:
                    val = float(val.replace(".", "").replace(",", "."))
                except ValueError:
                    val = 0.0
            else:
                val = float(val) if val else 0.0
            batch_items.append({"objeto": obj, "valor": val})

        batches = [batch_items[i:i + LLM_ZERO_MATCH_BATCH_SIZE] for i in range(0, len(batch_items), LLM_ZERO_MATCH_BATCH_SIZE)]
        lic_batches = [pool_to_classify[i:i + LLM_ZERO_MATCH_BATCH_SIZE] for i in range(0, len(pool_to_classify), LLM_ZERO_MATCH_BATCH_SIZE)]

        for batch_idx, (batch, lic_batch) in enumerate(zip(batches, lic_batches)):
            elapsed = time.time() - budget_start
            if elapsed > FILTER_ZERO_MATCH_BUDGET_S:
                for remaining_lic in pool_to_classify[classified:]:
                    remaining_lic.update({"_relevance_source": "pending_review", "_pending_review": True, "_pending_review_reason": "zero_match_budget_exceeded"})
                    pending_count += 1
                break

            job_elapsed = time.time() - job_start
            if job_elapsed > ZERO_MATCH_JOB_TIMEOUT_S:
                for remaining_lic in pool_to_classify[classified:]:
                    remaining_lic.update({"_relevance_source": "pending_review", "_pending_review": True, "_pending_review_reason": "zero_match_job_timeout"})
                    pending_count += 1
                logger.warning(f"CRIT-059: Job timeout at batch {batch_idx}")
                break

            try:
                batch_results = _classify_batch(items=batch, setor_name=sector_name, setor_id=setor, search_id=search_id)
                for lic_item, result in zip(lic_batch, batch_results):
                    is_relevant = result.get("is_primary", False) if isinstance(result, dict) else result
                    if is_relevant:
                        lic_item.update({"_relevance_source": "llm_zero_match", "_term_density": 0.0, "_matched_terms": []})
                        if isinstance(result, dict):
                            lic_item["_confidence_score"] = min(result.get("confidence", 60), 70)
                            lic_item["_llm_evidence"] = result.get("evidence", [])
                        else:
                            lic_item["_confidence_score"] = 60
                            lic_item["_llm_evidence"] = []
                        approved.append(lic_item)
                    else:
                        _is_pending = isinstance(result, dict) and result.get("pending_review", False)
                        if _is_pending and LLM_FALLBACK_PENDING_ENABLED:
                            lic_item.update({"_relevance_source": "pending_review", "_pending_review": True})
                            pending_count += 1
                        else:
                            rejected_count += 1
                    classified += 1
            except Exception as batch_err:
                logger.warning(f"CRIT-059: Batch {batch_idx} failed: {batch_err}")
                for lic_item in lic_batch:
                    if LLM_FALLBACK_PENDING_ENABLED:
                        lic_item.update({"_relevance_source": "pending_review", "_pending_review": True})
                        pending_count += 1
                    else:
                        rejected_count += 1
                    classified += 1

            if tracker:
                await tracker.emit("zero_match_progress", -1, f"Classificação IA: {classified}/{will_classify}", classified=classified, total=will_classify, approved=len(approved))

    except Exception as e:
        logger.error(f"CRIT-059: classify_zero_match_job failed: {e}", exc_info=True)
        ZERO_MATCH_JOB_STATUS.labels(status="failed").inc()
        if approved:
            await store_zero_match_results(search_id, approved)
        if tracker:
            await tracker.emit("zero_match_error", -1, "Classificação IA falhou parcialmente", approved=len(approved), error=str(e)[:200])
        duration = time.time() - job_start
        ZERO_MATCH_JOB_DURATION.observe(duration)
        return {"status": "failed", "approved": len(approved), "rejected": rejected_count, "pending": pending_count, "error": str(e)}

    await store_zero_match_results(search_id, approved)
    duration = time.time() - job_start
    ZERO_MATCH_JOB_DURATION.observe(duration)
    ZERO_MATCH_JOB_STATUS.labels(status="completed").inc()
    logger.info(f"CRIT-059: classify_zero_match_job complete (search_id={search_id}, classified={classified}, approved={len(approved)}, rejected={rejected_count}, pending={pending_count}, duration={duration:.1f}s)")
    if tracker:
        await tracker.emit("zero_match_ready", -1, f"Classificação concluída: {len(approved)} oportunidades encontradas", total_classified=classified, approved=len(approved), rejected=rejected_count)
    return {"status": "completed", "total_classified": classified, "approved": len(approved), "rejected": rejected_count, "pending": pending_count, "duration_s": round(duration, 1)}


# ============================================================================
# CONV-011b-1: Post-purchase email sequence step (delivery/followup/reengagement)
# ============================================================================


async def send_post_purchase_step(ctx: dict, sequence_id: str, step_index: int) -> dict:
    """Execute one step of a post-purchase sequence.

    Called by ARQ worker at each offset (0h, 48h, 7d) to send the email
    via Resend and advance the sequence. Uses product-aware templates from
    ``templates.emails.post_purchase`` with delivery-type adaptation.

    Note values:
      - ``user_not_found``: profile lookup returned no rows.
      - ``unknown_step``: step_name not in (delivery, followup, reengagement).

    Args:
        ctx: ARQ worker context.
        sequence_id: UUID of the post_purchase_sequences row.
        step_index: 0-based index of the step to execute.

    Returns:
        dict with status: "completed", "not_found", "already_sent", "step_mismatch", "error".
    """
    from supabase_client import get_supabase

    db = get_supabase()
    start = time.monotonic()

    # Fetch sequence
    result = db.table("post_purchase_sequences").select("*").eq("id", sequence_id).limit(1).execute()
    if not result.data:
        logger.warning(f"send_post_purchase_step: sequence not found: {sequence_id}")
        return {"status": "not_found", "sequence_id": sequence_id, "step_index": step_index}

    sequence = result.data[0]
    steps = sequence.get("sequence_steps") or []

    if step_index >= len(steps):
        logger.warning(
            f"send_post_purchase_step: step_index={step_index} out of range "
            f"(sequence has {len(steps)} steps) for sequence_id={sequence_id}"
        )
        return {"status": "step_mismatch", "sequence_id": sequence_id, "step_index": step_index}

    step = steps[step_index]

    # Check if this step was already sent
    if step.get("sent_at"):
        logger.info(
            f"send_post_purchase_step: step {step_index} already sent at {step['sent_at']} "
            f"for sequence_id={sequence_id}"
        )
        return {"status": "already_sent", "sequence_id": sequence_id, "step_index": step_index}

    step_name = step.get("step", f"step_{step_index}")
    product_sku = sequence.get("product_sku", "unknown")

    logger.info(
        f"Executing post-purchase step: sequence_id={sequence_id}, "
        f"step={step_name} (index={step_index}), product_sku={product_sku}"
    )

    # CONV-011b-2: Send actual email via Resend with product-aware templates
    try:
        # Fetch user profile for email + display name
        user_result = (
            db.table("profiles")
            .select("email, full_name")
            .eq("id", sequence["user_id"])
            .limit(1)
            .execute()
        )
        if not user_result.data:
            logger.warning(
                f"send_post_purchase_step: user not found for user_id={sequence['user_id']}"
            )
            now_iso = datetime.now(timezone.utc).isoformat()
            steps[step_index]["sent_at"] = now_iso
            new_current_step = step_index + 1
            new_status = "completed" if new_current_step >= len(steps) else sequence.get("status", "active")
            db.table("post_purchase_sequences").update({
                "sequence_steps": steps,
                "current_step": new_current_step,
                "status": new_status,
            }).eq("id", sequence_id).execute()
            return {
                "status": "completed", "sequence_id": sequence_id,
                "step_index": step_index, "step_name": step_name,
                "note": "user_not_found",
            }

        user_email = user_result.data[0].get("email", "")
        user_name = user_result.data[0].get("full_name") or user_email.split("@")[0]

        # Fetch product info for template personalization
        product_result = (
            db.table("digital_products")
            .select("name, description, price_brl, delivery_config, upsell_product_id, preview_config")
            .eq("sku", product_sku)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        product_data = product_result.data[0] if product_result.data else None
        product_name = (product_data or {}).get("name", product_sku.replace("-", " ").title())
        delivery_config = (product_data or {}).get("delivery_config") or {}
        delivery_type = delivery_config.get("type", "pdf")

        # Lookup upsell product name if configured
        upsell_id = (product_data or {}).get("upsell_product_id")
        upsell_name = None
        upsell_price = None
        upsell_url = None
        if upsell_id:
            upsell_result = (
                db.table("digital_products")
                .select("name, price_brl, sku")
                .eq("id", upsell_id)
                .eq("active", True)
                .limit(1)
                .execute()
            )
            if upsell_result.data:
                upsell_name = upsell_result.data[0].get("name")
                upsell_price = upsell_result.data[0].get("price_brl")
                upsell_sku = upsell_result.data[0].get("sku", "")
                upsell_url = f"{FRONTEND_URL}/produtos?sku={upsell_sku}"

        # Build download URL for PDF/CSV products
        download_url = None
        if delivery_type in ("pdf", "csv"):
            purchase_result = (
                db.table("intel_report_purchases")
                .select("pdf_url")
                .eq("id", sequence["purchase_id"])
                .limit(1)
                .execute()
            )
            if purchase_result.data:
                download_url = purchase_result.data[0].get("pdf_url")

        from templates.emails.post_purchase import (
            render_post_purchase_delivery,
            render_post_purchase_followup,
            render_post_purchase_reengagement,
        )

        preview_config = (product_data or {}).get("preview_config") or {}
        setor = preview_config.get("default_setor") if isinstance(preview_config, dict) else None

        if step_name == "delivery":
            subject, html = render_post_purchase_delivery(
                user_name=user_name, product_name=product_name,
                product_sku=product_sku, delivery_type=delivery_type,
                download_url=download_url, setor=setor,
            )
        elif step_name == "followup":
            trial_url = f"{FRONTEND_URL}/cadastro?utm_source=post_purchase&utm_medium=email&utm_campaign=followup_48h&utm_content={product_sku}&product_sku={product_sku}"
            subject, html = render_post_purchase_followup(
                user_name=user_name, product_name=product_name,
                product_sku=product_sku, upsell_product_name=upsell_name,
                upsell_product_price=upsell_price, upsell_product_url=upsell_url,
                trial_url=trial_url,
            )
        elif step_name == "reengagement":
            trial_url = f"{FRONTEND_URL}/cadastro?utm_source=post_purchase&utm_medium=email&utm_campaign=reengagement_7d&utm_content={product_sku}&product_sku={product_sku}"
            subject, html = render_post_purchase_reengagement(
                user_name=user_name, product_name=product_name,
                product_sku=product_sku, download_url=download_url,
                upsell_product_name=upsell_name, upsell_product_price=upsell_price,
                upsell_product_url=upsell_url, trial_url=trial_url,
            )
        else:
            logger.warning(
                f"send_post_purchase_step: unknown step_name={step_name} for "
                f"sequence_id={sequence_id}, marking as sent"
            )
            now_iso = datetime.now(timezone.utc).isoformat()
            steps[step_index]["sent_at"] = now_iso
            new_current_step = step_index + 1
            new_status = "completed" if new_current_step >= len(steps) else sequence.get("status", "active")
            db.table("post_purchase_sequences").update({
                "sequence_steps": steps,
                "current_step": new_current_step,
                "status": new_status,
            }).eq("id", sequence_id).execute()
            return {
                "status": "completed", "sequence_id": sequence_id,
                "step_index": step_index, "step_name": step_name,
                "note": "unknown_step",
            }

        from email_service import send_email
        from log_sanitizer import sanitize_string

        email_id = send_email(
            to=user_email, subject=subject, html=html,
            idempotency_key=f"post_purchase:{sequence_id}:{step_index}",
            tags=[
                {"name": "category", "value": "post_purchase"},
                {"name": "step", "value": step_name},
                {"name": "product_sku", "value": product_sku},
                {"name": "sequence_id", "value": sequence_id[:32]},
            ],
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        if email_id:
            steps[step_index]["sent_at"] = now_iso
        else:
            steps[step_index]["error"] = "send_email returned no email_id"
        logger.info(
            f"Post-purchase email sent: sequence_id={sequence_id}, "
            f"step={step_name}, to={sanitize_string(user_email)}, "
            f"product_sku={product_sku}, email_id={email_id}"
        )

        # CONV-011b-3: Track Mixpanel events for post-purchase analytics
        _track_post_purchase_event(
            event_name="post_purchase_email_sent",
            user_id=sequence["user_id"],
            properties={
                "product_sku": product_sku,
                "product_name": product_name,
                "step": step_name,
                "step_index": step_index,
                "sequence_id": sequence_id,
                "email_id": email_id or "unknown",
                "delivery_type": delivery_type,
                "has_upsell": bool(upsell_id),
                "upsell_product_name": upsell_name,
                "purchase_id": sequence.get("purchase_id", ""),
            },
        )

        # Track upsell exposure on followup and reengagement steps
        if upsell_name and step_name in ("followup", "reengagement"):
            _track_post_purchase_event(
                event_name="post_purchase_upsell_exposed",
                user_id=sequence["user_id"],
                properties={
                    "product_sku": product_sku,
                    "upsell_product_name": upsell_name,
                    "upsell_product_price_brl": upsell_price,
                    "step": step_name,
                    "sequence_id": sequence_id,
                },
            )
    except Exception as email_err:
        logger.error(
            f"send_post_purchase_step: failed to send email for "
            f"sequence_id={sequence_id}, step={step_name}: {email_err}"
        )
        steps[step_index]["error"] = str(email_err)[:500]
        # Don't advance — step will be retried on next ARQ tick
        db.table("post_purchase_sequences").update({
            "sequence_steps": steps,
        }).eq("id", sequence_id).execute()
        return {
            "status": "error",
            "sequence_id": sequence_id,
            "step_index": step_index,
            "step_name": step_name,
            "error": str(email_err)[:500],
        }

    # Determine new current_step and status
    new_current_step = step_index + 1
    new_status = sequence.get("status")

    if new_current_step >= len(steps):
        new_status = "completed"
    elif new_status != "active":
        new_status = "active"

    db.table("post_purchase_sequences").update({
        "sequence_steps": steps,
        "current_step": new_current_step,
        "status": new_status,
    }).eq("id", sequence_id).execute()

    duration = time.monotonic() - start
    logger.info(
        f"Post-purchase step completed: sequence_id={sequence_id}, "
        f"step={step_name} (index={step_index}), "
        f"current_step={new_current_step}, status={new_status}, "
        f"duration={duration:.2f}s"
    )

    return {
        "status": "completed",
        "sequence_id": sequence_id,
        "step_index": step_index,
        "step_name": step_name,
        "current_step": new_current_step,
        "sequence_status": new_status,
        "duration_s": round(duration, 2),
    }
