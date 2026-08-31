from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import Forbidden

from observability_hub.core.exceptions import EventCacheNotReadyError
from observability_hub.domains.access import repository


def _entry(payload: dict | None):
    return SimpleNamespace(payload=payload)


# Mesmo payload real capturado em domains/lineage/tests, ver docstring de
# repository.py — reaproveitado aqui pra validar também o parsing de
# endTime (jobStatistics.endTime), que lineage não precisa.
REAL_CTAS_PROTO_PAYLOAD = {
    "authenticationInfo": {
        "oauthInfo": {"oauthClientId": "32555940559.apps.googleusercontent.com"},
        "principalEmail": "fuzatimatheus.cloud@gmail.com",
    },
    "methodName": "jobservice.jobcompleted",
    "serviceData": {
        "jobCompletedEvent": {
            "eventName": "query_job_completed",
            "job": {
                "jobConfiguration": {
                    "query": {
                        "destinationTable": {
                            "datasetId": "TRUSTED",
                            "projectId": "observability-hub-dev",
                            "tableId": "ga4_sessions",
                        },
                        "statementType": "CREATE_TABLE_AS_SELECT",
                    }
                },
                "jobName": {
                    "jobId": "bqjob_r5bf5dfa96120dc26_000001a000b0cfae_1",
                    "location": "US",
                    "projectId": "observability-hub-dev",
                },
                "jobStatistics": {
                    "createTime": "2026-08-14T14:33:03.171Z",
                    "endTime": "2026-08-14T14:33:05.199Z",
                    "referencedTables": [
                        {
                            "datasetId": "RAW",
                            "projectId": "observability-hub-dev",
                            "tableId": "ga4_events",
                        }
                    ],
                },
                "jobStatus": {"error": {}, "state": "DONE"},
            },
        }
    },
    "serviceName": "bigquery.googleapis.com",
}


# --- _parse_table_ref --------------------------------------------------------


def test_parse_table_ref_valid_format():
    result = repository._parse_table_ref(
        {"projectId": "proj", "datasetId": "RAW", "tableId": "crm_leads"}
    )
    assert result == ("proj", "RAW", "crm_leads")


@pytest.mark.parametrize(
    "ref",
    [
        None,
        {},
        {"projectId": "proj", "datasetId": "RAW"},
        {"projectId": "proj", "tableId": "crm_leads"},
        {"datasetId": "RAW", "tableId": "crm_leads"},
    ],
)
def test_parse_table_ref_returns_none_for_malformed_input(ref):
    assert repository._parse_table_ref(ref) is None


# --- _parse_timestamp ----------------------------------------------------------


def test_parse_timestamp_parses_iso_with_z_suffix():
    result = repository._parse_timestamp("2026-08-14T14:33:05.199Z")
    assert result == datetime(2026, 8, 14, 14, 33, 5, 199000, tzinfo=UTC)


@pytest.mark.parametrize("raw", [None, ""])
def test_parse_timestamp_returns_none_for_missing_value(raw):
    assert repository._parse_timestamp(raw) is None


def test_parse_timestamp_returns_none_for_malformed_value():
    assert repository._parse_timestamp("not-a-date") is None


# --- _parse_entry -------------------------------------------------------------


def test_parse_entry_extracts_fields_and_timestamp_from_real_payload():
    event = repository._parse_entry(_entry(REAL_CTAS_PROTO_PAYLOAD))

    assert event is not None
    assert event.job_id == "bqjob_r5bf5dfa96120dc26_000001a000b0cfae_1"
    assert event.principal_email == "fuzatimatheus.cloud@gmail.com"
    assert event.destination_table == ("observability-hub-dev", "TRUSTED", "ga4_sessions")
    assert event.referenced_tables == [("observability-hub-dev", "RAW", "ga4_events")]
    assert event.timestamp == datetime(2026, 8, 14, 14, 33, 5, 199000, tzinfo=UTC)


def test_parse_entry_treats_anonymous_dataset_destination_as_no_destination():
    payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobName": {"jobId": "job789", "location": "US", "projectId": "proj"},
                    "jobConfiguration": {
                        "query": {
                            "destinationTable": {
                                "projectId": "proj",
                                "datasetId": "_dc808a0dc9597042ed10aa06b088d1851477dbb9",
                                "tableId": "anon7160e641_c778_4dc8_8e1e_ec80da94a128",
                            }
                        }
                    },
                    "jobStatistics": {
                        "endTime": "2026-08-14T10:00:00Z",
                        "referencedTables": [
                            {"projectId": "proj", "datasetId": "TRUSTED", "tableId": "ga4_sessions"}
                        ],
                    },
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.destination_table is None
    assert event.referenced_tables == [("proj", "TRUSTED", "ga4_sessions")]


def test_parse_entry_returns_none_when_payload_is_not_a_dict():
    assert repository._parse_entry(_entry(None)) is None
    assert repository._parse_entry(_entry("not a dict")) is None


def test_parse_entry_returns_none_when_job_completed_event_missing():
    assert repository._parse_entry(_entry({"serviceData": {}})) is None
    assert repository._parse_entry(_entry({})) is None


def test_parse_entry_handles_missing_end_time():
    payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobName": {"jobId": "job1", "location": "US", "projectId": "proj"},
                    "jobStatistics": {"referencedTables": []},
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.timestamp is None


# --- parse_access_events ------------------------------------------------------
#
# list_access_events foi removida no modelo de cache incremental — o
# request path não escaneia mais o Cloud Logging ao vivo, quem escaneia é
# jobs/refresh_event_cache.py (que passa entradas cruas pra parse_*).


def test_parse_access_events_is_pure_and_skips_invalid_entries():
    valid_payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobName": {"jobId": "job1"},
                    "jobStatistics": {"endTime": "2026-08-14T10:00:00Z", "referencedTables": []},
                }
            }
        }
    }

    events = repository.parse_access_events([_entry(valid_payload), _entry(None), _entry({})])

    assert [e.job_id for e in events] == ["job1"]


# --- serialize/deserialize_access_events ----------------------------------------


def test_serialize_deserialize_access_events_round_trips():
    events = [
        repository.AccessEvent(
            job_id="job1",
            principal_email="a@dp6.com.br",
            timestamp=datetime(2026, 8, 14, 10, 0, tzinfo=UTC),
            referenced_tables=[("proj", "RAW", "a")],
            destination_table=("proj", "GOLD", "b"),
        )
    ]

    round_tripped = repository.deserialize_access_events(repository.serialize_access_events(events))

    assert round_tripped == events


def test_deserialize_access_events_handles_no_timestamp():
    events = [
        repository.AccessEvent(
            job_id="job1",
            principal_email="a@dp6.com.br",
            timestamp=None,
            referenced_tables=[],
            destination_table=None,
        )
    ]

    round_tripped = repository.deserialize_access_events(repository.serialize_access_events(events))

    assert round_tripped[0].timestamp is None


# --- get_access_events_cached ----------------------------------------------------


def test_get_access_events_cached_returns_cache_hit_without_calling_list_entries(monkeypatch):
    client = MagicMock()
    storage_client = MagicMock()
    firestore_client = MagicMock()
    cached_events = [
        repository.AccessEvent(
            job_id="cached-job",
            principal_email="a@dp6.com.br",
            timestamp=None,
            referenced_tables=[],
            destination_table=None,
        )
    ]
    cached_at = object()
    monkeypatch.setattr(
        repository, "read_access_events_cache", lambda *a, **kw: (cached_events, cached_at)
    )

    events, returned_cached_at = repository.get_access_events_cached(
        client, storage_client, firestore_client, "proj"
    )

    assert events == cached_events
    assert returned_cached_at is cached_at
    client.list_entries.assert_not_called()


def test_get_access_events_cached_raises_not_ready_on_miss(monkeypatch):
    """Modelo incremental: cache miss não escaneia mais ao vivo — levanta
    EventCacheNotReadyError, que o service degrada pra resposta vazia com
    warning."""
    client = MagicMock()
    storage_client = MagicMock()
    firestore_client = MagicMock()
    monkeypatch.setattr(repository, "read_access_events_cache", lambda *a, **kw: None)

    with pytest.raises(EventCacheNotReadyError) as exc_info:
        repository.get_access_events_cached(client, storage_client, firestore_client, "proj")

    assert exc_info.value.project_id == "proj"
    client.list_entries.assert_not_called()


def test_get_access_events_cached_treats_cache_read_failure_as_miss(monkeypatch):
    """Regressão real: bucket sem IAM pra SA de runtime levantava
    Forbidden (não capturado por read_cache_bytes, que só trata NotFound).
    Falha ao LER o cache é logada e tratada como cache miss —
    EventCacheNotReadyError, nunca um 500 cru."""
    client = MagicMock()
    storage_client = MagicMock()
    firestore_client = MagicMock()
    monkeypatch.setattr(
        repository,
        "read_access_events_cache",
        lambda *a, **kw: (_ for _ in ()).throw(Forbidden("no access to bucket")),
    )

    with pytest.raises(EventCacheNotReadyError):
        repository.get_access_events_cached(client, storage_client, firestore_client, "proj")

    client.list_entries.assert_not_called()
