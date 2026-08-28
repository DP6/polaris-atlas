# Spec — Domínio: FinOps — Scanner de desperdício

**Versão:** 1.3 (leitura de audit log via cache pré-computado, mesmo
padrão de lineage/access/storage — ver "Fonte de dados" e seção "Critérios
de aceite")
**Status:** Aprovada
**Fase:** 4 — FinOps (primeira frente: scanner de desperdício)
**Última atualização:** 2026-08-28

---

## Objetivo

**Candidatas a particionamento** — tabelas grandes, sem partição, com
uma coluna `DATE`/`DATETIME`/`TIMESTAMP` candidata, com uma estimativa
(deliberadamente conservadora, nunca um número único de falsa precisão)
de quanto poderia ser economizado particionando.

**v1.2 (2026-08-25)**: esta spec cobria duas checagens até a v1.1 —
"Tabelas sem uso" foi removida daqui e absorvida por "Tabelas sem
consumidor" (`docs/specs/lineage.md`, domínio `lineage`/Governança), que
já cobria essencialmente a mesma pergunta ("quais tabelas ninguém está
lendo") por uma fonte de dados equivalente — as duas features
coexistindo em lugares diferentes do app era redundância de produto, não
uma diferença real de funcionalidade. A única capacidade exclusiva de
"Tabelas sem uso" (estimativa de custo de storage) foi levada pra
`OrphanTable` em vez de perdida — ver "Estimativa de economia — desenho"
em `lineage.md`.

Este é o primeiro dos três sub-domínios de FinOps do roadmap (`docs/prd.md`,
Fase 4) — budget/custo por dataset e otimizações sugeridas ficam pra
depois, não fazem parte desta spec.

---

## Fonte de dados

Combina duas fontes já usadas por outros domínios:

- **Cloud Logging** (audit logs de jobs BigQuery, `jobservice.jobcompleted`,
  custo $0) — mesmo formato legado `AuditData`/`jobCompletedEvent` de
  `domains/lineage`/`domains/access`. Aqui só interessa leitura
  (`referencedTables`) e um campo novo que nenhum outro domínio lê ainda:
  `jobStatistics.totalBilledBytes` — bytes realmente cobrados por aquele
  job, usado pra ancorar a estimativa de economia de particionamento em
  custo **observado**, não numa suposição do zero.
- **BigQuery `INFORMATION_SCHEMA`** (enumeração de tabelas, custo $0) +
  **`client.get_table()`** (`core/bigquery.py::get_tables_metadata`,
  REST, cacheado 5min, já usado por catalog/freshness — reaproveitado
  direto por ser `core/`, não um domínio) pra tamanho, contagem de
  linhas, `last_modified_time` e se a tabela já é particionada
  (`time_partitioning`/`range_partitioning`).

`domains/finops/repository.py` duplica o parsing de audit log (não
importa de `lineage`/`access` — nenhum domínio deste projeto importa de
outro).

**Revisado em 2026-08-28 — cache pré-computado, mesmo padrão de
`domains/lineage`/`domains/access`/`domains/storage`**: até esta revisão,
`GET .../partition-candidates` (e `.../budget`, ver `finops-budget.md`)
chamava `list_scan_events` **direto no request path** — scan síncrono de
30 dias de audit log a cada chamada. Volume alto o suficiente pra estourar
a cota `logging.googleapis.com/read_requests` do projeto (60/min, default;
dev+prod compartilham o balde na topologia single-project), o que
propagava como `429 TooManyRequests` não tratado → 500 → "Failed to fetch"
no browser. Bug real: 12 ocorrências em 7 dias num uso normal de tela.

**Mecanismo** (idêntico ao documentado em `docs/specs/lineage.md` seção
"Cache pré-computado" e `storage.md` seção 6.2): `jobs/refresh_event_cache.py`
(o mesmo Cloud Run Job diário, D-1, **sem recurso Terraform novo**) agora
também chama `list_scan_events` pra cada projeto conhecido e grava o
resultado (`ScanEvent`, com `timestamp` por evento) no cache compartilhado
`core/event_cache.py` (payload no bucket GCS `event_cache_bucket_name`,
metadado no Firestore; namespace `_CACHE_KIND = "finops_scan_events"`). O
endpoint passa a ler `get_scan_events_cached()` — cache hit não toca Cloud
Logging; cache miss cai pro scan ao vivo e grava pra próxima chamada
(auto-cura), mesmo racional de `get_access_events_cached`.

**Cache de 30 dias serve os dois consumidores**: `ScanEvent` carrega
`timestamp`, então o mesmo blob atende tanto `partition-candidates`
(janela fixa de 30d) quanto `budget` (recorte month-to-date por filtro no
service, ver `finops-budget.md`).

**429 residual** (cache miss durante pico, ou o Job): `list_scan_events`
usa `core/logging_client.py::list_entries_with_retry`, que faz retry
exponencial (backoff, deadline 30s) no 429/503 — a maioria dos picos nem
chega ao 503. O 429 que persistir vira `LoggingQuotaExceededError` → HTTP
**503 + `Retry-After`** (não um 500, não um resultado vazio). No Job,
`_refresh_project` captura `LoggingQuotaExceededError` (status
`quota_exceeded` no log) — um 429 num projeto não interrompe os demais.

**Fica no `try` principal do Job** (não isolado como storage): finops lê a
mesma fonte que lineage (`jobservice.jobcompleted`, mesmo filtro) — se
`list_job_events` passou, este passa. lineage e finops fazem dois scans
separados da mesma fonte porque os dataclasses diferem (`JobEvent` sem
`totalBilledBytes`/`timestamp`; `ScanEvent` sem `destinationTable`) e
domínios não compartilham parsing — tradeoff aceito (1×/dia, fora do
request path); unificar num scan cru com dois parsers fica pra depois se o
Job virar gargalo.

---

## Endpoints da API

### GET /api/v1/finops/{project_id}/partition-candidates
Tabelas grandes, não particionadas, com coluna candidata a chave de
partição.

**Parâmetros opcionais:**
- `datasets` (query, repetido, v1.1) — filtra a enumeração de tabelas
  pra um subconjunto de `dataset_id`.
- `tables` (query, repetido, v1.2) — formato `"dataset_id.table_id"`
  (mesmo formato de `ColumnTypeScanRequest.tables`, `docs/specs/
  finops-column-types.md`). Quando presente, filtra o resultado de
  `list_all_table_refs(datasets=...)` em Python contra o conjunto
  pedido antes do resto do pipeline — não pula a enumeração via
  `INFORMATION_SCHEMA` (diferente do caminho "sem enumeração" de
  column-type-suggestions), escopo mais simples por ora. Frontend
  (`PartitionCandidatesTab`) trocou o seletor de `datasets` (checkbox
  por dataset inteiro) por `ColumnTypeScopePicker` — mesmo componente
  de `docs/specs/finops-column-types.md` — dataset expansível → tabela
  individual, sempre manda `tables`, nunca `datasets`, num
  `Collapsible` que recolhe sozinho ao clicar "Executar".

**Response 200:**
```json
{
  "project_id": "observability-hub-dev",
  "lookback_days": 30,
  "candidates": [
    {
      "dataset_id": "RAW",
      "table_id": "ga4_events_flat",
      "size_bytes": 10737418240,
      "size_human": "10.74 GB",
      "row_count": 42000000,
      "candidate_partition_columns": ["event_date"],
      "observed_billed_bytes_30d": 1099511627776,
      "observed_cost_usd_30d": 6.25,
      "estimated_savings_usd_conservative": 1.875,
      "estimated_savings_usd_optimistic": 4.375,
      "savings_disclaimer": "Estimativa especulativa baseada no custo de scan REAL observado nos últimos 30 dias — não confirma que as queries filtram pela coluna de data candidata..."
    }
  ],
  "warning": null
}
```

`estimated_savings_usd_*` e `savings_disclaimer` só vêm preenchidos
quando `observed_billed_bytes_30d > 0` — sem custo real observado, a
tabela ainda aparece como candidata (tamanho/colunas), mas sem nenhuma
estimativa em R$/US$ (ver "Estimativa de economia — desenho").

---

## Estimativa de economia — desenho

Decisão de design discutida explicitamente com o usuário: **nunca
fabricar um número de aparência precisa sobre uma suposição não
verificada** — o risco de superestimar e gerar frustração depois pesa
mais que a conveniência de mostrar "um número só".

### Candidatas a particionamento
Aqui não dá pra saber se as queries reais filtram pela coluna de data
candidata sem rodar algo mais caro (analisar o texto de cada query) —
fora de escopo desta v1. Em vez de assumir uma redução do zero, o
desenho é:

1. Soma `totalBilledBytes` de todo job real que leu a tabela nos
   últimos 30 dias — **fato observado**, convertido em US$ pelo mesmo
   preço on-demand de `domains/quality` (`settings.bigquery_price_usd_per_tib`).
2. Só oferece uma estimativa de economia se **(a)** a tabela tem coluna
   candidata a partição **e** **(b)** houve custo real observado — sem
   os dois, mostra a tabela como candidata sem nenhum número de
   economia.
3. Quando oferece, mostra uma **faixa** (30%–70% de redução sobre o
   custo observado), não um valor único — o formato de faixa já
   comunica a incerteza, em vez de esconder atrás de uma falsa precisão.
4. Sempre acompanhada de `savings_disclaimer` explícito.

**Limitação assumida conscientemente**: se a query faz `JOIN` com outra
tabela grande, `totalBilledBytes` é o custo da query inteira, não
isolado só nesta tabela — não há tentativa de dividir a proporção por
tabela dentro de um job (dado que não está disponível no audit log).

---

## Estrutura de arquivos

```
apps/backend/src/observability_hub/
├── api/v1/
│   └── finops.py
├── core/
│   ├── bigquery.py         # get_tables_metadata() — reaproveitado, não duplicado (é core/)
│   └── config.py           # bigquery_storage_price_usd_per_gb_month_{active,long_term}
├── domains/finops/
│   ├── __init__.py
│   ├── service.py
│   ├── repository.py       # list_scan_events() + get_scan_events_cached()/serialize/deserialize/read/write (cache), list_all_table_refs(), get_date_like_columns()
│   └── schemas.py
├── jobs/
│   └── refresh_event_cache.py   # popula o cache de finops_scan_events pra cada projeto (D-1)
└── tests/unit/finops/
    ├── test_service.py
    └── test_repository.py
```

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| `tables` pedido junto com `datasets` | `datasets` filtra a enumeração primeiro, `tables` filtra o resultado depois — uma tabela só aparece se sobreviver aos dois filtros |
| `tables` com entrada malformada (sem `.`) | Descartada silenciosamente por `_parse_scoped_tables`, mesmo comportamento de `finops-column-types.md` |
| Tabela já particionada | Nunca aparece em `partition-candidates` |
| Tabela abaixo do limite de tamanho (1 GB) | Nunca aparece em `partition-candidates` — pequena demais pra valer o aviso |
| Tabela grande, não particionada, sem coluna DATE/DATETIME/TIMESTAMP | Não aparece — sem coluna candidata, sugestão não é viável |
| Candidata sem custo observado nos últimos 30 dias | Aparece sem `estimated_savings_usd_*`/`savings_disclaimer` (ambos `null`) |
| Nenhum evento de job no projeto | `warning` populado (mesmo texto/causas de lineage/access) |
| Cache hit | `cache_updated_at` na resposta = quando o Job (ou write-through de outra requisição) gerou o blob; Cloud Logging não é tocado |
| Cache miss | Scan ao vivo, grava o blob, `cache_updated_at = null` (dado veio ao vivo nesta chamada) |
| Falha ao ler/gravar o cache (GCS fora do ar, bucket sem IAM) | Logada e ignorada — cai pro scan ao vivo, nunca derruba a resposta |
| `429 TooManyRequests` no scan ao vivo (cota `read_requests` do projeto) | `LoggingQuotaExceededError` → HTTP 503 + `Retry-After: 60` (não 500, não resultado vazio) |

---

## Critérios de aceite — cache de audit log (v1.3)

Cobre `get_scan_events_cached` (usado por `partition-candidates` **e**
`budget`, ver `finops-budget.md`) e o refresh no Job diário.

| ID | Comportamento | Teste |
|---|---|---|
| AC-001 | Cache hit não chama `logging_client.list_entries` e devolve `cache_updated_at` do metadado | `test_get_scan_events_cached_returns_cache_hit_without_calling_list_entries` |
| AC-002 | Cache miss faz o scan ao vivo, grava o blob + `record_project_seen`, e retorna `cache_updated_at = None` | `test_get_scan_events_cached_falls_back_and_writes_cache_on_miss` |
| AC-003 | Falha ao ler o cache (qualquer exceção, não só miss) cai pro scan ao vivo em vez de propagar | `test_get_scan_events_cached_falls_back_to_live_scan_when_cache_read_fails` |
| AC-004 | `429 TooManyRequests` no scan ao vivo é re-tentado com backoff exponencial (`list_entries_with_retry`, deadline 30s); o que persistir vira `LoggingQuotaExceededError` (HTTP 503 + `Retry-After` em `main.py`) | `test_retries_on_too_many_requests_then_succeeds`, `test_persistent_too_many_requests_raises_quota_exceeded`, `test_get_scan_events_cached_raises_quota_exceeded_on_too_many_requests`, `test_handle_logging_quota_exceeded_returns_503_with_retry_after` |
| AC-005 | Falta de `roles/logging.viewer` no scan ao vivo propaga como `LoggingAccessDeniedError` | `test_get_scan_events_cached_propagates_access_denied` |
| AC-006 | `ScanEvent` sobrevive a serialize→deserialize (com e sem `timestamp`/`query_text`) | `test_serialize_deserialize_scan_events_round_trips`, `test_deserialize_scan_events_handles_no_timestamp_and_no_query_text` |
| AC-007 | O Job diário grava o cache de `finops_scan_events` pra cada projeto conhecido, no `try` principal (junto de lineage/access) | `test_refresh_project_writes_lineage_access_finops_and_storage_caches` |
| AC-008 | `429` no refresh de finops dentro do Job não interrompe o processamento dos demais projetos | `test_refresh_project_survives_finops_quota_error` |

## Suposições

| ID | Suposição | Status |
|---|---|---|
| ASM-001 | Um cache único de 30 dias de `ScanEvent` serve tanto `partition-candidates` (janela fixa 30d) quanto `budget` (recorte month-to-date por filtro no service), porque `ScanEvent` carrega `timestamp` por evento. Nos ~1 dia/ano em que a janela month-to-date passa de 30d (fim de mês de 31 dias), o começo do mês pode faltar — já coberto pelo `_BUDGET_RETENTION_CAVEAT` pré-existente, sem regressão. | confirmada |
| ASM-002 | finops e lineage lendo a mesma fonte (`jobservice.jobcompleted`) com dois scans separados no Job é aceitável (1×/dia, fora do request path). Unificar num scan cru + dois parsers só se o Job virar gargalo de cota. | confirmada |

## Perguntas em aberto

| ID | Pergunta | Status |
|---|---|---|
| Q-001 | Expor `cache_updated_at` também nas respostas de finops (como lineage/access já fazem)? | respondida — sim, campo opcional aditivo, 2026-08-28 |

## Fora do escopo desta spec

- Budget por dataset/projeto (custo mensal, top queries caras, top
  usuários por gasto, projeção do mês) — próxima frente de FinOps.
- Otimizações sugeridas além de particionamento (clustering, tipo de
  coluna) — próxima frente de FinOps.
- Análise do texto da query pra confirmar se ela de fato filtra pela
  coluna de data candidata — é isso que tornaria a estimativa de
  economia de particionamento precisa em vez de uma faixa; não
  implementado nesta v1.
- Exclusão automática de tabelas (a funcionalidade só relata, nunca
  apaga/modifica — mesma restrição de escopo somente-leitura de todo o
  Hub, `docs/prd.md`, "Fora do escopo").
- Deletar/arquivar tabelas sem uso — só relata, decisão fica com o
  usuário.
