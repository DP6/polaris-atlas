from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from google.api_core.exceptions import NotFound

from observability_hub.core.exceptions import LoggingAccessDeniedError, LoggingQuotaExceededError
from observability_hub.jobs import refresh_event_cache


def _event(job_id="j1", ts=None):
    """Stand-in mínimo pros JobEvent/AccessEvent/ScanEvent — o job só
    precisa de `.job_id` (merge_dedup) e `.timestamp` (evicção de janela)."""
    return SimpleNamespace(job_id=job_id, timestamp=ts or datetime.now(UTC))


def _recent_iso() -> str:
    return datetime.now(UTC).isoformat()


# --- _refresh_storage_read_keys ---------------------------------------------


def test_refresh_storage_read_keys_full_scan_writes_cache_and_returns_count(monkeypatch):
    scan_kwargs = {}

    def fake_scan(logging_client, project_id, *, since_receive_ts=None, page_pause=0.0):
        scan_kwargs["since_receive_ts"] = since_receive_ts
        return {("landing", "a.csv"): _recent_iso(), ("landing", "b.csv"): _recent_iso()}

    monkeypatch.setattr(
        refresh_event_cache.storage_repository, "scan_read_object_events", fake_scan
    )
    monkeypatch.setattr(
        refresh_event_cache.event_cache, "get_cache_metadata", lambda *a, **kw: None
    )
    write_calls = []
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "write_read_object_keys_cache",
        lambda *a, **kw: write_calls.append((a, kw)),
    )

    count = refresh_event_cache._refresh_storage_read_keys(
        MagicMock(), MagicMock(), MagicMock(), "proj", force_full=True
    )

    assert count == 2
    assert scan_kwargs["since_receive_ts"] is None
    assert len(write_calls) == 1
    assert write_calls[0][1]["mode"] == "full"
    assert write_calls[0][1]["last_full_scan_at"] is not None


def test_refresh_storage_read_keys_incremental_merges_delta_onto_existing(monkeypatch):
    anchor = datetime(2026, 8, 27, 3, 0, tzinfo=UTC)
    recent = _recent_iso()
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "read_read_object_keys_cache",
        lambda *a, **kw: {("landing", "old.csv"): recent},
    )
    monkeypatch.setattr(
        refresh_event_cache.event_cache,
        "get_cache_metadata",
        lambda *a, **kw: {"last_scan_receive_ts": anchor},
    )
    seen = {}

    def fake_scan(logging_client, project_id, *, since_receive_ts=None, page_pause=0.0):
        seen["since_receive_ts"] = since_receive_ts
        return {("landing", "new.csv"): recent}

    monkeypatch.setattr(
        refresh_event_cache.storage_repository, "scan_read_object_events", fake_scan
    )
    write_calls = []
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "write_read_object_keys_cache",
        lambda *a, **kw: write_calls.append((a, kw)),
    )

    count = refresh_event_cache._refresh_storage_read_keys(
        MagicMock(), MagicMock(), MagicMock(), "proj", force_full=False
    )

    assert seen["since_receive_ts"] == anchor
    assert count == 2  # old + new
    assert write_calls[0][1]["mode"] == "incremental"


def test_refresh_storage_read_keys_evicts_keys_outside_window(monkeypatch):
    stale = datetime(2020, 1, 1, tzinfo=UTC).isoformat()
    recent = _recent_iso()
    monkeypatch.setattr(
        refresh_event_cache.event_cache, "get_cache_metadata", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "scan_read_object_events",
        lambda *a, **kw: {("b", "stale.csv"): stale, ("b", "fresh.csv"): recent},
    )
    written = {}
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "write_read_object_keys_cache",
        lambda sc, fc, pid, keys, **kw: written.update(keys=keys),
    )

    count = refresh_event_cache._refresh_storage_read_keys(
        MagicMock(), MagicMock(), MagicMock(), "proj", force_full=True
    )

    assert count == 1
    assert set(written["keys"]) == {("b", "fresh.csv")}


def test_refresh_storage_read_keys_returns_zero_without_logging_access(monkeypatch):
    def _raise(*a, **kw):
        raise LoggingAccessDeniedError("proj")

    monkeypatch.setattr(
        refresh_event_cache.event_cache, "get_cache_metadata", lambda *a, **kw: None
    )
    monkeypatch.setattr(refresh_event_cache.storage_repository, "scan_read_object_events", _raise)
    write_calls = []
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "write_read_object_keys_cache",
        lambda *a, **kw: write_calls.append(1),
    )

    count = refresh_event_cache._refresh_storage_read_keys(
        MagicMock(), MagicMock(), MagicMock(), "proj", force_full=True
    )

    assert count == 0
    assert write_calls == []


def test_refresh_storage_read_keys_returns_zero_on_api_error(monkeypatch):
    """GCS Data Access audit logs (DATA_READ) podem não estar habilitados
    no projeto (docs/specs/storage.md seção 6.2) — não deve derrubar o
    refresh de lineage/access do mesmo projeto."""

    def _raise(*a, **kw):
        raise NotFound("some api error")

    monkeypatch.setattr(
        refresh_event_cache.event_cache, "get_cache_metadata", lambda *a, **kw: None
    )
    monkeypatch.setattr(refresh_event_cache.storage_repository, "scan_read_object_events", _raise)

    count = refresh_event_cache._refresh_storage_read_keys(
        MagicMock(), MagicMock(), MagicMock(), "proj", force_full=True
    )

    assert count == 0


# --- _known_projects -------------------------------------------------------------


def test_known_projects_unions_hub_projects_and_seen_projects(monkeypatch):
    monkeypatch.setattr(
        refresh_event_cache.admin_repository,
        "list_projects",
        lambda client: [{"project_id": "proj-a"}, {"project_id": "proj-b"}],
    )
    monkeypatch.setattr(
        refresh_event_cache.event_cache,
        "list_seen_projects",
        lambda client: ["proj-b", "proj-c"],
    )

    result = refresh_event_cache._known_projects(MagicMock())

    assert result == ["proj-a", "proj-b", "proj-c"]


# --- _refresh_project -----------------------------------------------------------


def _stub_job_parsers(monkeypatch, *, lineage=None, access=None, finops=None):
    """Registra as entradas cruas recebidas por cada parser em `seen` e
    devolve a lista de eventos configurada (ou [] por padrão — o
    windowing/merge do job precisa de objetos com `.job_id`/`.timestamp`,
    não strings)."""
    seen = {}

    def _mk(key, override):
        def _parser(entries):
            seen[key] = entries
            return list(override) if override is not None else []

        return _parser

    monkeypatch.setattr(
        refresh_event_cache.lineage_repository, "parse_job_events", _mk("lineage", lineage)
    )
    monkeypatch.setattr(
        refresh_event_cache.access_repository, "parse_access_events", _mk("access", access)
    )
    monkeypatch.setattr(
        refresh_event_cache.finops_repository, "parse_scan_events", _mk("finops", finops)
    )
    return seen


def test_refresh_project_full_scan_writes_all_four_caches(monkeypatch):
    """force_full → UM scan de jobservice.jobcompleted alimenta os 3
    parsers de lineage/access/finops; storage tem scan próprio. Mode
    "full" gravado no metadado dos 4 caches."""
    scan_calls = []

    def fake_scan(client, *, resource_names, filter_, page_size, project_id, page_pause=0.0):
        scan_calls.append((project_id, filter_))
        return ["e1", "e2"]

    monkeypatch.setattr(refresh_event_cache, "list_entries_with_retry", fake_scan)
    parsed = _stub_job_parsers(monkeypatch)

    wj, wa, wf, ws = [], [], [], []
    monkeypatch.setattr(
        refresh_event_cache.lineage_repository,
        "write_job_events_cache",
        lambda *a, **kw: wj.append(kw),
    )
    monkeypatch.setattr(
        refresh_event_cache.access_repository,
        "write_access_events_cache",
        lambda *a, **kw: wa.append(kw),
    )
    monkeypatch.setattr(
        refresh_event_cache.finops_repository,
        "write_scan_events_cache",
        lambda *a, **kw: wf.append(kw),
    )
    monkeypatch.setattr(
        refresh_event_cache.event_cache, "get_cache_metadata", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository, "scan_read_object_events", lambda *a, **kw: {}
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "write_read_object_keys_cache",
        lambda *a, **kw: ws.append(kw),
    )

    status, counts = refresh_event_cache._refresh_project(
        MagicMock(), MagicMock(), MagicMock(), "proj", force_full=True
    )

    assert status == "ok"
    assert counts["mode"] == "full"
    assert [c[0] for c in scan_calls] == ["proj"]  # um scan de job, não três
    assert 'timestamp>="' in scan_calls[0][1]
    assert parsed["lineage"] == parsed["access"] == parsed["finops"] == ["e1", "e2"]
    assert len(wj) == len(wa) == len(wf) == len(ws) == 1
    assert wj[0]["mode"] == "full"
    assert wj[0]["last_full_scan_at"] is not None


def test_refresh_project_incremental_uses_delta_filter_and_merges(monkeypatch):
    anchor = datetime(2026, 8, 27, 3, 0, tzinfo=UTC)
    existing_event = _event("old")
    new_event = _event("new")

    monkeypatch.setattr(
        refresh_event_cache.event_cache,
        "get_cache_metadata",
        lambda fc, kind, pid: {"last_scan_receive_ts": anchor},
    )
    monkeypatch.setattr(
        refresh_event_cache.lineage_repository,
        "read_job_events_cache",
        lambda *a, **kw: ([existing_event], None),
    )
    monkeypatch.setattr(
        refresh_event_cache.access_repository,
        "read_access_events_cache",
        lambda *a, **kw: ([], None),
    )
    monkeypatch.setattr(
        refresh_event_cache.finops_repository,
        "read_scan_events_cache",
        lambda *a, **kw: ([], None),
    )

    filters = []

    def fake_scan(client, *, resource_names, filter_, page_size, project_id, page_pause=0.0):
        filters.append(filter_)
        return ["raw"]

    monkeypatch.setattr(refresh_event_cache, "list_entries_with_retry", fake_scan)
    _stub_job_parsers(monkeypatch, lineage=[new_event])

    written = {}
    monkeypatch.setattr(
        refresh_event_cache.lineage_repository,
        "write_job_events_cache",
        lambda sc, fc, pid, events, **kw: written.update(events=events, kw=kw),
    )
    monkeypatch.setattr(
        refresh_event_cache.access_repository,
        "write_access_events_cache",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        refresh_event_cache.finops_repository,
        "write_scan_events_cache",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "read_read_object_keys_cache",
        lambda *a, **kw: {},
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository, "scan_read_object_events", lambda *a, **kw: {}
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "write_read_object_keys_cache",
        lambda *a, **kw: None,
    )

    status, counts = refresh_event_cache._refresh_project(
        MagicMock(), MagicMock(), MagicMock(), "proj", force_full=False
    )

    assert status == "ok"
    assert counts["mode"] == "incremental"
    assert "receiveTimestamp>" in filters[0]
    assert {e.job_id for e in written["events"]} == {"old", "new"}  # merge_dedup
    assert written["kw"]["mode"] == "incremental"


def test_refresh_project_full_scan_when_anchor_missing(monkeypatch):
    """Sem last_scan_receive_ts em algum kind (primeira execução) → full,
    mesmo com force_full=False."""
    monkeypatch.setattr(
        refresh_event_cache.event_cache, "get_cache_metadata", lambda *a, **kw: None
    )
    filters = []

    def fake_scan(client, *, resource_names, filter_, page_size, project_id, page_pause=0.0):
        filters.append(filter_)
        return []

    monkeypatch.setattr(refresh_event_cache, "list_entries_with_retry", fake_scan)
    _stub_job_parsers(monkeypatch)
    monkeypatch.setattr(
        refresh_event_cache.lineage_repository, "write_job_events_cache", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        refresh_event_cache.access_repository, "write_access_events_cache", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        refresh_event_cache.finops_repository, "write_scan_events_cache", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "read_read_object_keys_cache",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository, "scan_read_object_events", lambda *a, **kw: {}
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "write_read_object_keys_cache",
        lambda *a, **kw: None,
    )

    _status, counts = refresh_event_cache._refresh_project(
        MagicMock(), MagicMock(), MagicMock(), "proj", force_full=False
    )

    assert counts["mode"] == "full"
    assert 'timestamp>="' in filters[0]


def test_refresh_project_skips_project_without_logging_access(monkeypatch):
    def _raise(*a, **kw):
        raise LoggingAccessDeniedError("proj")

    monkeypatch.setattr(refresh_event_cache, "list_entries_with_retry", _raise)
    write_calls = []
    monkeypatch.setattr(
        refresh_event_cache.lineage_repository,
        "write_job_events_cache",
        lambda *a, **kw: write_calls.append(1),
    )

    status, _counts = refresh_event_cache._refresh_project(
        MagicMock(), MagicMock(), MagicMock(), "proj", force_full=True
    )

    assert status == "access_denied"
    assert write_calls == []


def test_refresh_project_skips_project_on_quota_exceeded(monkeypatch):
    def _raise(*a, **kw):
        raise LoggingQuotaExceededError("proj")

    monkeypatch.setattr(refresh_event_cache, "list_entries_with_retry", _raise)
    write_calls = []
    monkeypatch.setattr(
        refresh_event_cache.lineage_repository,
        "write_job_events_cache",
        lambda *a, **kw: write_calls.append(1),
    )

    status, _counts = refresh_event_cache._refresh_project(
        MagicMock(), MagicMock(), MagicMock(), "proj", force_full=True
    )

    assert status == "quota_exceeded"
    assert write_calls == []


def test_refresh_project_skips_project_that_does_not_exist(monkeypatch):
    """Caso real observado em produção: projeto registrado em hub_projects/
    "vistos" foi descontinuado/renomeado — Cloud Logging devolve 404
    NotFound (não 403 Forbidden) quando a SA do Hub não tem NENHUM
    binding de IAM no projeto. Sem isso capturado, o job inteiro morria
    (exit 1) na primeira entrada obsoleta."""

    def _raise(*a, **kw):
        raise NotFound("projects/inter-mta does not exist")

    monkeypatch.setattr(refresh_event_cache, "list_entries_with_retry", _raise)
    write_calls = []
    monkeypatch.setattr(
        refresh_event_cache.lineage_repository,
        "write_job_events_cache",
        lambda *a, **kw: write_calls.append(1),
    )

    status, _counts = refresh_event_cache._refresh_project(
        MagicMock(), MagicMock(), MagicMock(), "inter-mta", force_full=True
    )

    assert status == "api_error"
    assert write_calls == []


def test_refresh_project_skips_project_on_unexpected_error(monkeypatch):
    def _raise(*a, **kw):
        raise ValueError("algo inesperado")

    monkeypatch.setattr(refresh_event_cache, "list_entries_with_retry", _raise)

    status, _counts = refresh_event_cache._refresh_project(
        MagicMock(), MagicMock(), MagicMock(), "proj", force_full=True
    )

    assert status == "unexpected_error"


# --- main ---------------------------------------------------------------------


def test_main_refreshes_every_known_project(monkeypatch):
    monkeypatch.setattr(refresh_event_cache, "get_logging_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "get_storage_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "get_firestore_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "_known_projects", lambda firestore_client: ["a", "b"])
    monkeypatch.setattr(refresh_event_cache.settings, "cache_force_full", False)
    refreshed = []

    def _fake_refresh(logging_client, storage_client, firestore_client, project_id, *, force_full):
        refreshed.append((project_id, force_full))
        return "ok", {"job_events": 0}

    monkeypatch.setattr(refresh_event_cache, "_refresh_project", _fake_refresh)
    run_calls = {"start": 0, "record": [], "finish": 0}
    monkeypatch.setattr(
        refresh_event_cache.event_cache,
        "start_cache_run",
        lambda fc, projects: run_calls.__setitem__("start", run_calls["start"] + 1) or "run-1",
    )
    monkeypatch.setattr(
        refresh_event_cache.event_cache,
        "record_cache_run_project",
        lambda fc, run_id, pid, status, counts: run_calls["record"].append(pid),
    )
    monkeypatch.setattr(
        refresh_event_cache.event_cache,
        "finish_cache_run",
        lambda fc, run_id: run_calls.__setitem__("finish", run_calls["finish"] + 1),
    )

    refresh_event_cache.main()

    assert refreshed == [("a", False), ("b", False)]
    assert run_calls == {"start": 1, "record": ["a", "b"], "finish": 1}


def test_main_propagates_force_full_from_settings(monkeypatch):
    monkeypatch.setattr(refresh_event_cache, "get_logging_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "get_storage_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "get_firestore_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "_known_projects", lambda firestore_client: ["a"])
    monkeypatch.setattr(refresh_event_cache.settings, "cache_force_full", True)
    seen = []

    monkeypatch.setattr(
        refresh_event_cache,
        "_refresh_project",
        lambda lc, sc, fc, pid, *, force_full: seen.append(force_full) or ("ok", {}),
    )
    monkeypatch.setattr(
        refresh_event_cache.event_cache, "start_cache_run", lambda fc, projects: "run-1"
    )
    monkeypatch.setattr(
        refresh_event_cache.event_cache,
        "record_cache_run_project",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        refresh_event_cache.event_cache, "finish_cache_run", lambda fc, run_id: None
    )

    refresh_event_cache.main()

    assert seen == [True]


def test_main_restricts_to_cache_only_projects_from_settings(monkeypatch):
    """cache_only_projects (seleção do gatilho de admin) SUBSTITUI a união
    hub_projects ∪ "vistos" — roda exatamente os projetos pedidos."""
    monkeypatch.setattr(refresh_event_cache, "get_logging_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "get_storage_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "get_firestore_client", lambda: MagicMock())
    known_calls = []
    monkeypatch.setattr(
        refresh_event_cache,
        "_known_projects",
        lambda firestore_client: known_calls.append(1) or ["a", "b", "c"],
    )
    monkeypatch.setattr(refresh_event_cache.settings, "cache_force_full", False)
    monkeypatch.setattr(refresh_event_cache.settings, "cache_only_projects", "b, c")
    refreshed = []
    monkeypatch.setattr(
        refresh_event_cache,
        "_refresh_project",
        lambda lc, sc, fc, pid, *, force_full: refreshed.append(pid) or ("ok", {}),
    )
    monkeypatch.setattr(
        refresh_event_cache.event_cache, "start_cache_run", lambda fc, projects: "run-1"
    )
    monkeypatch.setattr(
        refresh_event_cache.event_cache, "record_cache_run_project", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        refresh_event_cache.event_cache, "finish_cache_run", lambda fc, run_id: None
    )

    refresh_event_cache.main()

    assert refreshed == ["b", "c"]
    assert known_calls == []  # _known_projects nem é consultado


def test_main_processes_all_projects_even_when_one_does_not_exist(monkeypatch):
    """Regressão end-to-end do bug real: usa _refresh_project de verdade
    (não mockado) — só o scan de audit log é mockado, pra provar que
    main() continua processando "b" mesmo com "inter-mta" quebrado no
    meio da lista, em vez de morrer no primeiro NotFound."""
    monkeypatch.setattr(refresh_event_cache, "get_logging_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "get_storage_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "get_firestore_client", lambda: MagicMock())
    monkeypatch.setattr(
        refresh_event_cache, "_known_projects", lambda firestore_client: ["a", "inter-mta", "b"]
    )
    monkeypatch.setattr(refresh_event_cache.settings, "cache_force_full", True)
    monkeypatch.setattr(
        refresh_event_cache.event_cache, "get_cache_metadata", lambda *a, **kw: None
    )

    def fake_list_entries_with_retry(client, *, project_id, **kw):
        if project_id == "inter-mta":
            raise NotFound("projects/inter-mta does not exist")
        return []

    monkeypatch.setattr(
        refresh_event_cache, "list_entries_with_retry", fake_list_entries_with_retry
    )
    monkeypatch.setattr(
        refresh_event_cache.lineage_repository, "write_job_events_cache", lambda *a, **kw: None
    )
    processed_access = []
    monkeypatch.setattr(
        refresh_event_cache.access_repository,
        "write_access_events_cache",
        lambda sc, fc, project_id, events, **kw: processed_access.append(project_id),
    )
    monkeypatch.setattr(
        refresh_event_cache.finops_repository, "write_scan_events_cache", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository, "scan_read_object_events", lambda *a, **kw: {}
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "write_read_object_keys_cache",
        lambda *a, **kw: None,
    )

    refresh_event_cache.main()  # não deve levantar

    assert processed_access == ["a", "b"]
