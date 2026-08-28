from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import Forbidden, TooManyRequests

from observability_hub.core import event_cache as event_cache_module
from observability_hub.core.exceptions import (
    LoggingAccessDeniedError,
    LoggingQuotaExceededError,
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


def _entry(payload):
    return SimpleNamespace(payload=payload)


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


def test_list_read_object_keys_parses_object_get_events():
    client = MagicMock()
    read_payload = {
        "resourceName": "projects/_/buckets/landing/objects/crm_leads/part-0001.csv",
        "methodName": "storage.objects.get",
    }
    # entrada sem resourceName (ex: evento de bucket, não de objeto) é ignorada
    other_payload = {"methodName": "storage.buckets.getStorageLayout"}
    client.list_entries.return_value = [_entry(read_payload), _entry(other_payload), _entry(None)]

    result = repository.list_read_object_keys(client, _PROJECT_ID, 90)

    assert result == {("landing", "crm_leads/part-0001.csv")}


def test_list_read_object_keys_empty_when_no_entries():
    client = MagicMock()
    client.list_entries.return_value = []

    assert repository.list_read_object_keys(client, _PROJECT_ID, 90) == set()


def test_list_read_object_keys_raises_logging_access_denied_on_forbidden():
    client = MagicMock()
    client.list_entries.side_effect = Forbidden("denied")

    with pytest.raises(LoggingAccessDeniedError):
        repository.list_read_object_keys(client, _PROJECT_ID, 90)


# --- serialize/deserialize_read_object_keys ---------------------------------


def test_serialize_deserialize_read_object_keys_round_trips():
    keys = {("landing", "crm_leads/part-0001.csv"), ("processed", "exports/a.csv")}

    round_tripped = repository._deserialize_read_object_keys(
        repository._serialize_read_object_keys(keys)
    )

    assert round_tripped == keys


def test_serialize_read_object_keys_empty_set_round_trips():
    round_tripped = repository._deserialize_read_object_keys(
        repository._serialize_read_object_keys(set())
    )

    assert round_tripped == set()


# --- get_read_object_keys_cached --------------------------------------------


def test_get_read_object_keys_cached_returns_cache_hit_without_scanning(monkeypatch):
    logging_client = MagicMock()
    storage_client = MagicMock()
    firestore_client = MagicMock()
    cached_keys = {("landing", "a.csv")}
    monkeypatch.setattr(repository, "read_read_object_keys_cache", lambda *a, **kw: cached_keys)

    result = repository.get_read_object_keys_cached(
        logging_client, storage_client, firestore_client, _PROJECT_ID
    )

    assert result == cached_keys
    logging_client.list_entries.assert_not_called()


def test_get_read_object_keys_cached_falls_back_and_writes_cache_on_miss(monkeypatch):
    logging_client = MagicMock()
    logging_client.list_entries.return_value = []
    storage_client = MagicMock()
    firestore_client = MagicMock()
    monkeypatch.setattr(repository, "read_read_object_keys_cache", lambda *a, **kw: None)
    write_calls = []
    monkeypatch.setattr(
        repository, "write_read_object_keys_cache", lambda *a, **kw: write_calls.append((a, kw))
    )
    seen_calls = []
    monkeypatch.setattr(
        event_cache_module, "record_project_seen", lambda *a, **kw: seen_calls.append((a, kw))
    )

    result = repository.get_read_object_keys_cached(
        logging_client, storage_client, firestore_client, _PROJECT_ID
    )

    assert result == set()
    logging_client.list_entries.assert_called_once()
    assert len(write_calls) == 1
    assert len(seen_calls) == 1


def test_get_read_object_keys_cached_falls_back_to_live_scan_when_cache_read_fails(monkeypatch):
    """Falha ao LER o cache (ex: Forbidden no bucket) nunca deve impedir
    o scan ao vivo — mesmo racional de
    domains/access/repository.py::get_access_events_cached."""
    logging_client = MagicMock()
    logging_client.list_entries.return_value = []
    storage_client = MagicMock()
    firestore_client = MagicMock()
    monkeypatch.setattr(
        repository,
        "read_read_object_keys_cache",
        lambda *a, **kw: (_ for _ in ()).throw(Forbidden("no access to bucket")),
    )
    monkeypatch.setattr(repository, "write_read_object_keys_cache", lambda *a, **kw: None)

    result = repository.get_read_object_keys_cached(
        logging_client, storage_client, firestore_client, _PROJECT_ID
    )

    assert result == set()
    logging_client.list_entries.assert_called_once()


def test_get_read_object_keys_cached_returns_live_data_when_cache_write_fails(monkeypatch):
    """Falha ao GRAVAR o cache não pode impedir a resposta de conter o
    resultado do scan ao vivo que já foi feito."""
    logging_client = MagicMock()
    logging_client.list_entries.return_value = []
    storage_client = MagicMock()
    firestore_client = MagicMock()
    live_keys = {("landing", "a.csv")}
    monkeypatch.setattr(repository, "read_read_object_keys_cache", lambda *a, **kw: None)
    monkeypatch.setattr(repository, "list_read_object_keys", lambda *a, **kw: live_keys)

    def _raise_write(*a, **kw):
        raise Forbidden("no access to bucket")

    monkeypatch.setattr(repository, "write_read_object_keys_cache", _raise_write)

    result = repository.get_read_object_keys_cached(
        logging_client, storage_client, firestore_client, _PROJECT_ID
    )

    assert result == live_keys


def test_get_read_object_keys_cached_propagates_logging_access_denied_from_live_scan(monkeypatch):
    """Diferente de falha ao ler/gravar cache (engolida), falta de acesso
    ao Cloud Logging no scan ao vivo deve propagar — quem chama
    (domains/storage/service.py) decide como comunicar isso."""
    logging_client = MagicMock()
    logging_client.list_entries.side_effect = Forbidden("denied")
    storage_client = MagicMock()
    firestore_client = MagicMock()
    monkeypatch.setattr(repository, "read_read_object_keys_cache", lambda *a, **kw: None)

    with pytest.raises(LoggingAccessDeniedError):
        repository.get_read_object_keys_cached(
            logging_client, storage_client, firestore_client, _PROJECT_ID
        )


def test_get_read_object_keys_cached_raises_quota_exceeded_on_too_many_requests(monkeypatch):
    """429 no scan ao vivo (cota read_requests/min do projeto) vira
    LoggingQuotaExceededError — quem chama (service) degrada pra warning."""
    logging_client = MagicMock()
    logging_client.list_entries.side_effect = TooManyRequests("quota exceeded")
    monkeypatch.setattr(repository, "read_read_object_keys_cache", lambda *a, **kw: None)

    with pytest.raises(LoggingQuotaExceededError) as exc_info:
        repository.get_read_object_keys_cached(
            logging_client, MagicMock(), MagicMock(), _PROJECT_ID
        )

    assert exc_info.value.project_id == _PROJECT_ID
