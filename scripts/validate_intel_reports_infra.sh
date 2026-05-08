#!/usr/bin/env bash
# validate_intel_reports_infra.sh — Validação de pré-requisitos de infra para Intel Reports
#
# Uso:
#   chmod +x scripts/validate_intel_reports_infra.sh
#   ./scripts/validate_intel_reports_infra.sh
#
# Issue #825 — Smoke test + validação go-live Intel Reports

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

pass() { printf "${GREEN}[PASS]${NC} %s\n" "$1"; PASS=$((PASS + 1)); }
fail() { printf "${RED}[FAIL]${NC} %s\n" "$1"; FAIL=$((FAIL + 1)); }
warn() { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; WARN=$((WARN + 1)); }
section() { printf "\n── %s ──\n" "$1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
ENV_FILE="$ROOT_DIR/.env"

echo "=== Intel Reports Infra Validation ==="
printf "Data: %s\n\n" "$(date '+%Y-%m-%d %H:%M:%S')"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Railway CLI
# ─────────────────────────────────────────────────────────────────────────────
section "Railway CLI"

if command -v railway >/dev/null 2>&1; then
    pass "railway CLI instalado"
else
    fail "railway CLI não encontrado. Instale: npm i -g @railway/cli"
fi

warn "railway whoami — verificar manualmente (omitido para evitar prompts interativos)"
printf "       Execute: railway whoami\n"

# ─────────────────────────────────────────────────────────────────────────────
# 2. Variáveis de ambiente via .env local
# ─────────────────────────────────────────────────────────────────────────────
section "Variáveis de Ambiente (via .env local)"

REQUIRED_ENV_VARS="STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY RESEND_API_KEY FRONTEND_URL"

if [ -f "$ENV_FILE" ]; then
    pass ".env encontrado em $ENV_FILE"
    for var in $REQUIRED_ENV_VARS; do
        VALUE=$(grep "^${var}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
        if [ -n "$VALUE" ]; then
            pass "env var $var configurada"
        else
            warn "env var $var não encontrada no .env (verificar Railway Dashboard)"
        fi
    done
else
    warn ".env não encontrado em $ENV_FILE"
    printf "       Variáveis obrigatórias: %s\n" "$REQUIRED_ENV_VARS"
    printf "       Verificar via: railway variables --kv | grep -E '(STRIPE|SUPABASE|RESEND|FRONTEND)'\n"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 3. Worker ARQ — generate_intel_report registrado
# ─────────────────────────────────────────────────────────────────────────────
section "Worker ARQ"

WORKER_CONFIG="$BACKEND_DIR/jobs/queue/config.py"
if [ -f "$WORKER_CONFIG" ]; then
    pass "jobs/queue/config.py existe"
    if grep -q "generate_intel_report" "$WORKER_CONFIG" 2>/dev/null; then
        pass "generate_intel_report registrado em WorkerSettings"
    else
        fail "generate_intel_report NÃO encontrado em jobs/queue/config.py"
    fi
else
    fail "backend/jobs/queue/config.py não encontrado"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 4. Bucket "intel-reports" referenciado no código
# ─────────────────────────────────────────────────────────────────────────────
section "Supabase Storage — Bucket intel-reports"

JOBS_FILE="$BACKEND_DIR/jobs/queue/jobs.py"
if [ -f "$JOBS_FILE" ]; then
    if grep -q '"intel-reports"' "$JOBS_FILE" 2>/dev/null; then
        pass "Bucket 'intel-reports' referenciado em jobs/queue/jobs.py"
    else
        fail "Bucket 'intel-reports' NÃO encontrado em jobs/queue/jobs.py"
    fi
else
    fail "backend/jobs/queue/jobs.py não encontrado"
fi

# Validar bucket via Supabase Management API (opcional)
SUPA_TOKEN=""
SUPA_REF=""
if [ -f "$ENV_FILE" ]; then
    SUPA_TOKEN=$(grep "^SUPABASE_ACCESS_TOKEN=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
    SUPA_REF=$(grep "^SUPABASE_PROJECT_REF=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
fi

if [ -n "$SUPA_TOKEN" ] && [ -n "$SUPA_REF" ]; then
    BUCKET_RESP=$(curl -sf --connect-timeout 10 \
        -H "Authorization: Bearer $SUPA_TOKEN" \
        "https://api.supabase.com/v1/projects/$SUPA_REF/storage/buckets" 2>/dev/null || echo "")
    if echo "$BUCKET_RESP" | grep -q '"intel-reports"' 2>/dev/null; then
        pass "Bucket 'intel-reports' confirmado no Supabase Storage"
    else
        fail "Bucket 'intel-reports' NÃO encontrado no Supabase Storage"
        printf "       Criar: Supabase Dashboard → Storage → New bucket → Nome: intel-reports, Tipo: Private\n"
    fi
else
    warn "SUPABASE_ACCESS_TOKEN/PROJECT_REF não disponíveis — validação do bucket omitida"
    printf "       Para validar: export SUPABASE_ACCESS_TOKEN e SUPABASE_PROJECT_REF no .env\n"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 5. Rotas backend e guards de segurança
# ─────────────────────────────────────────────────────────────────────────────
section "Rotas Backend e Guards de Segurança"

ROUTES_FILE="$BACKEND_DIR/routes/intel_reports.py"
if [ -f "$ROUTES_FILE" ]; then
    pass "routes/intel_reports.py existe"

    if grep -q "status_code=403" "$ROUTES_FILE" 2>/dev/null; then
        pass "Fix 403 ownership check implementado (distingue 404 inexistente de 403 não-dono)"
    else
        fail "Fix 403 NÃO implementado — usuário B receberia 404 em vez de 403 ao acessar PDF alheio"
    fi

    if grep -q '"ready"' "$ROUTES_FILE" 2>/dev/null; then
        pass "Status check usa 'ready' (alinhado com o job ARQ que salva status='ready')"
    else
        warn "Status check pode estar usando 'completed' em vez de 'ready' — inconsistência com o job ARQ"
    fi
else
    fail "routes/intel_reports.py não encontrado"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 6. Arquivos de teste existentes
# ─────────────────────────────────────────────────────────────────────────────
section "Cobertura de Testes"

TESTS_DIR="$BACKEND_DIR/tests"
for test_file in test_intel_report_billing.py test_intel_report_job.py test_intel_reports_smoke.py; do
    if [ -f "$TESTS_DIR/$test_file" ]; then
        pass "Arquivo de teste $test_file existe"
    else
        fail "Arquivo de teste $test_file NÃO encontrado"
    fi
done

# ─────────────────────────────────────────────────────────────────────────────
# 7. Stripe webhook (opcional — requer STRIPE_SECRET_KEY)
# ─────────────────────────────────────────────────────────────────────────────
section "Stripe Webhook"

STRIPE_KEY=""
if [ -f "$ENV_FILE" ]; then
    STRIPE_KEY=$(grep "^STRIPE_SECRET_KEY=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
fi

if [ -n "$STRIPE_KEY" ]; then
    WEBHOOKS=$(curl -sf --connect-timeout 10 \
        -u "${STRIPE_KEY}:" \
        "https://api.stripe.com/v1/webhook_endpoints?limit=10" 2>/dev/null || echo "")
    if echo "$WEBHOOKS" | grep -q "checkout.session.completed" 2>/dev/null; then
        pass "Webhook checkout.session.completed registrado no Stripe"
    else
        warn "checkout.session.completed não detectado — verificar: https://dashboard.stripe.com/webhooks"
    fi
else
    warn "STRIPE_SECRET_KEY não disponível — validação de webhook Stripe omitida"
    printf "       Verificar manualmente: https://dashboard.stripe.com/webhooks\n"
    printf "       Evento obrigatório: checkout.session.completed\n"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Resumo
# ─────────────────────────────────────────────────────────────────────────────
printf "\n═══════════════════════════════════════\n"
printf "  Resultado: PASS=%s  FAIL=%s  WARN=%s\n" "$PASS" "$FAIL" "$WARN"
printf "═══════════════════════════════════════\n"

if [ "$FAIL" -gt 0 ]; then
    printf "${RED}RESULTADO: FALHOU (%s checks falharam)${NC}\n" "$FAIL"
    printf "Corrija os itens [FAIL] antes do go-live.\n"
    exit 1
elif [ "$WARN" -gt 0 ]; then
    printf "${YELLOW}RESULTADO: OK COM AVISOS (%s warnings)${NC}\n" "$WARN"
    printf "Revise os [WARN] antes do go-live em produção.\n"
    exit 0
else
    printf "${GREEN}RESULTADO: TUDO OK — pronto para go-live${NC}\n"
    exit 0
fi
