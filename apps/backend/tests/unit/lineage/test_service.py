from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from observability_hub.core.config import settings
from observability_hub.core.exceptions import (
    EventCacheNotReadyError,
    LoggingAccessDeniedError,
    LoggingQuotaExceededError,
)
from observability_hub.domains.lineage import service
from observability_hub.domains.lineage.repository import JobEvent


def _event(
    referenced,
    destination,
    job_id="job1",
    source_buckets=(),
    destination_buckets=(),
):
    return JobEvent(
        job_id=job_id,
        principal_email="a@dp6.com.br",
        referenced_tables=referenced,
        destination_table=destination,
        source_buckets=list(source_buckets),
        destination_buckets=list(destination_buckets),
    )


def _events_by_project(mapping, denied=frozenset()):
    """Fake pra repository.get_job_events_cached: despacha por project_id,
    levantando LoggingAccessDeniedError pros projetos em `denied` — a
    travessia multi-hop pode consultar mais de um projeto por request.
    Retorna (eventos, cache_updated_at) — cache_updated_at fixo em None
    nos testes que não verificam explicitamente esse campo."""

    def _fake(logging_client, storage_client, firestore_client, project_id, lookback_days=30):
        if project_id in denied:
            raise LoggingAccessDeniedError(project_id)
        return mapping.get(project_id, []), None

    return _fake


# --- get_table_lineage ----------------------------------------------------


def test_get_table_lineage_finds_upstream_from_jobs_that_wrote_to_target(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    events = [
        _event(
            referenced=[("proj", "RAW", "crm_leads"), ("proj", "RAW", "crm_accounts")],
            destination=("proj", "GOLD", "leads_summary"),
        )
    ]
    monkeypatch.setattr(
        service.repository, "get_job_events_cached", _events_by_project({"proj": events})
    )

    result = service.get_table_lineage(
        client, logging_client, MagicMock(), MagicMock(), "proj", "GOLD", "leads_summary"
    )

    assert {(n.dataset_id, n.table_id, n.hop_distance) for n in result.nodes} == {
        ("RAW", "crm_leads", -1),
        ("RAW", "crm_accounts", -1),
    }
    assert result.warning is None
    assert result.truncated is False


def test_get_table_lineage_finds_downstream_from_jobs_that_read_target(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    events = [
        _event(
            referenced=[("proj", "RAW", "crm_leads")],
            destination=("proj", "GOLD", "leads_summary"),
        )
    ]
    monkeypatch.setattr(
        service.repository, "get_job_events_cached", _events_by_project({"proj": events})
    )

    result = service.get_table_lineage(
        client, logging_client, MagicMock(), MagicMock(), "proj", "RAW", "crm_leads"
    )

    assert {(n.dataset_id, n.table_id, n.hop_distance) for n in result.nodes} == {
        ("GOLD", "leads_summary", 1),
    }


def test_get_table_lineage_ignores_self_references(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    # Job que só sobrescreve a própria tabela (ex: MERGE) não deveria virar
    # upstream/downstream de si mesma, em nenhum hop.
    events = [
        _event(referenced=[("proj", "RAW", "crm_leads")], destination=("proj", "RAW", "crm_leads"))
    ]
    monkeypatch.setattr(
        service.repository, "get_job_events_cached", _events_by_project({"proj": events})
    )

    result = service.get_table_lineage(
        client, logging_client, MagicMock(), MagicMock(), "proj", "RAW", "crm_leads"
    )

    assert result.nodes == []
    assert result.edges == []


def test_get_table_lineage_sets_warning_when_no_events(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    monkeypatch.setattr(service.repository, "get_job_events_cached", _events_by_project({}))

    result = service.get_table_lineage(
        client, logging_client, MagicMock(), MagicMock(), "proj", "RAW", "crm_leads"
    )

    assert result.nodes == []
    assert result.warning is not None
    assert "proj" in result.warning


def test_get_table_lineage_follows_transitive_chain(monkeypatch):
    # daily_summary <- ga4_sessions <- ga4_events, mesmo projeto.
    client = MagicMock()
    logging_client = MagicMock()
    events = [
        _event(
            referenced=[("proj", "RAW", "ga4_events")],
            destination=("proj", "TRUSTED", "ga4_sessions"),
            job_id="job-events",
        ),
        _event(
            referenced=[("proj", "TRUSTED", "ga4_sessions")],
            destination=("proj", "GOLD", "daily_summary"),
            job_id="job-sessions",
        ),
    ]
    monkeypatch.setattr(
        service.repository, "get_job_events_cached", _events_by_project({"proj": events})
    )

    result = service.get_table_lineage(
        client, logging_client, MagicMock(), MagicMock(), "proj", "GOLD", "daily_summary"
    )

    assert {(n.dataset_id, n.table_id, n.hop_distance) for n in result.nodes} == {
        ("TRUSTED", "ga4_sessions", -1),
        ("RAW", "ga4_events", -2),
    }
    assert {(e.source, e.target) for e in result.edges} == {
        ("proj:RAW:ga4_events", "proj:TRUSTED:ga4_sessions"),
        ("proj:TRUSTED:ga4_sessions", "proj:GOLD:daily_summary"),
    }
    assert result.truncated is False


def test_get_table_lineage_join_fan_in_downstream(monkeypatch):
    # job-join: a,b -> c (JOIN); job-d: c -> d. Root = a, olhando downstream
    # — b não é alcançável a partir de a, não deve aparecer.
    client = MagicMock()
    logging_client = MagicMock()
    events = [
        _event(
            referenced=[("proj", "RAW", "a"), ("proj", "RAW", "b")],
            destination=("proj", "TRUSTED", "c"),
            job_id="job-join",
        ),
        _event(
            referenced=[("proj", "TRUSTED", "c")], destination=("proj", "GOLD", "d"), job_id="job-d"
        ),
    ]
    monkeypatch.setattr(
        service.repository, "get_job_events_cached", _events_by_project({"proj": events})
    )

    result = service.get_table_lineage(
        client, logging_client, MagicMock(), MagicMock(), "proj", "RAW", "a"
    )

    assert {(n.dataset_id, n.table_id, n.hop_distance) for n in result.nodes} == {
        ("TRUSTED", "c", 1),
        ("GOLD", "d", 2),
    }
    assert {(e.source, e.target) for e in result.edges} == {
        ("proj:RAW:a", "proj:TRUSTED:c"),
        ("proj:TRUSTED:c", "proj:GOLD:d"),
    }


def test_get_table_lineage_join_fan_in_upstream(monkeypatch):
    # Mesmo cenário do teste anterior, root = d olhando upstream: o fan-in
    # do JOIN precisa trazer a e b, não só c.
    client = MagicMock()
    logging_client = MagicMock()
    events = [
        _event(
            referenced=[("proj", "RAW", "a"), ("proj", "RAW", "b")],
            destination=("proj", "TRUSTED", "c"),
            job_id="job-join",
        ),
        _event(
            referenced=[("proj", "TRUSTED", "c")], destination=("proj", "GOLD", "d"), job_id="job-d"
        ),
    ]
    monkeypatch.setattr(
        service.repository, "get_job_events_cached", _events_by_project({"proj": events})
    )

    result = service.get_table_lineage(
        client, logging_client, MagicMock(), MagicMock(), "proj", "GOLD", "d"
    )

    assert {(n.dataset_id, n.table_id, n.hop_distance) for n in result.nodes} == {
        ("TRUSTED", "c", -1),
        ("RAW", "a", -2),
        ("RAW", "b", -2),
    }
    assert {(e.source, e.target) for e in result.edges} == {
        ("proj:RAW:a", "proj:TRUSTED:c"),
        ("proj:RAW:b", "proj:TRUSTED:c"),
        ("proj:TRUSTED:c", "proj:GOLD:d"),
    }


def test_get_table_lineage_cross_project_access_denied_soft_fails(monkeypatch):
    # Root em proj-a; um job de proj-a referencia tabela de proj-b;
    # proj-b sem acesso de Logging -> nó bloqueado, requisição não falha.
    client = MagicMock()
    logging_client = MagicMock()
    events_a = [
        _event(
            referenced=[("proj-b", "RAW", "shared")],
            destination=("proj-a", "GOLD", "x"),
            job_id="job1",
        )
    ]
    monkeypatch.setattr(
        service.repository,
        "get_job_events_cached",
        _events_by_project({"proj-a": events_a}, denied={"proj-b"}),
    )

    result = service.get_table_lineage(
        client, logging_client, MagicMock(), MagicMock(), "proj-a", "GOLD", "x"
    )

    denied_nodes = [n for n in result.nodes if n.access_denied]
    assert len(denied_nodes) == 1
    assert (denied_nodes[0].project_id, denied_nodes[0].dataset_id, denied_nodes[0].table_id) == (
        "proj-b",
        "RAW",
        "shared",
    )
    assert result.warning is None


def test_get_table_lineage_root_project_access_denied_raises(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    monkeypatch.setattr(
        service.repository, "get_job_events_cached", _events_by_project({}, denied={"proj"})
    )

    with pytest.raises(LoggingAccessDeniedError):
        service.get_table_lineage(
            client, logging_client, MagicMock(), MagicMock(), "proj", "GOLD", "x"
        )


def test_get_table_lineage_root_project_quota_exceeded_degrades_to_warning(monkeypatch):
    """Cota do Cloud Logging saturada no projeto raiz -> grafo vazio com
    aviso, não um 503 ('Failed to fetch' no browser)."""

    def _raise(*a, **kw):
        raise LoggingQuotaExceededError("proj")

    monkeypatch.setattr(service.repository, "get_job_events_cached", _raise)

    result = service.get_table_lineage(
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), "proj", "GOLD", "x"
    )

    assert result.nodes == []
    assert result.edges == []
    assert result.cache_updated_at is None
    assert result.warning is not None
    assert "limite de leitura de audit logs" in result.warning


def test_get_table_lineage_root_project_cache_not_ready_degrades_to_warning(monkeypatch):
    """Modelo incremental: cache ainda não gerado pro projeto raiz ->
    grafo vazio com aviso "cache não gerado", não um 503."""

    def _raise(*a, **kw):
        raise EventCacheNotReadyError("proj")

    monkeypatch.setattr(service.repository, "get_job_events_cached", _raise)

    result = service.get_table_lineage(
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), "proj", "GOLD", "x"
    )

    assert result.nodes == []
    assert result.edges == []
    assert result.warning is not None
    assert "ainda não foi gerado" in result.warning


def test_get_table_lineage_cross_project_cache_not_ready_soft_fails(monkeypatch):
    """Um projeto não-raiz sem cache gerado durante a expansão não derruba
    o grafo — só não expande a partir dele (igual a cota/acesso negado)."""
    root_events = [_event([("other", "RAW", "src")], ("proj", "GOLD", "x"))]

    def _fake(logging_client, storage_client, firestore_client, project_id, lookback_days=30):
        if project_id == "other":
            raise EventCacheNotReadyError(project_id)
        return root_events, None

    monkeypatch.setattr(service.repository, "get_job_events_cached", _fake)

    result = service.get_table_lineage(
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), "proj", "GOLD", "x"
    )

    assert any(n.project_id == "other" for n in result.nodes if n.type == "table")
    assert result.warning is None


def test_get_orphans_cache_not_ready_degrades_to_warning(monkeypatch):
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(service.repository, "list_all_table_refs", lambda *a, **kw: [("RAW", "t1")])

    def _raise(*a, **kw):
        raise EventCacheNotReadyError("proj")

    monkeypatch.setattr(service.repository, "get_job_events_cached", _raise)

    result = service.get_orphans(MagicMock(), MagicMock(), MagicMock(), MagicMock(), "proj")

    assert result.orphans == []
    assert result.warning is not None
    assert "ainda não foi gerado" in result.warning


def test_get_table_lineage_cross_project_quota_exceeded_soft_fails(monkeypatch):
    """Um projeto não-raiz que estoura a cota durante a expansão não
    derruba o grafo — só não expande a partir dele."""
    root_events = [_event([("other", "RAW", "src")], ("proj", "GOLD", "x"))]

    def _fake(logging_client, storage_client, firestore_client, project_id, lookback_days=30):
        if project_id == "other":
            raise LoggingQuotaExceededError(project_id)
        return root_events, None

    monkeypatch.setattr(service.repository, "get_job_events_cached", _fake)

    result = service.get_table_lineage(
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), "proj", "GOLD", "x"
    )

    # A aresta pro nó de "other" existe, mas não explodiu.
    assert any(n.project_id == "other" for n in result.nodes if n.type == "table")
    assert result.warning is None


def test_get_orphans_quota_exceeded_degrades_to_warning(monkeypatch):
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository, "list_all_table_refs", lambda *a, **kw: [("RAW", "t1"), ("RAW", "t2")]
    )

    def _raise(*a, **kw):
        raise LoggingQuotaExceededError("proj")

    monkeypatch.setattr(service.repository, "get_job_events_cached", _raise)

    result = service.get_orphans(MagicMock(), MagicMock(), MagicMock(), MagicMock(), "proj")

    assert result.orphans == []
    assert result.cache_updated_at is None
    assert result.warning is not None
    assert "limite de leitura de audit logs" in result.warning


def test_get_table_lineage_handles_cycle_across_different_jobs(monkeypatch):
    # a -> b (job1) e b -> a (job2): ciclo real via dois jobs distintos,
    # diferente da auto-referência (mesma tabela na origem e destino de
    # um único job).
    client = MagicMock()
    logging_client = MagicMock()
    events = [
        _event(referenced=[("proj", "RAW", "a")], destination=("proj", "RAW", "b"), job_id="job1"),
        _event(referenced=[("proj", "RAW", "b")], destination=("proj", "RAW", "a"), job_id="job2"),
    ]
    monkeypatch.setattr(
        service.repository, "get_job_events_cached", _events_by_project({"proj": events})
    )

    result = service.get_table_lineage(
        client, logging_client, MagicMock(), MagicMock(), "proj", "RAW", "a"
    )

    assert len(result.nodes) == 1
    assert (result.nodes[0].dataset_id, result.nodes[0].table_id) == ("RAW", "b")
    assert {(e.source, e.target) for e in result.edges} == {
        ("proj:RAW:a", "proj:RAW:b"),
        ("proj:RAW:b", "proj:RAW:a"),
    }


def test_get_table_lineage_respects_max_hops_and_sets_truncated(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    events = [
        _event(
            referenced=[("proj", "RAW", "ga4_events")],
            destination=("proj", "TRUSTED", "ga4_sessions"),
            job_id="job-events",
        ),
        _event(
            referenced=[("proj", "TRUSTED", "ga4_sessions")],
            destination=("proj", "GOLD", "daily_summary"),
            job_id="job-sessions",
        ),
    ]
    monkeypatch.setattr(
        service.repository, "get_job_events_cached", _events_by_project({"proj": events})
    )

    truncated_result = service.get_table_lineage(
        client,
        logging_client,
        MagicMock(),
        MagicMock(),
        "proj",
        "GOLD",
        "daily_summary",
        max_hops=1,
    )
    assert {(n.dataset_id, n.table_id) for n in truncated_result.nodes} == {
        ("TRUSTED", "ga4_sessions")
    }
    assert truncated_result.truncated is True

    full_result = service.get_table_lineage(
        client,
        logging_client,
        MagicMock(),
        MagicMock(),
        "proj",
        "GOLD",
        "daily_summary",
        max_hops=8,
    )
    assert full_result.truncated is False
    assert {(n.dataset_id, n.table_id) for n in full_result.nodes} == {
        ("TRUSTED", "ga4_sessions"),
        ("RAW", "ga4_events"),
    }


def test_get_table_lineage_dedupes_repeated_job_edges(monkeypatch):
    # Mesmo job rodando diariamente ao longo da janela de 30 dias gera
    # eventos repetidos com a mesma origem/destino -> uma única aresta.
    client = MagicMock()
    logging_client = MagicMock()
    events = [
        _event(
            referenced=[("proj", "RAW", "a")], destination=("proj", "GOLD", "b"), job_id="job-day1"
        ),
        _event(
            referenced=[("proj", "RAW", "a")], destination=("proj", "GOLD", "b"), job_id="job-day2"
        ),
        _event(
            referenced=[("proj", "RAW", "a")], destination=("proj", "GOLD", "b"), job_id="job-day3"
        ),
    ]
    monkeypatch.setattr(
        service.repository, "get_job_events_cached", _events_by_project({"proj": events})
    )

    result = service.get_table_lineage(
        client, logging_client, MagicMock(), MagicMock(), "proj", "GOLD", "b"
    )

    assert len(result.edges) == 1


# --- get_table_lineage — bucket como nó (docs/specs/storage.md seção 7) -----


def test_get_table_lineage_finds_bucket_upstream_via_load(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    events = [
        _event(
            referenced=[],
            destination=("proj", "RAW", "crm_leads_staging"),
            source_buckets=["landing"],
        )
    ]
    monkeypatch.setattr(
        service.repository, "get_job_events_cached", _events_by_project({"proj": events})
    )

    result = service.get_table_lineage(
        client, logging_client, MagicMock(), MagicMock(), "proj", "RAW", "crm_leads_staging"
    )

    assert len(result.nodes) == 1
    node = result.nodes[0]
    assert node.type == "bucket"
    assert node.bucket_name == "landing"
    assert node.hop_distance == -1
    assert node.dataset_id is None
    assert result.edges == [
        service.LineageEdge(
            source="bucket:landing", target="proj:RAW:crm_leads_staging", job_id="job1"
        )
    ]


def test_get_table_lineage_finds_bucket_downstream_via_extract(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    events = [
        _event(
            referenced=[("proj", "RAW", "crm_leads_staging")],
            destination=None,
            destination_buckets=["processed"],
        )
    ]
    monkeypatch.setattr(
        service.repository, "get_job_events_cached", _events_by_project({"proj": events})
    )

    result = service.get_table_lineage(
        client, logging_client, MagicMock(), MagicMock(), "proj", "RAW", "crm_leads_staging"
    )

    assert len(result.nodes) == 1
    node = result.nodes[0]
    assert node.type == "bucket"
    assert node.bucket_name == "processed"
    assert node.hop_distance == 1
    assert result.edges == [
        service.LineageEdge(
            source="proj:RAW:crm_leads_staging", target="bucket:processed", job_id="job1"
        )
    ]


def test_get_table_lineage_bucket_node_never_expands_further(monkeypatch):
    """Decisão tomada com o usuário (docs/specs/storage.md seção 7.2):
    bucket é sempre folha — mesmo que outro job qualquer no MESMO projeto
    leia do bucket alcançado, essa segunda aresta não deve aparecer no
    grafo, porque a travessia nunca tenta expandir a partir de um nó
    bucket."""
    client = MagicMock()
    logging_client = MagicMock()
    events = [
        # root -> extract -> bucket "processed"
        _event(
            referenced=[("proj", "RAW", "crm_leads_staging")],
            destination=None,
            destination_buckets=["processed"],
            job_id="extract-job",
        ),
        # outro job, no mesmo projeto, carrega de "processed" pra outra
        # tabela -- não deveria aparecer, porque bucket não expande.
        _event(
            referenced=[],
            destination=("proj", "GOLD", "should_not_appear"),
            source_buckets=["processed"],
            job_id="load-job",
        ),
    ]
    monkeypatch.setattr(
        service.repository, "get_job_events_cached", _events_by_project({"proj": events})
    )

    result = service.get_table_lineage(
        client,
        logging_client,
        MagicMock(),
        MagicMock(),
        "proj",
        "RAW",
        "crm_leads_staging",
        max_hops=8,
    )

    node_ids = {n.id for n in result.nodes}
    assert node_ids == {"bucket:processed"}
    assert "proj:GOLD:should_not_appear" not in node_ids


def test_get_table_lineage_bucket_root_side_ignores_unrelated_bucket_events(monkeypatch):
    """Só o bucket que participa do job de load/extract da tabela raiz
    deve virar nó — outro bucket sem relação, mesmo no mesmo evento de
    outro job, não deve vazar pro grafo."""
    client = MagicMock()
    logging_client = MagicMock()
    events = [
        _event(
            referenced=[],
            destination=("proj", "RAW", "crm_leads_staging"),
            source_buckets=["landing"],
            job_id="load-job",
        ),
        _event(
            referenced=[],
            destination=("proj", "OTHER", "unrelated"),
            source_buckets=["some-other-bucket"],
            job_id="unrelated-job",
        ),
    ]
    monkeypatch.setattr(
        service.repository, "get_job_events_cached", _events_by_project({"proj": events})
    )

    result = service.get_table_lineage(
        client, logging_client, MagicMock(), MagicMock(), "proj", "RAW", "crm_leads_staging"
    )

    assert {n.id for n in result.nodes} == {"bucket:landing"}


# --- get_orphans ------------------------------------------------------------


def test_get_orphans_returns_tables_never_referenced(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository,
        "list_all_table_refs",
        lambda *a, **kw: [("RAW", "crm_leads"), ("RAW", "crm_accounts"), ("GOLD", "unused_table")],
    )
    monkeypatch.setattr(
        service.repository,
        "get_job_events_cached",
        lambda *a, **kw: (
            [_event(referenced=[("proj", "RAW", "crm_leads")], destination=("proj", "GOLD", "x"))],
            None,
        ),
    )
    monkeypatch.setattr(service, "get_tables_metadata", lambda client, refs: {})

    result = service.get_orphans(client, logging_client, MagicMock(), MagicMock(), "proj")

    orphan_keys = {(o.dataset_id, o.table_id) for o in result.orphans}
    assert orphan_keys == {("RAW", "crm_accounts"), ("GOLD", "unused_table")}
    assert result.warning is None


def test_get_orphans_passes_datasets_and_lookback_days_through(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    captured = {}
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])

    def fake_list_all_table_refs(client, project_id, regions, datasets=None):
        captured["datasets"] = datasets
        return []

    def fake_get_job_events_cached(
        logging_client, storage_client, firestore_client, project_id, lookback_days=30
    ):
        captured["lookback_days"] = lookback_days
        return [], None

    monkeypatch.setattr(service.repository, "list_all_table_refs", fake_list_all_table_refs)
    monkeypatch.setattr(service.repository, "get_job_events_cached", fake_get_job_events_cached)

    result = service.get_orphans(
        client, logging_client, MagicMock(), MagicMock(), "proj", datasets=["RAW"], lookback_days=90
    )

    assert captured["datasets"] == ["RAW"]
    assert captured["lookback_days"] == 90
    assert result.lookback_days == 90


def test_get_orphans_ignores_referenced_tables_from_other_projects(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository, "list_all_table_refs", lambda *a, **kw: [("RAW", "crm_leads")]
    )
    monkeypatch.setattr(
        service.repository,
        "get_job_events_cached",
        lambda *a, **kw: (
            [_event(referenced=[("other-proj", "RAW", "crm_leads")], destination=None)],
            None,
        ),
    )
    monkeypatch.setattr(service, "get_tables_metadata", lambda client, refs: {})

    result = service.get_orphans(client, logging_client, MagicMock(), MagicMock(), "proj")

    assert {(o.dataset_id, o.table_id) for o in result.orphans} == {("RAW", "crm_leads")}


def test_get_orphans_sets_warning_when_no_events(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository, "list_all_table_refs", lambda *a, **kw: [("RAW", "crm_leads")]
    )
    monkeypatch.setattr(service.repository, "get_job_events_cached", lambda *a, **kw: ([], None))
    monkeypatch.setattr(service, "get_tables_metadata", lambda client, refs: {})

    result = service.get_orphans(client, logging_client, MagicMock(), MagicMock(), "proj")

    assert result.warning is not None
    assert len(result.orphans) == 1


def test_get_orphans_includes_estimated_storage_cost(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    modified = datetime.now(UTC) - timedelta(days=10)
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository, "list_all_table_refs", lambda *a, **kw: [("RAW", "crm_leads")]
    )
    monkeypatch.setattr(service.repository, "get_job_events_cached", lambda *a, **kw: ([], None))
    monkeypatch.setattr(
        service,
        "get_tables_metadata",
        lambda client, refs: {
            "proj.RAW.crm_leads": SimpleNamespace(num_bytes=1024**3, modified=modified)
        },
    )

    result = service.get_orphans(client, logging_client, MagicMock(), MagicMock(), "proj")

    assert result.orphans[0].size_bytes == 1024**3
    assert (
        result.orphans[0].estimated_monthly_storage_cost_usd
        == settings.bigquery_storage_price_usd_per_gb_month_active
    )


def test_get_orphans_defaults_cost_to_zero_when_metadata_missing(monkeypatch):
    client = MagicMock()
    logging_client = MagicMock()
    monkeypatch.setattr(service, "discover_regions", lambda project_id, client: ["US"])
    monkeypatch.setattr(
        service.repository, "list_all_table_refs", lambda *a, **kw: [("RAW", "crm_leads")]
    )
    monkeypatch.setattr(service.repository, "get_job_events_cached", lambda *a, **kw: ([], None))
    monkeypatch.setattr(service, "get_tables_metadata", lambda client, refs: {})

    result = service.get_orphans(client, logging_client, MagicMock(), MagicMock(), "proj")

    assert result.orphans[0].size_bytes == 0
    assert result.orphans[0].estimated_monthly_storage_cost_usd == 0.0
