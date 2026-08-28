from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import Forbidden

from observability_hub.core import event_cache as event_cache_module
from observability_hub.core.exceptions import (
    EventCacheNotReadyError,
    LoggingAccessDeniedError,
    StorageAccessDeniedError,
)
from observability_hub.domains.storage import repository

_PROJECT_ID = "observability-hub-dev"
_NOW = datetime(2026, 8, 17, tzinfo=UTC)


def _blob(size=0, storage_class="STANDARD", custom_time=None, updated=None):
    return SimpleNamespace(
        size=size, storage_class=storage_class, custom_time=custom_time, updated=updated
    )


def _days_ago(days):
    return _NOW - timedelta(days=days)


def _blob_named(name, size=10, updated=None, storage_class="STANDARD"):
    return SimpleNamespace(name=name, size=size, updated=updated, storage_class=storage_class)


def _entry(payload, timestamp=None):
    return SimpleNamespace(payload=payload, timestamp=timestamp)


def test_list_buckets_returns_client_result():
    client = MagicMock()
    bucket = SimpleNamespace(name="landing")
    client.list_buckets.return_value = iter([bucket])

    result = repository.list_buckets(client, _PROJECT_ID)

    assert result == [bucket]
    client.list_buckets.assert_called_once_with(project=_PROJECT_ID)


def test_list_buckets_raises_storage_access_denied_on_forbidden():
    client = MagicMock()
    client.list_buckets.side_effect = Forbidden("nope")

    with pytest.raises(StorageAccessDeniedError):
        repository.list_buckets(client, _PROJECT_ID)


def test_get_bucket_size_and_count_sums_blob_sizes(monkeypatch):
    blobs = [_blob(100), _blob(200), _blob(None)]
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: blobs)

    total_size, count = repository.get_bucket_size_and_count(MagicMock(), _PROJECT_ID, "landing")

    assert total_size == 300
    assert count == 3


def test_get_bucket_size_and_count_raises_storage_access_denied_on_forbidden(monkeypatch):
    def _raise(client, name):
        raise Forbidden("nope")

    monkeypatch.setattr(repository, "list_bucket_objects_cached", _raise)

    with pytest.raises(StorageAccessDeniedError):
        repository.get_bucket_size_and_count(MagicMock(), _PROJECT_ID, "landing")


def test_get_buckets_sizes_and_counts_runs_per_bucket(monkeypatch):
    sizes = {"landing": [_blob(10)], "processed": [_blob(20), _blob(30)]}
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: sizes[name])

    result = repository.get_buckets_sizes_and_counts(
        MagicMock(), _PROJECT_ID, ["landing", "processed"]
    )

    assert result == {"landing": (10, 1), "processed": (50, 2)}


def test_get_buckets_sizes_and_counts_empty_list_returns_empty_dict():
    assert repository.get_buckets_sizes_and_counts(MagicMock(), _PROJECT_ID, []) == {}


def test_get_eligible_waste_objects_filters_by_class_and_age(monkeypatch):
    blobs = [
        _blob(size=1, storage_class="STANDARD", updated=_days_ago(90)),  # elegível
        _blob(size=2, storage_class="NEARLINE", updated=_days_ago(90)),  # classe errada
        _blob(size=3, storage_class="STANDARD", updated=_days_ago(10)),  # recente demais
    ]
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: blobs)

    result = repository.get_eligible_waste_objects(MagicMock(), _PROJECT_ID, "landing", 60, _NOW)

    assert result == [blobs[0]]


def test_get_eligible_waste_objects_prefers_custom_time(monkeypatch):
    blob = _blob(size=1, storage_class="STANDARD", custom_time=_days_ago(90), updated=_days_ago(1))
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: [blob])

    result = repository.get_eligible_waste_objects(MagicMock(), _PROJECT_ID, "landing", 60, _NOW)

    assert result == [blob]


def test_get_eligible_waste_objects_ignores_blob_without_timestamp(monkeypatch):
    blob = _blob(size=1, storage_class="STANDARD", custom_time=None, updated=None)
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: [blob])

    result = repository.get_eligible_waste_objects(MagicMock(), _PROJECT_ID, "landing", 60, _NOW)

    assert result == []


def test_get_eligible_waste_objects_empty_bucket(monkeypatch):
    monkeypatch.setattr(repository, "list_bucket_objects_cached", lambda client, name: [])

    assert (
        repository.get_eligible_waste_objects(MagicMock(), _PROJECT_ID, "archive", 60, _NOW) == []
    )


def test_get_eligible_waste_objects_raises_storage_access_denied_on_forbidden(monkeypatch):
    def _raise(client, name):
        raise Forbidden("nope")

    monkeypatch.setattr(repository, "list_bucket_objects_cached", _raise)

    with pytest.raises(StorageAccessDeniedError):
        repository.get_eligible_waste_objects(MagicMock(), _PROJECT_ID, "landing", 60, _NOW)


def test_parse_resource_name_extracts_bucket_and_object():
    result = repository._parse_resource_name(
        "projects/_/buckets/landing/objects/crm_leads/2026-08-17/part-0001.csv"
    )
    assert result == ("landing", "crm_leads/2026-08-17/part-0001.csv")


def test_parse_resource_name_returns_none_for_bucket_only():
    assert repository._parse_resource_name("projects/_/buckets/landing") is None


def test_parse_resource_name_returns_none_for_empty():
    assert repository._parse_resource_name(None) is None
    assert repository._parse_resource_name("") is None


def test_browse_bucket_objects_returns_blobs_prefixes_and_next_token():
    client = MagicMock()
    blob = _blob_named("dt=2026-01-01/file.csv")
    iterator = MagicMock()
    iterator.pages = iter([[blob]])
    iterator.prefixes = {"dt=2026-01-02/", "dt=2026-01-01/"}
    iterator.next_page_token = "token-2"
    client.list_blobs.return_value = iterator

    blobs, prefixes, next_token = repository.browse_bucket_objects(
        client, _PROJECT_ID, "landing", prefix=None, page_token=None
    )

    assert blobs == [blob]
    assert prefixes == ["dt=2026-01-01/", "dt=2026-01-02/"]
    assert next_token == "token-2"
    client.list_blobs.assert_called_once_with(
        "landing", prefix=None, delimiter="/", page_token=None, max_results=100
    )


def test_browse_bucket_objects_returns_empty_when_no_more_pages():
    client = MagicMock()
    iterator = MagicMock()
    iterator.pages = iter([])
    iterator.prefixes = set()
    iterator.next_page_token = None
    client.list_blobs.return_value = iterator

    blobs, prefixes, next_token = repository.browse_bucket_objects(
        client, _PROJECT_ID, "landing", prefix=None, page_token=None
    )

    assert blobs == []
    assert prefixes == []
    assert next_token is None


def test_browse_bucket_objects_raises_storage_access_denied_on_forbidden_at_call():
    client = MagicMock()
    client.list_blobs.side_effect = Forbidden("denied")

    with pytest.raises(StorageAccessDeniedError):
        repository.browse_bucket_objects(client, _PROJECT_ID, "landing", None, None)


def test_browse_bucket_objects_raises_storage_access_denied_on_forbidden_during_iteration():
    def _raise_on_iter():
        raise Forbidden("denied")
        yield  # pragma: no cover

    client = MagicMock()
    iterator = MagicMock()
    iterator.pages = _raise_on_iter()
    client.list_blobs.return_value = iterator

    with pytest.raises(StorageAccessDeniedError):
        repository.browse_bucket_objects(client, _PROJECT_ID, "landing", None, None)


def test_scan_read_object_events_parses_object_get_events():
    client = MagicMock()
    ts = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
    read_payload = {
        "resourceName": "projects/_/buckets/landing/objects/crm_leads/part-0001.csv",
        "methodName": "storage.objects.get",
    }
    # entrada sem resourceName (ex: evento de bucket, não de objeto) é ignorada
    other_payload = {"methodName": "storage.buckets.getStorageLayout"}
    client.list_entries.return_value = [
        _entry(read_payload, ts),
        _entry(other_payload, ts),
        _entry(None, ts),
    ]

    result = repository.scan_read_object_events(client, _PROJECT_ID)

    assert result == {("landing", "crm_leads/part-0001.csv"): ts.isoformat()}


def test_scan_read_object_events_keeps_latest_timestamp_per_key():
    client = MagicMock()
    older = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)
    newer = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
    payload = {
        "resourceName": "projects/_/buckets/landing/objects/a.csv",
        "methodName": "storage.objects.get",
    }
    client.list_entries.return_value = [_entry(payload, older), _entry(payload, newer)]

    result = repository.scan_read_object_events(client, _PROJECT_ID)

    assert result == {("landing", "a.csv"): newer.isoformat()}


def test_scan_read_object_events_empty_when_no_entries():
    client = MagicMock()
    client.list_entries.return_value = []

    assert repository.scan_read_object_events(client, _PROJECT_ID) == {}


def test_scan_read_object_events_raises_logging_access_denied_on_forbidden():
    client = MagicMock()
    client.list_entries.side_effect = Forbidden("denied")

    with pytest.raises(LoggingAccessDeniedError):
        repository.scan_read_object_events(client, _PROJECT_ID)


def test_scan_read_object_events_full_scan_filter_uses_timestamp_floor():
    client = MagicMock()
    client.list_entries.return_value = []

    repository.scan_read_object_events(client, _PROJECT_ID, lookback_days=90)

    filter_ = client.list_entries.call_args.kwargs["filter_"]
    assert 'protoPayload.methodName="storage.objects.get"' in filter_
    assert 'timestamp>="' in filter_


def test_scan_read_object_events_incremental_filter_uses_receive_timestamp():
    client = MagicMock()
    client.list_entries.return_value = []
    anchor = datetime(2026, 8, 16, 3, 0, tzinfo=UTC)

    repository.scan_read_object_events(client, _PROJECT_ID, since_receive_ts=anchor)

    filter_ = client.list_entries.call_args.kwargs["filter_"]
    assert "receiveTimestamp>" in filter_
    assert 'timestamp>="' not in filter_


# --- serialize/deserialize_read_object_keys ---------------------------------


def test_serialize_deserialize_read_object_keys_round_trips():
    keys = {
        ("landing", "crm_leads/part-0001.csv"): "2026-08-15T12:00:00+00:00",
        ("processed", "exports/a.csv"): "2026-08-16T00:00:00+00:00",
    }

    round_tripped = repository._deserialize_read_object_keys(
        repository._serialize_read_object_keys(keys)
    )

    assert round_tripped == keys


def test_serialize_read_object_keys_empty_round_trips():
    round_tripped = repository._deserialize_read_object_keys(
        repository._serialize_read_object_keys({})
    )

    assert round_tripped == {}


def test_deserialize_read_object_keys_returns_none_for_old_set_format():
    """Blob no formato antigo (`[[bucket, objeto], ...]`, sem timestamp) —
    o job trata como "sem base incremental" e faz full scan."""
    import json

    old = json.dumps([["landing", "a.csv"], ["processed", "b.csv"]]).encode("utf-8")

    assert repository._deserialize_read_object_keys(old) is None


# --- get_read_object_keys_cached --------------------------------------------


def test_get_read_object_keys_cached_returns_cache_hit_keys_without_scanning(monkeypatch):
    logging_client = MagicMock()
    storage_client = MagicMock()
    firestore_client = MagicMock()
    cached = {("landing", "a.csv"): "2026-08-15T12:00:00+00:00"}
    monkeypatch.setattr(repository, "read_read_object_keys_cache", lambda *a, **kw: cached)

    result = repository.get_read_object_keys_cached(
        logging_client, storage_client, firestore_client, _PROJECT_ID
    )

    assert result == {("landing", "a.csv")}
    logging_client.list_entries.assert_not_called()


def test_get_read_object_keys_cached_raises_not_ready_and_records_project_on_miss(monkeypatch):
    """Modelo incremental: cache miss não escaneia mais ao vivo — registra
    o projeto (pro job pegá-lo) e levanta EventCacheNotReadyError, que
    domains/storage/service.py degrada pra warning best-effort."""
    logging_client = MagicMock()
    storage_client = MagicMock()
    firestore_client = MagicMock()
    monkeypatch.setattr(repository, "read_read_object_keys_cache", lambda *a, **kw: None)
    seen_calls = []
    monkeypatch.setattr(
        event_cache_module, "record_project_seen", lambda *a, **kw: seen_calls.append((a, kw))
    )

    with pytest.raises(EventCacheNotReadyError) as exc_info:
        repository.get_read_object_keys_cached(
            logging_client, storage_client, firestore_client, _PROJECT_ID
        )

    assert exc_info.value.project_id == _PROJECT_ID
    assert len(seen_calls) == 1
    logging_client.list_entries.assert_not_called()


def test_get_read_object_keys_cached_treats_cache_read_failure_as_miss(monkeypatch):
    """Falha ao LER o cache (ex: Forbidden no bucket) é logada e tratada
    como cache miss — EventCacheNotReadyError, nunca um 500 cru."""
    logging_client = MagicMock()
    storage_client = MagicMock()
    firestore_client = MagicMock()
    monkeypatch.setattr(
        repository,
        "read_read_object_keys_cache",
        lambda *a, **kw: (_ for _ in ()).throw(Forbidden("no access to bucket")),
    )
    monkeypatch.setattr(event_cache_module, "record_project_seen", lambda *a, **kw: None)

    with pytest.raises(EventCacheNotReadyError):
        repository.get_read_object_keys_cached(
            logging_client, storage_client, firestore_client, _PROJECT_ID
        )

    logging_client.list_entries.assert_not_called()
