from datetime import UTC, datetime
from unittest.mock import MagicMock

from google.cloud import firestore

from observability_hub.domains.budget import repository
from observability_hub.domains.budget.schemas import BudgetScope


def _fake_client_with_collection():
    """client.collection("hub_projects").document(project_id)
    .collection("budgets") -> MagicMock capturável (mesmo padrão de
    tests/unit/admin/test_project_admin_repository.py)."""
    client = MagicMock()
    hub_projects = MagicMock()
    project_doc = MagicMock()
    budgets_collection = MagicMock()

    client.collection.return_value = hub_projects
    hub_projects.document.return_value = project_doc
    project_doc.collection.return_value = budgets_collection

    return client, budgets_collection


def _doc(data: dict | None, exists: bool = True) -> MagicMock:
    snapshot = MagicMock()
    snapshot.exists = exists
    snapshot.to_dict.return_value = data
    return snapshot


def test_budget_doc_id_project_scope_is_fixed_segment():
    assert repository._budget_doc_id(BudgetScope.PROJECT) == "_project"


def test_budget_doc_id_dataset_scope_is_dataset_id():
    assert repository._budget_doc_id(BudgetScope.DATASET, "RAW") == "RAW"


def test_budget_doc_id_table_scope_has_two_segments():
    assert repository._budget_doc_id(BudgetScope.TABLE, "RAW", "events") == "RAW__events"


def test_list_budgets_orders_desc_no_in_memory_filter_needed():
    client, budgets_collection = _fake_client_with_collection()
    ordered_query = MagicMock()
    budgets_collection.order_by.return_value = ordered_query
    ordered_query.stream.return_value = [
        _doc({"scope": "project", "amount_usd": 100.0}),
        _doc({"scope": "dataset", "dataset_id": "RAW", "amount_usd": 20.0}),
    ]

    result = repository.list_budgets(client, "proj")

    client.collection.assert_called_once_with("hub_projects")
    budgets_collection.order_by.assert_called_once_with(
        "updated_at", direction=firestore.Query.DESCENDING
    )
    assert [b["amount_usd"] for b in result] == [100.0, 20.0]


def test_upsert_budget_new_sets_created_and_updated_timestamps():
    client, budgets_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    budgets_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(None, exists=False)

    result = repository.upsert_budget(client, "proj", BudgetScope.PROJECT, 300.0, "a@dp6.com.br")

    budgets_collection.document.assert_called_once_with("_project")
    doc_ref.set.assert_called_once()
    set_data = doc_ref.set.call_args[0][0]
    assert set_data["scope"] == "project"
    assert set_data["dataset_id"] is None
    assert set_data["table_id"] is None
    assert set_data["amount_usd"] == 300.0
    assert set_data["period"] == "month"
    assert set_data["created_by"] == "a@dp6.com.br"
    assert set_data["updated_by"] == "a@dp6.com.br"
    assert isinstance(set_data["created_at"], datetime)
    assert set_data["created_at"].tzinfo is UTC
    assert set_data["updated_at"] >= set_data["created_at"]
    assert result == set_data


def test_upsert_budget_preserves_created_at_and_created_by_on_repeat_but_updates_updated_by():
    client, budgets_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    budgets_collection.document.return_value = doc_ref
    original_created_at = datetime(2026, 1, 1, tzinfo=UTC)
    doc_ref.get.return_value = _doc(
        {
            "scope": "project",
            "dataset_id": None,
            "table_id": None,
            "amount_usd": 100.0,
            "period": "month",
            "created_by": "primeiro-admin@dp6.com.br",
            "created_at": original_created_at,
            "updated_at": original_created_at,
            "updated_by": "primeiro-admin@dp6.com.br",
        },
        exists=True,
    )

    result = repository.upsert_budget(
        client, "proj", BudgetScope.PROJECT, 500.0, "segundo-admin@dp6.com.br"
    )

    assert result["created_at"] == original_created_at
    assert result["created_by"] == "primeiro-admin@dp6.com.br"  # preservado
    assert result["updated_by"] == "segundo-admin@dp6.com.br"  # muda a cada edição
    assert result["amount_usd"] == 500.0
    assert result["updated_at"] > original_created_at


def test_upsert_budget_dataset_scope_uses_dataset_id_as_doc_id():
    client, budgets_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    budgets_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(None, exists=False)

    result = repository.upsert_budget(
        client, "proj", BudgetScope.DATASET, 40.0, "a@dp6.com.br", dataset_id="RAW"
    )

    budgets_collection.document.assert_called_once_with("RAW")
    assert result["dataset_id"] == "RAW"
    assert result["table_id"] is None


def test_remove_budget_table_scope_deletes_two_segment_doc_id():
    client, budgets_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    budgets_collection.document.return_value = doc_ref

    repository.remove_budget(client, "proj", BudgetScope.TABLE, dataset_id="RAW", table_id="events")

    budgets_collection.document.assert_called_once_with("RAW__events")
    doc_ref.delete.assert_called_once()


def test_get_project_budget_amount_returns_float_when_present():
    client, budgets_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    budgets_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc({"amount_usd": 250}, exists=True)

    assert repository.get_project_budget_amount(client, "proj") == 250.0
    budgets_collection.document.assert_called_once_with("_project")


def test_get_project_budget_amount_returns_none_when_missing():
    client, budgets_collection = _fake_client_with_collection()
    doc_ref = MagicMock()
    budgets_collection.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(None, exists=False)

    assert repository.get_project_budget_amount(client, "proj") is None
