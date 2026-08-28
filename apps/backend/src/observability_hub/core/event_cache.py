"""Cache compartilhado de eventos de audit log (Cloud Logging) entre
domains/lineage e domains/access — infraestrutura genérica (client
sempre via parâmetro, nunca instanciado aqui), não lógica de domínio.
Cada domínio é dono da própria (de)serialização (ver
domains/lineage/repository.py::serialize_job_events); este módulo só
move bytes e metadado.

Payload grande (lista de eventos serializada) vai pro Cloud Storage —
Firestore tem limite de 1MiB por documento e um projeto com uso real de
BigQuery numa organização inteira facilmente ultrapassa isso em 30 dias
de audit log. Metadado pequeno (quando foi gerado, quantos eventos) vai
pro Firestore, mesmo padrão de dado derivado já usado por
domains/quality/history_repository.py etc.

Populado pelo job periódico (jobs/refresh_event_cache.py, 1x/dia) e,
como fallback write-through, pelo próprio request path em cache miss —
quem grava não faz diferença pra quem lê.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from google.api_core.exceptions import NotFound
from google.cloud import firestore, storage

_CACHE_METADATA_COLLECTION = "event_cache_metadata"
# Projetos que passaram pelo request path via cache miss — inclui os
# liberados só por wildcard "*" em domains/admin/service.py, que nunca
# ganham doc em hub_projects. jobs/refresh_event_cache.py varre a união
# de hub_projects com esta coleção (ver docs/specs/lineage.md, ASM).
_SEEN_PROJECTS_COLLECTION = "event_cache_seen_projects"
# Registro de execuções do job de refresh (jobs/refresh_event_cache.py) —
# lido pela tela de acompanhamento em Administração → Caches. Um doc por
# execução, `projects` preenchido incrementalmente conforme cada projeto
# termina (a tela faz polling e vê os projetos "acenderem" um a um).
_CACHE_RUNS_COLLECTION = "event_cache_runs"
# Retenção de execuções pra a tabela de histórico de Administração → Caches
# (paginação até 50/página + filtros aplicados em Python sobre este total).
_CACHE_RUNS_KEEP = 200


def read_cache_bytes(
    storage_client: storage.Client, bucket_name: str, blob_path: str
) -> bytes | None:
    """None em cache miss (objeto nunca escrito) — não distingue de bucket
    inexistente, que é erro de configuração, não estado esperado."""
    blob = storage_client.bucket(bucket_name).blob(blob_path)
    try:
        return blob.download_as_bytes()
    except NotFound:
        return None


def write_cache_bytes(
    storage_client: storage.Client, bucket_name: str, blob_path: str, data: bytes
) -> None:
    blob = storage_client.bucket(bucket_name).blob(blob_path)
    blob.upload_from_string(data, content_type="application/json")


def _cache_metadata_doc(firestore_client: firestore.Client, cache_kind: str, project_id: str):
    return firestore_client.collection(_CACHE_METADATA_COLLECTION).document(
        f"{cache_kind}:{project_id}"
    )


def get_cache_metadata(
    firestore_client: firestore.Client, cache_kind: str, project_id: str
) -> dict | None:
    doc = _cache_metadata_doc(firestore_client, cache_kind, project_id).get()
    return doc.to_dict() if doc.exists else None


def set_cache_metadata(
    firestore_client: firestore.Client,
    cache_kind: str,
    project_id: str,
    event_count: int,
    *,
    window_start: datetime | None = None,
    last_scan_receive_ts: datetime | None = None,
    last_full_scan_at: datetime | None = None,
    mode: str | None = None,
) -> dict:
    """Grava o metadado do cache (doc `{cache_kind}:{project_id}`).

    Campos de janela (`window_start`, `last_scan_receive_ts`,
    `last_full_scan_at`, `mode`) alimentam o modelo incremental do job
    (jobs/refresh_event_cache.py) e a tela Administração → Caches:
    - `window_start`: piso da janela no blob atual (evento mais antigo mantido).
    - `last_scan_receive_ts`: high-water-mark de `receiveTimestamp` — o
      próximo delta escaneia `receiveTimestamp > isso`.
    - `last_full_scan_at`: quando foi o último scan completo (preservado
      entre runs incrementais).
    - `mode`: `"full"` | `"incremental"` do último write.

    `first_cached_at` e `last_full_scan_at` são preservados do doc anterior
    quando não vierem explícitos."""
    existing = get_cache_metadata(firestore_client, cache_kind, project_id) or {}
    now = datetime.now(UTC)
    data = {
        "cache_kind": cache_kind,
        "project_id": project_id,
        "event_count": event_count,
        "cached_at": now,
        "first_cached_at": existing.get("first_cached_at") or now,
        "window_start": window_start,
        "last_scan_receive_ts": last_scan_receive_ts,
        "last_full_scan_at": last_full_scan_at or existing.get("last_full_scan_at"),
        "mode": mode,
    }
    _cache_metadata_doc(firestore_client, cache_kind, project_id).set(data)
    return data


def merge_dedup(existing: list, new: list, *, key: Callable[[Any], object]) -> list:
    """Concatena `existing + new` deduplicando por `key(item)` — o item de
    `new` vence em colisão (é o dado mais recente). Itens com `key` falsy
    (ex.: job_id vazio) nunca são deduplicados — entram todos. Usado pelo
    merge incremental do job (jobs/refresh_event_cache.py) com
    `key=lambda e: e.job_id`."""
    by_key: dict[object, Any] = {}
    passthrough: list = []
    for item in existing:
        k = key(item)
        if k:
            by_key[k] = item
        else:
            passthrough.append(item)
    for item in new:
        k = key(item)
        if k:
            by_key[k] = item
        else:
            passthrough.append(item)
    return [*by_key.values(), *passthrough]


def record_project_seen(firestore_client: firestore.Client, project_id: str) -> None:
    """Efeito colateral do fallback síncrono (cache miss) no request path."""
    firestore_client.collection(_SEEN_PROJECTS_COLLECTION).document(project_id).set(
        {"project_id": project_id, "last_seen_at": datetime.now(UTC)}
    )


def list_seen_projects(firestore_client: firestore.Client) -> list[str]:
    docs = firestore_client.collection(_SEEN_PROJECTS_COLLECTION).stream()
    return [doc.id for doc in docs]


# --- Registro de execuções do job de refresh (tela de acompanhamento) --------


def _cache_run_id() -> str:
    # Ordenável lexicograficamente == cronologicamente (usado como doc id e
    # como chave de order_by, sem precisar de índice composto no Firestore).
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _prune_cache_runs(firestore_client: firestore.Client) -> None:
    docs = list(
        firestore_client.collection(_CACHE_RUNS_COLLECTION)
        .order_by("run_id", direction=firestore.Query.DESCENDING)
        .stream()
    )
    for doc in docs[_CACHE_RUNS_KEEP:]:
        doc.reference.delete()


def start_cache_run(firestore_client: firestore.Client, project_ids: list[str]) -> str:
    """Cria o doc da execução e retorna o run_id. `projects` começa vazio e
    é preenchido por record_cache_run_project conforme cada projeto termina."""
    run_id = _cache_run_id()
    firestore_client.collection(_CACHE_RUNS_COLLECTION).document(run_id).set(
        {
            "run_id": run_id,
            "started_at": datetime.now(UTC),
            "finished_at": None,
            "status": "running",
            "project_count": len(project_ids),
            "projects": {},
        }
    )
    _prune_cache_runs(firestore_client)
    return run_id


def record_cache_run_project(
    firestore_client: firestore.Client,
    run_id: str,
    project_id: str,
    status: str,
    counts: dict[str, object],
) -> None:
    # counts mistura contagens (int) com `mode` (str) desde o cache
    # incremental — Firestore é schemaless, o valor entra como está.
    firestore_client.collection(_CACHE_RUNS_COLLECTION).document(run_id).update(
        {f"projects.{project_id}": {"status": status, "finished_at": datetime.now(UTC), **counts}}
    )


def finish_cache_run(firestore_client: firestore.Client, run_id: str) -> None:
    firestore_client.collection(_CACHE_RUNS_COLLECTION).document(run_id).update(
        {"status": "done", "finished_at": datetime.now(UTC)}
    )


def list_cache_runs(firestore_client: firestore.Client, limit: int = 5) -> list[dict]:
    docs = (
        firestore_client.collection(_CACHE_RUNS_COLLECTION)
        .order_by("run_id", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [doc.to_dict() for doc in docs]
