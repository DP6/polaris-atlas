from datetime import UTC, datetime
from unittest.mock import MagicMock

from observability_hub.domains.admin import service
from observability_hub.domains.admin.schemas import UpsertProjectAdminRequest


def _fake_client() -> MagicMock:
    return MagicMock(name="firestore.Client")


# --- is_project_admin ----------------------------------------------------------


def test_is_project_admin_true_when_datasets_null_covers_any_dataset(monkeypatch):
    monkeypatch.setattr(
        service.project_admin_repository,
        "get_project_admin",
        lambda client, project_id, email: {"email": email, "datasets": None},
    )

    assert service.is_project_admin(_fake_client(), "a@dp6.com.br", "proj-a", "RAW") is True
    assert service.is_project_admin(_fake_client(), "a@dp6.com.br", "proj-a", None) is True


def test_is_project_admin_true_when_dataset_in_scoped_list(monkeypatch):
    monkeypatch.setattr(
        service.project_admin_repository,
        "get_project_admin",
        lambda client, project_id, email: {"email": email, "datasets": ["RAW", "TRUSTED"]},
    )

    assert service.is_project_admin(_fake_client(), "a@dp6.com.br", "proj-a", "RAW") is True


def test_is_project_admin_false_when_dataset_outside_scoped_list(monkeypatch):
    monkeypatch.setattr(
        service.project_admin_repository,
        "get_project_admin",
        lambda client, project_id, email: {"email": email, "datasets": ["RAW"]},
    )

    assert service.is_project_admin(_fake_client(), "a@dp6.com.br", "proj-a", "TRUSTED") is False


def test_is_project_admin_false_when_scoped_list_but_no_dataset_id(monkeypatch):
    """Endpoint project-scoped (dataset_id=None, ex: budget de projeto
    inteiro) — um admin restrito a datasets específicos nunca passa,
    mesmo que a lista não esteja vazia."""
    monkeypatch.setattr(
        service.project_admin_repository,
        "get_project_admin",
        lambda client, project_id, email: {"email": email, "datasets": ["RAW"]},
    )

    assert service.is_project_admin(_fake_client(), "a@dp6.com.br", "proj-a", None) is False


def test_is_project_admin_false_when_no_grant(monkeypatch):
    monkeypatch.setattr(
        service.project_admin_repository,
        "get_project_admin",
        lambda client, project_id, email: None,
    )

    assert service.is_project_admin(_fake_client(), "a@dp6.com.br", "proj-a", "RAW") is False


def test_is_project_admin_normalizes_email(monkeypatch):
    captured = {}

    def fake_get(client, project_id, email):
        captured["email"] = email
        return {"email": email, "datasets": None}

    monkeypatch.setattr(service.project_admin_repository, "get_project_admin", fake_get)

    service.is_project_admin(_fake_client(), "A@DP6.com.br", "proj-a", "RAW")

    assert captured["email"] == "a@dp6.com.br"


# --- list_project_admins --------------------------------------------------------


def test_list_project_admins_builds_response(monkeypatch):
    raw = [
        {
            "email": "a@dp6.com.br",
            "datasets": None,
            "granted_by": "super@dp6.com.br",
            "granted_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
        }
    ]
    monkeypatch.setattr(
        service.project_admin_repository, "list_project_admins", lambda client, project_id: raw
    )

    result = service.list_project_admins(_fake_client(), "proj-a")

    assert result.project_id == "proj-a"
    assert len(result.admins) == 1
    assert result.admins[0].email == "a@dp6.com.br"


# --- grant_project_admin ---------------------------------------------------------


def test_grant_project_admin_normalizes_emails_and_delegates(monkeypatch):
    captured = {}

    def fake_upsert(client, project_id, email, datasets, granted_by):
        captured.update(
            project_id=project_id, email=email, datasets=datasets, granted_by=granted_by
        )
        return {
            "email": email,
            "datasets": datasets,
            "granted_by": granted_by,
            "granted_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
        }

    monkeypatch.setattr(service.project_admin_repository, "upsert_project_admin", fake_upsert)

    result = service.grant_project_admin(
        _fake_client(),
        "proj-a",
        "New.Admin@DP6.com.br",
        UpsertProjectAdminRequest(datasets=["RAW"]),
        granted_by="Existing.Admin@DP6.com.br",
    )

    assert captured["email"] == "new.admin@dp6.com.br"
    assert captured["granted_by"] == "existing.admin@dp6.com.br"
    assert captured["datasets"] == ["RAW"]
    assert result.email == "new.admin@dp6.com.br"


# --- revoke_project_admin --------------------------------------------------------


def test_revoke_project_admin_delegates_to_repository(monkeypatch):
    captured = {}

    def fake_delete(client, project_id, email):
        captured.update(project_id=project_id, email=email)

    monkeypatch.setattr(service.project_admin_repository, "delete_project_admin", fake_delete)

    service.revoke_project_admin(_fake_client(), "proj-a", "Target@DP6.com.br")

    assert captured == {"project_id": "proj-a", "email": "target@dp6.com.br"}
