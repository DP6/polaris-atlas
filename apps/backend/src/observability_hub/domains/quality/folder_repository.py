"""Única camada que fala com o Firestore pras pastas de comparação de
profiling — service.py orquestra e decide acesso, nunca monta
paths/queries diretamente (mesmo racional de history_repository.py).

profiling_folders/{folder_id} (auto-id)
  name, created_by, created_at, updated_at, visibility, shared_with

profiling_folders/{folder_id}/entries/{entry_id} (auto-id)
  snapshot completo do run salvo — nunca uma referência a
  profiling_history (que tem trim-to-30 e apagaria a origem).
"""

from datetime import UTC, datetime

from google.cloud import firestore

_COLLECTION = "profiling_folders"
_ENTRIES_SUBCOLLECTION = "entries"


def _folders_collection(client: firestore.Client):
    return client.collection(_COLLECTION)


def _entries_collection(client: firestore.Client, folder_id: str):
    return _folders_collection(client).document(folder_id).collection(_ENTRIES_SUBCOLLECTION)


def create_folder(client: firestore.Client, name: str, created_by: str) -> dict:
    now = datetime.now(UTC)
    doc_ref = _folders_collection(client).document()
    data = {
        "name": name,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
        "visibility": "private",
        "shared_with": [],
    }
    doc_ref.set(data)
    return {**data, "folder_id": doc_ref.id}


def list_folders(client: firestore.Client) -> list[dict]:
    """Todas as pastas — filtro de quem pode ver cada uma acontece em
    service.py, não aqui (coleção pequena, mesmo racional de
    domains/admin/service.py::has_project_access escaneando hub_groups)."""
    docs = _folders_collection(client).stream()
    return [{**doc.to_dict(), "folder_id": doc.id} for doc in docs]


def get_folder(client: firestore.Client, folder_id: str) -> dict | None:
    doc = _folders_collection(client).document(folder_id).get()
    if not doc.exists:
        return None
    return {**doc.to_dict(), "folder_id": doc.id}


def update_folder(
    client: firestore.Client,
    folder_id: str,
    name: str,
    visibility: str,
    shared_with: list[str],
) -> dict:
    doc_ref = _folders_collection(client).document(folder_id)
    doc_ref.update(
        {
            "name": name,
            "visibility": visibility,
            "shared_with": shared_with,
            "updated_at": datetime.now(UTC),
        }
    )
    return get_folder(client, folder_id)  # type: ignore[return-value]


def delete_folder(client: firestore.Client, folder_id: str) -> None:
    entries = _entries_collection(client, folder_id)
    for doc in entries.stream():
        doc.reference.delete()
    _folders_collection(client).document(folder_id).delete()


def add_entry(client: firestore.Client, folder_id: str, entry: dict) -> dict:
    doc_ref = _entries_collection(client, folder_id).document()
    data = {**entry, "saved_at": datetime.now(UTC)}
    doc_ref.set(data)
    return {**data, "entry_id": doc_ref.id}


def list_entries(client: firestore.Client, folder_id: str) -> list[dict]:
    docs = (
        _entries_collection(client, folder_id)
        .order_by("saved_at", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [{**doc.to_dict(), "entry_id": doc.id} for doc in docs]


def count_entries(client: firestore.Client, folder_id: str) -> int:
    return len(list(_entries_collection(client, folder_id).stream()))


def delete_entry(client: firestore.Client, folder_id: str, entry_id: str) -> None:
    _entries_collection(client, folder_id).document(entry_id).delete()
