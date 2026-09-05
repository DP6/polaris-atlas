"""Só fala com o Cloud Logging — extrai eventos de job completado do
BigQuery a partir de audit logs (Data Access, categoria opcional —
precisa estar habilitada no projeto alvo; ver domains/access/service.py
sobre o aviso devolvido quando o resultado vem vazio).

Duplica (não importa) a lógica de parsing de domains/lineage/
repository.py — nenhum domínio deste projeto importa de outro (ver
CLAUDE.md, domínios isolados). Diferença: aqui o evento carrega também
o timestamp de conclusão do job (job.jobStatistics.endTime), necessário
pra "quando" — lineage não precisa disso.

Mesmo formato de payload validado em domains/lineage/repository.py
(legado AuditData/jobCompletedEvent, não BigQueryAuditMetadata/
jobChange).
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime

from google.cloud import firestore, storage
from google.cloud import logging as cloud_logging

from atlas.core import event_cache
from atlas.core.config import settings
from atlas.core.exceptions import EventCacheNotReadyError

LOOKBACK_DAYS = 30
_CACHE_KIND = "access"

logger = logging.getLogger(__name__)

TableRefTuple = tuple[str, str, str]  # (project_id, dataset_id, table_id)


@dataclass(frozen=True)
class AccessEvent:
    job_id: str
    principal_email: str
    timestamp: datetime | None
    referenced_tables: list[TableRefTuple]
    destination_table: TableRefTuple | None


def _parse_table_ref(ref: dict | None) -> TableRefTuple | None:
    if not ref:
        return None
    project_id = ref.get("projectId")
    dataset_id = ref.get("datasetId")
    table_id = ref.get("tableId")
    if not project_id or not dataset_id or not table_id:
        return None
    return project_id, dataset_id, table_id


def _parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _parse_entry(entry: cloud_logging.LogEntry) -> AccessEvent | None:
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

    job_config = job.get("jobConfiguration", {})
    destination_raw = job_config.get("query", {}).get("destinationTable") or job_config.get(
        "load", {}
    ).get("destinationTable")
    destination = _parse_table_ref(destination_raw)
    if destination is not None and destination[1].startswith("_"):
        # Dataset anônimo do BigQuery (cache de resultado de query
        # interativa sem destino explícito) — não é uma escrita real,
        # mesma convenção de domains/lineage/repository.py.
        destination = None

    job_name = job.get("jobName", {})
    job_id = job_name.get("jobId", "") if isinstance(job_name, dict) else ""
    principal_email = payload.get("authenticationInfo", {}).get("principalEmail", "")

    return AccessEvent(
        job_id=job_id,
        principal_email=principal_email,
        timestamp=timestamp,
        referenced_tables=referenced,
        destination_table=destination,
    )


def parse_access_events(entries: list[cloud_logging.LogEntry]) -> list[AccessEvent]:
    """Parsing puro (sem I/O) — jobs/refresh_event_cache.py faz UM scan de
    `jobservice.jobcompleted` e passa as entradas cruas pros 3 parsers
    (lineage/access/finops). Não há mais `list_access_events`: o request
    path lê só do cache (modelo incremental), quem escaneia é o job."""
    return [event for entry in entries if (event := _parse_entry(entry)) is not None]


# --- Cache de audit log (job periódico + fallback do request path) ---------


def serialize_access_events(events: list[AccessEvent]) -> bytes:
    payload = [
        {
            "job_id": e.job_id,
            "principal_email": e.principal_email,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "referenced_tables": [list(t) for t in e.referenced_tables],
            "destination_table": list(e.destination_table) if e.destination_table else None,
        }
        for e in events
    ]
    return json.dumps(payload).encode("utf-8")


def deserialize_access_events(data: bytes) -> list[AccessEvent]:
    raw = json.loads(data.decode("utf-8"))
    return [
        AccessEvent(
            job_id=r["job_id"],
            principal_email=r["principal_email"],
            timestamp=datetime.fromisoformat(r["timestamp"]) if r["timestamp"] else None,
            referenced_tables=[tuple(t) for t in r["referenced_tables"]],
            destination_table=tuple(r["destination_table"]) if r["destination_table"] else None,
        )
        for r in raw
    ]


def _cache_blob_path(project_id: str) -> str:
    return f"{_CACHE_KIND}/{project_id}.json"


def read_access_events_cache(
    storage_client: storage.Client, firestore_client: firestore.Client, project_id: str
) -> tuple[list[AccessEvent], datetime | None] | None:
    data = event_cache.read_cache_bytes(
        storage_client, settings.event_cache_bucket_name, _cache_blob_path(project_id)
    )
    if data is None:
        return None
    metadata = event_cache.get_cache_metadata(firestore_client, _CACHE_KIND, project_id)
    cached_at = metadata["cached_at"] if metadata else None
    return deserialize_access_events(data), cached_at


def write_access_events_cache(
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
    events: list[AccessEvent],
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
        serialize_access_events(events),
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


def get_access_events_cached(
    client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
) -> tuple[list[AccessEvent], datetime | None]:
    """Modelo incremental — o request path NÃO escaneia mais ao vivo em
    cache miss (o scan roda só no job diário ou no gatilho manual de admin).
    Cache hit -> (eventos, cached_at). Cache miss -> levanta
    `EventCacheNotReadyError`, que domains/access/service.py degrada pra
    resposta vazia com warning. O job diário só cobre `hub_projects`."""
    try:
        cached = read_access_events_cache(storage_client, firestore_client, project_id)
    except Exception:
        logger.exception(
            "Falha ao ler cache de access para %s — tratando como cache miss", project_id
        )
        cached = None

    if cached is not None:
        return cached

    raise EventCacheNotReadyError(project_id)
