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
