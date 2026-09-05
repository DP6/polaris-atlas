from datetime import UTC, datetime
from unittest.mock import MagicMock

from atlas.domains.admin import project_admin_repository as repository


def _fake_client_with_subcollection():
    """client.collection("hub_projects").document(project_id)
    .collection("project_admins") — três chamadas encadeadas, mockadas
    uma a uma pra poder configurar o mock antes de chamar o repository."""
    client = MagicMock()
    hub_projects = MagicMock()
    project_doc = MagicMock()
    project_admins = MagicMock()
    client.collection.return_value = hub_projects
    hub_projects.document.return_value = project_doc
    project_doc.collection.return_value = project_admins
    return client, hub_projects, project_doc, project_admins


def _doc(data: dict | None, exists: bool):
    snapshot = MagicMock()
    snapshot.exists = exists
    snapshot.to_dict.return_value = data
    return snapshot


def test_get_project_admin_returns_dict_when_doc_exists():
    client, hub_projects, project_doc, project_admins = _fake_client_with_subcollection()
    doc_ref = MagicMock()
    project_admins.document.return_value = doc_ref
    doc_ref.get.return_value = _doc({"email": "a@dp6.com.br", "datasets": None}, exists=True)

    result = repository.get_project_admin(client, "proj-a", "a@dp6.com.br")

    client.collection.assert_called_once_with("hub_projects")
    hub_projects.document.assert_called_once_with("proj-a")
    project_doc.collection.assert_called_once_with("project_admins")
    project_admins.document.assert_called_once_with("a@dp6.com.br")
    assert result == {"email": "a@dp6.com.br", "datasets": None}


def test_get_project_admin_returns_none_when_doc_missing():
    client, _, _, project_admins = _fake_client_with_subcollection()
    doc_ref = MagicMock()
    project_admins.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(None, exists=False)

    assert repository.get_project_admin(client, "proj-a", "ghost@dp6.com.br") is None


def test_list_project_admins_orders_by_email():
    client, _, _, project_admins = _fake_client_with_subcollection()
    ordered_query = MagicMock()
    project_admins.order_by.return_value = ordered_query
    ordered_query.stream.return_value = [
        _doc({"email": "a@dp6.com.br"}, exists=True),
        _doc({"email": "b@dp6.com.br"}, exists=True),
    ]

    result = repository.list_project_admins(client, "proj-a")

    project_admins.order_by.assert_called_once_with("email")
    assert result == [{"email": "a@dp6.com.br"}, {"email": "b@dp6.com.br"}]


def test_upsert_project_admin_preserves_granted_by_and_granted_at_on_existing():
    client, _, _, project_admins = _fake_client_with_subcollection()
    doc_ref = MagicMock()
    project_admins.document.return_value = doc_ref
    original_granted_at = datetime(2026, 1, 1, tzinfo=UTC)
    doc_ref.get.return_value = _doc(
        {
            "email": "a@dp6.com.br",
            "granted_by": "original-granter@dp6.com.br",
            "granted_at": original_granted_at,
        },
        exists=True,
    )

    result = repository.upsert_project_admin(
        client, "proj-a", "a@dp6.com.br", datasets=["RAW"], granted_by="new-granter@dp6.com.br"
    )

    assert result["granted_by"] == "original-granter@dp6.com.br"
    assert result["granted_at"] == original_granted_at
    assert result["datasets"] == ["RAW"]
    assert isinstance(result["updated_at"], datetime)
    assert result["updated_at"].tzinfo is UTC


def test_upsert_project_admin_sets_granted_by_on_first_grant():
    client, _, _, project_admins = _fake_client_with_subcollection()
    doc_ref = MagicMock()
    project_admins.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(None, exists=False)

    result = repository.upsert_project_admin(
        client, "proj-a", "a@dp6.com.br", datasets=None, granted_by="granter@dp6.com.br"
    )

    assert result["granted_by"] == "granter@dp6.com.br"
    assert result["datasets"] is None


def test_delete_project_admin_calls_document_delete():
    client, _, _, project_admins = _fake_client_with_subcollection()
    doc_ref = MagicMock()
    project_admins.document.return_value = doc_ref

    repository.delete_project_admin(client, "proj-a", "a@dp6.com.br")

    project_admins.document.assert_called_once_with("a@dp6.com.br")
    doc_ref.delete.assert_called_once()
