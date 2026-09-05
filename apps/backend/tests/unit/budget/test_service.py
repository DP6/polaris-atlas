from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from atlas.core.exceptions import ProjectAdminRequiredError
from atlas.domains.budget import service
from atlas.domains.budget.schemas import BudgetScope, BudgetUpsertRequest


def _raw(**overrides) -> dict:
    base = {
        "scope": "project",
        "dataset_id": None,
        "table_id": None,
        "amount_usd": 100.0,
        "period": "month",
        "created_by": "a@dp6.com.br",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 2, tzinfo=UTC),
        "updated_by": "a@dp6.com.br",
    }
    base.update(overrides)
    return base


def _allow_admin(monkeypatch, *, is_admin=True, is_project_admin=False):
    monkeypatch.setattr(service.admin_service, "is_admin", lambda client, email: is_admin)
    monkeypatch.setattr(
        service.admin_service,
        "is_project_admin",
        lambda client, email, project_id, dataset_id: is_project_admin,
    )


def test_list_budgets_wraps_repository_rows_no_email(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "list_budgets",
        lambda client, project_id: [_raw(), _raw(scope="dataset", dataset_id="RAW")],
    )

    result = service.list_budgets(MagicMock(), "proj")

    assert result.project_id == "proj"
    assert [b.scope for b in result.budgets] == [BudgetScope.PROJECT, BudgetScope.DATASET]
    assert all(b.project_id == "proj" for b in result.budgets)


# --- permissão -------------------------------------------------------------------


def test_upsert_budget_superadmin_bypasses_project_admin_check(monkeypatch):
    _allow_admin(monkeypatch, is_admin=True, is_project_admin=False)
    monkeypatch.setattr(
        service.repository, "upsert_budget", lambda client, p, scope, amount, by, **kw: _raw()
    )

    request = BudgetUpsertRequest(scope=BudgetScope.PROJECT, amount_usd=250.0)
    result = service.upsert_budget(MagicMock(), "proj", request, "super@dp6.com.br")

    assert result.amount_usd == 100.0  # veio do _raw() mockado


def test_upsert_budget_project_scope_requires_whole_project_admin(monkeypatch):
    """scope=project só passa pra quem tem datasets=null — is_project_admin
    é chamado com dataset_id=None (o request.dataset_id de scope=project),
    mesma regra de core/auth.py::require_project_admin."""
    captured = {}

    def fake_is_project_admin(client, email, project_id, dataset_id):
        captured["dataset_id"] = dataset_id
        return False

    monkeypatch.setattr(service.admin_service, "is_admin", lambda client, email: False)
    monkeypatch.setattr(service.admin_service, "is_project_admin", fake_is_project_admin)

    request = BudgetUpsertRequest(scope=BudgetScope.PROJECT, amount_usd=250.0)
    with pytest.raises(ProjectAdminRequiredError):
        service.upsert_budget(MagicMock(), "proj", request, "regular@dp6.com.br")

    assert captured["dataset_id"] is None


def test_upsert_budget_dataset_scope_admin_allowed_for_own_dataset(monkeypatch):
    _allow_admin(monkeypatch, is_admin=False, is_project_admin=True)
    monkeypatch.setattr(
        service.repository, "upsert_budget", lambda client, p, scope, amount, by, **kw: _raw()
    )

    request = BudgetUpsertRequest(scope=BudgetScope.DATASET, dataset_id="RAW", amount_usd=40.0)
    result = service.upsert_budget(MagicMock(), "proj", request, "dataset-admin@dp6.com.br")

    assert result.project_id == "proj"


def test_upsert_budget_denies_regular_user(monkeypatch):
    _allow_admin(monkeypatch, is_admin=False, is_project_admin=False)

    request = BudgetUpsertRequest(scope=BudgetScope.PROJECT, amount_usd=250.0)
    with pytest.raises(ProjectAdminRequiredError):
        service.upsert_budget(MagicMock(), "proj", request, "regular@dp6.com.br")


def test_remove_budget_denies_regular_user(monkeypatch):
    _allow_admin(monkeypatch, is_admin=False, is_project_admin=False)

    with pytest.raises(ProjectAdminRequiredError):
        service.remove_budget(
            MagicMock(), "proj", BudgetScope.DATASET, "regular@dp6.com.br", dataset_id="RAW"
        )


# --- delegação pra repository -----------------------------------------------------


def test_upsert_budget_forwards_request_fields_to_repository(monkeypatch):
    captured = {}
    _allow_admin(monkeypatch, is_admin=True)

    def _fake_upsert(
        client, project_id, scope, amount_usd, updated_by, dataset_id=None, table_id=None
    ):
        captured.update(
            project_id=project_id,
            scope=scope,
            amount_usd=amount_usd,
            updated_by=updated_by,
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
    result = service.upsert_budget(MagicMock(), "proj", request, "a@dp6.com.br")

    assert captured == {
        "project_id": "proj",
        "scope": BudgetScope.TABLE,
        "amount_usd": 12.5,
        "updated_by": "a@dp6.com.br",
        "dataset_id": "RAW",
        "table_id": "events",
    }
    assert result.amount_usd == 12.5
    assert result.table_id == "events"


def test_remove_budget_delegates_to_repository(monkeypatch):
    captured = {}
    _allow_admin(monkeypatch, is_admin=True)
    monkeypatch.setattr(
        service.repository,
        "remove_budget",
        lambda client, project_id, scope, dataset_id=None, table_id=None: captured.update(
            scope=scope, dataset_id=dataset_id, table_id=table_id
        ),
    )

    service.remove_budget(
        MagicMock(), "proj", BudgetScope.DATASET, "a@dp6.com.br", dataset_id="RAW"
    )

    assert captured == {"scope": BudgetScope.DATASET, "dataset_id": "RAW", "table_id": None}


def test_upsert_request_rejects_dataset_scope_without_dataset_id():
    with pytest.raises(ValueError, match="scope=dataset"):
        BudgetUpsertRequest(scope=BudgetScope.DATASET, amount_usd=10)


def test_upsert_request_rejects_non_positive_amount():
    with pytest.raises(ValueError):
        BudgetUpsertRequest(scope=BudgetScope.PROJECT, amount_usd=0)
