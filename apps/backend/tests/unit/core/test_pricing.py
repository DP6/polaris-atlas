from datetime import UTC, datetime, timedelta

from observability_hub.core import pricing
from observability_hub.core.config import settings


def test_estimate_bigquery_storage_cost_usd_uses_active_price_for_recently_modified():
    modified = datetime.now(UTC) - timedelta(days=10)
    now = datetime.now(UTC)

    result = pricing.estimate_bigquery_storage_cost_usd(1024**3, modified, now)

    assert result == round(settings.bigquery_storage_price_usd_per_gb_month_active, 4)


def test_estimate_bigquery_storage_cost_usd_uses_long_term_price_for_old_table():
    modified = datetime.now(UTC) - timedelta(days=120)
    now = datetime.now(UTC)

    result = pricing.estimate_bigquery_storage_cost_usd(1024**3, modified, now)

    assert result == round(settings.bigquery_storage_price_usd_per_gb_month_long_term, 4)


def test_estimate_bigquery_storage_cost_usd_uses_active_price_when_modified_is_none():
    now = datetime.now(UTC)

    result = pricing.estimate_bigquery_storage_cost_usd(1024**3, None, now)

    assert result == round(settings.bigquery_storage_price_usd_per_gb_month_active, 4)


def test_estimate_bigquery_storage_cost_usd_zero_bytes_is_zero_cost():
    now = datetime.now(UTC)

    result = pricing.estimate_bigquery_storage_cost_usd(0, None, now)

    assert result == 0.0
