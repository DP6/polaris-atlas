from unittest.mock import MagicMock

from google.api_core.exceptions import NotFound

from observability_hub.core.exceptions import LoggingAccessDeniedError, LoggingQuotaExceededError
from observability_hub.jobs import refresh_event_cache


def test_refresh_storage_read_keys_writes_cache_and_returns_count(monkeypatch):
    write_calls = []
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "list_read_object_keys",
        lambda client, project_id, lookback_days: {("landing", "a.csv"), ("landing", "b.csv")},
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "write_read_object_keys_cache",
        lambda *a, **kw: write_calls.append((a, kw)),
    )

    count = refresh_event_cache._refresh_storage_read_keys(
        MagicMock(), MagicMock(), MagicMock(), "proj"
    )

    assert count == 2
    assert len(write_calls) == 1


def test_refresh_storage_read_keys_returns_zero_without_logging_access(monkeypatch):
    def _raise(*a, **kw):
        raise LoggingAccessDeniedError("proj")

    monkeypatch.setattr(refresh_event_cache.storage_repository, "list_read_object_keys", _raise)
    write_calls = []
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "write_read_object_keys_cache",
        lambda *a, **kw: write_calls.append(1),
    )

    count = refresh_event_cache._refresh_storage_read_keys(
        MagicMock(), MagicMock(), MagicMock(), "proj"
    )

    assert count == 0
    assert write_calls == []


def test_refresh_storage_read_keys_returns_zero_on_api_error(monkeypatch):
    """GCS Data Access audit logs (DATA_READ) podem não estar habilitados
    no projeto (docs/specs/storage.md seção 6.2) — não deve derrubar o
    refresh de lineage/access do mesmo projeto."""

    def _raise(*a, **kw):
        raise NotFound("some api error")

    monkeypatch.setattr(refresh_event_cache.storage_repository, "list_read_object_keys", _raise)

    count = refresh_event_cache._refresh_storage_read_keys(
        MagicMock(), MagicMock(), MagicMock(), "proj"
    )

    assert count == 0


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


def test_refresh_project_scans_once_and_writes_all_four_caches(monkeypatch):
    """UM scan de audit log (list_entries_with_retry) alimenta os 3
    parsers de lineage/access/finops; storage tem scan próprio."""
    scan_calls = []

    def fake_scan(client, *, resource_names, filter_, page_size, project_id):
        scan_calls.append(project_id)
        return ["entry-1", "entry-2"]

    monkeypatch.setattr(refresh_event_cache, "list_entries_with_retry", fake_scan)

    parsed = {}
    monkeypatch.setattr(
        refresh_event_cache.lineage_repository,
        "parse_job_events",
        lambda entries: parsed.setdefault("lineage", entries) or [],
    )
    monkeypatch.setattr(
        refresh_event_cache.access_repository,
        "parse_access_events",
        lambda entries: parsed.setdefault("access", entries) or [],
    )
    monkeypatch.setattr(
        refresh_event_cache.finops_repository,
        "parse_scan_events",
        lambda entries: parsed.setdefault("finops", entries) or [],
    )

    write_job_calls, write_access_calls, write_finops_calls, write_storage_calls = [], [], [], []
    monkeypatch.setattr(
        refresh_event_cache.lineage_repository,
        "write_job_events_cache",
        lambda *a, **kw: write_job_calls.append((a, kw)),
    )
    monkeypatch.setattr(
        refresh_event_cache.access_repository,
        "write_access_events_cache",
        lambda *a, **kw: write_access_calls.append((a, kw)),
    )
    monkeypatch.setattr(
        refresh_event_cache.finops_repository,
        "write_scan_events_cache",
        lambda *a, **kw: write_finops_calls.append((a, kw)),
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "list_read_object_keys",
        lambda client, project_id, lookback_days: set(),
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "write_read_object_keys_cache",
        lambda *a, **kw: write_storage_calls.append((a, kw)),
    )

    refresh_event_cache._refresh_project(MagicMock(), MagicMock(), MagicMock(), "proj")

    assert scan_calls == ["proj"]  # UM scan de jobservice.jobcompleted, não três
    assert parsed["lineage"] == parsed["access"] == parsed["finops"] == ["entry-1", "entry-2"]
    assert len(write_job_calls) == 1
    assert len(write_access_calls) == 1
    assert len(write_finops_calls) == 1
    assert len(write_storage_calls) == 1


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

    # Não deve levantar — o job segue pros próximos projetos.
    refresh_event_cache._refresh_project(MagicMock(), MagicMock(), MagicMock(), "proj")

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

    # 429 persistente após o retry — logado como quota_exceeded, não propaga.
    refresh_event_cache._refresh_project(MagicMock(), MagicMock(), MagicMock(), "proj")

    assert write_calls == []


def test_refresh_project_skips_project_that_does_not_exist(monkeypatch):
    """Caso real observado em produção: projeto registrado em hub_projects/
    "vistos" foi descontinuado/renomeado — Cloud Logging devolve 404
    NotFound (não 403 Forbidden) quando a SA do Hub não tem NENHUM
    binding de IAM no projeto. Sem isso capturado, o job inteiro morria
    (exit 1) na primeira entrada obsoleta, sem processar mais nenhum
    projeto depois dela."""

    def _raise(*a, **kw):
        raise NotFound("projects/inter-mta does not exist")

    monkeypatch.setattr(refresh_event_cache, "list_entries_with_retry", _raise)
    write_calls = []
    monkeypatch.setattr(
        refresh_event_cache.lineage_repository,
        "write_job_events_cache",
        lambda *a, **kw: write_calls.append(1),
    )

    refresh_event_cache._refresh_project(MagicMock(), MagicMock(), MagicMock(), "inter-mta")

    assert write_calls == []


def test_refresh_project_skips_project_on_unexpected_error(monkeypatch):
    def _raise(*a, **kw):
        raise ValueError("algo inesperado")

    monkeypatch.setattr(refresh_event_cache, "list_entries_with_retry", _raise)

    # Não deve propagar — rede de segurança final do job em lote.
    refresh_event_cache._refresh_project(MagicMock(), MagicMock(), MagicMock(), "proj")


def test_main_refreshes_every_known_project(monkeypatch):
    monkeypatch.setattr(refresh_event_cache, "get_logging_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "get_storage_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "get_firestore_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "_known_projects", lambda firestore_client: ["a", "b"])
    refreshed = []

    def _fake_refresh(logging_client, storage_client, firestore_client, project_id):
        refreshed.append(project_id)
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

    assert refreshed == ["a", "b"]
    assert run_calls == {"start": 1, "record": ["a", "b"], "finish": 1}


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

    # project_id vem como kwarg: list_entries_with_retry(client, *, ..., project_id=...)
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
        lambda storage_client, firestore_client, project_id, events: processed_access.append(
            project_id
        ),
    )
    monkeypatch.setattr(
        refresh_event_cache.finops_repository, "write_scan_events_cache", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "list_read_object_keys",
        lambda client, project_id, lookback_days: set(),
    )
    monkeypatch.setattr(
        refresh_event_cache.storage_repository,
        "write_read_object_keys_cache",
        lambda *a, **kw: None,
    )

    refresh_event_cache.main()  # não deve levantar

    assert processed_access == ["a", "b"]
