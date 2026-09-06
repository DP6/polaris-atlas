from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from atlas.core.exceptions import ColumnNotFoundError, InvalidStatusTransitionError
from atlas.domains.metadata import service
from atlas.domains.metadata.schemas import (
    MetadataColumnUpsertRequest,
    MetadataStatusUpdateRequest,
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
    assert result.status is None


def test_get_table_metadata_builds_nested_objects(monkeypatch):
    raw = {
        "description": "desc",
        "owner": {"technical_owner": "a@dp6.com.br", "team": None},
        "classification": {"domain": "e-commerce", "sensitivity": "confidencial"},
        "status": "approved",
        "status_changed_by": "b@dp6.com.br",
        "status_changed_at": datetime(2026, 1, 2, tzinfo=UTC),
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
    assert result.status == "approved"
    assert result.status_changed_by == "b@dp6.com.br"


def test_get_table_metadata_ignores_legacy_steward_key(monkeypatch):
    # Docs gravados antes da v2.0 têm `steward` no owner — Pydantic ignora
    # o campo extra, não quebra a leitura.
    raw = {"owner": {"technical_owner": "a@dp6.com.br", "steward": "old@dp6.com.br", "team": "X"}}
    monkeypatch.setattr(service.repository, "get_table_metadata", lambda client, p, d, t: raw)

    result = service.get_table_metadata(_fake_client(), "proj-a", "RAW", "ga4_events")

    assert result.owner.technical_owner == "a@dp6.com.br"
    assert result.owner.team == "X"
    assert not hasattr(result.owner, "steward")


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
        lambda client, p, d, t: {
            "description": "old",
            "owner": {"technical_owner": "a@dp6.com.br"},
        },
    )
    monkeypatch.setattr(
        service.repository, "add_history_entry", lambda *a, **k: history_calls.append(k)
    )
    monkeypatch.setattr(
        service.repository, "upsert_table_metadata", lambda client, p, d, t, fields, by: fields
    )

    request = MetadataTableUpsertRequest(
        description="new", owner={"technical_owner": "b@dp6.com.br", "team": None}
    )
    service.upsert_table_metadata(
        _fake_client(), "proj-a", "RAW", "ga4_events", request, "a@dp6.com.br"
    )

    fields_changed = {c["field"] for c in history_calls}
    assert fields_changed == {"description", "owner"}


def test_upsert_table_metadata_ignores_status_field(monkeypatch):
    # `status` foi removido do request de campos — muda só por update_status.
    captured = {}
    monkeypatch.setattr(service.repository, "get_table_metadata", lambda client, p, d, t: {})
    monkeypatch.setattr(service.repository, "add_history_entry", lambda *a, **k: None)

    def fake_upsert(client, p, d, t, fields, by):
        captured["fields"] = fields
        return fields

    monkeypatch.setattr(service.repository, "upsert_table_metadata", fake_upsert)

    request = MetadataTableUpsertRequest.model_validate({"description": "x", "status": "approved"})
    service.upsert_table_metadata(
        _fake_client(), "proj-a", "RAW", "ga4_events", request, "a@dp6.com.br"
    )

    assert "status" not in captured["fields"]


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


# --- update_status (fluxo de revisão) ------------------------------------------


def _stub_status_repo(monkeypatch, *, current):
    calls = {"history": [], "set_status": []}
    monkeypatch.setattr(
        service.repository,
        "get_table_metadata",
        lambda client, p, d, t: {"status": current} if current is not None else {},
    )
    monkeypatch.setattr(
        service.repository,
        "add_history_entry",
        lambda *a, **k: calls["history"].append(k),
    )

    def fake_set_status(client, p, d, t, *, status, changed_by, review_note):
        calls["set_status"].append(
            {"status": status, "changed_by": changed_by, "review_note": review_note}
        )
        return {"status": status, "status_changed_by": changed_by, "review_note": review_note}

    monkeypatch.setattr(service.repository, "set_status", fake_set_status)
    return calls


def test_update_status_project_admin_submits_for_review(monkeypatch):
    calls = _stub_status_repo(monkeypatch, current="draft")

    result = service.update_status(
        _fake_client(),
        "proj-a",
        "RAW",
        "ga4_events",
        MetadataStatusUpdateRequest(target="in_review"),
        actor="a@dp6.com.br",
        is_superadmin=False,
    )

    assert result.status == "in_review"
    assert calls["set_status"][0]["status"] == "in_review"
    assert calls["history"][0]["field"] == "status"
    assert calls["history"][0]["new_value"] == "in_review"


def test_update_status_project_admin_can_approve_from_in_review(monkeypatch):
    calls = _stub_status_repo(monkeypatch, current="in_review")

    result = service.update_status(
        _fake_client(),
        "proj-a",
        "RAW",
        "ga4_events",
        MetadataStatusUpdateRequest(target="approved"),
        actor="a@dp6.com.br",
        is_superadmin=False,
    )

    assert result.status == "approved"
    assert calls["set_status"][0]["review_note"] is None


def test_update_status_project_admin_cannot_skip_straight_to_approved(monkeypatch):
    _stub_status_repo(monkeypatch, current="draft")

    with pytest.raises(InvalidStatusTransitionError):
        service.update_status(
            _fake_client(),
            "proj-a",
            "RAW",
            "ga4_events",
            MetadataStatusUpdateRequest(target="approved"),
            actor="a@dp6.com.br",
            is_superadmin=False,
        )


def test_update_status_return_for_changes_keeps_note(monkeypatch):
    calls = _stub_status_repo(monkeypatch, current="in_review")

    service.update_status(
        _fake_client(),
        "proj-a",
        "RAW",
        "ga4_events",
        MetadataStatusUpdateRequest(target="draft", note="faltou o dono técnico"),
        actor="rev@dp6.com.br",
        is_superadmin=False,
    )

    assert calls["set_status"][0]["review_note"] == "faltou o dono técnico"
    assert calls["history"][0]["note"] == "faltou o dono técnico"


def test_update_status_superadmin_submit_auto_approves(monkeypatch):
    calls = _stub_status_repo(monkeypatch, current="draft")

    result = service.update_status(
        _fake_client(),
        "proj-a",
        "RAW",
        "ga4_events",
        MetadataStatusUpdateRequest(target="in_review"),
        actor="super@dp6.com.br",
        is_superadmin=True,
    )

    assert result.status == "approved"
    assert calls["set_status"][0]["status"] == "approved"
    assert calls["history"][0]["new_value"] == "approved"


def test_update_status_noop_when_already_at_target(monkeypatch):
    calls = _stub_status_repo(monkeypatch, current="approved")

    service.update_status(
        _fake_client(),
        "proj-a",
        "RAW",
        "ga4_events",
        MetadataStatusUpdateRequest(target="approved"),
        actor="a@dp6.com.br",
        is_superadmin=False,
    )

    assert calls["history"] == []
    assert calls["set_status"] == []


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
    monkeypatch.setattr(service.repository, "get_table_metadata", lambda *a, **k: None)
    monkeypatch.setattr(service.repository, "add_history_entry", lambda *a, **k: None)
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
    monkeypatch.setattr(service.repository, "get_table_metadata", lambda *a, **k: None)
    monkeypatch.setattr(service.repository, "add_history_entry", lambda *a, **k: None)
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
    monkeypatch.setattr(service.repository, "get_table_metadata", lambda *a, **k: None)
    monkeypatch.setattr(service.repository, "add_history_entry", lambda *a, **k: None)

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


def test_upsert_column_metadata_writes_history_for_changed_column_fields(monkeypatch):
    history_calls = []
    monkeypatch.setattr(service.repository, "get_column_names", lambda *a, **k: ["email"])
    monkeypatch.setattr(
        service.repository,
        "get_table_metadata",
        lambda *a, **k: {"columns": {"email": {"description": "antigo", "pii": {"flag": False}}}},
    )
    monkeypatch.setattr(service.repository, "get_latest_pii_scan", lambda *a, **k: None)
    monkeypatch.setattr(
        service.repository, "add_history_entry", lambda *a, **k: history_calls.append(k)
    )
    monkeypatch.setattr(
        service.repository,
        "upsert_column_metadata",
        lambda client, p, d, t, column_name, fields, by: {"columns": {column_name: fields}},
    )

    request = MetadataColumnUpsertRequest(description="novo", pii_flag=True)
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

    by_field = {c["field"]: c for c in history_calls}
    assert set(by_field) == {"description", "pii_flag"}
    assert by_field["description"]["column_name"] == "email"
    assert by_field["description"]["old_value"] == "antigo"
    assert by_field["pii_flag"]["old_value"] == "False"
    assert by_field["pii_flag"]["new_value"] == "True"


def test_upsert_column_metadata_skips_history_when_column_field_unchanged(monkeypatch):
    history_calls = []
    monkeypatch.setattr(service.repository, "get_column_names", lambda *a, **k: ["email"])
    monkeypatch.setattr(
        service.repository,
        "get_table_metadata",
        lambda *a, **k: {"columns": {"email": {"description": "igual"}}},
    )
    monkeypatch.setattr(
        service.repository, "add_history_entry", lambda *a, **k: history_calls.append(k)
    )
    monkeypatch.setattr(
        service.repository,
        "upsert_column_metadata",
        lambda client, p, d, t, column_name, fields, by: {},
    )

    request = MetadataColumnUpsertRequest(description="igual")
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

    assert history_calls == []


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
            return {"status": "approved"}
        return None

    monkeypatch.setattr(service.repository, "get_table_metadata", fake_get_metadata)

    result = service.get_metadata_overview(_fake_client(), _fake_client(), "proj-a")

    assert result.total_tables == 2
    assert result.documented_count == 1
    table_ids = {t.table_id: t.has_metadata for t in result.tables}
    assert table_ids == {"documented": True, "undocumented": False}


def test_get_metadata_overview_filters_by_status(monkeypatch):
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["us"])
    monkeypatch.setattr(
        service.repository,
        "list_all_table_refs",
        lambda client, project_id, regions: [("RAW", "a"), ("RAW", "b")],
    )

    def fake_get_metadata(client, project_id, dataset_id, table_id):
        return {"status": "approved" if table_id == "a" else "draft"}

    monkeypatch.setattr(service.repository, "get_table_metadata", fake_get_metadata)

    result = service.get_metadata_overview(
        _fake_client(), _fake_client(), "proj-a", status="approved"
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
