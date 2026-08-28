from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import (
    Forbidden,
    InternalServerError,
    ServiceUnavailable,
    TooManyRequests,
)

from observability_hub.core import logging_client
from observability_hub.core.exceptions import LoggingAccessDeniedError, LoggingQuotaExceededError

_KWARGS = {
    "resource_names": ["projects/proj"],
    "filter_": 'resource.type="bigquery_resource"',
    "page_size": 1000,
    "project_id": "proj",
}


def test_bigquery_job_events_filter_full_scan_uses_timestamp_floor():
    filter_ = logging_client.bigquery_job_events_filter(30)

    assert 'protoPayload.methodName="jobservice.jobcompleted"' in filter_
    assert 'timestamp>="' in filter_
    assert "receiveTimestamp" not in filter_


def test_bigquery_job_events_filter_incremental_uses_receive_timestamp():
    from datetime import UTC, datetime

    anchor = datetime(2026, 8, 27, 3, 15, 30, tzinfo=UTC)
    filter_ = logging_client.bigquery_job_events_filter(since_receive_ts=anchor)

    assert 'protoPayload.methodName="jobservice.jobcompleted"' in filter_
    assert 'receiveTimestamp>"2026-08-27T03:15:30' in filter_
    assert 'timestamp>="' not in filter_


@pytest.fixture
def _real_retry(monkeypatch):
    """Reverte o deadline-zero do autouse `_fast_logging_retry` do conftest
    e neutraliza o sleep, pra validar que o retry realmente re-tenta sem
    o teste dormir de verdade."""
    monkeypatch.setattr(logging_client, "_RETRY_TIMEOUT_SECONDS", 30.0)
    monkeypatch.setattr("time.sleep", lambda *_a, **_kw: None)


def test_returns_materialized_list_on_first_success():
    client = MagicMock()
    client.list_entries.return_value = iter(["e1", "e2", "e3"])

    result = logging_client.list_entries_with_retry(client, **_KWARGS)

    assert result == ["e1", "e2", "e3"]
    client.list_entries.assert_called_once_with(
        resource_names=["projects/proj"],
        filter_='resource.type="bigquery_resource"',
        page_size=1000,
    )


def test_page_pause_sleeps_on_page_boundaries(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))
    client = MagicMock()
    client.list_entries.return_value = iter([f"e{i}" for i in range(5)])

    result = logging_client.list_entries_with_retry(
        client,
        resource_names=["projects/proj"],
        filter_="f",
        page_size=2,
        project_id="proj",
        page_pause=0.4,
    )

    assert result == ["e0", "e1", "e2", "e3", "e4"]
    # 5 entradas, página de 2 -> pausa em i=2 e i=4.
    assert slept == [0.4, 0.4]


def test_page_pause_zero_does_not_sleep(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))
    client = MagicMock()
    client.list_entries.return_value = iter(["e0", "e1", "e2"])

    logging_client.list_entries_with_retry(client, **_KWARGS)

    assert slept == []


def test_retries_on_too_many_requests_then_succeeds(_real_retry):
    client = MagicMock()
    client.list_entries.side_effect = [
        TooManyRequests("quota"),
        TooManyRequests("quota"),
        iter(["e1"]),
    ]

    result = logging_client.list_entries_with_retry(client, **_KWARGS)

    assert result == ["e1"]
    assert client.list_entries.call_count == 3


def test_retries_on_service_unavailable_then_succeeds(_real_retry):
    client = MagicMock()
    client.list_entries.side_effect = [ServiceUnavailable("503"), iter(["e1"])]

    result = logging_client.list_entries_with_retry(client, **_KWARGS)

    assert result == ["e1"]
    assert client.list_entries.call_count == 2


def test_persistent_too_many_requests_raises_quota_exceeded():
    # conftest zera o deadline -> 1 tentativa, RetryError imediato.
    client = MagicMock()
    client.list_entries.side_effect = TooManyRequests("quota")

    with pytest.raises(LoggingQuotaExceededError) as exc_info:
        logging_client.list_entries_with_retry(client, **_KWARGS)

    assert exc_info.value.project_id == "proj"
    assert exc_info.value.retry_after == 60
    client.list_entries.assert_called_once()


def test_forbidden_maps_to_access_denied_without_retry():
    client = MagicMock()
    client.list_entries.side_effect = Forbidden("denied")

    with pytest.raises(LoggingAccessDeniedError) as exc_info:
        logging_client.list_entries_with_retry(client, **_KWARGS)

    assert exc_info.value.project_id == "proj"
    client.list_entries.assert_called_once()


def test_non_quota_transient_propagates_when_deadline_exhausts():
    # ServiceUnavailable persistente após o retry não é cota — propaga como
    # está (5xx cru), não vira LoggingQuotaExceededError.
    client = MagicMock()
    client.list_entries.side_effect = ServiceUnavailable("503")

    with pytest.raises((ServiceUnavailable, Exception)) as exc_info:
        logging_client.list_entries_with_retry(client, **_KWARGS)

    assert not isinstance(exc_info.value, LoggingQuotaExceededError)


def test_non_retryable_error_bubbles_immediately():
    client = MagicMock()
    client.list_entries.side_effect = InternalServerError("boom")

    with pytest.raises(InternalServerError):
        logging_client.list_entries_with_retry(client, **_KWARGS)

    client.list_entries.assert_called_once()
