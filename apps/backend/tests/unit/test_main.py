import json

from atlas import main
from atlas.core.exceptions import LoggingQuotaExceededError


def test_handle_logging_quota_exceeded_returns_503_with_retry_after():
    exc = LoggingQuotaExceededError("proj", retry_after=60)

    response = main.handle_logging_quota_exceeded(request=None, exc=exc)

    assert response.status_code == 503
    assert response.headers["retry-after"] == "60"
    body = json.loads(response.body)
    assert body["error"] == "logging_quota_exceeded"
    assert body["retry_after_seconds"] == 60


def test_handle_logging_quota_exceeded_honors_custom_retry_after():
    exc = LoggingQuotaExceededError("proj", retry_after=15)

    response = main.handle_logging_quota_exceeded(request=None, exc=exc)

    assert response.headers["retry-after"] == "15"
    assert json.loads(response.body)["retry_after_seconds"] == 15
