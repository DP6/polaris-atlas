from unittest.mock import MagicMock

from google.api_core.exceptions import Forbidden, NotFound

from observability_hub.domains.admin import checklist_service


def _items_by_name(response):
    return {item.item: item for item in response.items}


def test_check_project_checklist_all_ok(monkeypatch):
    monkeypatch.setattr(checklist_service, "discover_regions", lambda project_id, client: ["US"])
    logging_client = MagicMock()
    logging_client.list_entries.return_value = []
    storage_client = MagicMock()
    storage_client.list_buckets.return_value = []

    result = checklist_service.check_project_checklist(
        MagicMock(), logging_client, storage_client, "proj-a"
    )

    items = _items_by_name(result)
    assert items["bigquery"].status == "ok"
    assert items["logging"].status == "ok"
    assert items["storage"].status == "ok"
    assert items["audit_logs"].status == "not_checked"
    assert result.project_id == "proj-a"


def test_check_project_checklist_bigquery_denied(monkeypatch):
    from observability_hub.core.exceptions import ProjectAccessDeniedError

    def _raise(project_id, client):
        raise ProjectAccessDeniedError(project_id)

    monkeypatch.setattr(checklist_service, "discover_regions", _raise)
    logging_client = MagicMock()
    logging_client.list_entries.return_value = []
    storage_client = MagicMock()
    storage_client.list_buckets.return_value = []

    result = checklist_service.check_project_checklist(
        MagicMock(), logging_client, storage_client, "proj-a"
    )

    assert _items_by_name(result)["bigquery"].status == "denied"


def test_check_project_checklist_bigquery_not_found(monkeypatch):
    from observability_hub.core.exceptions import ProjectNotFoundError

    def _raise(project_id, client):
        raise ProjectNotFoundError(project_id)

    monkeypatch.setattr(checklist_service, "discover_regions", _raise)
    logging_client = MagicMock()
    logging_client.list_entries.return_value = []
    storage_client = MagicMock()
    storage_client.list_buckets.return_value = []

    result = checklist_service.check_project_checklist(
        MagicMock(), logging_client, storage_client, "proj-a"
    )

    assert _items_by_name(result)["bigquery"].status == "not_found"


def test_check_project_checklist_logging_denied(monkeypatch):
    monkeypatch.setattr(checklist_service, "discover_regions", lambda project_id, client: ["US"])
    logging_client = MagicMock()
    logging_client.list_entries.side_effect = Forbidden("denied")
    storage_client = MagicMock()
    storage_client.list_buckets.return_value = []

    result = checklist_service.check_project_checklist(
        MagicMock(), logging_client, storage_client, "proj-a"
    )

    assert _items_by_name(result)["logging"].status == "denied"


def test_check_project_checklist_logging_not_found(monkeypatch):
    monkeypatch.setattr(checklist_service, "discover_regions", lambda project_id, client: ["US"])
    logging_client = MagicMock()
    logging_client.list_entries.side_effect = NotFound("missing")
    storage_client = MagicMock()
    storage_client.list_buckets.return_value = []

    result = checklist_service.check_project_checklist(
        MagicMock(), logging_client, storage_client, "proj-a"
    )

    assert _items_by_name(result)["logging"].status == "not_found"


def test_check_project_checklist_storage_denied(monkeypatch):
    monkeypatch.setattr(checklist_service, "discover_regions", lambda project_id, client: ["US"])
    logging_client = MagicMock()
    logging_client.list_entries.return_value = []
    storage_client = MagicMock()
    storage_client.list_buckets.side_effect = Forbidden("denied")

    result = checklist_service.check_project_checklist(
        MagicMock(), logging_client, storage_client, "proj-a"
    )

    assert _items_by_name(result)["storage"].status == "denied"


def test_check_project_checklist_audit_logs_always_not_checked_with_command_detail(monkeypatch):
    monkeypatch.setattr(checklist_service, "discover_regions", lambda project_id, client: ["US"])
    logging_client = MagicMock()
    logging_client.list_entries.return_value = []
    storage_client = MagicMock()
    storage_client.list_buckets.return_value = []

    result = checklist_service.check_project_checklist(
        MagicMock(), logging_client, storage_client, "proj-a"
    )

    audit_item = _items_by_name(result)["audit_logs"]
    assert audit_item.status == "not_checked"
    assert "proj-a" in audit_item.detail
    assert "get-iam-policy" in audit_item.detail
