from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import Forbidden, GoogleAPICallError

from observability_hub.core.exceptions import (
    EventCacheNotReadyError,
    ProjectAccessDeniedError,
)
from observability_hub.domains.finops import repository


def _row(**kwargs):
    return SimpleNamespace(**kwargs)


def _entry(payload: dict | None):
    return SimpleNamespace(payload=payload)


# --- _parse_table_ref --------------------------------------------------------


def test_parse_table_ref_valid_format():
    result = repository._parse_table_ref(
        {"projectId": "proj", "datasetId": "RAW", "tableId": "crm_leads"}
    )
    assert result == ("proj", "RAW", "crm_leads")


@pytest.mark.parametrize("ref", [None, {}, {"projectId": "proj", "datasetId": "RAW"}])
def test_parse_table_ref_returns_none_for_malformed_input(ref):
    assert repository._parse_table_ref(ref) is None


@pytest.mark.parametrize(
    "table_id",
    [
        "INFORMATION_SCHEMA.SCHEMATA",
        "INFORMATION_SCHEMA.TABLES",
        "INFORMATION_SCHEMA.TABLE_STORAGE",
    ],
)
def test_parse_table_ref_filters_information_schema_probes(table_id):
    # discover_regions/list_all_table_refs/get_date_like_columns do
    # próprio Hub rodam `project.region-X.INFORMATION_SCHEMA.*` — o audit
    # log real captura isso como datasetId="region-US" (ou outra região),
    # tableId="INFORMATION_SCHEMA.SCHEMATA" etc. Sem o filtro, isso
    # aparece como se "region-US" fosse um dataset real de cliente no
    # budget (bug real encontrado em dev).
    result = repository._parse_table_ref(
        {"projectId": "proj", "datasetId": "region-US", "tableId": table_id}
    )
    assert result is None


# --- _parse_timestamp / _parse_billed_bytes -------------------------------------


def test_parse_timestamp_parses_iso_with_z_suffix():
    from datetime import UTC, datetime

    assert repository._parse_timestamp("2026-08-14T14:33:05.199Z") == datetime(
        2026, 8, 14, 14, 33, 5, 199000, tzinfo=UTC
    )


@pytest.mark.parametrize("raw", [None, "", "not-a-date"])
def test_parse_timestamp_returns_none_for_missing_or_malformed_value(raw):
    assert repository._parse_timestamp(raw) is None


def test_parse_billed_bytes_parses_numeric_string():
    assert repository._parse_billed_bytes("10485760") == 10485760


@pytest.mark.parametrize("raw", [None, "", "not-a-number"])
def test_parse_billed_bytes_returns_zero_for_missing_or_malformed_value(raw):
    assert repository._parse_billed_bytes(raw) == 0


# --- _parse_entry -------------------------------------------------------------


def test_parse_entry_extracts_referenced_tables_timestamp_and_billed_bytes():
    payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobStatistics": {
                        "endTime": "2026-08-14T14:33:05.199Z",
                        "totalBilledBytes": "10485760",
                        "referencedTables": [
                            {"projectId": "proj", "datasetId": "RAW", "tableId": "ga4_events"}
                        ],
                    }
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.referenced_tables == [("proj", "RAW", "ga4_events")]
    assert event.total_billed_bytes == 10485760
    assert event.timestamp is not None


def test_parse_entry_extracts_job_id_principal_and_query_text():
    payload = {
        "authenticationInfo": {"principalEmail": "ana@dp6.com.br"},
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobName": {"jobId": "job-123", "location": "US", "projectId": "proj"},
                    "jobConfiguration": {"query": {"query": "SELECT 1"}},
                    "jobStatistics": {"endTime": "2026-08-14T10:00:00Z", "referencedTables": []},
                }
            }
        },
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.job_id == "job-123"
    assert event.principal_email == "ana@dp6.com.br"
    assert event.query_text == "SELECT 1"


def test_parse_entry_truncates_long_query_text():
    long_query = "SELECT " + "x" * 3000
    payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobConfiguration": {"query": {"query": long_query}},
                    "jobStatistics": {"referencedTables": []},
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.query_text is not None
    assert len(event.query_text) == repository._QUERY_TEXT_MAX_CHARS + 1  # +1 do "…"
    assert event.query_text.endswith("…")


def test_parse_entry_query_text_is_none_when_missing():
    payload = {
        "serviceData": {"jobCompletedEvent": {"job": {"jobStatistics": {"referencedTables": []}}}}
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.query_text is None


def test_parse_entry_defaults_billed_bytes_to_zero_when_missing():
    payload = {
        "serviceData": {
            "jobCompletedEvent": {
                "job": {
                    "jobStatistics": {"endTime": "2026-08-14T10:00:00Z", "referencedTables": []}
                }
            }
        }
    }

    event = repository._parse_entry(_entry(payload))

    assert event is not None
    assert event.total_billed_bytes == 0


def test_parse_entry_returns_none_when_payload_is_not_a_dict():
    assert repository._parse_entry(_entry(None)) is None


def test_parse_entry_returns_none_when_job_completed_event_missing():
    assert repository._parse_entry(_entry({})) is None


# --- parse_scan_events -------------------------------------------------------
#
# list_scan_events foi removida no modelo de cache incremental — o request
# path não escaneia mais o Cloud Logging ao vivo, quem escaneia é
# jobs/refresh_event_cache.py (que passa entradas cruas pra parse_*).


def test_parse_scan_events_is_pure_and_skips_invalid_entries():
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

    events = repository.parse_scan_events([_entry(valid_payload), _entry(None), _entry({})])

    assert [e.job_id for e in events] == ["job1"]


# --- serialize/deserialize_scan_events ----------------------------------------


def test_serialize_deserialize_scan_events_round_trips():
    events = [
        repository.ScanEvent(
            timestamp=datetime(2026, 8, 14, 10, 0, tzinfo=UTC),
            referenced_tables=[("proj", "RAW", "a"), ("proj", "GOLD", "b")],
            total_billed_bytes=10485760,
            job_id="job1",
            principal_email="ana@dp6.com.br",
            query_text="SELECT 1",
        )
    ]

    round_tripped = repository.deserialize_scan_events(repository.serialize_scan_events(events))

    assert round_tripped == events


def test_deserialize_scan_events_handles_no_timestamp_and_no_query_text():
    events = [
        repository.ScanEvent(
            timestamp=None,
            referenced_tables=[],
            total_billed_bytes=0,
            job_id="job1",
            principal_email="ana@dp6.com.br",
            query_text=None,
        )
    ]

    round_tripped = repository.deserialize_scan_events(repository.serialize_scan_events(events))

    assert round_tripped == events
    assert round_tripped[0].timestamp is None
    assert round_tripped[0].query_text is None


# --- get_scan_events_cached --------------------------------------------------


def _scan_event(job_id="job1"):
    return repository.ScanEvent(
        timestamp=datetime(2026, 8, 14, 10, 0, tzinfo=UTC),
        referenced_tables=[],
        total_billed_bytes=0,
        job_id=job_id,
        principal_email="ana@dp6.com.br",
        query_text=None,
    )


def test_get_scan_events_cached_returns_cache_hit_without_calling_list_entries(monkeypatch):
    client = MagicMock()
    cached_events = [_scan_event("cached-job")]
    cached_at = object()
    monkeypatch.setattr(
        repository, "read_scan_events_cache", lambda *a, **kw: (cached_events, cached_at)
    )

    events, returned_cached_at = repository.get_scan_events_cached(
        client, MagicMock(), MagicMock(), "proj"
    )

    assert events == cached_events
    assert returned_cached_at is cached_at
    client.list_entries.assert_not_called()


def test_get_scan_events_cached_raises_not_ready_on_miss(monkeypatch):
    """Modelo incremental: cache miss não escaneia mais ao vivo — levanta
    EventCacheNotReadyError, que domains/finops/service.py degrada pra
    resposta vazia com warning."""
    client = MagicMock()
    monkeypatch.setattr(repository, "read_scan_events_cache", lambda *a, **kw: None)

    with pytest.raises(EventCacheNotReadyError) as exc_info:
        repository.get_scan_events_cached(client, MagicMock(), MagicMock(), "proj")

    assert exc_info.value.project_id == "proj"
    client.list_entries.assert_not_called()


def test_get_scan_events_cached_treats_cache_read_failure_as_miss(monkeypatch):
    """Falha ao LER o cache (bucket sem IAM -> Forbidden, não tratado por
    read_cache_bytes que só pega NotFound) é logada e tratada como cache
    miss — EventCacheNotReadyError, nunca um 500 cru."""
    client = MagicMock()
    monkeypatch.setattr(
        repository,
        "read_scan_events_cache",
        lambda *a, **kw: (_ for _ in ()).throw(Forbidden("no access to bucket")),
    )

    with pytest.raises(EventCacheNotReadyError):
        repository.get_scan_events_cached(client, MagicMock(), MagicMock(), "proj")

    client.list_entries.assert_not_called()


# --- list_all_table_refs -------------------------------------------------------


def test_list_all_table_refs_returns_empty_for_no_regions():
    client = MagicMock()
    assert repository.list_all_table_refs(client, "proj", []) == []


def test_list_all_table_refs_merges_results_across_regions():
    client = MagicMock()

    def _query(sql, job_config=None):
        result = MagicMock()
        if "region-US" in sql:
            result.result.return_value = [SimpleNamespace(dataset_id="RAW", table_id="crm_leads")]
        else:
            result.result.return_value = [
                SimpleNamespace(dataset_id="RAW", table_id="crm_accounts")
            ]
        return result

    client.query.side_effect = _query

    refs = repository.list_all_table_refs(client, "proj", ["US", "EU"])

    assert set(refs) == {("RAW", "crm_leads"), ("RAW", "crm_accounts")}


def test_list_all_table_refs_filters_by_dataset_when_provided():
    client = MagicMock()
    result = MagicMock()
    result.result.return_value = [SimpleNamespace(dataset_id="RAW", table_id="crm_leads")]
    client.query.return_value = result

    repository.list_all_table_refs(client, "proj", ["US"], datasets=["RAW"])

    called_sql, called_kwargs = client.query.call_args
    assert "WHERE table_schema IN UNNEST(@datasets)" in called_sql[0]
    assert called_kwargs["job_config"].query_parameters[0].values == ["RAW"]


def test_list_all_table_refs_no_filter_when_datasets_not_provided():
    client = MagicMock()
    result = MagicMock()
    result.result.return_value = []
    client.query.return_value = result

    repository.list_all_table_refs(client, "proj", ["US"])

    called_sql, called_kwargs = client.query.call_args
    assert "WHERE" not in called_sql[0]
    assert called_kwargs["job_config"] is None


# --- get_current_storage_bytes -----------------------------------------------


def _bytes_row(logical_bytes):
    return SimpleNamespace(logical_bytes=logical_bytes)


def test_get_current_storage_bytes_returns_reason_for_no_regions():
    total, reason = repository.get_current_storage_bytes(MagicMock(), "proj", [])
    assert total is None
    assert reason is not None


def test_get_current_storage_bytes_uses_lowercase_region_and_table_storage_view():
    client = MagicMock()
    result = MagicMock()
    result.result.return_value = [_bytes_row(10)]
    client.query.return_value = result

    repository.get_current_storage_bytes(client, "proj", ["US"])

    called_sql = client.query.call_args[0][0]
    assert "region-us.INFORMATION_SCHEMA.TABLE_STORAGE`" in called_sql
    assert "region-US" not in called_sql
    assert "total_logical_bytes" in called_sql


def test_get_current_storage_bytes_sums_across_regions():
    client = MagicMock()

    def _query(sql, job_config=None):
        result = MagicMock()
        result.result.return_value = [_bytes_row(100 if "region-us." in sql else 25)]
        return result

    client.query.side_effect = _query

    total, reason = repository.get_current_storage_bytes(client, "proj", ["US", "EU"])

    assert total == 125
    assert reason is None


def test_get_current_storage_bytes_returns_reason_when_all_regions_fail():
    client = MagicMock()
    client.query.side_effect = GoogleAPICallError("400 Unrecognized name: foo")

    total, reason = repository.get_current_storage_bytes(client, "proj", ["US", "EU"])

    assert total is None
    assert "Unrecognized name" in reason


def test_get_current_storage_bytes_tolerates_one_failing_region():
    client = MagicMock()

    def _query(sql, job_config=None):
        if "region-eu." in sql:
            raise GoogleAPICallError("boom")
        result = MagicMock()
        result.result.return_value = [_bytes_row(7)]
        return result

    client.query.side_effect = _query

    total, reason = repository.get_current_storage_bytes(client, "proj", ["US", "EU"])

    assert total == 7
    assert reason is None


def test_get_current_storage_bytes_passes_dataset_and_table_filters_as_params():
    client = MagicMock()
    result = MagicMock()
    result.result.return_value = [_bytes_row(0)]
    client.query.return_value = result

    repository.get_current_storage_bytes(
        client, "proj", ["US"], datasets=["RAW"], tables=["RAW.events"]
    )

    called_sql, called_kwargs = client.query.call_args
    assert "table_schema IN UNNEST(@datasets)" in called_sql[0]
    assert "CONCAT(table_schema, '.', table_name) IN UNNEST(@tables)" in called_sql[0]
    param_names = {p.name for p in called_kwargs["job_config"].query_parameters}
    assert param_names == {"datasets", "tables"}


# --- get_date_like_columns -------------------------------------------------------


def test_get_date_like_columns_returns_column_names():
    client = MagicMock()
    result = MagicMock()
    result.result.return_value = [
        SimpleNamespace(column_name="event_date"),
        SimpleNamespace(column_name="created_at"),
    ]
    client.query.return_value = result

    columns = repository.get_date_like_columns(client, "proj", "RAW", "crm_leads", "US")

    assert columns == ["event_date", "created_at"]
    call_args = client.query.call_args
    assert "INFORMATION_SCHEMA.COLUMNS" in call_args.args[0]
    job_config = call_args.kwargs["job_config"]
    param_names = {p.name for p in job_config.query_parameters}
    assert param_names == {"dataset_id", "table_id", "date_like_types"}


# --- get_string_columns -----------------------------------------------------------


def test_get_string_columns_returns_column_names():
    client = MagicMock()
    result = MagicMock()
    result.result.return_value = [
        _row(column_name="customer_id"),
        _row(column_name="signup_date_raw"),
    ]
    client.query.return_value = result

    columns = repository.get_string_columns(client, "proj", "RAW", "crm_leads", "US")

    assert columns == ["customer_id", "signup_date_raw"]
    call_args = client.query.call_args
    assert "INFORMATION_SCHEMA.COLUMNS" in call_args.args[0]
    assert "data_type = 'STRING'" in call_args.args[0]


def test_get_string_columns_returns_empty_list_when_no_string_columns():
    client = MagicMock()
    client.query.return_value.result.return_value = []

    assert repository.get_string_columns(client, "proj", "RAW", "crm_leads", "US") == []


# --- is_view (finops) -------------------------------------------------------------


def test_is_view_true_for_view_table_type():
    client = MagicMock()
    client.query.return_value.result.return_value = [_row(table_type="VIEW")]

    assert repository.is_view(client, "proj", "RAW", "leads", "US") is True


def test_is_view_true_for_materialized_view_table_type():
    client = MagicMock()
    client.query.return_value.result.return_value = [_row(table_type="MATERIALIZED VIEW")]

    assert repository.is_view(client, "proj", "RAW", "leads", "US") is True


def test_is_view_false_for_base_table_type():
    client = MagicMock()
    client.query.return_value.result.return_value = [_row(table_type="BASE TABLE")]

    assert repository.is_view(client, "proj", "RAW", "leads", "US") is False


def test_is_view_false_when_no_rows_found():
    client = MagicMock()
    client.query.return_value.result.return_value = []

    assert repository.is_view(client, "proj", "RAW", "ghost", "US") is False


# --- dry_run (finops) --------------------------------------------------------------


def test_dry_run_uses_dry_run_job_config_and_returns_bytes():
    captured = {}

    def fake_query(sql, job_config=None):
        captured["job_config"] = job_config
        return SimpleNamespace(total_bytes_processed=12345)

    client = MagicMock()
    client.query.side_effect = fake_query

    result = repository.dry_run(client, "proj", "SELECT 1")

    assert result == 12345
    assert captured["job_config"].dry_run is True


def test_dry_run_raises_project_access_denied_on_forbidden():
    client = MagicMock()
    client.query.side_effect = Forbidden("Access Denied")

    with pytest.raises(ProjectAccessDeniedError) as exc_info:
        repository.dry_run(client, "proj", "SELECT 1")

    assert exc_info.value.project_id == "proj"


# --- execute_scan_query (finops) ----------------------------------------------------


def test_execute_scan_query_returns_first_row_as_dict():
    row = {"customer_id__non_null": 950, "customer_id__INT64": 950}
    client = MagicMock()
    client.query.return_value.result.return_value = [row]

    result = repository.execute_scan_query(client, "proj", "SELECT ...", timeout=60.0)

    assert result == row


def test_execute_scan_query_raises_project_access_denied_on_forbidden():
    client = MagicMock()
    client.query.side_effect = Forbidden("Access Denied")

    with pytest.raises(ProjectAccessDeniedError) as exc_info:
        repository.execute_scan_query(client, "proj", "SELECT ...", timeout=60.0)

    assert exc_info.value.project_id == "proj"
