from unittest.mock import MagicMock

import pytest

from atlas.core import auth as auth_module
from atlas.core.exceptions import (
    AdminAccessRequiredError,
    InvalidSessionError,
    ProjectAdminRequiredError,
    ProjectNotAuthorizedError,
)
from atlas.domains.auth.schemas import UserInfo


def test_get_current_user_decodes_session_cookie(monkeypatch):
    expected = UserInfo(email="a@dp6.com.br", name="A")
    monkeypatch.setattr(auth_module.service, "decode_session_token", lambda token: expected)

    result = auth_module.get_current_user(session="a-valid-jwt")

    assert result == expected


def test_get_current_user_raises_when_cookie_missing(monkeypatch):
    def fake_decode(token):
        assert token is None
        raise InvalidSessionError()

    monkeypatch.setattr(auth_module.service, "decode_session_token", fake_decode)

    with pytest.raises(InvalidSessionError):
        auth_module.get_current_user(session=None)


# --- require_admin -------------------------------------------------------------


def test_require_admin_returns_user_when_admin(monkeypatch):
    user = UserInfo(email="a@dp6.com.br", name="A")
    monkeypatch.setattr(auth_module.admin_service, "is_admin", lambda client, email: True)

    result = auth_module.require_admin(user=user, client=MagicMock())

    assert result == user


def test_require_admin_raises_when_not_admin(monkeypatch):
    user = UserInfo(email="a@dp6.com.br", name="A")
    monkeypatch.setattr(auth_module.admin_service, "is_admin", lambda client, email: False)

    with pytest.raises(AdminAccessRequiredError):
        auth_module.require_admin(user=user, client=MagicMock())


# --- require_project_access -----------------------------------------------------


def test_require_project_access_returns_user_when_allowed(monkeypatch):
    user = UserInfo(email="a@dp6.com.br", name="A")
    monkeypatch.setattr(
        auth_module.admin_service, "has_project_access", lambda client, email, project_id: True
    )

    result = auth_module.require_project_access(project_id="proj-a", user=user, client=MagicMock())

    assert result == user


def test_require_project_access_raises_when_not_allowed(monkeypatch):
    user = UserInfo(email="a@dp6.com.br", name="A")
    monkeypatch.setattr(
        auth_module.admin_service, "has_project_access", lambda client, email, project_id: False
    )

    with pytest.raises(ProjectNotAuthorizedError) as exc_info:
        auth_module.require_project_access(project_id="proj-a", user=user, client=MagicMock())

    assert exc_info.value.project_id == "proj-a"


# --- require_project_admin -------------------------------------------------------


def test_require_project_admin_superadmin_bypasses(monkeypatch):
    """Superadmin nunca chega a checar project_admins — is_admin sozinho
    já basta, mesmo sem doc em hub_projects/{p}/project_admins."""
    user = UserInfo(email="super@dp6.com.br", name="Super")
    monkeypatch.setattr(auth_module.admin_service, "is_admin", lambda client, email: True)
    monkeypatch.setattr(
        auth_module.admin_service,
        "is_project_admin",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deveria ser chamado")),
    )

    result = auth_module.require_project_admin(project_id="proj-a", user=user, client=MagicMock())

    assert result == user


def test_require_project_admin_null_datasets_covers_any_dataset(monkeypatch):
    user = UserInfo(email="admin@dp6.com.br", name="Admin")
    monkeypatch.setattr(auth_module.admin_service, "is_admin", lambda client, email: False)
    monkeypatch.setattr(auth_module.admin_service, "is_project_admin", lambda *a, **k: True)

    result = auth_module.require_project_admin(
        project_id="proj-a", dataset_id="RAW", user=user, client=MagicMock()
    )

    assert result == user


def test_require_project_admin_scoped_denies_outside_scope(monkeypatch):
    user = UserInfo(email="admin@dp6.com.br", name="Admin")
    monkeypatch.setattr(auth_module.admin_service, "is_admin", lambda client, email: False)
    monkeypatch.setattr(auth_module.admin_service, "is_project_admin", lambda *a, **k: False)

    with pytest.raises(ProjectAdminRequiredError) as exc_info:
        auth_module.require_project_admin(
            project_id="proj-a", dataset_id="TRUSTED", user=user, client=MagicMock()
        )

    assert exc_info.value.project_id == "proj-a"


def test_require_project_admin_denies_regular_user(monkeypatch):
    user = UserInfo(email="regular@dp6.com.br", name="Regular")
    monkeypatch.setattr(auth_module.admin_service, "is_admin", lambda client, email: False)
    monkeypatch.setattr(auth_module.admin_service, "is_project_admin", lambda *a, **k: False)

    with pytest.raises(ProjectAdminRequiredError):
        auth_module.require_project_admin(project_id="proj-a", user=user, client=MagicMock())
