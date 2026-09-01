# Spec — Domínio: Lineage e tabelas órfãs

**Versão:** 2.4 (cache de audit log **incremental** — delta diário por
`receiveTimestamp` + merge/evicção de janela rolante; request path não
escaneia mais ao vivo, degrada pra vazio com aviso quando o cache ainda
não foi gerado)
**Status:** Aprovada
**Fase:** 3 — Sprint 3.2 (lineage e órfãos)
**Última atualização:** 2026-08-28

---

## Histórico

A v1 (upstream/downstream restrito a 1 hop direto) foi implementada nos
commits `f18dfab`/`c33f950`/`0d28700`/`778e3fa` sem uma spec formal — este
documento nasce já como v2, cobrindo a extensão para cadeia transitiva
completa, e formaliza retroativamente o que já valia para a v1 (fonte de
dados, formato de audit log, aviso de resultado vazio).

---

## Objetivo

Reconstruir a cadeia completa de dependências de uma tabela BigQuery —
não só quem lê/escreve diretamente nela, mas toda a sequência de tabelas
intermediárias até onde a trilha de audit logs permitir (ex:
`GOLD.daily_summary` ← `TRUSTED.ga4_sessions` ← `RAW.ga4_events`),
representada como um grafo dirigido (nós = tabelas, arestas = jobs que
leram uma tabela e escreveram outra). Toda tabela é sempre identificada
com o prefixo do projeto (`project.dataset.table`), inclusive quando a
cadeia atravessa mais de um projeto GCP. Uma tabela gerada por `JOIN` de
duas fontes aparece no grafo com duas arestas de entrada (fan-in) — é a
forma natural de um grafo dirigido, não um caso especial.

Também mantém a detecção de tabelas órfãs (sem consumidor conhecido) do
projeto — esse endpoint continua 1-nível, não muda nesta versão (ver
"Fora do escopo").

---

## Fonte de dados

Cloud Logging — audit logs de jobs do BigQuery (`jobservice.jobcompleted`),
**custo $0** (é uma API de logs, não uma query BigQuery faturável):

- Formato legado `AuditData`/`jobCompletedEvent`
  (`google.cloud.bigquery.logging.v1.AuditData`), confirmado contra logs
  reais de `observability-hub-dev` — não o formato novo
  `BigQueryAuditMetadata`/`jobChange`. `referencedTables`/
  `destinationTable` vêm como dicts `{projectId, datasetId, tableId}`.
- Janela fixa: `LOOKBACK_DAYS = 30` (`domains/lineage/repository.py`), não
  configurável via parâmetro de API.
- Depende de **Data Access audit logs** habilitados no projeto (categoria
  opcional, diferente de Admin Activity logs, sempre ativos) e da SA de
  runtime ter `roles/logging.privateLogViewer` (não basta
  `roles/logging.viewer` — a chamada não falha, só retorna vazio). Quando
  o resultado vem vazio, a API devolve um aviso estático
  (`service._EMPTY_RESULT_WARNING`) explicando as três causas possíveis.

**Diferença da v1**: a travessia agora pode precisar consultar o Cloud
Logging de **mais de um projeto** — um por projeto distinto encontrado
durante a expansão do grafo, não só o projeto da tabela raiz. Isso não é
uma mudança de modelo de acesso: o ADR-006 já prevê a SA do Hub com
acesso simultâneo a múltiplos projetos-alvo (é só rodar o comando de
concessão uma vez por projeto, ver `docs/onboarding-cliente.md`) — é um
novo *padrão de uso* de um acesso que já podia existir. Cada projeto
distinto tocado pela travessia é consultado **no máximo uma vez por
requisição** (cache em memória por request, ver "Algoritmo de
travessia").

`GET /api/v1/lineage/{project_id}/orphans` continua também usando
`INFORMATION_SCHEMA.TABLES` (metadado gratuito, via
`domains/catalog`-style `discover_regions` + `list_all_table_refs`) para
levantar o universo de tabelas do projeto, comparado contra o conjunto de
tabelas referenciadas por algum job — inalterado da v1.

---

## Endpoints da API

### GET /api/v1/lineage/{project_id}/{dataset_id}/{table_id}
Retorna o grafo de lineage transitivo em torno da tabela informada.

**Parâmetros opcionais:**
- `max_hops` (query, default `8`, mínimo `1`, máximo `15`) — limite de
  saltos por direção (upstream e downstream são limitados
  independentemente; o alcance total da cadeia pode ser até
  `2 × max_hops`).

**Response 200:**
```json
{
  "root": { "project_id": "observability-hub-dev", "dataset_id": "GOLD", "table_id": "daily_summary" },
  "nodes": [
    {
      "id": "observability-hub-dev:TRUSTED:ga4_sessions",
      "project_id": "observability-hub-dev",
      "dataset_id": "TRUSTED",
      "table_id": "ga4_sessions",
      "hop_distance": -1,
      "is_root": false,
      "access_denied": false
    },
    {
      "id": "observability-hub-dev:RAW:ga4_events",
      "project_id": "observability-hub-dev",
      "dataset_id": "RAW",
      "table_id": "ga4_events",
      "hop_distance": -2,
      "is_root": false,
      "access_denied": false
    }
  ],
  "edges": [
    { "source": "observability-hub-dev:RAW:ga4_events", "target": "observability-hub-dev:TRUSTED:ga4_sessions", "job_id": "job-abc" },
    { "source": "observability-hub-dev:TRUSTED:ga4_sessions", "target": "observability-hub-dev:GOLD:daily_summary", "job_id": "job-def" }
  ],
  "lookback_days": 30,
  "max_hops": 8,
  "truncated": false,
  "warning": null
}
```

A tabela raiz **não** entra em `nodes` (só em `root`) — o frontend
sintetiza o nó raiz a partir desse campo. `hop_distance` é negativo para
upstream, positivo para downstream, sempre relativo à raiz (distância
mais curta encontrada, já que a travessia é BFS). `truncated=true`
quando `max_hops` foi atingido em alguma direção com fronteira ainda não
expandida — há possivelmente mais tabelas além do que foi retornado.

**Response 403** (sem acesso de Logging no projeto **raiz**): mesmo
comportamento da v1 — `LoggingAccessDeniedError` propaga, HTTP 403 com
comando de correção (`handle_logging_access_denied` em `main.py`). Sem
dados do projeto raiz não há nada pra montar. Projetos **não-raiz**
atingidos durante a expansão que não tenham acesso concedido **não**
derrubam a requisição — ver "Casos de borda".

---

### GET /api/v1/lineage/{project_id}/orphans (v2.1)
Ver `OrphansResponse`/`OrphanTable` em `domains/lineage/schemas.py`.
Continua 1-nível: uma tabela é órfã se nenhum job no projeto a
referenciou como fonte na janela de lookback, independente de cadeias
transitivas.

Dois query params novos (v2.1), ambos opcionais — sem eles o
comportamento é idêntico ao de antes (projeto inteiro, 30 dias):
- `datasets` (repetido, ex: `?datasets=RAW&datasets=TRUSTED`) — filtra
  `list_all_table_refs` pra um subconjunto de `dataset_id` via `WHERE
  table_schema IN UNNEST(@datasets)`. O frontend (`OrphansPage.tsx`)
  sempre manda um escopo explícito via `DatasetScopeGate` — escanear o
  projeto inteiro sem gate era lento em produção com muitos datasets;
  `None` continua existindo como capacidade da API (scripts/testes).
- `lookback_days` (`int`, `Query(default=30, ge=1)`, v2.2 2026-08-24 —
  era `LookbackDays` IntEnum restrito a 30/60/90/365; virou `int` livre
  pra o frontend (`OrphansPage.tsx::LookbackPicker`) oferecer "Outro"
  além dos atalhos) — propagado até `repository.list_job_events`, que
  aceita `lookback_days` como parâmetro em vez do antigo `LOOKBACK_DAYS`
  fixo do módulo (endpoints de lineage transitiva —
  `get_table_lineage`/upstream/downstream — continuam no default do
  módulo, não ganharam esse controle).

### Custo de storage estimado (v2.2)

`OrphanTable` ganhou `size_bytes: int` e
`estimated_monthly_storage_cost_usd: float` — capacidade absorvida de
"Tabelas sem uso" (`docs/specs/finops-waste-scanner.md`, removida de lá
na mesma versão por ser essencialmente a mesma pergunta — "quais tabelas
ninguém está lendo" — respondida em dois lugares do app).

```json
{
  "dataset_id": "RAW",
  "table_id": "old_import_2024",
  "size_bytes": 5368709120,
  "estimated_monthly_storage_cost_usd": 0.0537
}
```

Estimativa **factual**, não especulativa: `size_bytes` × preço de
storage por GB/mês (`settings.bigquery_storage_price_usd_per_gb_month_active`
ou `..._long_term`, conforme `last_modified_time` — BigQuery já rebaixa
a tarifa sozinho pra tabelas sem modificação há 90+ dias). Isso é custo
real de storage que já está sendo pago, não uma projeção — mesmo
racional que já valia em `finops-waste-scanner.md` antes da fusão.

`get_orphans` busca metadata (`core/bigquery.py::get_tables_metadata`,
REST, cacheado 5min) só das tabelas órfãs (não de todas as tabelas do
projeto) — menor, e é só isso que a response precisa. O cálculo em si
(`estimate_bigquery_storage_cost_usd`) mora em `core/pricing.py`, não em
`domains/finops/` nem duplicado aqui — é aritmética de preço pura, sem
estado de domínio, compartilhada entre `finops` (candidatas a
particionamento, que usa custo de scan, não de storage) e `lineage`; o
projeto só duplica entre domínios o que tem lógica própria de cada um
(ex: parsing de audit log), não utilitários puramente matemáticos.
Tabela sem metadata resolvível (race entre listagem e fetch) entra com
`size_bytes=0`/custo `0.0`, sem erro.

---

## Algoritmo de travessia

```python
# domains/lineage/service.py
def get_table_lineage(
    client: bigquery.Client,
    logging_client: cloud_logging.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    max_hops: int = 8,
) -> LineageGraphResponse:
    """
    BFS a partir da tabela raiz, independente em cada direção
    (upstream/downstream):

    1. Busca os eventos do projeto raiz (sem guarda — falha 403 propaga,
       igual v1). Semeia um cache de eventos por projeto
       (`events_cache: dict[project_id, list[JobEvent]]`) e um conjunto
       de projetos negados (`denied_projects: set[str]`), compartilhados
       pelas duas direções.
    2. Cada direção mantém seu próprio conjunto de nós visitados
       (`(project_id, dataset_id, table_id)`), semeado com a raiz —
       cycle-safe: revisitar um nó já visitado ainda registra a aresta
       de conexão, mas não expande o nó de novo.
    3. Por nível de BFS: para cada job do nó atual, upstream olha
       `referenced_tables` de jobs cujo `destination_table` é o nó atual;
       downstream olha o `destination_table` de jobs que referenciam o nó
       atual. Comparação sempre pela 3-tupla completa
       (project_id, dataset_id, table_id) — nunca só (dataset_id,
       table_id), que era o bug da v1 (colisão possível entre projetos
       diferentes com dataset/tabela de mesmo nome).
    4. Auto-referência (job cujo destino é a própria fonte, ex: MERGE)
       nunca vira aresta, em nenhum hop — mesma exclusão da v1, aplicada
       uniformemente em toda a travessia.
    5. Vizinho novo, dentro do limite de max_hops: busca eventos do
       projeto dele (cache por request — no máximo uma chamada de
       list_job_events por projeto por requisição, mesmo que a travessia
       toque esse projeto por caminhos diferentes ou pelas duas
       direções). Falha de acesso (LoggingAccessDeniedError) nesse
       projeto marca o nó como access_denied=True e não expande esse
       ramo — resto do grafo segue intacto.
    6. Vizinho novo, no limite de max_hops: nó é registrado mas não
       expandido; marca truncated=True.
    7. Fusão final: une nós/arestas das duas direções, dedup por id
       (nó) e por (source, target) (aresta) — necessário porque um ciclo
       que passa pela raiz (ex: A→B→A) pode ser descoberto
       independentemente pelas duas travessias direcionais.
    """
```

JOIN com múltiplas fontes não precisa de tratamento especial: um job com
`referenced_tables=[A, B]` e `destination_table=C` gera as arestas `A→C`
e `B→C` no mesmo passo de expansão — é exatamente o fan-in que o pedido
original descreve.

Deduplicação de aresta é por par `(source, target)`, não por job: como
`list_job_events` não garante ordenação e um job agendado diariamente
gera até 30 eventos repetidos na janela de 30 dias, cada par de tabelas
vira **uma** aresta (mesmo comportamento de dedup por `set()` que a v1 já
tinha para upstream/downstream). `job_id` na aresta é informativo — um
job observado para aquele par, não necessariamente o mais recente (não
há timestamp plumbado em `JobEvent` hoje).

`get_orphans` não muda — continua a lógica 1-nível já existente,
filtrando `ref[0] == project_id`.

---

## Cache pré-computado de audit log (v2.3)

**Motivação**: `list_job_events` (e o equivalente em `domains/access`)
escaneava Cloud Logging **a cada requisição**, sem limite de resultados,
para toda a janela de 30 dias — em projetos com volume real de audit log
(uso de BigQuery numa organização inteira), isso podia estourar o
timeout do Cloud Run (300s, sem override até esta versão) ou a memória
do container, e o Cloud Run derruba a conexão TCP nesses casos em vez de
devolver um erro HTTP — o browser reporta isso como `TypeError: Failed
to fetch`, sem status e sem mensagem útil. Era o problema real por trás
de "failed to fetch" recorrente em Lineage, Órfãs e Mapa de Acesso.

**Mecanismo**: um Cloud Run Job (`apps/backend/src/observability_hub/jobs/refresh_event_cache.py`,
infra em `infra/terraform/modules/cloud-run-job`) roda 1x/dia (D-1, cron
`"0 3 * * *"` UTC via Cloud Scheduler) e, para cada projeto registrado no
ADM (`domains/admin` `hub_projects` — a única fonte, ver
`jobs/refresh_event_cache.py::_known_projects` e ASM-003), faz **um único scan** de
`jobservice.jobcompleted` (via `core/logging_client.py::bigquery_job_events_filter`
+ `list_entries_with_retry`) e passa os `LogEntry` crus pros 3 parsers
`parse_job_events`/`parse_access_events`/`parse_scan_events`
(lineage/access/finops leem a mesma fonte) — desde 2026-08-28, antes eram
3 scans idênticos que estouravam a cota `read_requests` em projeto de
volume alto. `list_job_events` (scan+parse fundidos) fica pro request-path
fallback. Grava o resultado num cache compartilhado:
- Payload grande (lista de eventos serializada) → bucket GCS dedicado
  (`google_storage_bucket.event_cache`, `environments/{dev,prod}/main.tf`)
  — Firestore tem limite de 1MiB/doc, facilmente ultrapassado em 30 dias
  de audit log de um projeto com uso real. A SA de runtime do backend
  precisa de `roles/storage.objectAdmin` **no bucket** (não vem de
  graça por estarem no mesmo projeto —
  `google_storage_bucket_iam_member.event_cache_runtime_access`, ver
  ASM-006); sem isso, toda leitura/escrita levanta `Forbidden`.
- Metadado pequeno (`cached_at`, contagem de eventos) → Firestore
  (`core/event_cache.py`, mesmo padrão de dado derivado de
  `domains/quality/history_repository.py`).

### Modelo incremental (v2.4, 2026-08-28)

Cada execução do Job (diária ou gatilho manual) lê só o **delta** —
`receiveTimestamp > <maior high-water-mark salvo>` (não uma janela fixa
de N dias, pra capturar logs ingeridos com atraso) — faz `merge_dedup`
com o blob existente (por `job_id`, o evento novo vence) e **evicta** os
eventos fora da janela rolante: **31 dias** pros domínios de job
(`timestamp < hoje − 31d`), **90 dias** pra storage. Isso derruba a
leitura diária de ~15 páginas/projeto pra ~1. O metadado
(`core/event_cache.py::set_cache_metadata`) cresce com `window_start`,
`last_scan_receive_ts` (o anchor do próximo delta), `last_full_scan_at` e
`mode` (`"full"`/`"incremental"`).

O **full scan** da janela inteira só roda quando não há base incremental:
primeira execução do projeto, metadado sem `last_scan_receive_ts`, blob
sumido (lifecycle do bucket) — ou quando o toggle **"forçar completo"** do
gatilho de admin está ligado (`?force_full=true` → env
`OBSERVABILITY_HUB_CACHE_FORCE_FULL=1` só naquela execução, via
`run_v2.RunJobRequest.Overrides`; `core/config.py::settings.cache_force_full`).
`JobEvent` passou a carregar `timestamp` (`endTime or startTime or
createTime`) só pra a evicção de janela funcionar.

O request path (`get_job_events_cached`, `get_access_events_cached`,
`get_scan_events_cached`, `get_read_object_keys_cached`) **não escaneia
mais o Cloud Logging ao vivo em cache miss**. Cache hit → devolve o dado.
Cache miss (ou falha ao ler o blob — bucket sem permissão, GCS fora do
ar) → levanta `EventCacheNotReadyError` (só o run do Job, diário ou
manual, popula o cache; um projeto fora de `hub_projects` nunca sai desse
estado). Os serviços de
lineage/access/finops/storage capturam essa exceção **junto** de
`LoggingQuotaExceededError` e degradam pra grafo/lista/tela vazia com um
`warning` ("o cache ainda não foi gerado…"); `main.py` mapeia pra HTTP
503 só como rede de segurança. `_get_project_events` (travessia de
lineage) trata `EventCacheNotReadyError` num projeto não-raiz como
soft-fail, igual a `LoggingAccessDeniedError`.

**Exceção**: `/orphans?lookback_days=<custom>` (power-user) continua
escaneando ao vivo via `list_job_events` — opt-out explícito, caminho
raro. `get_table_lineage`/BFS transitivo e `/orphans` sem `lookback_days`
sempre passam pelo cache.

**Gatilho manual**: `POST /api/v1/admin/event-cache/refresh`
(admin-only) dispara a mesma execução completa do Job sob demanda, sem
esperar o ciclo diário — usado pelo botão "Atualizar cache agora" em
Admin → Por projeto. Cloud Run Jobs exigem `roles/run.invoker` pra
serem executados (diferente do Service, que usa
`invoker_iam_disabled=true`); tanto a SA dedicada do Scheduler quanto a
própria SA de runtime do backend têm essa role sobre o Job, então o
gatilho manual não precisa de nenhum segredo/token customizado.

O Job roda com a **mesma SA de runtime do Cloud Run Service**
correspondente (`backend-dev-run`/`backend-prod-run`) — nunca uma SA
nova, porque é essa identidade que já tem `roles/logging.privateLogViewer`
concedida manualmente em cada projeto-alvo onboardado
(`docs/onboarding-cliente.md`). Nenhum recurso novo é criado em nenhum
projeto-alvo/cliente — bucket, Job e Scheduler vivem só no projeto do
próprio Hub, preservando "o Hub nunca instala nada no projeto alvo"
(ADR-006).

`GET .../{dataset_id}/{table_id}`, `GET .../orphans` e
`GET /api/v1/access/.../{table_id}` ganham `cache_updated_at: datetime | None`
na resposta — `null` quando o dado veio ao vivo nesta própria chamada
(cache miss), preenchido com o timestamp da última execução do Job (ou
da última escrita via fallback) quando veio do cache.

---

## Estrutura de arquivos

```
apps/backend/src/observability_hub/
├── api/v1/
│   └── lineage.py         # GET /lineage/{project_id}/{dataset_id}/{table_id}, /orphans
├── core/
│   ├── exceptions.py      # LoggingAccessDeniedError
│   ├── logging_client.py  # get_logging_client()
│   ├── event_cache.py     # cache genérico (GCS + Firestore), compartilhado com domains/access
│   └── run_client.py      # Cloud Run Admin API (gatilho manual de admin)
├── domains/lineage/
│   ├── __init__.py
│   ├── service.py         # BFS bidirecional, cache por projeto, merge
│   ├── repository.py      # list_job_events() (scan ao vivo, inalterado) + get_job_events_cached()/write_job_events_cache()
│   └── schemas.py         # LineageNode, LineageEdge, LineageGraphResponse, TableRef, OrphanTable, OrphansResponse
├── jobs/
│   └── refresh_event_cache.py  # entrypoint do Cloud Run Job (1x/dia + gatilho manual)
└── tests/unit/
    ├── core/test_event_cache.py
    ├── jobs/test_refresh_event_cache.py
    └── lineage/
        ├── test_service.py
        └── test_repository.py
```

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Auto-referência (MERGE escreve na própria fonte) | Nunca vira aresta, em nenhum hop |
| Dataset destino anônimo (`_...`, cache de query interativa) | Tratado como sem destino na origem (`repository._parse_entry`), não gera aresta |
| `JOIN` com múltiplas fontes | Fan-in: duas (ou mais) arestas independentes convergindo no mesmo nó |
| Tabela em projeto sem acesso de Logging, **não-raiz** | Nó marcado `access_denied=true`, ramo não expandido, resto do grafo intacto |
| Tabela raiz em projeto sem acesso de Logging | HTTP 403 (hard-fail, igual v1 — sem dado nenhum pra montar) |
| Ciclo (`A→B→A`, jobs diferentes) | Nós/arestas aparecem uma vez cada após a fusão; travessia não reprocessa nó já visitado |
| `max_hops` atingido com fronteira não vazia | `truncated: true` na resposta |
| Job repetido diariamente na janela (mesma aresta) | Deduplicada — uma aresta por par `(source, target)`, não uma por job |
| Nenhum evento de job no projeto raiz | `warning` populado (mesmo texto/causas da v1), `nodes`/`edges` vazios |
| `max_hops` fora do intervalo 1–15 | HTTP 422 (validação do `Query(ge=1, le=15)`) |
| Projeto nunca varrido pelo Job (cache miss) — modelo incremental v2.4 | Request path **não escaneia ao vivo**: levanta `EventCacheNotReadyError` → serviço degrada pra grafo/lista vazia com `warning` "cache ainda não gerado". O run do Job (diário ou gatilho manual) popula — mas só se o projeto estiver em `hub_projects` (ASM-003); um projeto não cadastrado fica permanentemente nesse estado. `main.py` mapeia pra 503 só como rede de segurança |
| Projeto não-raiz sem cache durante a expansão (v2.4) | Soft-fail em `_get_project_events` — não expande a partir dele, resto do grafo intacto (igual a `LoggingAccessDeniedError`/`LoggingQuotaExceededError`) |
| `429 TooManyRequests` (cota `read_requests`/min do projeto) — só no Job de refresh ou no scan custom de `/orphans` (v2.4: request path comum não escaneia mais) | `list_entries_with_retry` faz retry exponencial (backoff, deadline 30s); o 429 persistente vira `LoggingQuotaExceededError` → mesma degradação pra vazio+`warning` do cache-não-gerado |
| `lookback_days` custom em `/orphans` | Único caminho do request path que ainda escaneia ao vivo (`list_job_events`) — opt-out explícito |
| 1ª execução do Job pós-deploy v2.4 / metadado sem anchor / blob sumido (lifecycle) / toggle "forçar completo" | **Full scan** da janela de 31 dias; grava `mode: "full"` + `last_full_scan_at`. Runs seguintes voltam a `mode: "incremental"` (delta por `receiveTimestamp`) |
| Evento de audit log sem `timestamp` parseável (após o fallback `endTime or startTime or createTime`) | Descartado na evicção de janela do Job — população ~zero na prática |
| Job falha num projeto (acesso negado, projeto inexistente/descontinuado, ou qualquer outro erro) | Logado e pulado — não derruba o refresh dos demais projetos conhecidos |
| Admin dispara o gatilho manual enquanto o ciclo diário já está rodando | Duas execuções do Job em paralelo — sem deduplicação na v1, ambas terminam gravando o mesmo resultado (idempotente) |

---

## Critérios de aceite

| ID | Comportamento | Testado em |
|---|---|---|
| AC-001 | Cache hit não chama `client.list_entries` (Cloud Logging) | `test_get_job_events_cached_returns_cache_hit_without_calling_list_entries` |
| AC-002 | Cache miss (lookback default) **não** escaneia ao vivo — levanta `EventCacheNotReadyError` | `test_get_job_events_cached_raises_not_ready_on_miss` |
| AC-003 | `lookback_days` diferente do default do módulo escaneia ao vivo (opt-out) | `test_get_job_events_cached_ignores_cache_for_non_default_lookback`, `test_get_job_events_cached_raises_quota_exceeded_on_custom_lookback` |
| AC-004 | O job de refresh cobre exatamente os projetos de `hub_projects` (registro do ADM) — nada mais | `test_known_projects_returns_registered_projects_only` |
| AC-005 | Falha em um projeto durante o refresh (acesso negado, projeto inexistente, ou qualquer erro inesperado) não interrompe os demais | `test_refresh_project_skips_project_without_logging_access`, `test_refresh_project_skips_project_that_does_not_exist`, `test_refresh_project_skips_project_on_unexpected_error`, `test_main_processes_all_projects_even_when_one_does_not_exist` |
| AC-006 | Gatilho manual de admin chama a Cloud Run Admin API com o nome de Job do ambiente atual | `test_trigger_event_cache_refresh_calls_run_client_with_environment_job_name` |
| AC-007 | Falha ao ler o cache (qualquer exceção, não só cache miss) é tratada como cache miss (`EventCacheNotReadyError`), nunca propaga como 500 | `test_get_job_events_cached_treats_cache_read_failure_as_miss` |
| AC-008 | Job em modo incremental usa filtro `receiveTimestamp>` e faz merge (dedup por `job_id`) do delta com o blob existente | `test_refresh_project_incremental_uses_delta_filter_and_merges` |
| AC-009 | Job cai em full scan (`mode: "full"`, filtro `timestamp>=`) quando falta anchor no metadado ou `force_full` está ligado | `test_refresh_project_full_scan_when_anchor_missing`, `test_refresh_project_full_scan_writes_all_four_caches` |
| AC-010 | Gatilho manual com "forçar completo" injeta a env só naquela execução do Job | `test_trigger_event_cache_refresh_forwards_force_full`, `test_trigger_job_execution_force_full_injects_env_override` |
| AC-011 | Serviços degradam `EventCacheNotReadyError` pra resposta vazia + `warning` (não 503) | `test_get_table_lineage_root_project_cache_not_ready_degrades_to_warning`, `test_get_orphans_cache_not_ready_degrades_to_warning`, `test_get_table_lineage_cross_project_cache_not_ready_soft_fails` |

---

## Suposições

| ID | Suposição | Status |
|---|---|---|
| ASM-001 | GCS (não Firestore) para o payload de eventos — Firestore tem limite de 1MiB/doc, facilmente ultrapassado por 30 dias de audit log num projeto com uso real de BigQuery numa org inteira | confirmada com o usuário durante a implementação |
| ASM-002 | Job roda com a mesma SA de runtime do Cloud Run Service (nunca uma SA nova) — evita reabrir o onboarding manual de IAM cross-project (`docs/onboarding-cliente.md`) de todo cliente já liberado | confirmada |
| ASM-003 | ~~`hub_projects` não é uma lista exaustiva de projetos consultados (acesso via wildcard `"*"` não gera doc lá) — por isso o job também cobre projetos "vistos" via cache miss no request path~~ | **invalidada** (2026-08-31, decisão de produto confirmada com o usuário): `hub_projects` passou a ser a **única** fonte de projetos operados pelo Hub. O wildcard `"*"` controla só *acesso* — um projeto acessível só por wildcard precisa ser cadastrado em Admin → Projetos pra entrar no ciclo do cache e nos seletores. A coleção `event_cache_seen_projects` e `record_project_seen` foram removidas; resíduos limpos por `scripts/cleanup_unregistered_project_cache.py` |
| ASM-004 | Gatilho manual de admin não precisa de deduplicação de execuções concorrentes na v1 — o resultado é idempotente (regrava o mesmo cache), então uma segunda execução em paralelo não corrompe nada, só desperdiça uma chamada a mais | confirmada |
| ASM-005 | Cloud Logging devolve `404 NotFound` (não `403 Forbidden`) quando a SA do Hub não tem **nenhum** binding de IAM no projeto — diferente de "tem acesso mas falta a role certa" (`LoggingAccessDeniedError`). `hub_projects` pode conter entradas obsoletas (projeto descontinuado/renomeado); o job trata os dois casos (e qualquer outro erro de API) como "pula e segue" | confirmada em produção — causou `Container called exit(1)` na primeira execução real do job em dev, ver CHANGELOG |
| ASM-006 | O bucket do cache não concede acesso a nenhuma SA por padrão só por estar no mesmo projeto — a SA de runtime do backend precisa de um `google_storage_bucket_iam_member` explícito (`roles/storage.objectAdmin`); sem ele, `read_cache_bytes`/`write_cache_bytes` levantam `Forbidden`, não capturado pelo `except NotFound` original. `get_job_events_cached`/`get_access_events_cached` passaram a capturar qualquer exceção (não só `NotFound`) ao redor do read/write do cache, caindo pro scan ao vivo | confirmada em produção — causou um "Failed to fetch" novo (mais rápido, HTTP 500 sem CORS) na primeira consulta real pós-deploy, ver CHANGELOG |

## Perguntas em aberto

| ID | Pergunta | Status | Resposta |
|---|---|---|---|
| Q-001 | Intervalo de refresh do job periódico? | respondida | 1x/dia (D-1), às 03:00 UTC — não 15 minutos como cogitado inicialmente, para manter o custo de execução baixo |
| Q-002 | O gatilho manual de admin deve permitir escolher um projeto específico, ou sempre atualizar todos de uma vez? | respondida | Sempre todos de uma vez — mais simples de operar; refresh por projeto individual fica como possível extensão futura |
| Q-003 | Vale adicionar um cap total de eventos (`max_results`) no scan ao vivo, como defesa adicional além do cache? | aberta | — |

---

## Fora do escopo desta spec

- Página de tabelas órfãs (`GET /orphans`) — continua 1-nível, lista
  plana, não vira grafo.
- Histórico/time-travel de schema ao longo da cadeia (lineage reflete o
  estado atual dos nomes de tabela, não versões anteriores).
- Drill-down por job individual na aresta — cada aresta carrega só um
  `job_id` informativo, não a lista completa de jobs que geraram aquela
  relação na janela.
- Detecção de PII ao longo da cadeia (domínio separado, `domains/pii`).
- Configuração de `LOOKBACK_DAYS` via parâmetro de API (continua fixo em
  30 dias, só `max_hops` é parametrizável nesta versão).


---

## Refresh visual - pendente (2026-09) — FEITO (R2-8)

Implementado na rodada 2 (R2-8): `LineagePage` na rota
`/lineage/:datasetId/:tableId` (antes era só uma aba do `ProfilingDialog`,
deletado na R2-7). Arestas `animated` do @xyflow recoloridas pra amarelo +
glow (`.dp6-lineage` no index.css); `onEdgeMouseEnter` destaca a aresta +
os 2 nós que ela liga e atenua o resto (AC-LIN-RV-02); `nodesep`/`ranksep`
maiores + altura 540 (AC-LIN-RV-03). 3 `<Panel>`: Impacto de mudança de
schema (tabelas a jusante = `hop_distance>0`; views que quebrariam via
**B6** — novo `LineageNode.table_type`, best-effort de
`INFORMATION_SCHEMA.TABLES`, só nós do projeto raiz; **jobs agendados = "—"**,
exige integração com Scheduled Queries — fora desta rodada), Fontes
(`hop_distance === -1`), Consumidores (`=== 1`). Indicador `<CacheStalenessBadge>`
+ "· profundidade limitada a {max_hops} hops" (AC-LIN-RV-06).

### ACs originais


Pedidos do brief `frontend-visual-refresh.md` (sec. Lineage) que sao feature de
dataviz nova (nao polish). Viram branch propria depois do review, com o
usuario validando em `dev` a cada iteracao. Ver
`frontend-visual-refresh-plan.md` sec.5.

| ID | Comportamento | Teste |
|---|---|---|
| AC-LIN-RV-01 | Arestas do grafo animadas (fluxo tracejado "vivo") em `LineageGraph`; a animacao para num frame sob `prefers-reduced-motion`. | `test_lineage_graph_edges_animated` |
| AC-LIN-RV-02 | Hover numa **aresta** (nao so num no) destaca a aresta + os dois nos que ela liga e atenua o resto. | `test_lineage_edge_hover_highlights_pair` |
| AC-LIN-RV-03 | Area do grafo maior (altura >= ~520px) com mais respiro entre nos. | (visual) |
| AC-LIN-RV-04 | Painel "Impacto a montante" com **contagem**: tabelas afetadas / views que quebrariam / jobs agendados se o schema da tabela-foco mudar. | `test_lineage_upstream_impact_counts` |
| AC-LIN-RV-05 | Paineis "Fontes" (origens diretas, incl. bucket GCS como no) e "Consumidores" (quem le a tabela-foco). | `test_lineage_sources_and_consumers_panels` |
| AC-LIN-RV-06 | Indicador textual "cache atualizado ha X . profundidade limitada a Y hops" - reusa `CacheStalenessBadge` + o `max_hops` que o backend ja aplica. | `test_lineage_cache_and_depth_indicator` |

Suposicao **ASM-LIN-RV-01** (aberta): AC-LIN-RV-04 pode exigir o backend
expor a contagem de "views que quebrariam / jobs agendados" - hoje o
lineage traz so as relacoes. Confirmar na implementacao se e derivavel do
grafo em cache ou e campo novo.
