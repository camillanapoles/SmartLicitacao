"""
CNAE to SmartLic sector mapping.

Maps Brazilian CNAE (Classificação Nacional de Atividades Econômicas)
codes to SmartLic sector IDs used by the search pipeline.

DATA-CNAE-001 (2026-05-11): primary source of truth is now the DB table
``public.cnae_setor_mapping`` (Supabase). The hardcoded ``CNAE_TO_SETOR``
dict below is kept as a fallback for resilience (DB down, RLS misconfig,
boot before migrations applied) and as documentation of the initial seed.

Coverage snapshot (2026-05-07): 59 CNAEs mapped across 9 sectors.
IBGE CNAE 2.3 has ~1300 active subclasses. Coverage = 59/1300 = ~4.5%.
"""

from __future__ import annotations

import functools
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Hardcoded fallback dict — kept in sync with the seed insert in
# supabase/migrations/20260511120000_cnae_setor_mapping.sql. DB is the
# source of truth at runtime; this dict only activates when the DB
# lookup fails (transient error or cnae_code missing).
CNAE_TO_SETOR: dict[str, str] = {
    # Engenharia / Construção Civil
    "4120": "engenharia",    # Construção de edifícios
    "4211": "engenharia",    # Construção de rodovias e ferrovias
    "4212": "engenharia",    # Construção de obras de arte especiais
    "4213": "engenharia",    # Obras de urbanização - ruas, praças e calçadas
    "4221": "engenharia",    # Construção de redes de abastecimento de água
    "4222": "engenharia",    # Construção de redes de abastecimento de água e saneamento
    "4223": "engenharia",    # Construção de redes de transportes por dutos
    "4291": "engenharia",    # Obras portuárias, marítimas e fluviais
    "4292": "engenharia",    # Montagem de instalações industriais
    "4299": "engenharia",    # Outras obras de engenharia civil não especificadas
    "4311": "engenharia",    # Demolição e preparação de canteiros de obras
    "4312": "engenharia",    # Perfurações e sondagens
    "4313": "engenharia",    # Obras de terraplenagem
    "4319": "engenharia",    # Serviços de preparação do terreno NEC
    "4321": "engenharia",    # Instalações elétricas
    "4322": "engenharia",    # Instalações hidráulicas, ventilação e refrigeração
    "4329": "engenharia",    # Outras instalações em construções NEC
    "4391": "engenharia",    # Obras de fundações
    "4399": "engenharia",    # Serviços especializados para construção NEC
    "7111": "engenharia",    # Serviços de arquitetura
    "7112": "engenharia",    # Serviços de engenharia
    "7119": "engenharia",    # Atividades técnicas relacionadas à engenharia e arquitetura
    # Vestuário / Uniformes
    "4781": "vestuario",     # Comércio varejista de artigos de vestuário e acessórios
    "1412": "vestuario",     # Confecção de peças de vestuário, exceto roupas íntimas
    "1413": "vestuario",     # Confecção de roupas íntimas
    "1421": "vestuario",     # Fabricação de meias
    "1422": "vestuario",     # Fabricação de artigos do vestuário, produzidos em malharias
    # Facilities / Limpeza
    "8121": "servicos_prediais",  # Limpeza em prédios e em domicílios
    "8122": "servicos_prediais",  # Imunização e controle de pragas urbanas
    "8129": "servicos_prediais",  # Limpeza e conservação de logradouros e vias públicas
    "8130": "servicos_prediais",  # Atividades paisagísticas
    # Vigilância / Segurança
    "8011": "vigilancia",    # Atividades de vigilância e segurança privada
    "8012": "vigilancia",    # Atividades de transporte de valores
    # Saúde / Hospitalar
    "3250": "saude",         # Fabricação de instrumentos e materiais para uso médico
    "4644": "saude",         # Comércio atacadista de instrumentos e materiais para uso médico
    "4645": "saude",         # Comércio atacadista de instrumentos e materiais odontológicos
    "8610": "saude",         # Atividades de atendimento hospitalar
    "8621": "saude",         # Serviços ambulatoriais providos por médicos e odontólogos
    "8630": "saude",         # Atividades de atenção ambulatorial executadas por outros profissionais da saúde
    # Alimentação / Merenda
    "1011": "alimentos",     # Abate de reses, exceto suínos
    "1091": "alimentos",     # Fabricação de produtos de panificação e confeitaria
    "4639": "alimentos",     # Comércio atacadista de produtos alimentícios em geral
    "4711": "alimentos",     # Comércio varejista de produtos alimentícios em geral
    # TI / Informática
    "6201": "informatica",   # Desenvolvimento de programas de computador sob encomenda
    "6202": "informatica",   # Desenvolvimento e licenciamento de programas de computador
    "6209": "informatica",   # Suporte técnico, manutenção e outros serviços em TI
    "6311": "informatica",   # Tratamento de dados, provedores de serviços de aplicação
    "6319": "informatica",   # Portais, provedores de conteúdo e outros serviços de informação
    # Equipamentos / Eletroeletrônicos
    "2710": "equipamentos",  # Fabricação de geradores, transformadores, motores elétricos
    "2759": "equipamentos",  # Fabricação de outros aparelhos eletrodomésticos NEC
    "2861": "equipamentos",  # Fabricação de ferramentas
    # Transporte / Logística
    "4921": "transporte",    # Transporte rodoviário coletivo de passageiros, com itinerário fixo, municipal
    "4922": "transporte",    # Transporte rodoviário coletivo de passageiros, intermunicipal
    "4924": "transporte",    # Transporte escolar
    "4929": "transporte",    # Outros transportes rodoviários de passageiros NEC
    "4930": "transporte",    # Transporte rodoviário de carga
    # Administração Pública (compradores) — mapear para engenharia como setor mais frequente
    "8411": "engenharia",    # Administração pública em geral
    "8412": "engenharia",    # Regulação das atividades de saúde, educação, serviços culturais
    "8413": "engenharia",    # Regulação das atividades econômicas
}

# Reverse mapping: sector descriptions for user feedback
SETOR_NAMES: dict[str, str] = {
    "engenharia": "Engenharia, Projetos e Obras",
    "vestuario": "Vestuário e Uniformes",
    "servicos_prediais": "Serviços Prediais e Facilities",
    "vigilancia": "Vigilância e Segurança",
    "equipamentos": "Equipamentos",
    "alimentos": "Alimentos e Merenda",
    "informatica": "TI e Sistemas",
    "saude": "Saúde e Hospitalar",
    "transporte": "Transporte e Logística",
}


def _extract_prefix(cnae: str) -> str:
    """Extract the 4-digit prefix from a CNAE string in any common format.

    "4781", "4781-4/00", "47814" -> "4781". Returns "" if no 4 digits found.
    """
    cleaned = (cnae or "").strip().replace(" ", "")
    prefix = ""
    for ch in cleaned:
        if ch.isdigit():
            prefix += ch
            if len(prefix) == 4:
                return prefix
    return prefix if len(prefix) == 4 else ""


def _db_lookup(cnae_prefix: str) -> Optional[str]:
    """Query Supabase ``cnae_setor_mapping`` for ``cnae_prefix``.

    Returns ``setor_id`` if found, ``None`` if missing, and ``None`` (after
    logging) on any transient error so the caller can fall back to the
    hardcoded dict.

    Skips rows whose ``notes = 'deleted'`` (soft-delete convention).
    """
    try:
        from supabase_client import get_supabase  # local import to avoid boot cycles
        sb = get_supabase()
        result = (
            sb.table("cnae_setor_mapping")
            .select("setor_id, notes")
            .eq("cnae_code", cnae_prefix)
            .limit(1)
            .execute()
        )
        rows = getattr(result, "data", None) or []
        if not rows:
            return None
        row = rows[0]
        if (row.get("notes") or "").strip().lower() == "deleted":
            return None
        return row.get("setor_id")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("cnae_db_lookup_failed cnae=%s err=%s", cnae_prefix, exc)
        return None


@functools.lru_cache(maxsize=1024)
def lookup_cnae_setor(cnae_code: str) -> Optional[str]:
    """Resolve a CNAE code to a SmartLic sector id.

    Resolution order:
      1. DB ``public.cnae_setor_mapping`` (primary, runtime-editable).
      2. Hardcoded ``CNAE_TO_SETOR`` dict (fallback, ships with code).
      3. ``None`` if both miss — callers may default to "geral".

    Cached via ``functools.lru_cache``; admin CRUD endpoints MUST call
    :func:`invalidate_cnae_cache` after writes so subsequent lookups
    re-query the DB.
    """
    prefix = _extract_prefix(cnae_code)
    if not prefix:
        return None
    db = _db_lookup(prefix)
    if db is not None:
        return db
    return CNAE_TO_SETOR.get(prefix)


def invalidate_cnae_cache() -> None:
    """Clear the lookup_cnae_setor LRU cache.

    Admin CRUD endpoints (POST/PATCH/DELETE /v1/admin/cnae-mapping) call
    this after writes so the next request observes the new mapping.
    """
    lookup_cnae_setor.cache_clear()


def map_cnae_to_setor(cnae: str) -> str:
    """
    Map CNAE code to SmartLic sector ID.

    Extracts the 4-digit prefix from CNAE codes in various formats:
    - "4781" → "vestuario"
    - "4781-4/00" → "vestuario"
    - "47814" → "vestuario"

    Falls back to "geral" if CNAE is not recognized or cannot be parsed.
    Emits a warning log when falling back so gaps can be tracked.

    Args:
        cnae: CNAE code or prefix string

    Returns:
        Sector ID string (e.g., "vestuario", "servicos_prediais", "geral")
    """
    prefix = _extract_prefix(cnae)
    if not prefix:
        logger.warning("cnae_not_mapped cnae=%r fallback=geral", cnae)
        return "geral"

    result = lookup_cnae_setor(prefix)
    if result is None:
        logger.warning("cnae_not_mapped cnae=%s fallback=geral", prefix)
        return "geral"
    return result


def get_setor_name(setor_id: str) -> str:
    """Get human-readable sector name."""
    return SETOR_NAMES.get(setor_id, setor_id.replace("_", " ").title())
