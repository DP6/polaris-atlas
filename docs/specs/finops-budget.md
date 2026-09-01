# Spec — Domínio: FinOps — Budget de custo

**Versão:** 1.7 (refresh visual R2-11 — `GET /finops/{p}/table-scores`:
score de eficiência de custo por tabela [3 fatores: particionamento,
utilização, eficiência de scan] + agregado do projeto ponderado por
tamanho. Fórmula **provisória**, ver Q-002. Nenhuma query BQ nova. v1.6:
`GET /finops/{p}/cost-series` (série query+storage pro gráfico combo).
v1.5: CRUD de meta de custo por usuário (`domains/budget`). v1.4: cache de
audit log **incremental**, janela 30 → **31 dias** — ver ASM-001)
**Status:** Aprovada
**Fase:** 4 — FinOps (segunda frente: budget por dataset/projeto)
**Última atualização:** 2026-09-01

---

## Objetivo

Três visões de custo do mês corrente, todas derivadas da mesma fonte já
usada pelo scanner de desperdício — nenhuma integração nova:

1. **Custo agrupado, agrupamento configurável** — Tabela | Dataset |
   Usuário | Dia | Mês | Ano (`group_by`). A v1.1 tinha substituído o
   "custo por dataset" fixo da v1.0 pelo `group_by` genérico (table por
   default cobria o caso, achatando dataset em detalhe extra) — a v1.2
   trouxe `dataset` de volta como uma **opção** dentro do mesmo
   `group_by` (pedido do usuário: granularidade de tabela é demais pra
   uma visão "quanto cada área/dataset custa", útil quando um
   dataset ≈ um time/domínio de dado). Ver "Agrupamento configurável"
   abaixo.
2. **Top N queries mais caras** — os jobs individuais de maior custo.
3. **Projeção do mês** — custo até agora, média diária, projeção pro
   total do mês.

*(A v1.0 também tinha "top N gastadores" como visão separada — removida
na v1.1: `group_by=user` cobre o mesmo caso, sem duplicar lógica de
agregação.)*

---

## Fonte de dados — por que não precisa de nada novo configurado

A opção óbvia seria **BigQuery Billing Export** (Cloud Billing exportado
pra uma tabela BigQuery) — mas ela quebra custo só por **projeto + SKU**,
nunca por dataset/tabela individual, então não resolveria "quanto esse
dataset custou" mesmo se configurada. A granularidade que este domínio
precisa só existe nos **audit logs de jobs do BigQuery** (Cloud Logging,
`jobservice.jobcompleted`) — mesma fonte que `scan_unused_tables`/
`scan_partition_candidates` já leem, com dois campos que nenhuma outra
função deste domínio usava antes: `principalEmail` (quem rodou) e
`jobConfiguration.query.query` (o texto da query, truncado em 2000
caracteres — `repository._QUERY_TEXT_MAX_CHARS` — pra não inflar a
resposta de top queries).

Nenhuma API nova, nenhuma role de IAM nova — `roles/logging.privateLogViewer`
já é exigido no checklist de `docs/onboarding-cliente.md` pra lineage/
access/scanner de desperdício, e cobre budget também.

### É uma estimativa, não a fatura real

`totalBilledBytes × settings.bigquery_price_usd_per_tib` é a mesma conta
que o BigQuery mostra como prévia de custo antes de rodar uma query —
precisa **se o projeto usa cobrança on-demand** (por bytes escaneados,
o padrão, e a mesma premissa que já vale pra `domains/quality` e pro
scanner de desperdício). Se o projeto usa **flat-rate/Editions** (slots
reservados, custo fixo por capacidade), essa estimativa **não reflete o
gasto real** — nesse modelo o custo é por hora de slot, não por byte
escaneado. Isso não é uma limitação nova desta feature especificamente:
é a mesma premissa on-demand que já está embutida em toda estimativa de
custo do Hub. Documentado aqui porque budget é onde um número errado
mais provavelmente vira uma decisão financeira.

### Diferente do mapa de acesso: a SA do próprio Hub CONTA aqui

`domains/access` exclui a SA de runtime do Hub da agregação porque ali a
pergunta é "quem consome essa tabela de fora" (rodar profiling pela UI
não é um consumidor externo real). Budget pergunta outra coisa: "quanto
está sendo gasto de verdade nesse projeto" — e profiling/PII rodados
pela UI do Hub **custam dinheiro de verdade**, então devem contar tanto
em `group_by=table` quanto em `group_by=user` (a SA do Hub pode
legitimamente aparecer ali se o usuário rodar muitos scans). Nenhuma
exclusão é aplicada por identidade do principal.

### Bug real corrigido: regiões fantasma no agrupamento por tabela

**Sintoma observado em dev:** `groups` (então `by_dataset`) trazia
entradas como `region-US` com custo residual (~$0.07) sem corresponder
a nenhum dataset real do projeto.

**Causa raiz** (investigada com `gcloud logging read` + replay da lógica
de agregação contra ~5000 eventos reais de `observability-hub-dev`,
agosto/2026): `discover_regions()` / `repository.list_all_table_refs()` /
`repository.get_date_like_columns()` — usadas por `catalog`, `freshness`
e pelo próprio `finops` para descoberta de metadados a custo ~zero —
rodam queries region-qualificadas
(`` `project.region-X.INFORMATION_SCHEMA.*` ``). O audit log dessas
queries registra `referencedTables[].datasetId="region-US"` (ou
`region-EU`, etc.) e `tableId="INFORMATION_SCHEMA.SCHEMATA"` (ou
`.TABLES`, `.TABLE_STORAGE`...) — indistinguível, à primeira vista, de
uma tabela real de cliente chamada `region-US`. Na amostra investigada,
**4989 de 5000 jobs (99,8%)** eram esse ruído, todos disparados pela SA
de runtime do Hub — deixando só ~11 jobs de atividade real.

**Fix:** `repository._parse_table_ref()` descarta qualquer referência
cujo `table_id` comece com `INFORMATION_SCHEMA.`, na origem — benefício
automático para todas as funções deste domínio (`scan_unused_tables`,
`scan_partition_candidates`, `get_budget`), não só budget.
`service.get_budget()` reforça isso pulando o evento inteiro (não só a
atribuição de dataset, mas também `top_queries`) quando, após o filtro,
`real_tables` fica vazio — cobre tanto "só referenciava
INFORMATION_SCHEMA" quanto "só referenciava tabela de outro projeto".
Ver teste `test_parse_table_ref_filters_information_schema_probes`
(`tests/unit/finops/test_repository.py`) e
`test_get_budget_skips_events_with_no_real_table_information_schema_only`
(`tests/unit/finops/test_service.py`).

Esse era o bug real por trás de um relato inicial tecnicamente impreciso
(hipótese de iteração sobre `BQ_REGIONS` chamando
`INFORMATION_SCHEMA.JOBS`, o que este domínio nunca fez — `get_budget`
sempre leu só Cloud Logging). A causa raiz confirmada foi outra, mas o
sintoma reportado ($0.07 fantasma) era real.

---

## Endpoint da API

### GET /api/v1/finops/{project_id}/budget
Sempre relativo ao **mês corrente** (dia 1 até agora, UTC) — não é uma
janela fixa como o scanner de desperdício.

**Parâmetros opcionais:**
- `group_by` (query, default `table`) — um de `table`, `dataset`,
  `user`, `day`, `month`, `year`. Ver "Agrupamento configurável".
- `limit` (query, default `10`, mínimo `1`, máximo `50`) — tamanho de
  `top_queries`.

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "period_start": "2026-08-01T00:00:00Z",
  "lookback_days": 15,
  "group_by": "table",
  "groups": [
    {
      "key": "observability-hub-dev.RAW.ga4_events",
      "cost_usd": 5.68,
      "billed_bytes": 1000000000000,
      "job_count": 12
    }
  ],
  "total_cost_usd": 8.88,
  "top_queries": [
    {
      "job_id": "bqjob_...",
      "principal_email": "ana@dp6.com.br",
      "executed_at": "2026-08-14T14:33:05Z",
      "billed_bytes": 1000000000000,
      "cost_usd": 5.68,
      "tables": ["observability-hub-dev.RAW.ga4_events"],
      "query_text": "SELECT ..."
    }
  ],
  "projection": {
    "days_elapsed": 15,
    "days_in_month": 31,
    "cost_so_far_usd": 8.88,
    "daily_average_usd": 0.592,
    "projected_month_total_usd": 18.35
  },
  "budget_target_usd": 250.0,
  "warning": null
}
```

`budget_target_usd` (v1.5, refresh visual R2-9) — a meta de custo mensal
que **o usuário logado** cadastrou pra este projeto (escopo `project`),
lida do Firestore (ver "Cadastro de budget"). `null` quando não há
cadastro — o `ComboChart` do FinOps simplesmente não desenha a linha de
referência. Só o escopo `project` alimenta este campo; budgets de
dataset/tabela aparecem só no CRUD abaixo (a linha do gráfico geral do
projeto não teria como representar N metas de granularidade menor).
Depende de `get_current_user` (o endpoint deixou de ser puramente
project-scoped — passou a ter recorte por usuário).

---

## Cadastro de budget (CRUD — v1.5, refresh visual R2-9)

Metas de custo **por usuário**, não compartilhadas (ASM-005 do brief /
ASM-002 abaixo). Firestore, coleção `users/{email}/budgets/{doc_id}` —
mesmo lugar e mesmo racional dos favoritos (`domains/favorites`), sem
superfície de permissão nova. `doc_id` determinístico pelo alvo:

| `scope` | `doc_id` | Campos exigidos no upsert |
|---|---|---|
| `project` | `{project_id}` | — |
| `dataset` | `{project_id}__{dataset_id}` | `dataset_id` |
| `table` | `{project_id}__{dataset_id}__{table_id}` | `dataset_id` + `table_id` |

Registro salvo: `{ project_id, scope, dataset_id, table_id, amount_usd,
period: "month", created_by, created_at, updated_at }`. `amount_usd` é
sempre mensal nesta fase (`period` fixo — cadastro simples). `created_at`
/ `created_by` são **preservados** num upsert repetido do mesmo alvo
(reeditar o valor não reordena a lista, ordenada por `updated_at` desc,
nem reatribui autoria) — mesmo comportamento de `favorites.add_favorite`
pra `added_at`.

### GET /api/v1/finops/{project_id}/budgets
Lista os budgets do usuário logado no projeto. Filtro por `project_id` é
in-memory (coleção pequena — um punhado de budgets por usuário — evita
exigir índice composto no Firestore). Ordenado por `updated_at` desc.

```json
{ "project_id": "observability-hub-dev",
  "budgets": [
    { "project_id": "observability-hub-dev", "scope": "project",
      "dataset_id": null, "table_id": null, "amount_usd": 250.0,
      "period": "month", "created_by": "ana@dp6.com.br",
      "created_at": "2026-09-01T12:00:00Z", "updated_at": "2026-09-01T12:00:00Z" } ] }
```

### PUT /api/v1/finops/{project_id}/budgets
Upsert de um budget. Body `{ scope, dataset_id?, table_id?, amount_usd }`
(`BudgetUpsertRequest`). Validação de coerência escopo×campos no schema
(422 se `scope=dataset` sem `dataset_id`, `scope=table` sem `table_id`,
`scope=project` com qualquer um, ou `amount_usd <= 0`). Retorna o
`BudgetEntry` salvo (200).

### DELETE /api/v1/finops/{project_id}/budgets
Remove um budget. Query params `scope` (obrigatório), `dataset_id`,
`table_id`. `204` mesmo se o doc não existia (idempotente, aponta pro
`doc_id` exato sem query — igual ao DELETE de favoritos).

Os três exigem `require_project_access` (dependency do router, path tem
`project_id`) **e** `get_current_user` (recorte por usuário).

---

## Série temporal de custo (`cost-series` — v1.6, refresh visual R2-10)

Alimenta o gráfico combo da visão geral de FinOps (AC-FIN-RV-01/02):
custo de **query** e de **storage** por período, filtrável.

### GET /api/v1/finops/{project_id}/cost-series

**Parâmetros opcionais (query):**
- `granularity` — `day` (default) ou `month`. Chave do ponto = `YYYY-MM-DD`
  ou `YYYY-MM`.
- `cost_type` — `all` (default), `query`, `storage`. `query` pula a
  timeline de storage inteira (`storage_available=false`).
- `lookback_days` — 1–31, default 30. Teto de 31 porque o cache de audit
  log só guarda 31 dias (v1.4) e o gráfico combina os dois eixos.
- `datasets` — repetível; restringe a esses datasets.
- `tables` — repetível, forma `dataset.table`; restringe a essas tabelas.

**Response 200 (`CostSeriesResponse`):**
```json
{
  "project_id": "observability-hub-dev",
  "granularity": "day",
  "cost_type": "all",
  "period_start": "2026-08-03T00:00:00Z",
  "period_end": "2026-09-01T14:00:00Z",
  "points": [
    { "period": "2026-08-03", "query_cost_usd": 1.23,
      "storage_cost_usd": 0.44, "total_cost_usd": 1.67 }
  ],
  "storage_available": true,
  "cache_updated_at": null,
  "warning": null
}
```

`points` é **contíguo** (um ponto por dia/mês da janela, mesmo sem custo
— o gráfico não pode ter buraco).

### De onde vem cada série

| Série | Fonte | Custo BQ |
|---|---|---|
| `query_cost_usd` | Mesmo cache de audit log de `get_budget` (`get_scan_events_cached`, 31 dias) — nenhum scan novo. `total_billed_bytes` do evento somado no dia do `timestamp`, `× settings.bigquery_price_usd_per_tib`. Fan-out **não** aplicado: cada evento conta **uma vez** por período (evita inflar o total); com filtro de dataset/tabela, o evento entra se **qualquer** tabela real referenciada casar. | $0 (cache) |
| `storage_cost_usd` | `INFORMATION_SCHEMA.TABLE_STORAGE_USAGE_TIMELINE_BY_PROJECT` (fan-out por região, agregado no SQL — `SUM(COALESCE(total_logical_usage_bytes, total_physical_usage_bytes, 0))` por `usage_date`). Custo do dia = `bytes_GB × tarifa active / dias_do_mês` — usa a tarifa `active` (ignora o desconto long-term → linha de storage é um teto suave) e assume cobrança lógica/on-demand (mesma premissa de "É uma estimativa" acima). | Ver "Dry-run" abaixo |

### `storage_available` e degradação

`get_storage_cost_timeline` devolve `None` se **nenhuma** região respondeu
(permissão de metadado ausente, view indisponível na região, schema
diferente do esperado) — o service marca `storage_available=false`,
`storage_cost_usd` fica `0` em todos os pontos, `query_cost_usd` continua
válido, e um `warning` explica. Uma região que falha sozinha é ignorada
(as outras contam). **Nunca vira 500** — lição do incidente da rodada 1
(SQL nova quebrando `/validate` → 500 sem header de CORS → "Failed to
fetch"): qualquer `GoogleAPICallError`/`ValueError` da query é engolido
por região.

### Dry-run (regra do CLAUDE.md)

A query nova toca **só** `INFORMATION_SCHEMA.TABLE_STORAGE_USAGE_TIMELINE_BY_PROJECT`,
uma view de metadado — o BigQuery **não cobra** query sobre
`INFORMATION_SCHEMA` (mesma base $0 já assumida em
`repository.list_all_table_refs` / `get_date_like_columns`, que rodam
`region-X.INFORMATION_SCHEMA.*`). Um `dry_run` retornaria
`total_bytes_processed = 0`. Isso **precisa ser confirmado em dev** após o
deploy da branch `feat/r2-finops-cost-series` (o deploy é a verificação —
não há credencial de GCP no ambiente de desenvolvimento local pra rodar o
dry-run antes). Se por algum motivo a view cobrar, a degradação acima
ainda protege o endpoint; ajustar aqui se o dry-run em dev mostrar bytes.

---

## Score de eficiência de custo por tabela (v1.7, refresh visual R2-11)

Dois números pra AC-FIN-RV-03: um **por tabela** (coluna ordenável +
anel compacto no scanner de desperdício / Top ofensores; anel grande +
decomposição no drill-down) e um **do projeto** (anel "Eficiência de
custo" — já prototipado). Mesma escala 0–100, maior = mais eficiente.

### GET /api/v1/finops/{project_id}/table-scores

**Params opcionais:** `datasets` (repetível), `limit` (1–500, default 100).

**Response (`TableScoresResponse`):**
```json
{
  "project_id": "observability-hub-dev",
  "lookback_days": 30,
  "project_efficiency_score": 78,
  "tables": [
    { "dataset_id": "RAW", "table_id": "ga4_events_raw",
      "score": 34, "size_bytes": 812000000000,
      "observed_cost_usd_30d": 12.40, "is_partitioned": false,
      "factors": [
        { "name": "partitioning", "value": 0.12, "weight": 0.45,
          "detail": "Economia estimada de US$ 10.90 sobre US$ 12.40 ..." },
        { "name": "utilization", "value": 1.0, "weight": 0.30,
          "detail": "Consultada nos últimos 30 dias" },
        { "name": "scan_efficiency", "value": 0.4, "weight": 0.25,
          "detail": "Bytes escaneados em 30d = 15.0× o tamanho da tabela" }
      ] }
  ],
  "cache_updated_at": null,
  "warning": null
}
```
`tables` vem ordenado **pior score primeiro** (empate → maior primeiro).

### Fórmula (PROVISÓRIA — Q-002)

`score = round(100 · Σ fator.value · fator.weight)`, três fatores, pesos
somando 1.0. **Só sinais que o domínio `finops` já tem** — nada de drift
de schema (`domains/quality`) nem "é órfã" (`domains/lineage`): domínios
são isolados (CLAUDE.md). Esses sinais, se quisermos, entram depois por um
campo alimentado por um job que cruza domínios, não por import.

| Fator | Peso | `value` (0–1) |
|---|---|---|
| `partitioning` | 0.45 | `1.0` se particionada, ou sem candidata a partição, ou sem custo de scan observado. Senão `clamp(1 − economia_otimista_particionamento / custo_scan_30d, 0, 1)` — `0` = quase todo o custo dá pra economizar particionando. Reaproveita `scan_partition_candidates`. |
| `utilization` | 0.30 | `1.0` se escaneada ≥ 1× em 30d. Senão `clamp(1 − size_gb / 100, 0, 1)` — tabela ≥ 100 GB nunca consultada em 30d → `0` (storage pago sem retorno). |
| `scan_efficiency` | 0.25 | `1 / (1 + (bytes_escaneados_30d / size_bytes) / 10)` — escanear a tabela inteira 10× em 30d → `0.5`; premia pruning / cache / filtros. `1.0` se sem scan oneroso. |

**Score do projeto** = média dos scores por tabela **ponderada por
`size_bytes`** (as grandes dominam o custo); fallback pra média simples se
todos os tamanhos forem 0; `100` se não há tabela.

### Custo BQ

**Nenhuma query nova.** Usa `list_all_table_refs` +
`get_tables_metadata` (REST `get_table`, cacheado) + o cache de audit log
+ `scan_partition_candidates` (que já roda `get_date_like_columns` só nas
tabelas > 1 GB não particionadas). Sem `dry_run` a reportar.

---

## Agrupamento configurável (`group_by`)

Uma ou mais chaves por evento, calculadas em `service._group_keys()`:

| `group_by` | Chave | Cardinalidade por evento |
|---|---|---|
| `table` (default) | `project.dataset.table` de cada tabela real referenciada | 1 por tabela tocada — fan-out em `JOIN`, mesma aproximação de "custo por dataset" da v1.0 |
| `dataset` (v1.2) | `project.dataset` de cada dataset real referenciado | 1 por dataset tocado — mesmo fan-out do `table`, mas deduplicado a nível de dataset: duas tabelas do mesmo dataset no mesmo evento (`JOIN` entre elas) contam **uma vez** pro dataset, não duas |
| `user` | `principal_email` | 1 |
| `day` | `timestamp.date().isoformat()` | 1 |
| `month` | `timestamp.strftime('%Y-%m')` | 1 |
| `year` | `str(timestamp.year)` | 1 |

`table` e `dataset` são os únicos com fan-out (uma query com `JOIN`
soma o custo inteiro em cada tabela/dataset tocado, não dividido pela
proporção real de bytes — mesma limitação da v1.0, ver "Fora do
escopo"); as demais dimensões são 1:1 por evento. Link de "voltar pro
dataset" na UI (`BudgetPage.tsx::groupKeyLink`) funciona igual nos dois
— a chave de `dataset` já É `project.dataset`, sem terceiro segmento
pra cortar.

---

## Lógica de agregação

```python
# domains/finops/service.py
def get_budget(
    logging_client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
    group_by: BudgetGroupBy = BudgetGroupBy.TABLE,
    limit: int = 10,
) -> BudgetResponse:
    """
    1. month_start = dia 1 do mês corrente, 00:00 UTC. lookback_days =
       dias desde month_start + 1 — usado só pra projeção/caveat; NÃO é
       mais passado pro scan (ver passo 2).
    2. Busca eventos com repository.get_scan_events_cached() — lê o cache
       incremental de 31 dias (mesmo blob que partition-candidates usa,
       ver finops-waste-scanner.md v1.4, "Fonte de dados"). Cache miss
       levanta EventCacheNotReadyError → BudgetResponse vazio com warning
       (não escaneia mais ao vivo). O recorte pro mês corrente sai do
       filtro do passo 3, não de uma janela de scan menor.
       referenced_tables já vem sem entradas INFORMATION_SCHEMA (filtro
       na origem, repository._parse_table_ref). Retorna também
       cache_updated_at, propagado pra BudgetResponse.
    3. Descarta evento sem timestamp, anterior a month_start (a folga do
       passo 1 pode trazer eventos do fim do mês anterior),
       com total_billed_bytes <= 0, ou cujo real_tables (tabelas
       referenciadas que pertencem a este project_id) fique vazio depois
       do filtro — ver "Bug real corrigido: regiões fantasma".
    4. Por evento: soma total_billed_bytes/job_count em uma ou mais
       chaves via _group_keys(group_by, event, real_tables); guarda a
       linha bruta de CostlyQuery.
    5. groups ordenado por custo desc; top_queries ordenado por custo
       desc, cortado em `limit`.
    6. Projeção: daily_average = custo_total_do_mês_até_agora /
       lookback_days (dias corridos do mês, não só dias com atividade —
       um mês com poucos dias ativos não deve inflar a média).
       days_in_month via calendar.monthrange(). projected_total =
       daily_average × days_in_month.
    """
```

---

## Estrutura de arquivos

```
apps/backend/src/observability_hub/
├── api/v1/
│   └── finops.py          # + GET /finops/{project_id}/budget?group_by=...
│                          # + GET/PUT/DELETE /finops/{project_id}/budgets (CRUD, v1.5)
│                          # + GET /finops/{project_id}/cost-series (v1.6)
│                          # + GET /finops/{project_id}/table-scores (v1.7)
├── domains/finops/
│   ├── service.py          # + get_budget() (user_email → budget_target_usd); + get_cost_series() (v1.6); + _table_efficiency_score() + compute_table_scores() (v1.7)
│   ├── repository.py       # ScanEvent + get_scan_events_cached() (cache, ver finops-waste-scanner.md v1.4); _parse_table_ref filtra INFORMATION_SCHEMA; + StorageTimelineDay + get_storage_cost_timeline() (v1.6)
│   └── schemas.py          # + BudgetResponse (+ budget_target_usd); + CostSeries* (v1.6); + TableScoreFactor, TableScore, TableScoresResponse (v1.7)
├── domains/budget/          # v1.5 — CRUD de meta de custo por usuário (Firestore, espelha domains/favorites)
│   ├── schemas.py           # BudgetScope, BudgetEntry, BudgetUpsertRequest, BudgetListResponse
│   ├── repository.py        # _budget_doc_id, list/upsert/remove_budget, get_project_budget_amount
│   └── service.py           # wrappers finos sobre repository
└── tests/unit/
    ├── finops/test_service.py      # + get_budget/budget_target_usd + get_cost_series (v1.6) + _table_efficiency_score / compute_table_scores (v1.7)
    ├── finops/test_repository.py   # + INFORMATION_SCHEMA filter + get_storage_cost_timeline (v1.6)
    └── budget/{test_repository,test_service}.py  # v1.5 — doc_id por escopo, preservação de created_at, get_project_budget_amount
```

Frontend (`apps/frontend/src/features/finops/BudgetPage.tsx`): duas
abas via `Tabs` do shadcn/ui — "Custo por agrupamento" (seletor de
`group_by` em pill buttons, tabela ordenável, total no rodapé via
`TableFooter`) e "Queries mais caras" (tabela ordenável por custo/bytes/
data; coluna "Tabelas" como badges; texto da query oculto por padrão,
com toggle "Ver query"/"Ocultar query" por linha que expande um bloco
`SqlPreview` — mesmo componente compartilhado do preview de SQL do
profiling — abaixo da linha, evitando a sobreposição visual que a v1.0
tinha com o texto da query inline na célula).

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Referência a `INFORMATION_SCHEMA.*` (probes de região do próprio Hub) | Filtrada na origem (`repository._parse_table_ref`) — nunca vira dataset/tabela fantasma em nenhum `group_by` |
| Evento cujas `referenced_tables`, após o filtro acima, não sobra nenhuma do `project_id` (só probe ou só tabela de outro projeto) | Evento inteiro pulado — não entra em `groups` nem em `top_queries` |
| Evento com `total_billed_bytes <= 0` | Ignorado em toda agregação — não soma custo nem `job_count` |
| Evento anterior a `month_start` | Ignorado (a folga de `lookback_days = dias + 1` pode trazer alguns) |
| Query com `JOIN` entre tabelas (`group_by=table`) | Custo somado em **cada** tabela tocada, não dividido — mesma aproximação do scanner de desperdício |
| Query com `JOIN` entre tabelas do mesmo dataset (`group_by=dataset`) | Custo somado **uma vez** pro dataset (dedup via `set`), diferente de `group_by=table` — evita inflar artificialmente o custo de um dataset só porque a query tocou duas tabelas dele |
| Mesmo usuário com múltiplos jobs no mês (`group_by=user`) | Um único `CostGroup`, `job_count` e `billed_bytes` somados |
| Texto de query maior que 2000 caracteres | Truncado com "…" no fim (`repository._QUERY_TEXT_MAX_CHARS`) |
| Mês com mais de 31 dias corridos até agora (dia 31 de mês de 31 dias) | O cache incremental cobre 31 dias, então o mês corrente **inteiro** cabe na janela — o `_BUDGET_RETENTION_CAVEAT` volta a disparar só quando os audit logs realmente expiraram (retenção de 30 dias do Cloud Logging sem sink customizado), não sempre no dia 31 (regressão da v1.3 revertida) |
| Nenhum evento de job no projeto | `warning` populado (mesmo texto/causas de lineage/access/scanner de desperdício), `groups`/`top_queries` vazios |
| Cache hit / miss (`EventCacheNotReadyError`) / falha de cache / `429` no Job | Idêntico ao documentado em `finops-waste-scanner.md` v1.4, "Casos de borda" e "Critérios de aceite" — `get_scan_events_cached` é compartilhado pelos dois endpoints; o request path não escaneia mais ao vivo |
| `limit` fora do intervalo 1–50 | HTTP 422 (validação do `Query(ge=1, le=50)`) |
| `group_by` fora do enum | HTTP 422 (validação do `Query` com `BudgetGroupBy`) |
| **cost-series:** `lookback_days` fora de 1–31 | Clampado no service (não é 422) — o teto de 31 é o limite do cache, não uma escolha do chamador |
| **cost-series:** timeline de storage indisponível em todas as regiões | `storage_available=false`, `storage_cost_usd=0` em todos os pontos, `query_cost_usd` intacto, `warning` explica — nunca 500 |
| **cost-series:** dia sem query e sem storage | Ponto presente com os três valores `0` (série contígua, sem buraco) |
| **cost-series:** `cost_type=query` | Timeline de storage nem é consultada; `storage_available=false` |

---

## Suposições

| ID | Suposição | Status |
|---|---|---|
| ASM-001 | `budget` usa o mesmo cache de `partition-candidates` (não um scan com janela month-to-date variável): o recorte pro mês corrente já era feito por `event.timestamp < month_start` no service, não pela janela do scan. Desde a v1.4 a janela do cache é **31 dias** (evicção do Job incremental), então o mês corrente inteiro cabe — o efeito colateral da v1.3 (o `_BUDGET_RETENTION_CAVEAT` disparar sempre no dia 31) foi revertido. | confirmada |
| ASM-002 | **cost-series:** `INFORMATION_SCHEMA.TABLE_STORAGE_USAGE_TIMELINE_BY_PROJECT` é uma view de metadado que o BigQuery **não cobra** (query $0), mesma base de `list_all_table_refs`/`get_date_like_columns`. Precisa ser confirmada por `dry_run` em dev depois do deploy de `feat/r2-finops-cost-series` — não há credencial de GCP no ambiente local pra rodar antes. Se cobrar, a degradação `storage_available=false` já protege; ajustar a fonte da série de storage. | aberta |
| ASM-003 | **cost-series:** custo de storage por dia usa a tarifa `active` e bytes lógicos (`total_logical_usage_bytes`, com fallback pra `total_physical_usage_bytes`), dividido pelos dias do mês — a linha de storage é um teto suave (ignora desconto long-term) e assume cobrança lógica/on-demand, mesma premissa do resto do domínio. Suficiente pra um gráfico direcional; não é fatura. | confirmada |

---

## Fora do escopo desta spec

- **Terceira frente de FinOps** (otimizações sugeridas de clustering/tipo
  de coluna) — fica pra depois.
- **Custo real exato** via BigQuery Billing Export — decisão consciente
  de não usar, ver "Fonte de dados" (não teria a granularidade de
  dataset que este domínio precisa, mesmo se configurado).
- **Suporte a projetos flat-rate/Editions** — a estimativa assume
  cobrança on-demand; num projeto flat-rate os números aqui não
  refletem o gasto real (mesma premissa já embutida em `domains/quality`
  e no scanner de desperdício).
- **Histórico entre meses** — só o mês corrente; sem persistência,
  cada consulta reflete só a janela de audit logs disponível agora.
- **Atribuição proporcional de custo em JOINs multi-tabela** — custo
  soma inteiro em cada tabela tocada (`group_by=table`), não dividido
  pela proporção real de bytes por tabela dentro do job (dado que não
  está disponível no audit log).
- **Combinar duas dimensões de `group_by` na mesma resposta** (ex:
  usuário × dia) — só uma dimensão por chamada; cruzar dimensões fica
  pra uma iteração futura se houver demanda concreta.


---

## Refresh visual - pendente (2026-09)

Pedidos do brief `frontend-visual-refresh.md` (sec. FinOps). Feature de dataviz
nova; branch propria depois do review. Ver
`frontend-visual-refresh-plan.md` sec.5. Escopo de budget **travado**: so
cadastro simples (dataset **e** tabela), sem compartilhamento entre
usuarios (ASM-005 do brief).

| ID | Comportamento | Teste |
|---|---|---|
| AC-FIN-RV-01 | Grafico de custo = combo **coluna (diario) + linha (acumulado)**, com projecao tracejada e linha de budget. | `test_finops_cost_combo_chart` |
| AC-FIN-RV-02 | Filtros do grafico: dataset, tabela, granularidade (mes/dia), tipo de custo (query / storage / ambos). **Backend (R2-10):** `GET /finops/{p}/cost-series?granularity=&cost_type=&lookback_days=&datasets=&tables=` → série contígua de `query_cost_usd`/`storage_cost_usd`/`total_cost_usd` por período. | `test_get_cost_series_month_granularity_uses_year_month_keys`, `test_get_cost_series_dataset_filter_excludes_nonmatching_query_events`, `test_get_cost_series_cost_type_query_skips_storage`, `test_get_cost_series_adds_storage_cost_when_timeline_present` |
| AC-FIN-RV-03 | **Dois scores distintos**: (a) "Eficiencia de custo" geral do projeto (anel composto - ja prototipado); (b) "Score por tabela" individual - coluna "Score" ordenavel (anel compacto + numero) no scanner de desperdicio / Top ofensores **e** anel grande + decomposicao no drill-down da linha (Q-002). **Backend (R2-11):** `GET /finops/{p}/table-scores` → `project_efficiency_score` + `tables[].score` + `tables[].factors[]` (decomposicao). Formula provisoria (Q-002). | `test_table_efficiency_score_penalizes_large_never_scanned_table`, `test_table_efficiency_score_penalizes_unpartitioned_with_big_savings`, `test_compute_table_scores_sorts_worst_first_and_aggregates_project`, `test_compute_table_scores_uses_partition_candidate_savings` |
| AC-FIN-RV-04 | Cadastro de budget com granularidade por **dataset e por tabela** (`scope=project\|dataset\|table` no CRUD). So cadastro simples - sem convite/aceite/compartilhamento. GET/PUT/DELETE `/finops/{p}/budgets`, por usuario (Firestore). O valor de `scope=project` volta como `budget_target_usd` no `GET /finops/{p}/budget`. | `test_upsert_budget_dataset_scope_uses_two_segment_doc_id`, `test_upsert_request_rejects_dataset_scope_without_dataset_id`, `test_get_budget_injects_user_budget_target_from_firestore` |
| AC-FIN-RV-05 | "Top ofensores" com mini-grafico de tendencia de 7 dias por linha. | `test_finops_top_offenders_trend` |

Status (2026-09): **backend de AC-FIN-RV-02/03/04 implementado** —
R2-9 (`budgets` CRUD + `budget_target_usd`), R2-10
(`cost-series`), R2-11 (`table-scores`). Falta a UI: R2-12 monta
`FinOpsOverviewPage` consumindo os três endpoints (big numbers +
`ComboChart` com filtros + anel de eficiência + coluna "Score" +
drill-down + Top ofensores) — fecha AC-FIN-RV-01/02/03/05 no front. A
fórmula do score (Q-002) e os filtros do gráfico entram no review
do PR final.

Suposicao **ASM-FIN-RV-01** (respondida, R2-10/R2-11): AC-FIN-RV-02 exigiu
endpoint novo (`cost-series`) com query nova de storage (só
`INFORMATION_SCHEMA`, $0 — ASM-002); AC-FIN-RV-03 **não** exigiu query
nova (`table-scores` reaproveita `scan_partition_candidates` + metadado +
cache). Nenhum `dry_run` com bytes a reportar.

### Perguntas em aberto

| ID | Pergunta | Status |
|---|---|---|
| Q-002 | A fórmula do score por tabela (3 fatores — particionamento 0.45 / utilização 0.30 / eficiência de scan 0.25 — e o agregado do projeto ponderado por tamanho) é a certa? Pesos, limiares (`100 GB` pra zerar utilização, `10×` pra meia-nota de scan) e a ausência de "drift de schema" / "é órfã" (sinais cross-domain, deixados de fora de propósito) precisam de validação de produto. | aberta — revisar no PR final; a decomposição em `factors[]` na resposta existe justamente pra recalibrar sem quebrar contrato |

Suposicao **ASM-FIN-RV-02** (confirmada, R2-9): o budget mora em
`users/{email}/budgets` (por usuario), nao em `projects/{projectId}/budgets`
(compartilhado). Satisfaz ASM-005 do brief ("sem compartilhamento") sem
adicionar superficie de permissao nova — cada usuario ve e edita so os
seus, mesma fronteira dos favoritos. Se um dia o produto quiser budget de
equipe, e um endpoint/colecao nova, nao uma migracao deste.
