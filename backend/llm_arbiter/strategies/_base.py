"""Base ABC and shared LLM-call helper for classification strategies (REF-VAL-002).

The shared helper ``run_llm_classification`` factors out the common machinery
that all LLM-using strategies need:

  - L1 (in-memory) + L2 (Redis) cache read
  - Monthly budget cap short-circuit
  - OpenAI chat.completions call
  - Structured / binary response parsing
  - Token logging + cache write
  - Error fallback (PENDING_REVIEW or hard REJECT)

It calls back into ``llm_arbiter.classification`` for the cache/parse/log
primitives so behaviour is bit-for-bit equivalent to the pre-refactor
``classify_contract_primary_match`` function.
"""

from __future__ import annotations

import hashlib
import logging
import time as _time_module
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ClassificationStrategy(ABC):
    """ABC for a single density-tier classification strategy."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical name of this strategy (matches legacy ``prompt_level``)."""

    @abstractmethod
    def classify(
        self,
        *,
        objeto: str,
        valor: float,
        setor_name: Optional[str] = None,
        termos_busca: Optional[list[str]] = None,
        setor_id: Optional[str] = None,
        search_id: str = "",
    ) -> dict:
        """Return the legacy classification dict.

        Shape mirrors ``classify_contract_primary_match`` exactly::

            {
                "is_primary": bool,
                "confidence": int,           # 0..100
                "evidence": list[str],
                "rejection_reason": Optional[str],
                "needs_more_data": bool,
                # optional keys present only on some paths:
                "pending_review": bool,
                "_classification_source": str,
            }
        """


def run_llm_classification(
    *,
    user_prompt: str,
    mode: str,
    context: str,
    objeto: str,
    valor: float,
    objeto_truncated: str,
    prompt_level: str,
    setor_id: Optional[str],
    search_id: str,
    structured_enabled: bool = True,
) -> dict:
    """Shared LLM-call core extracted from ``classify_contract_primary_match``.

    All LLM-using strategies funnel through this helper so cache key shape,
    metrics labels, budget gating and parsing remain identical.
    """
    # Late imports to avoid circulars with the facade re-export module.
    from llm_arbiter import classification as _cls
    from metrics import (
        ARBITER_CACHE_HITS,
        ARBITER_CACHE_MISSES,
        LLM_CALLS,
        LLM_DURATION,
        LLM_FALLBACK_REJECTS_TOTAL,
    )
    from middleware import search_id_var

    _search_id = search_id_var.get("-")

    prompt_version = "v2" if structured_enabled else "v1"
    cache_key = hashlib.md5(
        f"{prompt_version}:{mode}:{context}:{valor}:{objeto_truncated}:{prompt_level}:{setor_id or ''}".encode()
    ).hexdigest()

    if cache_key in _cls._arbiter_cache:
        _cls._arbiter_cache.move_to_end(cache_key)
        ARBITER_CACHE_HITS.labels(level="l1").inc()
        logger.debug(
            f"LLM arbiter cache L1 HIT: mode={mode} "
            f"context={context[:50]}... valor={valor}"
        )
        return _cls._arbiter_cache[cache_key]

    redis_cached = _cls._arbiter_cache_get_redis(cache_key)
    if redis_cached is not None:
        ARBITER_CACHE_HITS.labels(level="l2").inc()
        return redis_cached

    ARBITER_CACHE_MISSES.inc()

    # STORY-2.11 (EPIC-TD-2026Q2 P0): Budget cap short-circuit.
    try:
        from llm_budget import is_budget_exceeded_sync

        if is_budget_exceeded_sync():
            logger.warning(
                f"STORY-2.11: LLM monthly budget exceeded — returning PENDING_REVIEW | "
                f"search={_search_id} mode={mode} prompt_level={prompt_level}"
            )
            try:
                from metrics import LLM_BUDGET_REJECTIONS

                LLM_BUDGET_REJECTIONS.labels(caller="arbiter").inc()
            except Exception:
                pass
            return {
                "is_primary": False,
                "confidence": 0,
                "evidence": [],
                "rejection_reason": "llm_budget_exceeded",
                "needs_more_data": False,
                "pending_review": True,
                "_classification_source": "budget_cap",
            }
    except Exception:
        pass

    try:
        if structured_enabled:
            system_prompt = (
                "Você é um classificador conservador de licitações públicas. "
                "Em caso de dúvida, responda NAO. "
                "Apenas responda SIM se o contrato é CLARAMENTE e PRIMARIAMENTE sobre o setor. "
                "Responda em formato JSON válido conforme a estrutura solicitada."
            )
            effective_max_tokens = _cls.LLM_STRUCTURED_MAX_TOKENS
        else:
            system_prompt = (
                "Você é um classificador conservador de licitações. "
                "Em caso de dúvida, responda NAO. "
                "Apenas responda SIM se o contrato é CLARAMENTE e PRIMARIAMENTE sobre o setor. "
                "Responda APENAS 'SIM' ou 'NAO'."
            )
            effective_max_tokens = _cls.LLM_MAX_TOKENS

        api_kwargs: dict[str, Any] = {
            "model": _cls.LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": effective_max_tokens,
            "temperature": _cls.LLM_TEMPERATURE,
        }
        if structured_enabled:
            api_kwargs["response_format"] = {"type": "json_object"}

        _llm_start = _time_module.time()
        # Lazy import via facade so tests can patch ``llm_arbiter._get_client``.
        import llm_arbiter as _lm

        response = _lm._get_client().chat.completions.create(**api_kwargs)
        _llm_elapsed = _time_module.time() - _llm_start

        raw_content = response.choices[0].message.content.strip()

        usage = getattr(response, "usage", None)
        if usage and search_id:
            _cls._log_token_usage(
                search_id,
                input_tokens=getattr(usage, "prompt_tokens", 0),
                output_tokens=getattr(usage, "completion_tokens", 0),
            )

        if structured_enabled:
            classification = _cls._parse_structured_response(raw_content, objeto, search_id)
            is_primary = classification.classe == "SIM"
            result = {
                "is_primary": is_primary,
                "confidence": classification.confianca,
                "evidence": classification.evidencias,
                "rejection_reason": classification.motivo_exclusao,
                "needs_more_data": classification.precisa_mais_dados,
            }
        else:
            llm_response = raw_content.upper()
            is_primary = llm_response == "SIM"
            result = {
                "is_primary": is_primary,
                "confidence": 100 if is_primary else 0,
                "evidence": [],
                "rejection_reason": None,
                "needs_more_data": False,
            }

        _decision = "SIM" if is_primary else "NAO"
        LLM_DURATION.labels(model=_cls.LLM_MODEL, decision=_decision).observe(_llm_elapsed)
        LLM_CALLS.labels(model=_cls.LLM_MODEL, decision=_decision, zone=prompt_level).inc()

        _cls._arbiter_cache_set(cache_key, result)
        _cls._arbiter_cache_set_redis(cache_key, result)

        logger.info(
            f"LLM arbiter decision: {_decision} conf={result['confidence']}% | "
            f"search={_search_id} mode={mode} prompt_level={prompt_level} structured={structured_enabled} "
            f"context={context[:50]}... valor=R${valor:,.2f}"
        )

        return result

    except Exception as e:
        LLM_CALLS.labels(model=_cls.LLM_MODEL, decision="ERROR", zone=prompt_level).inc()

        from config import LLM_FALLBACK_PENDING_ENABLED

        _gray_zone_levels = {"zero_match", "standard", "conservative"}
        if LLM_FALLBACK_PENDING_ENABLED and prompt_level in _gray_zone_levels:
            logger.warning(
                f"LLM arbiter FAILED (PENDING_REVIEW fallback): {e} | "
                f"search={_search_id} mode={mode} prompt_level={prompt_level} "
                f"context={context[:50]}... valor={valor:,.2f}"
            )
            from metrics import LLM_FALLBACK_PENDING

            _sector_label = context[:50] if mode == "setor" else "termos"
            _reason = type(e).__name__
            LLM_FALLBACK_PENDING.labels(sector=_sector_label, reason=_reason).inc()
            _pending_confidence = 40 if prompt_level in {"standard", "conservative"} else 0
            return {
                "is_primary": False,
                "confidence": _pending_confidence,
                "evidence": [],
                "rejection_reason": "LLM unavailable",
                "needs_more_data": False,
                "pending_review": True,
                "_classification_source": "llm_fallback_pending",
            }

        logger.error(
            f"LLM arbiter FAILED (defaulting to REJECT): {e} | "
            f"search={_search_id} mode={mode} context={context[:50]}... valor={valor:,.2f}"
        )
        try:
            _setor_label = setor_id or "unknown"
            _reason = type(e).__name__
            LLM_FALLBACK_REJECTS_TOTAL.labels(setor=_setor_label, reason=_reason).inc()
        except Exception:
            pass
        return {
            "is_primary": False,
            "confidence": 0,
            "evidence": [],
            "rejection_reason": "LLM unavailable",
            "needs_more_data": False,
        }


def build_user_prompt(
    *,
    prompt_level: str,
    setor_name: Optional[str],
    termos_busca: Optional[list[str]],
    objeto_truncated: str,
    valor: float,
    setor_id: Optional[str],
    structured_enabled: bool = True,
) -> tuple[str, str, str]:
    """Build the user prompt + return (user_prompt, mode, context).

    Centralises the prompt-builder dispatch so each LLM strategy only declares
    which builder to use.
    """
    from llm_arbiter.prompt_builder import (
        _STRUCTURED_JSON_INSTRUCTION,
        _build_conservative_prompt,
        _build_standard_sector_prompt,
        _build_zero_match_prompt,
    )

    if setor_name:
        mode = "setor"
        context = setor_name
        if prompt_level == "zero_match":
            user_prompt = _build_zero_match_prompt(
                setor_id=setor_id,
                setor_name=setor_name,
                objeto_truncated=objeto_truncated,
                valor=valor,
                structured=structured_enabled,
            )
        elif prompt_level == "conservative":
            user_prompt = _build_conservative_prompt(
                setor_id=setor_id,
                setor_name=setor_name,
                objeto_truncated=objeto_truncated,
                valor=valor,
                structured=structured_enabled,
            )
        else:
            user_prompt = _build_standard_sector_prompt(
                setor_name=setor_name,
                objeto_truncated=objeto_truncated,
                valor=valor,
                structured=structured_enabled,
            )
    else:
        mode = "termos"
        context = ", ".join(termos_busca) if termos_busca else ""
        suffix = _STRUCTURED_JSON_INSTRUCTION if structured_enabled else "\nResponda APENAS: SIM ou NAO"
        user_prompt = (
            f"Termos buscados: {context}\n"
            f"Valor: R$ {valor:,.2f}\n"
            f"Objeto: {objeto_truncated}\n\n"
            f"Os termos buscados descrevem o OBJETO PRINCIPAL deste contrato "
            f"(não itens secundários)?{suffix}"
        )

    return user_prompt, mode, context
