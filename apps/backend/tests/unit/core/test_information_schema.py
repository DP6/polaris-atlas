from datetime import UTC, datetime
from unittest.mock import MagicMock

from google.api_core.exceptions import Forbidden, NotFound

from atlas.core import information_schema


def _row(**kwargs):
    """Fake de `bigquery.table.Row` — só precisa suportar `.get(field)`,
    que é tudo que `core/information_schema.py::_row_to_dict` usa. Um
    dict comum já serve (tem `.get` nativo)."""
    return kwargs


# --- list_recent_jobs -----------------------------------------------------


def test_list_recent_jobs_returns_empty_for_no_regions():
    assert information_schema.list_recent_jobs(MagicMock(), "proj", []) == []


def test_list_recent_jobs_merges_results_across_regions():
    client = MagicMock()

    def _query(sql, job_config=None):
        job = MagicMock()
        if "region-US" in sql:
            job.result.return_value = [_row(job_id="j1", user_email="a@x.com")]
        else:
            job.result.return_value = [_row(job_id="j2", user_email="b@x.com")]
        return job

    client.query.side_effect = _query

    rows = information_schema.list_recent_jobs(client, "proj", ["US", "EU"])

    assert {r["job_id"] for r in rows} == {"j1", "j2"}


def test_list_recent_jobs_uses_lookback_days_as_query_parameter():
    client = MagicMock()
    job = MagicMock()
    job.result.return_value = []
    client.query.return_value = job

    information_schema.list_recent_jobs(client, "proj", ["US"], lookback_days=45)

    _sql, kwargs = client.query.call_args
    params = kwargs["job_config"].query_parameters
    assert params[0].name == "lookback_days"
    assert params[0].value == 45


def test_list_recent_jobs_ignores_region_without_permission():
    client = MagicMock()

    def _query(sql, job_config=None):
        if "region-US" in sql:
            raise Forbidden("no access")
        job = MagicMock()
        job.result.return_value = [_row(job_id="j1")]
        return job

    client.query.side_effect = _query

    rows = information_schema.list_recent_jobs(client, "proj", ["US", "EU"])

    assert [r["job_id"] for r in rows] == ["j1"]


def test_list_recent_jobs_ignores_region_not_found():
    client = MagicMock()

    def _query(sql, job_config=None):
        if "region-US" in sql:
            raise NotFound("no jobs view yet")
        job = MagicMock()
        job.result.return_value = [_row(job_id="j1")]
        return job

    client.query.side_effect = _query

    rows = information_schema.list_recent_jobs(client, "proj", ["US", "EU"])

    assert [r["job_id"] for r in rows] == ["j1"]


# --- parse_table_ref_snake --------------------------------------------------


def test_parse_table_ref_snake_returns_tuple_for_complete_ref():
    ref = {"project_id": "p", "dataset_id": "d", "table_id": "t"}
    assert information_schema.parse_table_ref_snake(ref) == ("p", "d", "t")


def test_parse_table_ref_snake_returns_none_for_missing_field():
    assert information_schema.parse_table_ref_snake({"project_id": "p", "dataset_id": "d"}) is None


def test_parse_table_ref_snake_returns_none_for_none():
    assert information_schema.parse_table_ref_snake(None) is None


# --- most_recent_timestamp ---------------------------------------------------


def test_most_recent_timestamp_prefers_end_time():
    end = datetime(2026, 1, 1, tzinfo=UTC)
    start = datetime(2025, 1, 1, tzinfo=UTC)
    row = {"end_time": end, "start_time": start, "creation_time": start}
    assert information_schema.most_recent_timestamp(row) == end


def test_most_recent_timestamp_falls_back_to_start_time_then_creation_time():
    creation = datetime(2024, 1, 1, tzinfo=UTC)
    assert information_schema.most_recent_timestamp(
        {"end_time": None, "start_time": None, "creation_time": creation}
    ) == creation
    assert information_schema.most_recent_timestamp({}) is None
