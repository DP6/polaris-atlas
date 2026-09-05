from datetime import datetime
from unittest.mock import MagicMock

from google.cloud import firestore

from atlas.domains.quality import folder_repository


def _fake_folders_collection():
    """MagicMock cujo client.collection("profiling_folders") devolve um
    mock único e previsível — mesmo padrão de test_history_repository.py."""
    client = MagicMock()
    folders = MagicMock()
    client.collection.return_value = folders
    return client, folders


def test_create_folder_writes_private_by_default():
    client, folders = _fake_folders_collection()
    doc_ref = MagicMock()
    doc_ref.id = "folder-1"
    folders.document.return_value = doc_ref

    result = folder_repository.create_folder(client, "Comparação Q3", "ana@dp6.com.br")

    client.collection.assert_called_once_with("profiling_folders")
    doc_ref.set.assert_called_once()
    written = doc_ref.set.call_args[0][0]
    assert written["name"] == "Comparação Q3"
    assert written["created_by"] == "ana@dp6.com.br"
    assert written["visibility"] == "private"
    assert written["shared_with"] == []
    assert isinstance(written["created_at"], datetime)
    assert result["folder_id"] == "folder-1"
    assert result["name"] == "Comparação Q3"


def test_list_folders_returns_all_with_ids():
    client, folders = _fake_folders_collection()
    doc_a = MagicMock(id="a")
    doc_a.to_dict.return_value = {"name": "A"}
    doc_b = MagicMock(id="b")
    doc_b.to_dict.return_value = {"name": "B"}
    folders.stream.return_value = [doc_a, doc_b]

    result = folder_repository.list_folders(client)

    assert result == [{"name": "A", "folder_id": "a"}, {"name": "B", "folder_id": "b"}]


def test_get_folder_returns_none_when_missing():
    client, folders = _fake_folders_collection()
    doc_ref = MagicMock()
    doc = MagicMock(exists=False)
    doc_ref.get.return_value = doc
    folders.document.return_value = doc_ref

    assert folder_repository.get_folder(client, "ghost") is None


def test_get_folder_returns_dict_with_id_when_found():
    client, folders = _fake_folders_collection()
    doc_ref = MagicMock()
    doc = MagicMock(exists=True, id="folder-1")
    doc.to_dict.return_value = {"name": "A"}
    doc_ref.get.return_value = doc
    folders.document.return_value = doc_ref

    result = folder_repository.get_folder(client, "folder-1")

    assert result == {"name": "A", "folder_id": "folder-1"}


def test_update_folder_writes_fields_and_returns_updated():
    client, folders = _fake_folders_collection()
    doc_ref = MagicMock()
    doc = MagicMock(exists=True, id="folder-1")
    doc.to_dict.return_value = {
        "name": "Novo nome",
        "visibility": "shared_all",
        "shared_with": [],
    }
    doc_ref.get.return_value = doc
    folders.document.return_value = doc_ref

    result = folder_repository.update_folder(client, "folder-1", "Novo nome", "shared_all", [])

    doc_ref.update.assert_called_once()
    written = doc_ref.update.call_args[0][0]
    assert written["name"] == "Novo nome"
    assert written["visibility"] == "shared_all"
    assert isinstance(written["updated_at"], datetime)
    assert result["folder_id"] == "folder-1"


def test_delete_folder_deletes_entries_then_folder():
    client, folders = _fake_folders_collection()
    table_doc = MagicMock()
    entries = MagicMock()
    folders.document.return_value = table_doc
    table_doc.collection.return_value = entries
    entry_doc = MagicMock()
    entries.stream.return_value = [entry_doc]

    folder_repository.delete_folder(client, "folder-1")

    entry_doc.reference.delete.assert_called_once()
    table_doc.delete.assert_called_once()


def test_add_entry_writes_with_saved_at():
    client, folders = _fake_folders_collection()
    table_doc = MagicMock()
    entries = MagicMock()
    folders.document.return_value = table_doc
    table_doc.collection.return_value = entries
    doc_ref = MagicMock(id="entry-1")
    entries.document.return_value = doc_ref

    result = folder_repository.add_entry(
        client, "folder-1", {"project_id": "proj", "dataset_id": "RAW", "table_id": "t"}
    )

    doc_ref.set.assert_called_once()
    written = doc_ref.set.call_args[0][0]
    assert written["project_id"] == "proj"
    assert isinstance(written["saved_at"], datetime)
    assert result["entry_id"] == "entry-1"


def test_list_entries_orders_by_saved_at_descending():
    client, folders = _fake_folders_collection()
    table_doc = MagicMock()
    entries = MagicMock()
    folders.document.return_value = table_doc
    table_doc.collection.return_value = entries
    ordered_query = MagicMock()
    entries.order_by.return_value = ordered_query
    doc = MagicMock(id="entry-1")
    doc.to_dict.return_value = {"project_id": "proj"}
    ordered_query.stream.return_value = [doc]

    result = folder_repository.list_entries(client, "folder-1")

    entries.order_by.assert_called_once_with("saved_at", direction=firestore.Query.DESCENDING)
    assert result == [{"project_id": "proj", "entry_id": "entry-1"}]


def test_count_entries_returns_length():
    client, folders = _fake_folders_collection()
    table_doc = MagicMock()
    entries = MagicMock()
    folders.document.return_value = table_doc
    table_doc.collection.return_value = entries
    entries.stream.return_value = [MagicMock(), MagicMock(), MagicMock()]

    assert folder_repository.count_entries(client, "folder-1") == 3


def test_delete_entry_deletes_the_right_document():
    client, folders = _fake_folders_collection()
    table_doc = MagicMock()
    entries = MagicMock()
    folders.document.return_value = table_doc
    table_doc.collection.return_value = entries
    doc_ref = MagicMock()
    entries.document.return_value = doc_ref

    folder_repository.delete_entry(client, "folder-1", "entry-1")

    entries.document.assert_called_once_with("entry-1")
    doc_ref.delete.assert_called_once()
