from datetime import UTC, datetime
from unittest.mock import MagicMock

from google.api_core.exceptions import NotFound

from atlas.domains.metadata import repository


def _fake_client_with_subcollection():
    """client.collection("hub_projects").document(project_id)
    .collection("metadata_tables") — mesma técnica de
    tests/unit/admin/test_project_admin_repository.py."""
    client = MagicMock()
    hub_projects = MagicMock()
    project_doc = MagicMock()
    metadata_tables = MagicMock()
    client.collection.return_value = hub_projects
    hub_projects.document.return_value = project_doc
    project_doc.collection.return_value = metadata_tables
    return client, metadata_tables


def _doc(data: dict | None, exists: bool):
    snapshot = MagicMock()
    snapshot.exists = exists
    snapshot.to_dict.return_value = data
    return snapshot


# --- get_table_metadata / upsert_table_metadata ---------------------------------


def test_get_table_metadata_returns_none_when_doc_missing():
    client, metadata_tables = _fake_client_with_subcollection()
    doc_ref = MagicMock()
    metadata_tables.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(None, exists=False)

    assert repository.get_table_metadata(client, "proj-a", "RAW", "ga4_events") is None
    metadata_tables.document.assert_called_once_with("RAW__ga4_events")


def test_upsert_table_metadata_preserves_created_at_and_untouched_fields():
    client, metadata_tables = _fake_client_with_subcollection()
    doc_ref = MagicMock()
    metadata_tables.document.return_value = doc_ref
    original_created_at = datetime(2026, 1, 1, tzinfo=UTC)
    doc_ref.get.return_value = _doc(
        {
            "description": "old description",
            "owner": {"technical_owner": "a@dp6.com.br"},
            "created_at": original_created_at,
            "columns": {"col_a": {"description": "col desc"}},
        },
        exists=True,
    )

    result = repository.upsert_table_metadata(
        client, "proj-a", "RAW", "ga4_events", {"description": "new description"}, "b@dp6.com.br"
    )

    assert result["description"] == "new description"
    assert result["owner"] == {"technical_owner": "a@dp6.com.br"}  # não tocado
    assert result["columns"] == {"col_a": {"description": "col desc"}}  # não tocado
    assert result["created_at"] == original_created_at
    assert result["updated_by"] == "b@dp6.com.br"


def test_upsert_table_metadata_explicit_none_clears_field():
    client, metadata_tables = _fake_client_with_subcollection()
    doc_ref = MagicMock()
    metadata_tables.document.return_value = doc_ref
    doc_ref.get.return_value = _doc({"description": "old"}, exists=True)

    result = repository.upsert_table_metadata(
        client, "proj-a", "RAW", "ga4_events", {"description": None}, "a@dp6.com.br"
    )

    assert result["description"] is None


# --- upsert_column_metadata -------------------------------------------------------


def test_upsert_column_metadata_adds_new_column_without_touching_others():
    client, metadata_tables = _fake_client_with_subcollection()
    doc_ref = MagicMock()
    metadata_tables.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(
        {"description": "table desc", "columns": {"col_a": {"description": "existing"}}},
        exists=True,
    )

    result = repository.upsert_column_metadata(
        client, "proj-a", "RAW", "ga4_events", "col_b", {"description": "new col"}, "a@dp6.com.br"
    )

    assert result["columns"]["col_a"] == {"description": "existing"}
    assert result["columns"]["col_b"] == {"description": "new col"}
    assert result["description"] == "table desc"


def test_upsert_column_metadata_merges_into_existing_column():
    client, metadata_tables = _fake_client_with_subcollection()
    doc_ref = MagicMock()
    metadata_tables.document.return_value = doc_ref
    doc_ref.get.return_value = _doc(
        {"columns": {"col_a": {"description": "old desc", "glossary_term": "Term"}}}, exists=True
    )

    result = repository.upsert_column_metadata(
        client, "proj-a", "RAW", "ga4_events", "col_a", {"description": "new desc"}, "a@dp6.com.br"
    )

    assert result["columns"]["col_a"]["description"] == "new desc"
    assert result["columns"]["col_a"]["glossary_term"] == "Term"  # preservado


# --- history ------------------------------------------------------------------


def test_add_history_entry_and_list_history():
    client, metadata_tables = _fake_client_with_subcollection()
    doc_ref = MagicMock()
    metadata_tables.document.return_value = doc_ref
    history_collection = MagicMock()
    doc_ref.collection.return_value = history_collection

    repository.add_history_entry(
        client, "proj-a", "RAW", "ga4_events", "description", "old", "new", "a@dp6.com.br"
    )

    doc_ref.collection.assert_called_once_with("history")
    history_collection.add.assert_called_once()
    added = history_collection.add.call_args[0][0]
    assert added["field"] == "description"
    assert added["old_value"] == "old"
    assert added["new_value"] == "new"
    assert added["changed_by"] == "a@dp6.com.br"


def test_list_history_orders_by_changed_at_desc():
    client, metadata_tables = _fake_client_with_subcollection()
    doc_ref = MagicMock()
    metadata_tables.document.return_value = doc_ref
    history_collection = MagicMock()
    doc_ref.collection.return_value = history_collection
    ordered_query = MagicMock()
    history_collection.order_by.return_value = ordered_query
    ordered_query.stream.return_value = [
        _doc({"field": "description", "changed_at": datetime(2026, 1, 2, tzinfo=UTC)}, exists=True)
    ]

    result = repository.list_history(client, "proj-a", "RAW", "ga4_events")

    assert len(result) == 1
    assert result[0]["field"] == "description"


# --- PII (read-only) ------------------------------------------------------------


def test_get_latest_pii_scan_returns_none_when_never_scanned():
    client, _ = _fake_client_with_subcollection()
    pii_history = MagicMock()
    table_doc = MagicMock()
    scans = MagicMock()
    client.collection.side_effect = lambda name: {
        "hub_projects": MagicMock(),
        "pii_scan_history": pii_history,
    }[name]
    pii_history.document.return_value = table_doc
    table_doc.collection.return_value = scans
    ordered_query = MagicMock()
    scans.order_by.return_value = ordered_query
    limited_query = MagicMock()
    ordered_query.limit.return_value = limited_query
    limited_query.stream.return_value = []

    result = repository.get_latest_pii_scan(client, "proj-a", "RAW", "ga4_events")

    assert result is None
    pii_history.document.assert_called_once_with("proj-a_RAW_ga4_events")


def test_get_latest_pii_scan_returns_most_recent():
    client, _ = _fake_client_with_subcollection()
    pii_history = MagicMock()
    table_doc = MagicMock()
    scans = MagicMock()
    client.collection.side_effect = lambda name: {
        "hub_projects": MagicMock(),
        "pii_scan_history": pii_history,
    }[name]
    pii_history.document.return_value = table_doc
    table_doc.collection.return_value = scans
    ordered_query = MagicMock()
    scans.order_by.return_value = ordered_query
    limited_query = MagicMock()
    ordered_query.limit.return_value = limited_query
    limited_query.stream.return_value = [_doc({"columns": [{"column_name": "email"}]}, exists=True)]

    result = repository.get_latest_pii_scan(client, "proj-a", "RAW", "ga4_events")

    assert result == {"columns": [{"column_name": "email"}]}


# --- enumeração via BigQuery ------------------------------------------------------


def test_get_column_names_returns_none_when_table_not_found():
    bq_client = MagicMock()
    bq_client.get_table.side_effect = NotFound("gone")

    result = repository.get_column_names(bq_client, "proj-a", "RAW", "ghost")

    assert result is None


def test_get_column_names_returns_schema_field_names():
    bq_client = MagicMock()
    field_a = MagicMock()
    field_a.name = "col_a"
    field_b = MagicMock()
    field_b.name = "col_b"
    bq_table = MagicMock()
    bq_table.schema = [field_a, field_b]
    bq_client.get_table.return_value = bq_table

    result = repository.get_column_names(bq_client, "proj-a", "RAW", "ga4_events")

    assert result == ["col_a", "col_b"]
