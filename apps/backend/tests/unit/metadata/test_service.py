from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from observability_hub.core.exceptions import ColumnNotFoundError
from observability_hub.domains.metadata import service
from observability_hub.domains.metadata.schemas import (
    MetadataColumnUpsertRequest,
    MetadataTableUpsertRequest,
)


def _fake_client() -> MagicMock:
    return MagicMock(name="client")


# --- get_table_metadata ----------------------------------------------------------


def test_get_table_metadata_returns_has_metadata_false_when_undocumented(monkeypatch):
    monkeypatch.setattr(service.repository, "get_table_metadata", lambda client, p, d, t: None)

    result = service.get_table_metadata(_fake_client(), "proj-a", "RAW", "ga4_events")

    assert result.has_metadata is False
    assert result.description is None
    assert result.columns == {}


def test_get_table_metadata_builds_nested_objects(monkeypatch):
    raw = {
        "description": "desc",
        "owner": {"technical_owner": "a@dp6.com.br", "steward": None, "team": None},
        "classification": {"domain": "e-commerce", "sensitivity": "confidencial"},
        "certification_status": "approved",
        "related_links": [{"label": "Runbook", "url": "https://x"}],
        "columns": {"col_a": {"description": "c", "glossary_term": None, "pii": None}},
        "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_by": "a@dp6.com.br",
    }
    monkeypatch.setattr(service.repository, "get_table_metadata", lambda client, p, d, t: raw)

    result = service.get_table_metadata(_fake_client(), "proj-a", "RAW", "ga4_events")

    assert result.has_metadata is True
    assert result.owner.technical_owner == "a@dp6.com.br"
    assert result.classification.sensitivity == "confidencial"
    assert result.related_links[0].url == "https://x"
    assert "col_a" in result.columns


# --- upsert_table_metadata (patch parcial + histórico) ----------------------------


def test_upsert_table_metadata_partial_update_only_sends_provided_fields(monkeypatch):
    captured = {}
    monkeypatch.setattr(service.repository, "get_table_metadata", lambda client, p, d, t: {})
    monkeypatch.setattr(service.repository, "add_history_entry", lambda *a, **k: None)

    def fake_upsert(client, project_id, dataset_id, table_id, fields, updated_by):
        captured["fields"] = fields
        return {**fields, "updated_by": updated_by}

    monkeypatch.setattr(service.repository, "upsert_table_metadata", fake_upsert)

    request = MetadataTableUpsertRequest(description="new description")
    service.upsert_table_metadata(
        _fake_client(), "proj-a", "RAW", "ga4_events", request, "a@dp6.com.br"
    )

    assert captured["fields"] == {"description": "new description"}


def test_upsert_table_metadata_writes_history_entry_per_changed_field(monkeypatch):
    history_calls = []
    monkeypatch.setattr(
        service.repository,
        "get_table_metadata",
        lambda client, p, d, t: {"description": "old", "certification_status": "draft"},
    )
    monkeypatch.setattr(
        service.repository, "add_history_entry", lambda *a, **k: history_calls.append(k)
    )
    monkeypatch.setattr(
        service.repository, "upsert_table_metadata", lambda client, p, d, t, fields, by: fields
    )

    request = MetadataTableUpsertRequest(description="new", certification_status="approved")
    service.upsert_table_metadata(
        _fake_client(), "proj-a", "RAW", "ga4_events", request, "a@dp6.com.br"
    )

    fields_changed = {c["field"] for c in history_calls}
    assert fields_changed == {"description", "certification_status"}


def test_upsert_table_metadata_skips_history_when_value_unchanged(monkeypatch):
    history_calls = []
    monkeypatch.setattr(
        service.repository, "get_table_metadata", lambda client, p, d, t: {"description": "same"}
    )
    monkeypatch.setattr(
        service.repository, "add_history_entry", lambda *a, **k: history_calls.append(k)
    )
    monkeypatch.setattr(
        service.repository, "upsert_table_metadata", lambda client, p, d, t, fields, by: fields
    )

    request = MetadataTableUpsertRequest(description="same")
    service.upsert_table_metadata(
        _fake_client(), "proj-a", "RAW", "ga4_events", request, "a@dp6.com.br"
    )

    assert history_calls == []


# --- upsert_column_metadata --------------------------------------------------------


def test_upsert_column_metadata_404_when_column_missing_from_real_table(monkeypatch):
    monkeypatch.setattr(service.repository, "get_column_names", lambda *a, **k: ["col_a"])

    request = MetadataColumnUpsertRequest(description="x")
    with pytest.raises(ColumnNotFoundError):
        service.upsert_column_metadata(
            _fake_client(),
            _fake_client(),
            "proj-a",
            "RAW",
            "ga4_events",
            "col_ghost",
            request,
            "a@dp6.com.br",
        )


def test_upsert_column_metadata_404_when_table_not_found(monkeypatch):
    monkeypatch.setattr(service.repository, "get_column_names", lambda *a, **k: None)

    request = MetadataColumnUpsertRequest(description="x")
    with pytest.raises(ColumnNotFoundError):
        service.upsert_column_metadata(
            _fake_client(),
            _fake_client(),
            "proj-a",
            "RAW",
            "ghost_table",
            "col_a",
            request,
            "a@dp6.com.br",
        )


def test_upsert_column_metadata_pii_flag_always_records_manual_confirmation(monkeypatch):
    captured = {}
    monkeypatch.setattr(service.repository, "get_column_names", lambda *a, **k: ["email"])
    monkeypatch.setattr(
        service.repository,
        "get_latest_pii_scan",
        lambda *a, **k: {
            "columns": [{"column_name": "email", "flagged": True, "confidence": "high"}]
        },
    )

    def fake_upsert(client, p, d, t, column_name, fields, by):
        captured["fields"] = fields
        return {"columns": {column_name: fields}}

    monkeypatch.setattr(service.repository, "upsert_column_metadata", fake_upsert)

    # Confirma exatamente o que o scanner já disse (flag=True, mesmo que scanner_flagged=True)
    request = MetadataColumnUpsertRequest(pii_flag=True)
    service.upsert_column_metadata(
        _fake_client(),
        _fake_client(),
        "proj-a",
        "RAW",
        "ga4_events",
        "email",
        request,
        "a@dp6.com.br",
    )

    pii = captured["fields"]["pii"]
    assert pii["flag"] is True
    assert pii["source"] == "manual"
    assert pii["scanner_flagged"] is True
    assert pii["scanner_confidence"] == "high"
    assert pii["confirmed_by"] == "a@dp6.com.br"
    assert pii["confirmed_at"] is not None


def test_upsert_column_metadata_pii_flag_never_scanned_leaves_scanner_fields_none(monkeypatch):
    captured = {}
    monkeypatch.setattr(service.repository, "get_column_names", lambda *a, **k: ["email"])
    monkeypatch.setattr(service.repository, "get_latest_pii_scan", lambda *a, **k: None)

    def fake_upsert(client, p, d, t, column_name, fields, by):
        captured["fields"] = fields
        return {"columns": {column_name: fields}}

    monkeypatch.setattr(service.repository, "upsert_column_metadata", fake_upsert)

    request = MetadataColumnUpsertRequest(pii_flag=True)
    service.upsert_column_metadata(
        _fake_client(),
        _fake_client(),
        "proj-a",
        "RAW",
        "ga4_events",
        "email",
        request,
        "a@dp6.com.br",
    )

    pii = captured["fields"]["pii"]
    assert pii["scanner_flagged"] is None
    assert pii["scanner_confidence"] is None


def test_upsert_column_metadata_description_only_does_not_touch_pii(monkeypatch):
    captured = {}
    monkeypatch.setattr(service.repository, "get_column_names", lambda *a, **k: ["email"])

    def fake_upsert(client, p, d, t, column_name, fields, by):
        captured["fields"] = fields
        return {}

    monkeypatch.setattr(service.repository, "upsert_column_metadata", fake_upsert)

    request = MetadataColumnUpsertRequest(description="only description")
    service.upsert_column_metadata(
        _fake_client(),
        _fake_client(),
        "proj-a",
        "RAW",
        "ga4_events",
        "email",
        request,
        "a@dp6.com.br",
    )

    assert captured["fields"] == {"description": "only description"}


# --- get_suggested_pii -------------------------------------------------------------


def test_get_suggested_pii_never_scanned(monkeypatch):
    monkeypatch.setattr(service.repository, "get_latest_pii_scan", lambda *a, **k: None)

    result = service.get_suggested_pii(_fake_client(), "proj-a", "RAW", "ga4_events")

    assert result.scanned is False
    assert result.columns == []


def test_get_suggested_pii_returns_latest_scan_columns(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_latest_pii_scan",
        lambda *a, **k: {
            "columns": [
                {"column_name": "email", "flagged": True, "confidence": "high"},
                {"column_name": "id", "flagged": False, "confidence": None},
            ]
        },
    )

    result = service.get_suggested_pii(_fake_client(), "proj-a", "RAW", "ga4_events")

    assert result.scanned is True
    assert len(result.columns) == 2
    assert result.columns[0].column_name == "email"
    assert result.columns[0].flagged is True


# --- get_metadata_overview ----------------------------------------------------------


def test_get_metadata_overview_includes_undocumented_tables(monkeypatch):
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["us"])
    monkeypatch.setattr(
        service.repository,
        "list_all_table_refs",
        lambda client, project_id, regions: [("RAW", "documented"), ("RAW", "undocumented")],
    )

    def fake_get_metadata(client, project_id, dataset_id, table_id):
        if table_id == "documented":
            return {"certification_status": "approved"}
        return None

    monkeypatch.setattr(service.repository, "get_table_metadata", fake_get_metadata)

    result = service.get_metadata_overview(_fake_client(), _fake_client(), "proj-a")

    assert result.total_tables == 2
    assert result.documented_count == 1
    table_ids = {t.table_id: t.has_metadata for t in result.tables}
    assert table_ids == {"documented": True, "undocumented": False}


def test_get_metadata_overview_filters_by_certification_status(monkeypatch):
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["us"])
    monkeypatch.setattr(
        service.repository,
        "list_all_table_refs",
        lambda client, project_id, regions: [("RAW", "a"), ("RAW", "b")],
    )

    def fake_get_metadata(client, project_id, dataset_id, table_id):
        return {"certification_status": "approved" if table_id == "a" else "draft"}

    monkeypatch.setattr(service.repository, "get_table_metadata", fake_get_metadata)

    result = service.get_metadata_overview(
        _fake_client(), _fake_client(), "proj-a", certification_status="approved"
    )

    assert [t.table_id for t in result.tables] == ["a"]


def test_get_metadata_overview_filters_by_dataset(monkeypatch):
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["us"])
    monkeypatch.setattr(
        service.repository,
        "list_all_table_refs",
        lambda client, project_id, regions: [("RAW", "a"), ("TRUSTED", "b")],
    )
    monkeypatch.setattr(service.repository, "get_table_metadata", lambda *a, **k: None)

    result = service.get_metadata_overview(
        _fake_client(), _fake_client(), "proj-a", datasets=["TRUSTED"]
    )

    assert [t.dataset_id for t in result.tables] == ["TRUSTED"]
