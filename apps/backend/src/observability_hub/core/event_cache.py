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

from datetime import UTC, datetime

from google.api_core.exceptions import NotFound
from google.cloud import firestore, storage

_CACHE_METADATA_COLLECTION = "event_cache_metadata"
# Projetos que passaram pelo request path via cache miss — inclui os
# liberados só por wildcard "*" em domains/admin/service.py, que nunca
# ganham doc em hub_projects. jobs/refresh_event_cache.py varre a união
# de hub_projects com esta coleção (ver docs/specs/lineage.md, ASM).
_SEEN_PROJECTS_COLLECTION = "event_cache_seen_projects"


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
    firestore_client: firestore.Client, cache_kind: str, project_id: str, event_count: int
) -> dict:
    data = {
        "cache_kind": cache_kind,
        "project_id": project_id,
        "event_count": event_count,
        "cached_at": datetime.now(UTC),
    }
    _cache_metadata_doc(firestore_client, cache_kind, project_id).set(data)
    return data


def record_project_seen(firestore_client: firestore.Client, project_id: str) -> None:
    """Efeito colateral do fallback síncrono (cache miss) no request path."""
    firestore_client.collection(_SEEN_PROJECTS_COLLECTION).document(project_id).set(
        {"project_id": project_id, "last_seen_at": datetime.now(UTC)}
    )


def list_seen_projects(firestore_client: firestore.Client) -> list[str]:
    docs = firestore_client.collection(_SEEN_PROJECTS_COLLECTION).stream()
    return [doc.id for doc in docs]
