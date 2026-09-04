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
from datetime import datetime

from google.api_core.exceptions import Forbidden, GoogleAPICallError
from google.cloud import bigquery, firestore, storage
from google.cloud import logging as cloud_logging

from observability_hub.core import event_cache
from observability_hub.core.config import settings
from observability_hub.core.exceptions import EventCacheNotReadyError, ProjectAccessDeniedError

logger = logging.getLogger(__name__)

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
    timestamp = _parse_timestamp(
        job_stats.get("endTime") or job_stats.get("startTime") or job_stats.get("createTime")
    )
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


def parse_scan_events(entries: list[cloud_logging.LogEntry]) -> list[ScanEvent]:
    """Parsing puro (sem I/O) — jobs/refresh_event_cache.py faz UM scan de
    `jobservice.jobcompleted` e passa as entradas cruas pros 3 parsers
    (lineage/access/finops). Não há mais `list_scan_events`: o request path
    lê só do cache (modelo incremental), quem escaneia é o job."""
    return [event for entry in entries if (event := _parse_entry(entry)) is not None]


# --- Cache de audit log (só o job periódico escaneia; request path só lê) --
#
# /finops/{project}/partition-candidates e /finops/{project}/budget leem
# apenas do cache (modelo incremental) — quem escaneia o Cloud Logging é
# jobs/refresh_event_cache.py (scan diário incremental + full manual),
# mesmo padrão de domains/lineage, domains/access e domains/storage.
# Ver docs/specs/finops-waste-scanner.md e CHANGELOG.md.


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
    *,
    window_start: datetime | None = None,
    last_scan_receive_ts: datetime | None = None,
    last_full_scan_at: datetime | None = None,
    mode: str | None = None,
) -> None:
    event_cache.write_cache_bytes(
        storage_client,
        settings.event_cache_bucket_name,
        _cache_blob_path(project_id),
        serialize_scan_events(events),
    )
    event_cache.set_cache_metadata(
        firestore_client,
        _CACHE_KIND,
        project_id,
        len(events),
        window_start=window_start,
        last_scan_receive_ts=last_scan_receive_ts,
        last_full_scan_at=last_full_scan_at,
        mode=mode,
    )


def get_scan_events_cached(
    logging_client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
) -> tuple[list[ScanEvent], datetime | None]:
    """Modelo incremental — o request path NÃO escaneia mais ao vivo em
    cache miss (o scan roda só no job diário ou no gatilho manual de admin).
    Cache hit -> (eventos, cached_at); serve tanto scan_partition_candidates
    quanto get_budget (recorte month-to-date por filtro no service). Cache
    miss -> levanta `EventCacheNotReadyError`, que domains/finops/service.py
    degrada pra resposta vazia com warning. O job diário só cobre
    `hub_projects`."""
    try:
        cached = read_scan_events_cache(storage_client, firestore_client, project_id)
    except Exception:
        logger.exception(
            "Falha ao ler cache de finops para %s — tratando como cache miss", project_id
        )
        cached = None

    if cached is not None:
        return cached

    raise EventCacheNotReadyError(project_id)


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


def _short_error(exc: BaseException) -> str:
    """Primeira linha da mensagem da exceção, sem stack — o suficiente pra
    distinguir 403 (permissão) de 404 (view/região) de 400 (coluna) no
    warning que sobe pra UI."""
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    return text[:180]


def get_current_storage_bytes(
    client: bigquery.Client,
    project_id: str,
    regions: list[str],
    datasets: list[str] | None = None,
    tables: list[str] | None = None,
    max_workers: int = 8,
) -> tuple[int | None, str | None]:
    """Total de bytes lógicos de storage AGORA, somado sobre as tabelas do
    projeto (opcionalmente filtradas por dataset ou `dataset.table`), de
    `INFORMATION_SCHEMA.TABLE_STORAGE` — view de metadado ($0, mesma base
    de list_all_table_refs). Fan-out por região; qualificador em minúscula
    (`region-us`).

    Usa o snapshot atual, não a timeline histórica: a família
    `TABLE_STORAGE_USAGE_TIMELINE_*` tem schema de coluna instável entre
    versões (o Hub bateu em `400 Unrecognized name` em dev) e, numa janela
    de ~30 dias, o storage praticamente não varia — uma linha plana no
    nível atual é suficiente pro gráfico de custo do mês. `total_logical_bytes`
    é coluna estável e documentada de `TABLE_STORAGE`.

    Retorna `(bytes, None)` se ao menos uma região respondeu; `(None,
    motivo)` se **nenhuma** respondeu — `motivo` é a 1ª linha do erro do
    BigQuery (403/404/400…), propagado pro warning. Nunca 500; região que
    falha sozinha é ignorada."""
    if not regions:
        return None, "nenhuma região com dataset no projeto"

    filters: list[str] = []
    params: list[bigquery.ArrayQueryParameter] = []
    if datasets:
        filters.append("table_schema IN UNNEST(@datasets)")
        params.append(bigquery.ArrayQueryParameter("datasets", "STRING", datasets))
    if tables:
        filters.append("CONCAT(table_schema, '.', table_name) IN UNNEST(@tables)")
        params.append(bigquery.ArrayQueryParameter("tables", "STRING", tables))
    where = f"WHERE {' AND '.join(filters)}" if filters else ""

    def _query_region(region: str) -> tuple[int | None, str | None]:
        sql = f"""
            SELECT SUM(COALESCE(total_logical_bytes, 0)) AS logical_bytes
            FROM `{project_id}.region-{region.lower()}.INFORMATION_SCHEMA.TABLE_STORAGE`
            {where}
        """
        try:
            rows = list(
                client.query(
                    sql, job_config=bigquery.QueryJobConfig(query_parameters=params)
                ).result()
            )
        except (GoogleAPICallError, ValueError) as exc:
            reason = _short_error(exc)
            logger.warning(
                "Storage snapshot indisponível em region-%s de %s: %s",
                region.lower(),
                project_id,
                reason,
            )
            return None, reason
        return (int(rows[0].logical_bytes or 0) if rows else 0), None

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        per_region = list(pool.map(_query_region, regions))

    if all(byte_total is None for byte_total, _reason in per_region):
        reasons = sorted({reason for _b, reason in per_region if reason})
        return None, "; ".join(reasons) or "erro desconhecido"
    return sum(byte_total for byte_total, _r in per_region if byte_total is not None), None


def get_storage_bytes_by_table(
    client: bigquery.Client,
    project_id: str,
    regions: list[str],
    datasets: list[str] | None = None,
    tables: list[str] | None = None,
    max_workers: int = 8,
) -> tuple[dict[tuple[str, str], int] | None, str | None]:
    """Igual a get_current_storage_bytes, mas GROUP BY table_schema,
    table_name em vez de somar tudo — usada pelo breakdown de custo por
    tabela/dataset de get_budget (include_storage=True,
    docs/specs/finops-budget.md v1.12). Mesma fonte $0, mesmo contrato de
    erro: (dict, None) se ao menos uma região responder — merge por
    (dataset_id, table_id) somando entre regiões —, (None, motivo) se
    nenhuma responder. Nunca lança."""
    if not regions:
        return None, "nenhuma região com dataset no projeto"

    filters: list[str] = []
    params: list[bigquery.ArrayQueryParameter] = []
    if datasets:
        filters.append("table_schema IN UNNEST(@datasets)")
        params.append(bigquery.ArrayQueryParameter("datasets", "STRING", datasets))
    if tables:
        filters.append("CONCAT(table_schema, '.', table_name) IN UNNEST(@tables)")
        params.append(bigquery.ArrayQueryParameter("tables", "STRING", tables))
    where = f"WHERE {' AND '.join(filters)}" if filters else ""

    def _query_region(region: str) -> tuple[dict[tuple[str, str], int] | None, str | None]:
        sql = f"""
            SELECT table_schema, table_name,
                   SUM(COALESCE(total_logical_bytes, 0)) AS logical_bytes
            FROM `{project_id}.region-{region.lower()}.INFORMATION_SCHEMA.TABLE_STORAGE`
            {where}
            GROUP BY table_schema, table_name
        """
        try:
            rows = list(
                client.query(
                    sql, job_config=bigquery.QueryJobConfig(query_parameters=params)
                ).result()
            )
        except (GoogleAPICallError, ValueError) as exc:
            reason = _short_error(exc)
            logger.warning(
                "Storage por tabela indisponível em region-%s de %s: %s",
                region.lower(),
                project_id,
                reason,
            )
            return None, reason
        return {
            (row.table_schema, row.table_name): int(row.logical_bytes or 0) for row in rows
        }, None

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        per_region = list(pool.map(_query_region, regions))

    if all(result is None for result, _reason in per_region):
        reasons = sorted({reason for _r, reason in per_region if reason})
        return None, "; ".join(reasons) or "erro desconhecido"

    merged: dict[tuple[str, str], int] = {}
    for result, _reason in per_region:
        if result is None:
            continue
        for key, byte_count in result.items():
            merged[key] = merged.get(key, 0) + byte_count
    return merged, None


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
