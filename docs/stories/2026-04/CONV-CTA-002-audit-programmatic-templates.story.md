# Story CONV-CTA-002: Audit e CTA em templates programáticos (W2)

## Status
Draft

## Validation Notes

**NO-GO @po 2026-05-01 (score 5/10)**

Gaps que reprovam o checklist:
- **AC (criterion 3):** "TBD — definir após signal 7d de CONV-CTA-001". AC ausentes por design (W2 gated).
- **Scope IN/OUT (criterion 4):** apenas paths listados; falta delimitar mudança (ex.: variante CTA, posicionamento, copy).
- **Complexity (criterion 6):** sem estimativa.
- **Risks (criterion 8):** não documentados.
- **DoD (criterion 9):** não definidos.

**Fix premature inviável:** dependência upstream (`CONV-CTA-001`) está em `InReview` — sem signal de produção 7-14d, AC desta W2 não podem ser derivados sem violar o design da Story (gating intencional).

**Re-validate gate:** quando `CONV-CTA-001` atingir `Done` + 7d em produção com bounce/CTR registrados, autor deve preencher AC + Scope IN/OUT + DoD + Risks e re-invocar `*validate-story-draft`.

## Epic
[EPIC-CONV-DIAG-2026-04-30](EPIC-CONV-DIAG-2026-04-30.md)

## Story

**As a** visitante orgânico que aterrissa em qualquer página programática do SmartLic,
**I want** ver um CTA claro de trial no topo/rodapé,
**so that** tenha caminho óbvio ao produto — sem depender do template da página individual.

**Escopo W2 (gated em signal 7-14d de CONV-CTA-001).**

## Paths a auditar (AC8 de CONV-CTA-001)

- `/cnpj/[cnpj]`
- `/orgaos/[slug]`
- `/municipios/[slug]`
- `/observatorio/[slug]`
- `/observatorio/raio-x-setor/[id]`
- `/observatorio/raio-x-municipio/[id]`
- `/observatorio/raio-x-orgao/[id]`
- `/observatorio/raio-x-alerta/[id]`
- `/contratos/[setor]`
- `/contratos/[setor]/[uf]`

## Acceptance Criteria

TBD — definir após signal 7d de CONV-CTA-001 (discriminador H1: bounce programmatic).

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-05-01 | 0.1 | Placeholder criado como AC8 de CONV-CTA-001. ACs a definir após W1 signal. | @dev |
| 2026-05-01 | 0.2 | NO-GO @po (score 5/10). AC=TBD por design + W1 (CONV-CTA-001) em InReview. Re-validar após W1 entregar 7d signal em produção. Permanece Draft. | @po |
