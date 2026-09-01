from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from observability_hub.domains.budget import service
from observability_hub.domains.budget.schemas import BudgetScope, BudgetUpsertRequest


def _raw(**overrides) -> dict:
    base = {
        "project_id": "proj",
        "scope": "project",
        "dataset_id": None,
        "table_id": None,
        "amount_usd": 100.0,
        "period": "month",
        "created_by": "a@dp6.com.br",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 2, tzinfo=UTC),
    }
    base.update(overrides)
    return base


def test_list_budgets_wraps_repository_rows(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "list_budgets",
        lambda client, email, project_id: [_raw(), _raw(scope="dataset", dataset_id="RAW")],
    )

    result = service.list_budgets(MagicMock(), "a@dp6.com.br", "proj")

    assert result.project_id == "proj"
    assert [b.scope for b in result.budgets] == [BudgetScope.PROJECT, BudgetScope.DATASET]


def test_upsert_budget_forwards_request_fields_to_repository(monkeypatch):
    captured = {}

    def _fake_upsert(client, email, project_id, scope, amount_usd, dataset_id=None, table_id=None):
        captured.update(
            email=email,
            project_id=project_id,
            scope=scope,
            amount_usd=amount_usd,
            dataset_id=dataset_id,
            table_id=table_id,
        )
        return _raw(
            scope=scope.value, dataset_id=dataset_id, table_id=table_id, amount_usd=amount_usd
        )

    monkeypatch.setattr(service.repository, "upsert_budget", _fake_upsert)

    request = BudgetUpsertRequest(
        scope=BudgetScope.TABLE, dataset_id="RAW", table_id="events", amount_usd=12.5
    )
    result = service.upsert_budget(MagicMock(), "a@dp6.com.br", "proj", request)

    assert captured == {
        "email": "a@dp6.com.br",
        "project_id": "proj",
        "scope": BudgetScope.TABLE,
        "amount_usd": 12.5,
        "dataset_id": "RAW",
        "table_id": "events",
    }
    assert result.amount_usd == 12.5
    assert result.table_id == "events"


def test_remove_budget_delegates_to_repository(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        service.repository,
        "remove_budget",
        lambda client, email, project_id, scope, dataset_id=None, table_id=None: captured.update(
            scope=scope, dataset_id=dataset_id, table_id=table_id
        ),
    )

    service.remove_budget(
        MagicMock(), "a@dp6.com.br", "proj", BudgetScope.DATASET, dataset_id="RAW"
    )

    assert captured == {"scope": BudgetScope.DATASET, "dataset_id": "RAW", "table_id": None}


def test_upsert_request_rejects_dataset_scope_without_dataset_id():
    with pytest.raises(ValueError, match="scope=dataset"):
        BudgetUpsertRequest(scope=BudgetScope.DATASET, amount_usd=10)


def test_upsert_request_rejects_non_positive_amount():
    with pytest.raises(ValueError):
        BudgetUpsertRequest(scope=BudgetScope.PROJECT, amount_usd=0)
