"""
SEN-BE-010 AC3: Load test reproducing the Stage 4-7 wedge pattern.

Replicates the traffic shape that drove backend RSS to 5.5GB sustained:
  - SSG burst from frontend build (4146 pages × 6 endpoints = ~25k requests)
  - Googlebot/Bingbot crawl wave (sitemap + observatorio + cnpj concurrent)
  - Cron tasks running simultaneously (19 lifespan loops + 9 ARQ schedules)

Memory references:
  - project_backend_outage_2026_04_27 (Stage 2 Googlebot wave saturation)
  - feedback_pool_leak_caller_timeout_vs_sql_timeout (caller wait_for vs SQL pool)
  - feedback_web_concurrency_4_amplifier (WC=4 amplifier; manter WC=1 Hobby)
  - feedback_supabase_disk_io_root_cause_pattern

Run (NOT in CI — reproducible local against staging or local backend):

    pip install locust  # not in requirements; install ad-hoc for load runs
    locust -f backend/tests/load/stage_4_7_pattern.py \\
      --host=https://api.smartlic.tech \\
      --users=50 --spawn-rate=5 --run-time=10m --headless

Pre-fix baseline: capture RSS p99 + slow_request count via Sentry/Prometheus.
Post-fix target (AC6 24h soak): RSS p99 <2GB sob mesma load.

Memory feedback_locust_catch_response: sempre chamar response.success() ou
response.failure() explicitamente. Unmarked = default fail.
"""

from __future__ import annotations

try:
    from locust import HttpUser, task, between
except ImportError as exc:  # pragma: no cover — locust optional
    raise ImportError(
        "locust não instalado. Instale ad-hoc para load runs:\n"
        "  pip install locust\n"
        "Não adicionar a requirements.txt — ferramenta de dev only."
    ) from exc


# Sample CNPJs / orgaos / municipios extraídos de produção (Sentry top-talkers).
# Lista pequena — Locust dispara distribuição uniforme por iteração.
SAMPLE_CNPJS = [
    "00000000000191",  # Banco do Brasil S.A.
    "33000167000101",  # Petrobras
    "33683111000180",  # Caixa
    "59307595000148",  # JBS
    "60872514000150",  # Whirlpool
]

SAMPLE_ORGAO_SLUGS = [
    "ministerio-da-defesa",
    "secretaria-da-saude-sp",
    "prefeitura-do-rio-de-janeiro",
    "exercito-brasileiro",
    "anatel",
]

SAMPLE_MUNICIPIO_SLUGS = [
    "sao-paulo-sp",
    "rio-de-janeiro-rj",
    "belo-horizonte-mg",
    "porto-alegre-rs",
    "salvador-ba",
]

SAMPLE_CATMATS = ["150142", "270471", "330081", "390015", "450055"]


class GooglebotCrawler(HttpUser):
    """
    Simula crawler agressivo: sitemap → entity pages.
    Peso 4 — replica pattern observado em Stage 2 (Googlebot wave saturou
    perfil-b2g + fornecedor profile sob WC=1 + sync .execute()).
    """

    weight = 4
    wait_time = between(0.5, 2.0)

    @task(3)
    def crawl_sitemap_index(self) -> None:
        with self.client.get("/sitemap.xml", catch_response=True, name="/sitemap.xml") as resp:
            if resp.status_code == 200 and resp.text.startswith("<?xml"):
                resp.success()
            else:
                resp.failure(f"sitemap_index http={resp.status_code}")

    @task(2)
    def crawl_sitemap_shard(self) -> None:
        # IDs 0..4 atuais (SEO-PROG-006 propõe 10 shards futuro)
        for shard_id in (0, 1, 2, 3, 4):
            with self.client.get(
                f"/sitemap/{shard_id}.xml",
                catch_response=True,
                name=f"/sitemap/{shard_id}.xml",
            ) as resp:
                if resp.status_code == 200:
                    resp.success()
                else:
                    resp.failure(f"sitemap_shard_{shard_id} http={resp.status_code}")

    @task(5)
    def crawl_cnpj_profile(self) -> None:
        cnpj = self._pick(SAMPLE_CNPJS)
        with self.client.get(
            f"/v1/empresa/{cnpj}/perfil-b2g",
            catch_response=True,
            name="/v1/empresa/[cnpj]/perfil-b2g",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"perfil_b2g http={resp.status_code}")

    @task(3)
    def crawl_orgao_stats(self) -> None:
        slug = self._pick(SAMPLE_ORGAO_SLUGS)
        with self.client.get(
            f"/v1/orgao/{slug}/stats",
            catch_response=True,
            name="/v1/orgao/[slug]/stats",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"orgao_stats http={resp.status_code}")

    @task(2)
    def crawl_observatorio(self) -> None:
        with self.client.get(
            "/v1/observatorio/raio-x-setor",
            catch_response=True,
            name="/v1/observatorio/raio-x-setor",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"observatorio http={resp.status_code}")

    @staticmethod
    def _pick(seq):
        import random
        return random.choice(seq)


class SsgBuildBurst(HttpUser):
    """
    Simula frontend SSG build burst (memory feedback_build_hammers_backend_cascade):
    fetches concurrent ao backend para gerar páginas estáticas.
    Peso 2 — burst curto mas 4146 pages × 6 endpoints = ~25k requests amplificados.
    """

    weight = 2
    wait_time = between(0.05, 0.2)

    @task(4)
    def build_sitemap_endpoint(self) -> None:
        endpoints = [
            "/v1/sitemap/cnpjs",
            "/v1/sitemap/orgaos",
            "/v1/sitemap/itens",
            "/v1/sitemap/municipios",
            "/v1/sitemap/fornecedores-cnpj",
            "/v1/sitemap/contratos-orgao-indexable",
            "/v1/sitemap/licitacoes-indexable",
        ]
        ep = endpoints[hash(self) % len(endpoints)]
        with self.client.get(ep, catch_response=True, name=ep) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"sitemap_endpoint {ep} http={resp.status_code}")

    @task(2)
    def build_item_profile(self) -> None:
        catmat = SAMPLE_CATMATS[hash(self) % len(SAMPLE_CATMATS)]
        with self.client.get(
            f"/v1/itens/{catmat}/profile",
            catch_response=True,
            name="/v1/itens/[catmat]/profile",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"item_profile http={resp.status_code}")


class HumanUser(HttpUser):
    """Baseline — usuário humano padrão (peso 1 — small noise)."""

    weight = 1
    wait_time = between(2.0, 8.0)

    @task
    def health_check(self) -> None:
        with self.client.get("/health/live", catch_response=True, name="/health/live") as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"health http={resp.status_code}")
