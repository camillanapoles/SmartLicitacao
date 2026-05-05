"""
CNAE to SmartLic sector mapping.

Maps Brazilian CNAE (Classificação Nacional de Atividades Econômicas)
codes to SmartLic sector IDs used by the search pipeline.

Lookup architecture (DATA-CNAE-002 — re-implementation after PR #679 revert):
    L1: ``CNAE_TO_SETOR`` — module-level dict, hardcoded baseline + DB merge.
        Updated in-place by :func:`load_cnae_from_db` (called from
        ``startup.lifespan``). Never replaced — DB rows merge over the
        hardcoded baseline so unmapped keys still resolve via the legacy
        snapshot even if the DB is unreachable.
    L2: ``public.cnae_setores`` table (Supabase) — optional override.
        If the table is empty, missing, or unreachable, lookups answer
        from the hardcoded baseline (Gap-8 status quo).

Why no listener / no ARQ cron / no TTL cache (DATA-CNAE-002 vs #679):
    PR #679 was reverted (#702) because its lazily-spawned daemon thread
    (Redis pubsub listener with its own event loop) blocked the Railway
    healthcheck on cold start. This re-implementation deliberately omits:
      * the Redis pubsub listener (PR #702 suspect cause #1)
      * the ARQ cron registration `start_cnae_coverage_task` (suspect #2)
      * the admin CRUD surface (would require PostgREST cache propagation
        — suspect #3)
    Instead, the warmup is a one-shot synchronous-style merge during
    ``lifespan`` startup, wrapped in a non-fatal try/except guard.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# CNAE→sector mappings
# Format: CNAE 4-digit prefix → sector_id
#
# This dict is the source of truth for `map_cnae_to_setor`. It is populated
# at import time with the hardcoded baseline (below) and may be MERGED with
# rows from `public.cnae_setores` during startup via :func:`load_cnae_from_db`.
# DB rows override the hardcoded baseline; missing keys fall through to the
# baseline so the function never raises on cold start or DB outage.
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


def map_cnae_to_setor(cnae: str) -> str:
    """
    Map CNAE code to SmartLic sector ID.

    Extracts the 4-digit prefix from CNAE codes in various formats:
    - "4781" → "vestuario"
    - "4781-4/00" → "vestuario"
    - "47814" → "vestuario"

    Falls back to "vestuario" if CNAE not recognized.

    Args:
        cnae: CNAE code or prefix string

    Returns:
        Sector ID string (e.g., "vestuario", "servicos_prediais")
    """
    # Extract 4-digit prefix: handle "4781-4/00", "4781400", "4781" formats
    cleaned = cnae.strip().replace(" ", "")
    # Take first 4 digits
    prefix = ""
    for ch in cleaned:
        if ch.isdigit():
            prefix += ch
            if len(prefix) == 4:
                break

    if not prefix or len(prefix) < 4:
        return "geral"  # Default fallback for unknown/unparseable CNAE

    return CNAE_TO_SETOR.get(prefix, "geral")


def get_setor_name(setor_id: str) -> str:
    """Get human-readable sector name."""
    return SETOR_NAMES.get(setor_id, setor_id.replace("_", " ").title())


def load_cnae_from_db() -> Optional[dict[str, str]]:
    """Load CNAE→setor overrides from ``public.cnae_setores``.

    Called once at startup from ``startup.lifespan`` (DATA-CNAE-002).
    Returns a fresh dict on success (possibly empty if the table exists
    but has no rows) or ``None`` on any failure — caller is expected to
    log a warning and proceed with the hardcoded baseline.

    Failure modes that MUST NOT raise:
      * Supabase unreachable (network / DNS)
      * Table missing (PostgREST PGRST205 — schema cache stale)
      * Permission denied (RLS misconfigured)
      * Malformed rows
    All collapse to ``None`` — a non-fatal signal to the caller.
    """
    try:
        from supabase_client import get_supabase  # local import: keep tests fast
    except Exception as exc:  # pragma: no cover — import-time failure
        logger.debug("cnae_mapping: supabase_client import failed: %s", exc)
        return None

    try:
        sb = get_supabase()
        result = (
            sb.table("cnae_setores")
            .select("codigo_cnae,setor")
            .execute()
        )
    except Exception as exc:
        logger.debug(
            "cnae_mapping: DB load failed (%s) — caller should fall back",
            exc,
        )
        return None

    rows = getattr(result, "data", None) or []
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        codigo = row.get("codigo_cnae")
        setor = row.get("setor")
        if isinstance(codigo, str) and isinstance(setor, str) and codigo and setor:
            out[codigo] = setor
    return out
