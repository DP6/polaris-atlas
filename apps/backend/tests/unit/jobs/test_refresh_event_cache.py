from unittest.mock import MagicMock

from observability_hub.core.exceptions import LoggingAccessDeniedError
from observability_hub.domains.lineage.repository import JobEvent
from observability_hub.jobs import refresh_event_cache


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


def test_refresh_project_writes_lineage_and_access_caches(monkeypatch):
    write_job_calls = []
    write_access_calls = []
    monkeypatch.setattr(
        refresh_event_cache.lineage_repository,
        "list_job_events",
        lambda client, project_id: [
            JobEvent(
                job_id="j1",
                principal_email="a@dp6.com.br",
                referenced_tables=[],
                destination_table=None,
            )
        ],
    )
    monkeypatch.setattr(
        refresh_event_cache.lineage_repository,
        "write_job_events_cache",
        lambda *a, **kw: write_job_calls.append((a, kw)),
    )
    monkeypatch.setattr(
        refresh_event_cache.access_repository, "list_access_events", lambda client, project_id: []
    )
    monkeypatch.setattr(
        refresh_event_cache.access_repository,
        "write_access_events_cache",
        lambda *a, **kw: write_access_calls.append((a, kw)),
    )

    refresh_event_cache._refresh_project(MagicMock(), MagicMock(), MagicMock(), "proj")

    assert len(write_job_calls) == 1
    assert len(write_access_calls) == 1


def test_refresh_project_skips_project_without_logging_access(monkeypatch):
    def _raise(*a, **kw):
        raise LoggingAccessDeniedError("proj")

    monkeypatch.setattr(refresh_event_cache.lineage_repository, "list_job_events", _raise)
    write_calls = []
    monkeypatch.setattr(
        refresh_event_cache.lineage_repository,
        "write_job_events_cache",
        lambda *a, **kw: write_calls.append(1),
    )

    # Não deve levantar — o job segue pros próximos projetos.
    refresh_event_cache._refresh_project(MagicMock(), MagicMock(), MagicMock(), "proj")

    assert write_calls == []


def test_main_refreshes_every_known_project(monkeypatch):
    monkeypatch.setattr(refresh_event_cache, "get_logging_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "get_storage_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "get_firestore_client", lambda: MagicMock())
    monkeypatch.setattr(refresh_event_cache, "_known_projects", lambda firestore_client: ["a", "b"])
    refreshed = []
    monkeypatch.setattr(
        refresh_event_cache,
        "_refresh_project",
        lambda logging_client, storage_client, firestore_client, project_id: refreshed.append(
            project_id
        ),
    )

    refresh_event_cache.main()

    assert refreshed == ["a", "b"]
