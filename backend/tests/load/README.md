# Backend Load Tests — Stage Pattern Reproducers

Locust scenarios reproduzem padrões de saturação observados em prod.

## Stage 4-7 Pattern (`stage_4_7_pattern.py`)

Reproduz wedge backend 2026-04-27 a 29:
- SSG burst (31 workers, weight=5)
- Googlebot crawl (weight=4)
- Health probe (weight=1, monitoring)

### Local smoke
```bash
pip install locust==2.32.0
cd backend/tests/load
locust -f stage_4_7_pattern.py --host http://localhost:8000 --users 5 --run-time 30s --headless
```

### Weekly CI
Workflow `.github/workflows/load-test-weekly.yml` cron Sun 02:00 UTC contra `https://api.smartlic.tech`.

### Thresholds
- p95 latency: <5000ms
- error_rate: <5%

Falha CI publica Sentry alert.
