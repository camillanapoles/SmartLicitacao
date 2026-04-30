"""Stage 4-7 wedge pattern reproducer.

Simula concorrência observada nos incidents 2026-04-27 a 29:
- 31 workers SSG burst (sitemap fetchers)
- Googlebot crawl
- ARQ cron paralelas

Memory: project_backend_outage_2026_04_29_stage5, feedback_build_hammers_backend_cascade.
"""

from locust import HttpUser, task, between, events
import random

SAMPLE_CNPJS = [
    "10000000000100", "20000000000200", "30000000000300",
    "40000000000400", "50000000000500",
]

SAMPLE_ORGAO_SLUGS = [
    "ministerio-da-fazenda", "tribunal-de-contas-uniao",
    "agencia-nacional-de-aguas",
]

SAMPLE_SECTORS = [
    "construcao", "informatica", "alimentos", "limpeza", "vestuario",
]


class SSGSitemapBurstUser(HttpUser):
    """Simula 31 workers SSG fan-out: 6 endpoints sequenciais por shard."""

    weight = 5
    wait_time = between(0.5, 2.0)

    @task
    def sitemap_fanout(self):
        for endpoint in [
            "/v1/sitemap/contratos-orgao",
            "/v1/sitemap/cnpjs",
            "/v1/sitemap/orgaos",
            "/v1/sitemap/municipios",
            "/v1/sitemap/fornecedores-cnpj",
            "/v1/sitemap/itens",
            "/v1/sitemap/licitacoes-indexable",
        ]:
            with self.client.get(
                endpoint,
                name=f"SSG {endpoint}",
                catch_response=True,
                timeout=15,
            ) as r:
                if r.status_code in (200, 304):
                    r.success()
                elif r.status_code == 404:
                    r.success()  # endpoint pode não existir ainda
                else:
                    r.failure(f"sitemap fan-out {r.status_code}")


class GooglebotCrawlerUser(HttpUser):
    """Simula Googlebot crawl em rotas SEO programmatic."""

    weight = 4
    wait_time = between(1.0, 3.0)

    def on_start(self):
        self.client.headers["User-Agent"] = (
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        )

    @task(3)
    def cnpj_profile(self):
        cnpj = random.choice(SAMPLE_CNPJS)
        with self.client.get(
            f"/v1/empresa/{cnpj}",
            name="Googlebot /v1/empresa/[cnpj]",
            catch_response=True,
            timeout=20,
        ) as r:
            if r.status_code in (200, 404):
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(2)
    def orgao_profile(self):
        slug = random.choice(SAMPLE_ORGAO_SLUGS)
        with self.client.get(
            f"/v1/orgaos/{slug}",
            name="Googlebot /v1/orgaos/[slug]",
            catch_response=True,
            timeout=20,
        ) as r:
            if r.status_code in (200, 404):
                r.success()
            else:
                r.failure(f"{r.status_code}")

    @task(2)
    def sector_observatorio(self):
        sector = random.choice(SAMPLE_SECTORS)
        with self.client.get(
            f"/v1/observatorio/{sector}",
            name="Googlebot /v1/observatorio/[setor]",
            catch_response=True,
            timeout=20,
        ) as r:
            if r.status_code in (200, 404):
                r.success()
            else:
                r.failure(f"{r.status_code}")


class HealthProbeUser(HttpUser):
    """Probe paralelo /health/ready (deveria SEMPRE retornar 200 <2s)."""

    weight = 1
    wait_time = between(5.0, 10.0)

    @task
    def health_ready(self):
        with self.client.get(
            "/health/ready",
            name="health/ready",
            catch_response=True,
            timeout=5,
        ) as r:
            if r.status_code == 200 and r.elapsed.total_seconds() < 2.0:
                r.success()
            else:
                r.failure(f"health degraded {r.status_code} {r.elapsed.total_seconds():.2f}s")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print summary stats; fail run if p95 > 5s ou error_rate > 5%."""
    stats = environment.stats.total
    p95 = stats.get_response_time_percentile(0.95)
    error_rate = stats.fail_ratio * 100
    print("\n=== Stage 4-7 Reproducer Summary ===")
    print(f"Total requests: {stats.num_requests}")
    print(f"P95 latency: {p95:.0f} ms")
    print(f"Error rate: {error_rate:.2f}%")
    if p95 > 5000 or error_rate > 5:
        print(f"FAIL: p95={p95}ms (>5000) or error_rate={error_rate}% (>5%)")
        environment.process_exit_code = 1
