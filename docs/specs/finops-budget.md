# Spec — Domínio: FinOps — Budget de custo

**Versão:** 1.12 (2026-09-04 — fusão "Detalhamento de custo", branch
`feat/finops-cost-detail`: `GET /finops/{p}/budget` ganha
`include_storage` [bool, default `false`] — quando `true` e `group_by` é
`table`/`dataset`, `CostGroup` ganha `storage_cost_usd`/`total_cost_usd`
[**união** de chaves: toda tabela com storage > 0 aparece, mesmo as nunca
consultadas na janela — `cost_usd=0` nesse caso, sinal de tabela
abandonada]. Fonte nova só pro storage: `repository.get_storage_bytes_by_table`
[mesma `INFORMATION_SCHEMA.TABLE_STORAGE` de `get_current_storage_bytes`,
$0, agrupada por tabela em vez de somada]. A tela `BudgetPage`
["Budget de custo" → **"Detalhamento de custo"**, mesma rota
`/finops/budget`] passa a mostrar, quando `group_by` é tabela/dataset: um
ranking em barras empilhadas query+storage, colunas de custo
query/storage/total, comparação com a meta cadastrada por tabela/dataset
[`GET .../budgets`, já existia — só nunca tinha sido comparada com gasto
real em lugar nenhum da UI] e drill-down por linha [expande, busca sob
demanda a série diária via `cost-series` filtrado pra aquela
tabela/dataset]. Sem tela/rota/sidebar nova — tudo dentro da tela de
Budget já existente, decisão do usuário depois de um primeiro desenho
como tela separada.)
v1.11 (2026-09-04 — `GET /finops/{p}/cost-series` ganha `total_cost_usd`
na resposta [soma de `points[].total_cost_usd`, já filtrada por
`cost_type`/janela/`datasets`/`tables` — nenhuma query BQ nova]:
**implementado** na v1.12 acima como pré-requisito do fix abaixo. O card
"Gasto no mês" da `FinOpsOverviewPage` estava lendo `budget.total_cost_usd`
[só custo de query, e reagia ao filtro de período apesar do nome] — a
correção final (decidida com o usuário) foi diferente do desenho original
desta entrada: em vez de renomear um único card pra "Gasto no período",
a tela ganhou **dois** cards — "Gasto no mês" [sempre month-to-date real,
`budget.projection.cost_so_far_usd`, v1.10, nunca muda com o filtro] e
"Gasto no período filtrado" [novo, lê `seriesQuery.data.total_cost_usd`
— aqui sim a parte desta entrada — bate com o "Acumulado" do gráfico e
herda o filtro de `cost_type`, que antes só afetava o gráfico]. O filtro
de Período e de Tipo de custo saíram de dentro do `Panel` do gráfico pra
um bloco visual único que também contém o card filtrado, deixando claro
o que o filtro afeta. **Ainda planejado, não implementado nesta v1.12**:
o endpoint novo `GET /finops/{p}/cost-history` — totais **mensais**
persistidos no Firestore [`hub_projects/{p}/finops_daily_costs/{data}`,
granularidade diária, retenção **24 meses**, gravado pelo Job diário pra
**todo** `hub_project` — não só o projeto aberto na UI], fora do alcance
do cache de 31 dias de audit log, pra comparar até 24 meses pra trás. Não
interfere com a projeção month-to-date da v1.10 abaixo — `projection`
continua vindo só de `get_budget`.)
v1.10 (fix `fix/finops-projection-days-elapsed` — a projeção
mensal (`projection.projected_month_total_usd`) virou **month-to-date
real**, decidido pelo usuário entre as opções levantadas em
`finops-overview-date-range` (v1.9): `cost_so_far_usd`/`daily_average_usd`
passam a somar só os eventos do dia 1 do mês corrente até hoje, e
`days_elapsed` passa a ser `days_elapsed_in_month` (calendário) — nada
disso depende mais de `lookback_days`/`from`/`to`, que continuam só
recortando `groups`/`top_queries`/`total_cost_usd`. Antes (v1.8), a
projeção reusava a janela escolhida como base do run-rate; como
`lookback_days` (default 30) e `days_in_month` (28–31) ficavam sempre
próximos, `projected_month_total_usd` colapsava pra ≈ `cost_so_far_usd` —
achado registrado no CHANGELOG em `finops-overview-date-range` sem fix
aplicado. `BudgetResponse.lookback_days` (não mais
`projection.days_elapsed`) é o campo certo pra exibir "janela analisada"
no FE. Cabe sempre no cache de `_FINOPS_CACHE_MAX_DAYS` porque nenhum mês
tem mais de 31 dias (ASM-001).)
v1.9 (rodada 3 — filtro de data real na Visão Geral, AC-FIN-RV-02:
`GET /finops/{p}/budget` e `GET /finops/{p}/cost-series` ganham `from`/`to`
(query, `YYYY-MM-DD`) — um intervalo explícito, que passa a valer sobre
`lookback_days` quando presente. Continuam clampados no piso do cache
(~31 dias) e num fim de janela nunca no futuro — `_resolve_date_window`
central aos dois endpoints, nunca 422, sempre um `warning` quando algo foi
ajustado. `BudgetResponse` ganha `period_end` (só tinha `period_start`).
FE: `FinOpsOverviewPage` ganha os atalhos "Mês atual"/"Tudo" + dois
`DateField` ("De"/"Até") — a linha de teto do budget (`refLine`) só
aparece quando a janela efetiva tem ≥ 20 dias, pra não comparar um
intervalo curto contra uma meta mensal inteira.)
v1.8 (rodada 3 — `GET /finops/{p}/budget` ganhou `lookback_days`
(1–31, default 30); a janela deixou de ser fixa no mês corrente e a
projeção virou run-rate `média_da_janela × dias_do_mês`. FE: `LookbackPicker`
compartilhado, seletor 7/15/30 no gate do `BudgetPage`.)
v1.7 (refresh visual R2-11 — `GET /finops/{p}/table-scores`:
score de eficiência de custo por tabela [3 fatores: particionamento,
utilização, eficiência de scan] + agregado do projeto ponderado por
tamanho. Fórmula **provisória**, ver Q-002. Nenhuma query BQ nova. v1.6:
`GET /finops/{p}/cost-series` (série query+storage pro gráfico combo).
v1.5: CRUD de meta de custo por usuário (`domains/budget`). v1.4: cache de
audit log **incremental**, janela 30 → **31 dias** — ver ASM-001)
**Status:** Aprovada
**Fase:** 4 — FinOps (segunda frente: budget por dataset/projeto)
**Última atualização:** 2026-09-04 (v1.12)

---

## Objetivo

Três visões de custo da janela escolhida (default 30 dias), todas derivadas da mesma fonte já
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
4. **Comparação com meses anteriores** (v1.11, planejada — não
   implementada nesta v1.12) — totais mensais persistidos, até 24 meses
   pra trás. Ver "Histórico mensal (`cost-history` — v1.11)".
5. **Split query/storage e comparação com meta por tabela/dataset**
   (v1.12) — quando `group_by` é tabela ou dataset, `include_storage`
   soma o custo de storage (união com todas as tabelas que têm storage,
   mesmo sem query no período) e a UI compara com a meta cadastrada. Ver
   "Split de storage por tabela/dataset (`include_storage` — v1.12)"
   abaixo.

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
Janela **"últimos N dias"** (rodada 3; antes era fixo no mês corrente).

**Parâmetros opcionais:**
- `group_by` (query, default `table`) — um de `table`, `dataset`,
  `user`, `day`, `month`, `year`. Ver "Agrupamento configurável".
- `limit` (query, default `10`, mínimo `1`, máximo `50`) — tamanho de
  `top_queries`.
- `lookback_days` (query, default `30`, `1`–`31`) — janela analisada, só
  recorta `groups`/`top_queries`/`total_cost_usd`. `period_start = now -
  lookback_days`. Teto de 31 = retenção do cache de audit log (fora dele
  o `_BUDGET_RETENTION_CAVEAT` avisa). O service clampa (não é 422). A
  **projeção mensal** (objeto `projection`) é **independente** deste
  parâmetro — ver abaixo.
- `from`/`to` (query, `YYYY-MM-DD`, rodada 3 — filtro de data real da
  Visão Geral, AC-FIN-RV-02) — intervalo explícito, que **sobrescreve**
  `lookback_days` quando presente (`_resolve_date_window`). `to` clampado
  pra nunca ficar no futuro (vira hoje); `from` clampado pro piso do
  cache (hoje − 30 dias); se `from` vier depois de `to` após os clamps,
  o service troca os dois em vez de 422. Qualquer clamp entra no
  `warning` da resposta — nunca falha/trunca em silêncio.
- `include_storage` (query, default `false`, v1.12) — quando `true` e
  `group_by` é `table`/`dataset`, cada `CostGroup` ganha
  `storage_cost_usd`/`total_cost_usd` (`null` nos dois quando o flag é
  `false`, ou quando `group_by` não é table/dataset — ignorado
  silenciosamente nesse caso, sem erro). Ver "Split de storage por
  tabela/dataset" abaixo.

**Projeção mensal (`projection`) — month-to-date real, v1.10:**
sempre calculada sobre o dia 1 do mês corrente até hoje, **nunca** sobre
`lookback_days`/`from`/`to` (decisão do usuário — v1.8 tinha deixado a
projeção reusar a janela escolhida como base do run-rate, mas com
`lookback_days` default 30 ≈ `days_in_month`, `projected_month_total_usd`
colapsava pra ≈ `cost_so_far_usd`, achado sem fix em
`finops-overview-date-range`). `days_elapsed` = dias corridos do mês
corrente (`hoje.day`), `cost_so_far_usd`/`daily_average_usd` somam só os
eventos do mês corrente. Cabe sempre no cache de `_FINOPS_CACHE_MAX_DAYS`
(nenhum mês tem mais de 31 dias, ASM-001). Pra exibir a janela
efetivamente usada nas outras três visões (`groups`/`top_queries`/
`total_cost_usd`), o FE deve ler `lookback_days` (topo da resposta), não
mais `projection.days_elapsed`.

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "period_start": "2026-08-01T00:00:00Z",
  "period_end": "2026-08-15T00:00:00Z",
  "lookback_days": 15,
  "group_by": "table",
  "groups": [
    {
      "key": "observability-hub-dev.RAW.ga4_events",
      "cost_usd": 5.68,
      "billed_bytes": 1000000000000,
      "job_count": 12,
      "storage_cost_usd": null,
      "total_cost_usd": null
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
    "days_elapsed": 14,
    "days_in_month": 31,
    "cost_so_far_usd": 21.40,
    "daily_average_usd": 1.529,
    "projected_month_total_usd": 47.39
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
dataset/tabela até a v1.11 só apareciam no CRUD abaixo (a linha do gráfico
geral do projeto não teria como representar N metas de granularidade
menor) — a partir da v1.12, a tela "Detalhamento de custo" (`group_by`
tabela/dataset) compara cada `CostGroup` com a meta de mesmo escopo,
client-side (`GET .../budgets` já traz todos os escopos, ver "Split de
storage por tabela/dataset" abaixo). Depende de `get_current_user` (o
endpoint deixou de ser puramente project-scoped — passou a ter recorte
por usuário).

---

## Split de storage por tabela/dataset (`include_storage` — v1.12)

Antes da v1.12, `group_by=table`/`dataset` só somava custo de **query**
(via os mesmos eventos de audit log de sempre) — não havia como ver,
agrupado por tabela, quanto do custo é storage. `cost-series` (v1.6) já
faz esse split, mas como série temporal única do projeto inteiro, sem
quebra por tabela/dataset.

**Fonte:** `repository.get_storage_bytes_by_table` — mesma view
`INFORMATION_SCHEMA.TABLE_STORAGE` de `get_current_storage_bytes`
(metadado, $0), só que com `GROUP BY table_schema, table_name` em vez de
`SUM` — nenhuma query BigQuery nova de fato, é o mesmo padrão de
fan-out por região já usado em todo o domínio. Custo de storage por
chave usa a mesma metodologia "linha plana prorateada pelos dias da
janela" de `_storage_cost_for_day` (já usada em `cost-series`).

**União, não interseção:** quando `include_storage=true`, `groups`
passa a incluir toda tabela com `storage_bytes > 0` — mesmo as que não
tiveram nenhuma query na janela (`cost_usd=0` nesse caso). Decisão do
usuário: esse é o sinal mais útil de FinOps aqui — uma tabela abandonada
que só acumula custo de storage é exatamente o tipo de desperdício que
esse domínio existe pra achar, e escondê-la (só decorar as tabelas já
consultadas) deixaria esse caso invisível.

**Escopo do parâmetro:** só tem efeito com `group_by=table` ou
`group_by=dataset` — nas outras agregações (`user`/`day`/`month`/`year`)
não existe um "dono" natural de bytes de storage, então `include_storage`
é ignorado silenciosamente (sem warning, sem erro — `storage_cost_usd`/
`total_cost_usd` continuam `null`). Também é ignorado se o endpoint for
chamado sem `client` de BigQuery injetado (não deveria acontecer via API,
só relevante pra quem chama `service.get_budget` diretamente, ex. testes).

**Degradação:** se nenhuma região responder a query de storage
(permissão, schema, etc.), `groups` volta só com o custo de query
(comportamento pré-v1.12) e um `warning` explica o motivo — nunca falha o
endpoint inteiro por causa do storage.

**Frontend (`BudgetPage`, renomeada "Detalhamento de custo"):** quando
`group_by` é tabela/dataset, a aba "Custo por agrupamento" ganha um
toggle "Tipo de custo" (Tudo/Query/Storage — só filtra o gráfico de
ranking, o backend não tem esse parâmetro), um gráfico de barras
empilhadas com as 10 chaves de maior `total_cost_usd`, colunas extras na
tabela (custo query/storage/total + meta + badge "Dentro"/"Acima da
meta") e uma linha expansível por chave que busca sob demanda (só quando
expandida) a série diária via `cost-series` filtrado pra aquela
tabela/dataset (`tables=["dataset.table"]` ou `datasets=["dataset"]` —
sem o `project_id`, formato que o filtro de `cost-series` já espera).

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
- `from`/`to` (query, `YYYY-MM-DD`, rodada 3) — mesmo `_resolve_date_window`
  de `get_budget`: sobrescreve `lookback_days` quando presente, mesmo
  clamp no piso do cache e no fim no futuro, mesmo `warning` quando ajusta.
  `period_end` da resposta passa a refletir o `to` efetivo (antes era
  sempre "agora").
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
  "total_cost_usd": 8.41,
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

`total_cost_usd` (v1.11, **implementado na v1.12**) — soma de
`points[].total_cost_usd` da resposta inteira, já respeitando
`cost_type`/`datasets`/`tables`/janela (nenhuma soma nova: os pontos já
carregam o valor certo, isto só agrega). **Fonte do card "Gasto no
período filtrado" da `FinOpsOverviewPage`** — o card lê este campo em vez
de `budget.total_cost_usd`, garantindo que bate com o "Acumulado" do
`ComboChart` (mesma resposta) e reage a `cost_type`/data do jeito que o
gráfico já reage, sem chamada HTTP extra. Convive com um segundo card,
"Gasto no mês" (`budget.projection.cost_so_far_usd`, v1.10, sempre
month-to-date real, nunca muda com o filtro) — a v1.11 original previa só
um card renomeado; a v1.12 manteve os dois, decisão do usuário.
`budget_target_usd` e `projection` (month-to-date real, v1.10) continuam
vindo só de `GET .../budget` — não têm equivalente aqui.

### De onde vem cada série

| Série | Fonte | Custo BQ |
|---|---|---|
| `query_cost_usd` | Mesmo cache de audit log de `get_budget` (`get_scan_events_cached`, 31 dias) — nenhum scan novo. `total_billed_bytes` do evento somado no dia do `timestamp`, `× settings.bigquery_price_usd_per_tib`. Fan-out **não** aplicado: cada evento conta **uma vez** por período (evita inflar o total); com filtro de dataset/tabela, o evento entra se **qualquer** tabela real referenciada casar. | $0 (cache) |
| `storage_cost_usd` | `INFORMATION_SCHEMA.TABLE_STORAGE` — **snapshot atual**, `SUM(COALESCE(total_logical_bytes, 0))` por região (fan-out, minúscula). Vira uma **linha plana**: cada dia da janela recebe `bytes_GB × tarifa active / dias_do_mês`. Tarifa `active` (ignora desconto long-term → teto suave), cobrança lógica/on-demand (mesma premissa de "É uma estimativa"). **Não** usa a família `TABLE_STORAGE_USAGE_TIMELINE_*` (histórica) — ver "Por que snapshot, não timeline". | $0 (metadado) |

### `storage_available` e degradação

`get_current_storage_bytes` devolve `(None, motivo)` se **nenhuma** região
respondeu — `motivo` é a **1ª linha do erro real do BigQuery** (403 / 404
/ 400 …), propagada pro `warning` da resposta (`"… Motivo do BigQuery:
<motivo>."`). O service marca `storage_available=false`, `storage_cost_usd`
fica `0` em todos os pontos, `query_cost_usd` continua válido. Uma região
que falha sozinha é ignorada. **Nunca vira 500** — lição do incidente da
rodada 1 (SQL nova quebrando `/validate` → 500 sem header de CORS →
"Failed to fetch"): qualquer `GoogleAPICallError`/`ValueError` é engolido
por região. Qualificador de região em **minúscula** (`region-us`).

### Por que snapshot, não timeline (R2-11.5)

A primeira versão (R2-10) usou `TABLE_STORAGE_USAGE_TIMELINE_BY_PROJECT`
pra ter storage *histórico* por dia. Em dev a chamada do Hub caiu em
`400 Unrecognized name: total_logical_usage_bytes` — o schema de coluna
dessa família de views não bate com o que a doc sugere e varia entre
versões. Trocado por `TABLE_STORAGE` (snapshot atual, coluna
`total_logical_bytes` **estável e documentada**) desenhando uma linha
plana: numa janela de ≤ 31 dias o volume de storage praticamente não
muda, então o histórico agregava pouco valor pro gráfico de "custo do
mês". Se um dia quisermos a curva real de crescimento de storage, é uma
iteração à parte com a timeline confirmada por schema.

### Dry-run (regra do CLAUDE.md)

A query toca **só** `INFORMATION_SCHEMA.TABLE_STORAGE`, uma view de
metadado — o BigQuery **não cobra** query sobre `INFORMATION_SCHEMA`
(mesma base $0 de `repository.list_all_table_refs` /
`get_date_like_columns`). O teste manual `SELECT * … TABLE_STORAGE_USAGE_TIMELINE…`
do usuário já provou que essa família de views responde no projeto (a SA
tem a permissão de metadado); o erro era só o nome da coluna. Se por
algum motivo a view cobrar, a degradação acima
ainda protege o endpoint; ajustar aqui se o dry-run em dev mostrar bytes.

---

## Histórico mensal (`cost-history` — v1.11, planejada)

`cost-series`/`budget` só enxergam a janela do cache de audit log (piso
de 31 dias, ver `finops-waste-scanner.md` v1.4) — não dá pra comparar
"este mês vs. mês passado" com eles. Este endpoint lê uma fonte
**diferente e persistida**, sem esse teto.

### Onde o dado vive

Firestore, banco nomeado por ambiente (`hub-dev`/`hub-prod`, já
provisionado — nenhum recurso GCP novo, nenhuma role de IAM nova).
Subcoleção por projeto, mesmo padrão de `hub_projects/{project_id}` e de
`users/{email}/budgets/{doc_id}`:

```
hub_projects/{project_id}/finops_daily_costs/{YYYY-MM-DD}
  { date, query_cost_usd, storage_cost_usd, total_cost_usd,
    billed_bytes, storage_bytes, computed_at }
```

**Quem grava:** `jobs/refresh_event_cache.py` — o mesmo Job diário
(D-1, `0 3 * * *` UTC) que já itera todo `hub_project` pra
lineage/access/finops/storage — ganha um passo a mais: depois do scan do
dia, calcula o custo de query **só daquele dia** (não os 31d) + a foto de
storage do dia e faz upsert do doc acima. Sem Cloud Run Job novo, sem
Cloud Scheduler novo.

**Escopo: todo `hub_project`**, não só o projeto aberto na UI no
momento — mesmo racional do resto do Job, que já roda pra todos
independente do que está selecionado na tela.

**Retenção: 24 meses**, rolante — o próprio Job, ao gravar o dia D-1,
apaga docs de `finops_daily_costs` com `date` anterior a
`hoje − 24 meses` (paridade com o teto de `months` do endpoint abaixo:
não guarda dado que o endpoint nunca consegue expor). Sem TTL nativo do
Firestore nesta fase — a eviction é lógica do Job, mesmo padrão do cache
de 31 dias, só que num período maior e sempre um doc por dia (sem
merge/dedup — não há re-scan retroativo de um dia já gravado).

### GET /api/v1/finops/{project_id}/cost-history

Agrega **só** o Firestore — nunca toca Cloud Logging nem o cache de 31
dias.

**Parâmetros opcionais:**
- `months` (query, default `12`, `1`–`24`) — quantos meses pra trás,
  contando o mês corrente. Clampado (não 422), mesma filosofia do resto
  do domínio. Teto de 24 = retenção do Firestore acima.

**Response 200 (`CostHistoryResponse`):**
```json
{
  "project_id": "observability-hub-dev",
  "months": [
    { "month": "2026-08", "query_cost_usd": 0.28, "storage_cost_usd": 0.03,
      "total_cost_usd": 0.31, "days_recorded": 31 }
  ],
  "history_available_since": "2026-09-05",
  "warning": null
}
```
`months` é **contíguo** (um ponto por mês pedido, mesmo sem nenhum doc —
mesmo princípio de `points` em `cost-series`, sem buraco no gráfico de
comparação). `days_recorded` deixa explícito quando um mês está
incompleto (início do histórico, ou dia(s) em que o Job falhou/pulou —
sem preencher retroativamente por estimativa). `history_available_since`
= data do primeiro doc já gravado em **qualquer** `hub_project` — a UI
usa isso pra rotular "histórico começa em X" em vez de desenhar meses
anteriores como gasto zero (zero ≠ ausência de dado).

### Sem backfill

Não há como reconstruir meses anteriores à data de deploy desta feature
— os 31 dias do cache de audit log não cobrem retroativamente o
suficiente. O histórico só começa a acumular a partir do primeiro run do
Job depois do deploy. Ver ASM-004.

### Frontend (planejado)

Nova seção "Comparar com meses anteriores" na `FinOpsOverviewPage` —
gráfico de barras por mês + variação % vs. mês anterior, hook
`useCostHistory` novo em `features/finops/hooks.ts`.

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
| `scan_efficiency` | 0.25 | `1 / (1 + (bytes_escaneados_30d / size_bytes) / 10)` — escanear a tabela inteira 10× em 30d → `0.5`; premia pruning / cache / filtros. `1.0` se sem scan oneroso **ou se a tabela tem menos de 1 GB** (`_SCORE_SCAN_MIN_SIZE_BYTES` = mesma linha do candidato a partição — re-scan de tabela pequena custa centavos, não é sinal de desperdício). |

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
    logging_client, storage_client, firestore_client, project_id,
    group_by: BudgetGroupBy = BudgetGroupBy.TABLE,
    limit: int = 10,
    lookback_days: int = 30,   # rodada 3 — clampado a 1..31
    user_email: str | None = None,
) -> BudgetResponse:
    """
    1. period_start = now - lookback_days (clamp 1..31). Não há mais
       `month_start`.
    2. Busca eventos com repository.get_scan_events_cached() — lê o cache
       incremental de 31 dias (mesmo blob que partition-candidates usa,
       ver finops-waste-scanner.md v1.4). Cache miss levanta
       EventCacheNotReadyError → BudgetResponse vazio com warning.
       referenced_tables já vem sem entradas INFORMATION_SCHEMA (filtro
       na origem, repository._parse_table_ref).
    3. Descarta evento sem timestamp, anterior a `period_start`, com
       total_billed_bytes <= 0, ou cujo real_tables fique vazio (ver
       "Bug real corrigido: regiões fantasma").
    4. Por evento: soma total_billed_bytes/job_count em uma ou mais
       chaves via _group_keys(group_by, event, real_tables); guarda a
       linha bruta de CostlyQuery.
    5. groups ordenado por custo desc; top_queries desc, cortado em `limit`.
    6. Projeção (month-to-date real, independente de lookback_days/
       from/to): custo_do_mes_corrente = soma dos mesmos eventos
       filtrados por [dia 1 do mês, hoje] em vez de [start_date,
       end_date]; days_elapsed_in_month = hoje.day; daily_average =
       custo_do_mes_corrente / days_elapsed_in_month; days_in_month via
       calendar.monthrange(); projected_month_total = daily_average ×
       days_in_month. `days_elapsed` da resposta = days_elapsed_in_month
       (calendário) — a "janela analisada" das outras 3 visões é
       `BudgetResponse.lookback_days`.
    """
```

---

## Estrutura de arquivos

```
apps/backend/src/observability_hub/
├── api/v1/
│   └── finops.py          # + GET /finops/{project_id}/budget?group_by=...&include_storage=... (v1.12)
│                          # + GET/PUT/DELETE /finops/{project_id}/budgets (CRUD, v1.5)
│                          # + GET /finops/{project_id}/cost-series (v1.6)
│                          # + GET /finops/{project_id}/table-scores (v1.7)
│                          # + GET /finops/{project_id}/cost-history (v1.11, planejada — não implementada)
├── domains/finops/
│   ├── service.py          # + get_budget() (user_email → budget_target_usd; projeção month-to-date real, v1.10; include_storage + _merge_storage_into_groups(), v1.12); + get_cost_series() (v1.6, + total_cost_usd, v1.11/v1.12); + _table_efficiency_score() + compute_table_scores() (v1.7); + get_cost_history() (v1.11, planejada — não implementada)
│   ├── repository.py       # ScanEvent + get_scan_events_cached() (cache, ver finops-waste-scanner.md v1.4); _parse_table_ref filtra INFORMATION_SCHEMA; + StorageTimelineDay + get_storage_cost_timeline() (v1.6); + get_storage_bytes_by_table() (v1.12 — storage por tabela/dataset, GROUP BY em vez de SUM); + write_daily_cost_snapshot()/list_daily_cost_snapshots()/evict_daily_cost_snapshots_older_than() (v1.11, planejada — hub_projects/{p}/finops_daily_costs)
│   └── schemas.py          # + BudgetResponse (+ budget_target_usd); + CostGroup.storage_cost_usd/total_cost_usd (v1.12); + CostSeries* (v1.6, + total_cost_usd, v1.11/v1.12); + TableScoreFactor, TableScore, TableScoresResponse (v1.7); + CostHistoryResponse, CostHistoryMonth (v1.11, planejada)
├── domains/budget/          # v1.5 — CRUD de meta de custo por usuário (Firestore, espelha domains/favorites)
│   ├── schemas.py           # BudgetScope, BudgetEntry, BudgetUpsertRequest, BudgetListResponse
│   ├── repository.py        # _budget_doc_id, list/upsert/remove_budget, get_project_budget_amount
│   └── service.py           # wrappers finos sobre repository
├── jobs/
│   └── refresh_event_cache.py   # v1.11, planejada — depois do scan do dia, grava o snapshot diário de custo (query do dia + foto de storage) por hub_project e evicta o que passou de 24 meses
└── tests/unit/
    ├── finops/test_service.py      # + get_budget/budget_target_usd + get_cost_series (v1.6) + _table_efficiency_score / compute_table_scores (v1.7) + total_cost_usd (v1.12) + get_budget(include_storage=True) (v1.12) + get_cost_history (v1.11, planejada)
    ├── finops/test_repository.py   # + INFORMATION_SCHEMA filter + get_storage_cost_timeline (v1.6) + get_storage_bytes_by_table (v1.12) + snapshot diário / eviction 24 meses (v1.11, planejada)
    └── budget/{test_repository,test_service}.py  # v1.5 — doc_id por escopo, preservação de created_at, get_project_budget_amount
```

Frontend (`apps/frontend/src/features/finops/BudgetPage.tsx`, renomeada
"Detalhamento de custo" na UI — arquivo/rota mantidos, v1.12): o gate
pré-run tem `LookbackPicker` compartilhado (presets 7/15/30 + "Outro",
`components/LookbackPicker.tsx`, também usado por Tabelas órfãs) + seletor
de `group_by` + limite. Depois de "Executar", duas abas via `Tabs` do
shadcn/ui — "Custo por agrupamento" (seletor de `group_by` em pill
buttons; quando `group_by` é tabela/dataset e a resposta trouxe split de
storage: toggle "Tipo de custo" local, gráfico de ranking em barras
empilhadas query+storage [top 10], colunas extras de custo query/storage/
total + meta cadastrada [`useBudgets`, join client-side por escopo] +
badge "Dentro"/"Acima da meta", linha expansível com drill-down de série
diária via `cost-series` filtrado; tabela ordenável, total no rodapé via
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
| Evento anterior a `period_start` (`now - lookback_days`) | Ignorado |
| `lookback_days` fora de 1–31 (budget) | Clampado no service (não é 422) — 31 é o limite do cache |
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
| **budget:** `include_storage=true` com `group_by` fora de table/dataset | Ignorado silenciosamente — `storage_cost_usd`/`total_cost_usd` continuam `null` em todo `CostGroup`, sem warning |
| **budget:** `include_storage=true` e nenhuma região responde a query de storage | `groups` volta idêntico ao comportamento pré-v1.12 (só custo de query), `warning` explica o motivo — nunca falha o endpoint inteiro |
| **budget:** tabela com storage > 0 mas nenhuma query no período (`include_storage=true`) | Aparece em `groups` com `cost_usd=0`/`billed_bytes=0`/`job_count=0` e `storage_cost_usd` > 0 — decisão do usuário (união, não interseção) |
| **cost-history:** mês pedido sem nenhum doc gravado no Firestore | Aparece na resposta com os três custos `0.0` e `days_recorded=0` — série contígua, sem buraco (mesmo princípio de `cost-series`) |
| **cost-history:** `months` fora de 1–24 | Clampado no service (não é 422) — 24 é o teto de retenção do Firestore, não uma escolha do chamador |
| **cost-history:** Job de um dia específico falhou (não gravou o snapshot daquele dia) | O mês correspondente sai com `days_recorded` menor que o total de dias do mês — nunca preenchido retroativamente por estimativa |

---

## Suposições

| ID | Suposição | Status |
|---|---|---|
| ASM-001 | `budget` usa o mesmo cache de `partition-candidates` (não um scan com janela month-to-date variável): o recorte pro mês corrente já era feito por `event.timestamp < month_start` no service, não pela janela do scan. Desde a v1.4 a janela do cache é **31 dias** (evicção do Job incremental), então o mês corrente inteiro cabe — o efeito colateral da v1.3 (o `_BUDGET_RETENTION_CAVEAT` disparar sempre no dia 31) foi revertido. | confirmada |
| ASM-002 | **cost-series / storage:** as views `INFORMATION_SCHEMA.TABLE_STORAGE*` são metadado que o BigQuery **não cobra** ($0). **Resolvida (2026-09, R2-11.5):** o `storage_available=false` em dev era `400 Unrecognized name: total_logical_usage_bytes` — schema de coluna da família `TABLE_STORAGE_USAGE_TIMELINE_*` não bate com a doc. Trocado pra `TABLE_STORAGE` (snapshot, coluna estável `total_logical_bytes`, linha plana). Permissão **não** era o problema (o teste manual do usuário responde). Sem role nova em `docs/onboarding-cliente.md`. | confirmada |
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
- ~~**Histórico entre meses** — só o mês corrente; sem persistência,
  cada consulta reflete só a janela de audit logs disponível agora.~~
  Coberto a partir da v1.11 (planejada) — `GET .../cost-history`,
  Firestore, sem depender do cache de 31 dias. Ver "Histórico mensal
  (`cost-history` — v1.11, planejada)". Continua fora de escopo: dado
  anterior à data de deploy desta feature (sem backfill, ver ASM-004).
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
| AC-FIN-RV-02 | Filtros do grafico: dataset, tabela, granularidade (mes/dia), tipo de custo (query / storage / ambos), **periodo (data final / intervalo customizado, atalhos "Mês atual"/"Tudo" — rodada 3)**. **Backend (R2-10 + rodada 3):** `GET /finops/{p}/cost-series?granularity=&cost_type=&lookback_days=&from=&to=&datasets=&tables=` → série contígua de `query_cost_usd`/`storage_cost_usd`/`total_cost_usd` por período; `from`/`to` sobrescrevem `lookback_days` via `_resolve_date_window` (mesmo helper de `get_budget`), clampados no piso do cache e nunca no futuro. O teto de budget (`refLine`) só desenha quando a janela efetiva tem ≥ 20 dias (senão comparar contra uma meta mensal inteira engana). | `test_get_cost_series_month_granularity_uses_year_month_keys`, `test_get_cost_series_dataset_filter_excludes_nonmatching_query_events`, `test_get_cost_series_cost_type_query_skips_storage`, `test_get_cost_series_adds_storage_cost_when_timeline_present`, `test_resolve_date_window_explicit_range_is_used_as_is`, `test_resolve_date_window_clamps_future_end_date_and_warns`, `test_resolve_date_window_clamps_start_date_older_than_cache_floor_and_warns`, `test_resolve_date_window_swaps_inverted_range_defensively`, `test_get_cost_series_with_explicit_from_to_returns_that_range`, `test_get_budget_with_explicit_from_to_narrows_the_window` |
| AC-FIN-RV-03 | **Dois scores distintos**: (a) "Eficiencia de custo" geral do projeto (anel composto - ja prototipado); (b) "Score por tabela" individual - coluna "Score" ordenavel (anel compacto + numero) no scanner de desperdicio / Top ofensores **e** anel grande + decomposicao no drill-down da linha (Q-002). **Backend (R2-11):** `GET /finops/{p}/table-scores` → `project_efficiency_score` + `tables[].score` + `tables[].factors[]` (decomposicao). Formula provisoria (Q-002). | `test_table_efficiency_score_penalizes_large_never_scanned_table`, `test_table_efficiency_score_penalizes_unpartitioned_with_big_savings`, `test_compute_table_scores_sorts_worst_first_and_aggregates_project`, `test_compute_table_scores_uses_partition_candidate_savings` |
| AC-FIN-RV-04 | Cadastro de budget com granularidade por **dataset e por tabela** (`scope=project\|dataset\|table` no CRUD). So cadastro simples - sem convite/aceite/compartilhamento. GET/PUT/DELETE `/finops/{p}/budgets`, por usuario (Firestore). O valor de `scope=project` volta como `budget_target_usd` no `GET /finops/{p}/budget`. | `test_upsert_budget_dataset_scope_uses_two_segment_doc_id`, `test_upsert_request_rejects_dataset_scope_without_dataset_id`, `test_get_budget_injects_user_budget_target_from_firestore` |
| AC-FIN-RV-05 | "Top ofensores" com mini-grafico de tendencia de 7 dias por linha. | `test_finops_top_offenders_trend` |

Status (2026-09): **backend de AC-FIN-RV-02/03/04 implementado** —
R2-9 (`budgets` CRUD + `budget_target_usd`), R2-10
(`cost-series`), R2-11 (`table-scores`). R2-12 montou
`FinOpsOverviewPage` consumindo os três endpoints (big numbers +
`ComboChart` com filtros + anel de eficiência + coluna "Score" +
drill-down + Top ofensores) — fecha AC-FIN-RV-01/02/03/05 no front. A
rodada 3 fechou o filtro de período de AC-FIN-RV-02 (antes só
granularidade/tipo de custo existiam; período ainda era fixo em
`lookback_days`): `from`/`to` em `get_budget`/`get_cost_series`, dois
`DateField` + atalhos "Mês atual"/"Tudo" no front. A fórmula do score
(Q-002) segue em aberto pro review do PR final.

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

---

## Histórico mensal e consistência card/gráfico — pendente (2026-09)

Motivada por uma inconsistência real observada em produção (dev): o card
"Gasto no mês" mostrava US$ 0,009298 enquanto o "Acumulado" do gráfico,
com o filtro de tipo de custo em "Tudo", mostrava US$ 0,01 — a diferença
real era o custo de storage (que o card nunca somava, só query), somada
ao efeito de `formatUsd` trocar de 6 pra 2 casas decimais bem em torno de
US$ 0,01. Ver "Histórico mensal (`cost-history` — v1.11, planejada)" e o
novo campo `total_cost_usd` em `cost-series` pro contrato completo — esta
seção só rastreia critérios de aceite, suposições e status. Independente
da projeção month-to-date da v1.10 (fix `fix/finops-projection-days-elapsed`)
— nenhum dos dois mexe no cálculo do outro.

Decisões confirmadas com o usuário (2026-09-04): retenção do histórico
diário = **24 meses**; escopo da gravação = **todo `hub_project`** (não
só o projeto aberto na UI); janela do endpoint de comparação = **24
meses**, mesmo teto da retenção (ver ASM-005/ASM-006 abaixo).

| ID | Comportamento | Teste |
|---|---|---|
| AC-FIN-HIST-01 | `cost-series` retorna `total_cost_usd` = soma de `points[].total_cost_usd`, já respeitando os filtros aplicados aos pontos (`cost_type`/`datasets`/`tables`/janela) | `test_get_cost_series_total_cost_usd_matches_sum_of_points` |
| AC-FIN-HIST-02 | Card "Gasto no período" (`FinOpsOverviewPage`) lê `seriesQuery.data.total_cost_usd` em vez de `budgetQuery.data.total_cost_usd` — muda ao trocar `cost_type` (Tudo/Query/Storage) ou o intervalo de data, sem chamada HTTP extra; `budgetQuery` continua alimentando "Meta mensal" e "Projeção do mês" | teste de FE (React Testing Library) |
| AC-FIN-HIST-03 | O Job diário grava `hub_projects/{p}/finops_daily_costs/{data}` pra **todo** `hub_project`, não só o selecionado na UI | `test_refresh_project_writes_daily_cost_snapshot` |
| AC-FIN-HIST-04 | O Job apaga, na mesma execução, docs de `finops_daily_costs` com `date < hoje − 24 meses` | `test_refresh_project_evicts_daily_cost_snapshots_older_than_24_months` |
| AC-FIN-HIST-05 | `GET /cost-history` agrega só a partir do Firestore, nunca toca Cloud Logging/cache de 31 dias | `test_get_cost_history_reads_only_firestore` |
| AC-FIN-HIST-06 | `months` fora de 1–24 é clampado, não 422 | `test_get_cost_history_clamps_months` |
| AC-FIN-HIST-07 | Mês sem nenhum doc no período pedido aparece com os três custos `0.0` e `days_recorded=0` (série contígua, sem buraco) | `test_get_cost_history_fills_gaps_with_zero` |
| AC-FIN-HIST-08 | `history_available_since` reflete a data do primeiro doc gravado em qualquer `hub_project` — meses anteriores a essa data aparecem com `days_recorded=0`, nunca como "gasto zero real" | `test_get_cost_history_reports_history_available_since` |

### Suposições

| ID | Suposição | Status |
|---|---|---|
| ASM-004 | Sem backfill: histórico só existe a partir da data de deploy desta feature — os 31 dias do cache de audit log não cobrem meses anteriores o suficiente pra reconstruir nada além do mês corrente. `history_available_since` comunica isso na resposta em vez de esconder. | confirmada |
| ASM-005 | Retenção de 24 meses no Firestore (`finops_daily_costs`) e teto de `months` em `cost-history` são o mesmo número de propósito — evita guardar dado que o endpoint nunca consegue expor. Se um dia divergirem, revisar os dois juntos. Decidido com o usuário em 2026-09-04. | confirmada |
| ASM-006 | O snapshot diário é gravado pra **todo** `hub_project`, não só o que está aberto na UI no momento — mesmo racional do resto do Job (já roda pra todos por causa de lineage/access/storage). Custo: mais writes de Firestore por dia (um por `hub_project`), considerado desprezível frente ao resto do Job. Decidido com o usuário em 2026-09-04. | confirmada |

**Status (2026-09-04): spec aprovada, implementação pendente.** Nenhum
código escrito ainda — esta seção documenta o plano debatido com o
usuário (card `total_cost_usd`, snapshot diário no Firestore, endpoint
`cost-history`) antes de tocar em `service.py`/`repository.py`/
`refresh_event_cache.py`, seguindo a regra deste repositório de não
implementar sem spec aprovada.
