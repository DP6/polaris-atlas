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

from observability_hub.core import event_cache
from observability_hub.core.config import settings
from observability_hub.core.logging_client import (
    LOGGING_PAGE_SIZE,
    bigquery_job_events_filter,
    list_entries_with_retry,
)

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
    timestamp = _parse_timestamp(job_stats.get("endTime"))

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


def list_access_events(client: cloud_logging.Client, project_id: str) -> list[AccessEvent]:
    """Levanta LoggingAccessDeniedError se a SA de runtime não tiver
    roles/logging.viewer no projeto, e LoggingQuotaExceededError se a cota
    read_requests/min do projeto persistir estourada após o retry (ver
    core/logging_client.py::list_entries_with_retry). Lista vazia (sem
    erro) é o resultado tanto de "nenhum job rodou na janela" quanto de
    "Data Access audit logs desabilitados" — indistinguível por aqui, ver
    aviso estático em domains/access/service.py.

    Só cobre acessos originados por jobs que rodaram NESTE projeto — um
    job rodando em outro projeto que referencia uma tabela deste projeto
    (leitura cross-project) não aparece aqui, porque o audit log dele
    vive no projeto onde o job rodou, não no projeto da tabela lida (ver
    docs/specs/access.md, "Casos de borda")."""
    entries = list_entries_with_retry(
        client,
        resource_names=[f"projects/{project_id}"],
        filter_=bigquery_job_events_filter(LOOKBACK_DAYS),
        page_size=LOGGING_PAGE_SIZE,
        project_id=project_id,
    )
    return parse_access_events(entries)


def parse_access_events(entries: list[cloud_logging.LogEntry]) -> list[AccessEvent]:
    """Parsing puro (sem I/O) — separado de list_access_events pra
    jobs/refresh_event_cache.py alimentar lineage/access/finops de um scan
    único do Cloud Logging (ver core/logging_client.py::bigquery_job_events_filter)."""
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
) -> None:
    event_cache.write_cache_bytes(
        storage_client,
        settings.event_cache_bucket_name,
        _cache_blob_path(project_id),
        serialize_access_events(events),
    )
    event_cache.set_cache_metadata(firestore_client, _CACHE_KIND, project_id, len(events))


def get_access_events_cached(
    client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
) -> tuple[list[AccessEvent], datetime | None]:
    """Endpoint de access não tem lookback_days variável (sempre
    LOOKBACK_DAYS) — cache sempre elegível, diferente de lineage/orphans.
    cached_at None significa que o dado veio ao vivo nesta chamada.
    Qualquer falha ao ler/gravar o cache é logada e ignorada — o cache é
    uma otimização, uma falha nele nunca deve derrubar a resposta pro
    usuário (ver domains/lineage/repository.py::get_job_events_cached,
    mesmo racional)."""
    try:
        cached = read_access_events_cache(storage_client, firestore_client, project_id)
    except Exception:
        logger.exception(
            "Falha ao ler cache de access para %s — caindo pro scan ao vivo", project_id
        )
    else:
        if cached is not None:
            return cached

    # list_access_events já mapeia Forbidden -> LoggingAccessDeniedError e
    # 429 persistente -> LoggingQuotaExceededError (via
    # core/logging_client.py::list_entries_with_retry); as duas propagam,
    # main.py mapeia pra 403/503.
    events = list_access_events(client, project_id)

    try:
        write_access_events_cache(storage_client, firestore_client, project_id, events)
        event_cache.record_project_seen(firestore_client, project_id)
    except Exception:
        logger.exception("Falha ao gravar cache de access para %s", project_id)

    return events, None
