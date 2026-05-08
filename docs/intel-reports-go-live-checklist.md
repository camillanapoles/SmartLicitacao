# Intel Reports — Checklist de Go-Live

**Issue:** #825 — Smoke test + validação go-live Intel Reports  
**Pré-requisito:** Issue #824 (bucket Supabase Storage) fechada ✓  
**Stack:** FastAPI + ARQ + Supabase Storage + Stripe one-time payment

---

## Execução Rápida (automação)

```bash
# 1. Validação de infra (rodar do root do projeto)
./scripts/validate_intel_reports_infra.sh

# 2. Smoke tests unitários
cd backend && python3 -m pytest tests/test_intel_reports_smoke.py -v

# 3. Cobertura completa intel-reports
cd backend && python3 -m pytest tests/test_intel_report_billing.py tests/test_intel_report_job.py tests/test_intel_reports_smoke.py -v
```

---

## Checklist Detalhado

### Infra

- [ ] **Bucket `intel-reports` existe** no Supabase Storage e é privado  
  Verificar: Supabase Dashboard → Storage → intel-reports (tipo: Private)  
  Alternativa via API:
  ```bash
  export SUPABASE_ACCESS_TOKEN=$(grep SUPABASE_ACCESS_TOKEN .env | cut -d= -f2)
  curl -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
    "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/storage/buckets"
  ```

- [ ] **Bucket aceita upload via service_role** — testar com arquivo dummy:
  ```bash
  cd backend
  python3 -c "
  from supabase_client import get_supabase
  sb = get_supabase()
  result = sb.storage.from_('intel-reports').upload(
      path='smoke-test/dummy.txt',
      file=b'smoke test',
      file_options={'content-type': 'text/plain', 'upsert': 'true'}
  )
  print('Upload OK:', result)
  sb.storage.from_('intel-reports').remove(['smoke-test/dummy.txt'])
  print('Cleanup OK')
  "
  ```

- [ ] **Stripe product configurado** com `mode=payment`, `unit_amount=19700`, `currency=brl`  
  Verificar via Dashboard Stripe ou:
  ```bash
  # Requer STRIPE_SECRET_KEY
  curl -s -u $STRIPE_SECRET_KEY: \
    "https://api.stripe.com/v1/products?limit=10" | python3 -m json.tool | grep -A5 "Intel Report"
  ```

- [ ] **Webhook `checkout.session.completed` registrado** em `https://api.smartlic.tech/webhooks/stripe`  
  Verificar: https://dashboard.stripe.com/webhooks  
  Eventos obrigatórios:
  - `checkout.session.completed`
  - `checkout.session.async_payment_succeeded` (para Boleto/PIX)
  - `payment_intent.payment_failed`

- [ ] **Worker ARQ rodando** com `generate_intel_report` registrado  
  Verificar via Railway:
  ```bash
  railway logs --tail --service bidiq-worker 2>/dev/null | grep -i "generate_intel_report\|Worker started"
  ```
  Ou confirmar via testes:
  ```bash
  cd backend && python3 -m pytest tests/test_intel_report_job.py::test_worker_settings_registers_generate_intel_report -v
  ```

---

### Fluxo de Compra (CNPJ — R$197)

- [ ] **CTA visível** em `/cnpj/{cnpj}` → redireciona para Stripe Checkout  
  Testar: acessar https://smartlic.tech/cnpj/52407089000109 e verificar botão de compra

- [ ] **Checkout Stripe abre** com produto "Relatório Intel CNPJ" e preço R$197,00

- [ ] **Pagamento com cartão de teste** → redirect para `/intel-reports/{sessionId}`  
  Cartão de teste Stripe: `4242 4242 4242 4242`, validade qualquer futura, CVV `123`  
  Após redirect, page deve mostrar status `pending` → `generating` → `ready`

- [ ] **Polling recebe status `ready`** dentro de 120s  
  Verificar via Rails logs:
  ```bash
  railway logs --tail --service bidiq-worker 2>/dev/null | grep "purchase_id\|status.*ready\|Intel Report"
  ```

- [ ] **Download PDF funciona** — verificar que resposta é `application/pdf` e começa com `%PDF`

- [ ] **Email `intel_report_ready.html` enviado** após geração — verificar em Resend Dashboard  
  https://resend.com/emails → filtrar por tag `category=intel_report`

---

### Fluxo de Cancelamento

- [ ] **Cancelar no Stripe** → redirect para `/intel-reports/cancelado`  
  Testar: iniciar checkout e clicar "Voltar" ou fechar antes de pagar

- [ ] **Nenhuma row criada** em `intel_report_purchases` para sessão cancelada  
  Verificar via Supabase Dashboard:
  ```sql
  SELECT * FROM intel_report_purchases ORDER BY created_at DESC LIMIT 5;
  ```

---

### Fluxo de Falha no Job

- [ ] **Simular falha no ARQ job** → status `failed` → refund Stripe automático disparado  
  Via Supabase Dashboard, inserir row com `status=pending` e `stripe_payment_intent_id` inválido:
  ```sql
  INSERT INTO intel_report_purchases (user_id, product_type, entity_key, status, stripe_payment_intent_id)
  VALUES ('USER_UUID', 'cnpj', 'TEST', 'pending', 'pi_invalid_test');
  ```
  Depois verificar que o job:
  1. Tenta 3 vezes (max_tries=3 no WorkerSettings)
  2. Na 3ª tentativa, chama `stripe.Refund.create`
  3. Atualiza status para `failed`

- [ ] **Email de notificação de falha** enviado ao usuário

---

### Segurança

- [ ] **Download sem auth → 401**  
  ```bash
  curl -i https://api.smartlic.tech/v1/intel-reports/SOME_ID/download
  # Esperado: HTTP/1.1 401
  ```

- [ ] **Status sem auth → 401**  
  ```bash
  curl -i https://api.smartlic.tech/v1/intel-reports/SOME_ID
  # Esperado: HTTP/1.1 401
  ```

- [ ] **Usuário B não acessa PDF de usuário A → 403** (não 404)  
  Verificar comportamento: autenticar como usuário B e tentar acessar purchase_id de usuário A  
  Esperado: `{"detail": "Acesso negado: este relatório não pertence ao usuário autenticado."}`

- [ ] **Smoke tests de segurança passam**:
  ```bash
  cd backend && python3 -m pytest tests/test_intel_reports_smoke.py -v -k "auth or forbidden"
  ```

---

### Observabilidade (Sentry)

- [ ] **Nenhum Sentry error** durante o fluxo completo  
  Monitorar: https://confenge.sentry.io/issues/?project=smartlic-backend  
  Verificar ausência de erros novos após execução do fluxo

- [ ] **ARQ job concluiu** com `status=ready` em <60s para CNPJ com dados existentes  
  Verificar via Railway Worker logs:
  ```bash
  railway logs --service bidiq-worker --tail
  ```

---

## Checklist de Rollback

Se algo falhar durante o go-live:

1. **Desabilitar CTA no frontend** — comentar ou feature-flag `IntelReportCTA.tsx`
2. **Cancelar compras pendentes** via Stripe Dashboard → pagamentos → reembolsar
3. **Verificar status** das rows em `intel_report_purchases`:
   ```sql
   SELECT status, count(*) FROM intel_report_purchases GROUP BY status;
   ```
4. **Verificar worker** no Railway — reiniciar se necessário:
   ```bash
   railway redeploy --service bidiq-worker -y
   ```

---

## Referências

- Implementação: `backend/routes/intel_reports.py` — 4 endpoints
- Job ARQ: `backend/jobs/queue/jobs.py` → `generate_intel_report`
- Webhook: `backend/webhooks/handlers/checkout.py` → `handle_intel_report_checkout_completed`
- Frontend success page: `frontend/app/intel-reports/[sessionId]/page.tsx`
- Frontend CTA: `frontend/app/cnpj/[cnpj]/IntelReportCTA.tsx`
- Frontend cancel page: `frontend/app/intel-reports/cancelado/`
- Testes unitários: `backend/tests/test_intel_report_billing.py`, `test_intel_report_job.py`, `test_intel_reports_smoke.py`
- Script de validação: `scripts/validate_intel_reports_infra.sh`

---

*Checklist gerado para issue #825 — Smoke test + validação go-live Intel Reports*
