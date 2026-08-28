"""Fala com o Cloud Logging (jobs completados, pra saber quem escaneou o
quê e quanto pagou) e com o BigQuery (INFORMATION_SCHEMA, pra enumerar
tabelas do projeto — custo $0). domains/finops/service.py combina os
dois; core/bigquery.py::get_tables_metadata resolve tamanho/partição/
last_modified por tabela (REST, cacheado, já usado por catalog/
freshness — reaproveitado direto, é core/, não outro domínio).

Duplica o parsing de audit log de domains/lineage/repository.py (não
importa — nenhum domínio deste projeto importa de outro, ver CLAUDE.md).
Diferença: aqui só interessa leitura (referenced_tables), não destino, e
os campos novos são jobStatistics.totalBilledBytes (custo real já pago
escaneando a tabela — ancora a estimativa de economia de particionamento
em dado observado, ver docs/specs/finops-waste-scanner.md) e, pra
budget (docs/specs/finops-budget.md), job_id/principal_email/query_text
— quem rodou o quê e o texto da query, truncado em
_QUERY_TEXT_MAX_CHARS pra não inflar a resposta de "top queries".
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from google.api_core.exceptions import Forbidden, TooManyRequests
from google.cloud import bigquery, firestore, storage
from google.cloud import logging as cloud_logging

from observability_hub.core import event_cache
from observability_hub.core.config import settings
from observability_hub.core.exceptions import (
    LoggingAccessDeniedError,
    LoggingQuotaExceededError,
    ProjectAccessDeniedError,
)

logger = logging.getLogger(__name__)

_PAGE_SIZE = 1000
_DATE_LIKE_TYPES = {"DATE", "DATETIME", "TIMESTAMP"}
_QUERY_TEXT_MAX_CHARS = 2000

# Janela do scan de audit log de jobs (partition-candidates usa direto;
# budget recorta month-to-date por filtro no service). Fixa, pra o cache
# diário poder servir os dois consumidores — ver get_scan_events_cached.
LOOKBACK_DAYS = 30
# Namespace do cache dentro do bucket compartilhado (core/event_cache.py) e
# "kind" do metadado no Firestore. lineage usa "lineage", access "access",
# storage "storage_read_keys" — prefixos distintos no mesmo bucket.
_CACHE_KIND = "finops_scan_events"

# INFORMATION_SCHEMA.TABLES.table_type usa "VIEW" e "MATERIALIZED VIEW"
# (com espaço) — nenhum dos dois suporta TABLESAMPLE no BigQuery. Mesma
# constante de domains/pii/repository.py (duplicada, não importada —
# domínios isolados, ver CLAUDE.md).
_VIEW_TABLE_TYPES = {"VIEW", "MATERIALIZED VIEW"}

TableRefTuple = tuple[str, str, str]  # (project_id, dataset_id, table_id)


@dataclass(frozen=True)
class ScanEvent:
    timestamp: datetime | None
    referenced_tables: list[TableRefTuple]
    total_billed_bytes: int
    job_id: str = ""
    principal_email: str = ""
    query_text: str | None = None


def _parse_table_ref(ref: dict | None) -> TableRefTuple | None:
    if not ref:
        return None
    project_id = ref.get("projectId")
    dataset_id = ref.get("datasetId")
    table_id = ref.get("tableId")
    if not project_id or not dataset_id or not table_id:
        return None
    if table_id.startswith("INFORMATION_SCHEMA."):
        # Query de metadado do próprio Hub (discover_regions,
        # list_all_table_refs, get_date_like_columns — todas rodam
        # `project.region-X.INFORMATION_SCHEMA.*`) — não é uma tabela
        # real de cliente. Sem esse filtro, "region-US"/"region-EU"/etc.
        # aparecem como se fossem datasets reais no budget, com custo
        # real (pequeno, mas não-zero) de cada probe de região — bug
        # real encontrado em dev, não hipotético (ver
        # docs/specs/finops-budget.md, "Casos de borda").
        return None
    return project_id, dataset_id, table_id


def _parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _parse_billed_bytes(raw: str | None) -> int:
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def _parse_query_text(job: dict) -> str | None:
    raw = job.get("jobConfiguration", {}).get("query", {}).get("query")
    if not raw:
        return None
    if len(raw) > _QUERY_TEXT_MAX_CHARS:
        return raw[:_QUERY_TEXT_MAX_CHARS] + "…"
    return raw


def _parse_entry(entry: cloud_logging.LogEntry) -> ScanEvent | None:
    payload = entry.payload if isinstance(entry.payload, dict) else None
    if payload is None:
        return None

    job = payload.get("serviceData", {}).get("jobCompletedEvent", {}).get("job", {})
    if not job:
        return None

    job_stats = job.get("jobStatistics", {})
    raw_referenced = job_stats.get("referencedTables", [])
    referenced = [ref for r in raw_referenced if (ref := _parse_table_ref(r)) is not None]
    timestamp = _parse_timestamp(job_stats.get("endTime"))
    total_billed_bytes = _parse_billed_bytes(job_stats.get("totalBilledBytes"))

    job_name = job.get("jobName", {})
    job_id = job_name.get("jobId", "") if isinstance(job_name, dict) else ""
    principal_email = payload.get("authenticationInfo", {}).get("principalEmail", "")

    return ScanEvent(
        job_id=job_id,
        principal_email=principal_email,
        timestamp=timestamp,
        referenced_tables=referenced,
        total_billed_bytes=total_billed_bytes,
        query_text=_parse_query_text(job),
    )


def list_scan_events(
    client: cloud_logging.Client, project_id: str, lookback_days: int
) -> list[ScanEvent]:
    """Levanta LoggingAccessDeniedError se a SA de runtime não tiver
    roles/logging.viewer no projeto. Lista vazia (sem erro) é o resultado
    tanto de "nenhum job rodou na janela" quanto de "Data Access audit
    logs desabilitados" — indistinguível por aqui, ver aviso estático em
    domains/finops/service.py.

    lookback_days > 30 esbarra na retenção padrão dos audit logs do Cloud
    Logging (30 dias, salvo bucket/sink customizado) — ver
    docs/specs/finops-waste-scanner.md, "Casos de borda"."""
    cutoff = (datetime.now(UTC) - timedelta(days=lookback_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    filter_ = (
        'resource.type="bigquery_resource" '
        'protoPayload.methodName="jobservice.jobcompleted" '
        f'timestamp>="{cutoff}"'
    )
    try:
        entries = client.list_entries(
            resource_names=[f"projects/{project_id}"],
            filter_=filter_,
            page_size=_PAGE_SIZE,
        )
        return [event for entry in entries if (event := _parse_entry(entry)) is not None]
    except Forbidden as exc:
        raise LoggingAccessDeniedError(project_id) from exc


# --- Cache de audit log (job periódico + fallback do request path) ---------
#
# Antes desta seção, /finops/{project}/partition-candidates e
# /finops/{project}/budget chamavam list_scan_events() direto no request
# path — scan síncrono de 30 dias de audit log do Cloud Logging a cada
# chamada, mesmo problema estrutural que domains/lineage, domains/access e
# domains/storage já resolveram com este padrão (job diário
# jobs/refresh_event_cache.py + core/event_cache.py). Ver CHANGELOG.md.


def serialize_scan_events(events: list[ScanEvent]) -> bytes:
    payload = [
        {
            "job_id": e.job_id,
            "principal_email": e.principal_email,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "referenced_tables": [list(t) for t in e.referenced_tables],
            "total_billed_bytes": e.total_billed_bytes,
            "query_text": e.query_text,
        }
        for e in events
    ]
    return json.dumps(payload).encode("utf-8")


def deserialize_scan_events(data: bytes) -> list[ScanEvent]:
    raw = json.loads(data.decode("utf-8"))
    return [
        ScanEvent(
            job_id=r["job_id"],
            principal_email=r["principal_email"],
            timestamp=datetime.fromisoformat(r["timestamp"]) if r["timestamp"] else None,
            referenced_tables=[tuple(t) for t in r["referenced_tables"]],
            total_billed_bytes=r["total_billed_bytes"],
            query_text=r.get("query_text"),
        )
        for r in raw
    ]


def _cache_blob_path(project_id: str) -> str:
    return f"{_CACHE_KIND}/{project_id}.json"


def read_scan_events_cache(
    storage_client: storage.Client, firestore_client: firestore.Client, project_id: str
) -> tuple[list[ScanEvent], datetime | None] | None:
    """None em cache miss. cached_at pode ser None mesmo com hit se o
    metadado não for encontrado (não deveria acontecer em uso normal —
    escrito junto do blob — mas não é motivo pra propagar erro)."""
    data = event_cache.read_cache_bytes(
        storage_client, settings.event_cache_bucket_name, _cache_blob_path(project_id)
    )
    if data is None:
        return None
    metadata = event_cache.get_cache_metadata(firestore_client, _CACHE_KIND, project_id)
    cached_at = metadata["cached_at"] if metadata else None
    return deserialize_scan_events(data), cached_at


def write_scan_events_cache(
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
    events: list[ScanEvent],
) -> None:
    event_cache.write_cache_bytes(
        storage_client,
        settings.event_cache_bucket_name,
        _cache_blob_path(project_id),
        serialize_scan_events(events),
    )
    event_cache.set_cache_metadata(firestore_client, _CACHE_KIND, project_id, len(events))


def get_scan_events_cached(
    logging_client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
) -> tuple[list[ScanEvent], datetime | None]:
    """Lê o cache pré-computado (job periódico ou fallback write-through de
    outra requisição); em cache miss, escaneia LOOKBACK_DAYS dias ao vivo e
    grava pra próxima chamada (auto-cura) — mesmo racional de
    domains/access/repository.py::get_access_events_cached. ScanEvent
    carrega timestamp por evento, então o mesmo cache de 30 dias serve
    tanto scan_partition_candidates (janela fixa) quanto get_budget
    (recorte month-to-date por filtro no service).

    cached_at None = dado veio ao vivo nesta chamada. Falha ao ler/gravar o
    cache é logada e ignorada (otimização, nunca derruba a resposta).
    LoggingAccessDeniedError (scan ao vivo sem roles/logging.viewer)
    propaga — main.py mapeia. TooManyRequests (429, cota
    ReadRequestsPerMinutePerProject do projeto — dev+prod compartilham)
    vira LoggingQuotaExceededError -> HTTP 503; o retry com backoff que
    suavizaria a maioria dos 429 antes disso entra depois em
    core/logging_client.py::list_entries_with_retry (ver CHANGELOG)."""
    try:
        cached = read_scan_events_cache(storage_client, firestore_client, project_id)
    except Exception:
        logger.exception(
            "Falha ao ler cache de finops para %s — caindo pro scan ao vivo", project_id
        )
    else:
        if cached is not None:
            return cached

    try:
        events = list_scan_events(logging_client, project_id, LOOKBACK_DAYS)
    except TooManyRequests as exc:
        raise LoggingQuotaExceededError(project_id) from exc

    try:
        write_scan_events_cache(storage_client, firestore_client, project_id, events)
        event_cache.record_project_seen(firestore_client, project_id)
    except Exception:
        logger.exception("Falha ao gravar cache de finops para %s", project_id)

    return events, None


def list_all_table_refs(
    client: bigquery.Client,
    project_id: str,
    regions: list[str],
    max_workers: int = 8,
    datasets: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Todas as (dataset_id, table_id) do projeto, via INFORMATION_SCHEMA
    por região em paralelo — custo $0, mesma técnica de
    domains/lineage/repository.py::list_all_table_refs (duplicado, não
    importado — domínios isolados). datasets filtra pra um subconjunto
    de dataset_id quando informado — escanear o projeto inteiro é a
    exceção (script/teste), não o caminho do frontend."""
    if not regions:
        return []

    def _list_region(region: str) -> list[tuple[str, str]]:
        sql = f"""
            SELECT table_schema AS dataset_id, table_name AS table_id
            FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.TABLES`
        """
        job_config = None
        if datasets:
            sql += " WHERE table_schema IN UNNEST(@datasets)"
            job_config = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ArrayQueryParameter("datasets", "STRING", datasets)]
            )
        rows = client.query(sql, job_config=job_config).result()
        return [(row.dataset_id, row.table_id) for row in rows]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(_list_region, regions))
    return [ref for region_refs in results for ref in region_refs]


def get_date_like_columns(
    client: bigquery.Client, project_id: str, dataset_id: str, table_id: str, location: str
) -> list[str]:
    """Colunas DATE/DATETIME/TIMESTAMP da tabela — candidatas a chave de
    partição. Custo $0 (INFORMATION_SCHEMA.COLUMNS)."""
    query = f"""
        SELECT column_name
        FROM `{project_id}.region-{location}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_schema = @dataset_id AND table_name = @table_id
          AND data_type IN UNNEST(@date_like_types)
        ORDER BY ordinal_position
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id),
            bigquery.ScalarQueryParameter("table_id", "STRING", table_id),
            bigquery.ArrayQueryParameter("date_like_types", "STRING", sorted(_DATE_LIKE_TYPES)),
        ]
    )
    rows = client.query(query, job_config=job_config).result()
    return [row.column_name for row in rows]


def get_string_columns(
    client: bigquery.Client, project_id: str, dataset_id: str, table_id: str, location: str
) -> list[str]:
    """Nomes das colunas STRING da tabela — únicas elegíveis pra
    sugestão de tipo nesta v1 (ver docs/specs/finops-column-types.md,
    "Fora do escopo"). Custo $0 (INFORMATION_SCHEMA)."""
    query = f"""
        SELECT column_name
        FROM `{project_id}.region-{location}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_schema = @dataset_id AND table_name = @table_id
          AND data_type = 'STRING'
        ORDER BY ordinal_position
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id),
            bigquery.ScalarQueryParameter("table_id", "STRING", table_id),
        ]
    )
    rows = client.query(query, job_config=job_config).result()
    return [row.column_name for row in rows]


def is_view(
    client: bigquery.Client, project_id: str, dataset_id: str, table_id: str, location: str
) -> bool:
    """VIEW e MATERIALIZED VIEW não suportam TABLESAMPLE no BigQuery — o
    sql_builder precisa saber disso antes de montar a query de scan.
    Duplica domains/pii/repository.py::is_view (não importa — domínios
    isolados)."""
    query = f"""
        SELECT table_type
        FROM `{project_id}.region-{location}.INFORMATION_SCHEMA.TABLES`
        WHERE table_schema = @dataset_id AND table_name = @table_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id),
            bigquery.ScalarQueryParameter("table_id", "STRING", table_id),
        ]
    )
    rows = list(client.query(query, job_config=job_config).result())
    return bool(rows) and rows[0].table_type in _VIEW_TABLE_TYPES


def dry_run(client: bigquery.Client, project_id: str, sql: str) -> int:
    """Bytes que a query processaria, sem executar de fato — usado pelo
    endpoint /column-type-suggestions/estimate, gratuito por definição
    (dry run não cobra)."""
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    try:
        job = client.query(sql, job_config=job_config)
    except Forbidden as exc:
        raise ProjectAccessDeniedError(project_id) from exc
    return job.total_bytes_processed


def execute_scan_query(client: bigquery.Client, project_id: str, sql: str, timeout: float) -> dict:
    """Query de scan é sempre uma única linha agregada — mesmo tabela
    com 0 linhas amostradas retorna 1 linha com contagens zeradas."""
    try:
        rows = list(client.query(sql).result(timeout=timeout))
    except Forbidden as exc:
        raise ProjectAccessDeniedError(project_id) from exc
    row = rows[0]
    return dict(row.items())
