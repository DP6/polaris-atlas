from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from atlas.core.exceptions import AccessRequestNotFoundError, LastAdminLockoutError
from atlas.domains.admin import service
from atlas.domains.admin.schemas import (
    UpsertHubGroupRequest,
    UpsertHubProjectRequest,
    UpsertHubUserRequest,
    WorkspaceGroupInfo,
)


def _fake_client() -> MagicMock:
    return MagicMock(name="firestore.Client")


# --- list_users --------------------------------------------------------------


def test_list_users_builds_response(monkeypatch):
    raw = [
        {
            "email": "a@dp6.com.br",
            "is_admin": True,
            "allowed_projects": ["*"],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "updated_by": "a@dp6.com.br",
        }
    ]
    monkeypatch.setattr(service.repository, "list_users", lambda client: raw)

    result = service.list_users(_fake_client())

    assert len(result.users) == 1
    assert result.users[0].email == "a@dp6.com.br"


# --- upsert_user ---------------------------------------------------------------


def test_upsert_user_normalizes_email_and_updated_by(monkeypatch):
    captured = {}

    def fake_upsert(client, email, is_admin, allowed_projects, updated_by):
        captured.update(
            email=email, is_admin=is_admin, allowed_projects=allowed_projects, updated_by=updated_by
        )
        return {
            "email": email,
            "is_admin": is_admin,
            "allowed_projects": allowed_projects,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "updated_by": updated_by,
        }

    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    monkeypatch.setattr(service.repository, "upsert_user", fake_upsert)

    result = service.upsert_user(
        _fake_client(),
        "A@DP6.com.br",
        UpsertHubUserRequest(is_admin=False, allowed_projects=["proj-a"]),
        updated_by="ADMIN@dp6.com.br",
    )

    assert captured["email"] == "a@dp6.com.br"
    assert captured["updated_by"] == "admin@dp6.com.br"
    assert result.email == "a@dp6.com.br"


def test_upsert_user_allows_demoting_admin_when_other_admins_remain(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"email": email, "is_admin": True},
    )
    monkeypatch.setattr(
        service.repository,
        "list_users",
        lambda client: [
            {"email": "a@dp6.com.br", "is_admin": True},
            {"email": "b@dp6.com.br", "is_admin": True},
        ],
    )
    monkeypatch.setattr(
        service.repository,
        "upsert_user",
        lambda client, email, is_admin, allowed_projects, updated_by: {
            "email": email,
            "is_admin": is_admin,
            "allowed_projects": allowed_projects,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "updated_by": updated_by,
        },
    )

    result = service.upsert_user(
        _fake_client(),
        "a@dp6.com.br",
        UpsertHubUserRequest(is_admin=False, allowed_projects=[]),
        updated_by="b@dp6.com.br",
    )

    assert result.is_admin is False


def test_upsert_user_blocks_demoting_last_admin(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"email": email, "is_admin": True},
    )
    monkeypatch.setattr(
        service.repository,
        "list_users",
        lambda client: [{"email": "a@dp6.com.br", "is_admin": True}],
    )

    with pytest.raises(LastAdminLockoutError):
        service.upsert_user(
            _fake_client(),
            "a@dp6.com.br",
            UpsertHubUserRequest(is_admin=False, allowed_projects=[]),
            updated_by="a@dp6.com.br",
        )


# --- delete_user ---------------------------------------------------------------


def test_delete_user_blocks_deleting_last_admin(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"email": email, "is_admin": True},
    )
    monkeypatch.setattr(
        service.repository,
        "list_users",
        lambda client: [{"email": "a@dp6.com.br", "is_admin": True}],
    )

    with pytest.raises(LastAdminLockoutError):
        service.delete_user(_fake_client(), "a@dp6.com.br")


def test_delete_user_allows_deleting_non_admin(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"email": email, "is_admin": False},
    )
    delete_mock = MagicMock()
    monkeypatch.setattr(service.repository, "delete_user", delete_mock)

    service.delete_user(_fake_client(), "a@dp6.com.br")

    assert delete_mock.call_args[0][1] == "a@dp6.com.br"


def test_delete_user_is_idempotent_for_unknown_email(monkeypatch):
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    delete_mock = MagicMock()
    monkeypatch.setattr(service.repository, "delete_user", delete_mock)

    service.delete_user(_fake_client(), "ghost@dp6.com.br")

    delete_mock.assert_called_once()


# --- is_admin --------------------------------------------------------------------


def test_is_admin_true_when_flagged(monkeypatch):
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: {"is_admin": True})
    assert service.is_admin(_fake_client(), "a@dp6.com.br") is True


def test_is_admin_false_when_no_doc(monkeypatch):
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    assert service.is_admin(_fake_client(), "ghost@dp6.com.br") is False


def test_is_admin_normalizes_email_case(monkeypatch):
    seen = {}

    def fake_get_user(client, email):
        seen["email"] = email
        return {"is_admin": True}

    monkeypatch.setattr(service.repository, "get_user", fake_get_user)

    service.is_admin(_fake_client(), "A@DP6.com.br")

    assert seen["email"] == "a@dp6.com.br"


# --- has_project_access -----------------------------------------------------------


def _stub_no_public_project(monkeypatch):
    """Default pra quem não é o foco do teste: nenhum projeto marcado
    is_public e nenhum grupo concedendo acesso. Sem isso, MagicMock()
    tanto pra get_project quanto pro retorno não-mockado de list_groups
    quebraria testes que não são sobre esses eixos (fail-closed quebrado,
    ou TypeError ao iterar um MagicMock)."""
    monkeypatch.setattr(service.repository, "get_project", lambda client, project_id: None)
    monkeypatch.setattr(service.repository, "list_groups", lambda client: [])


def test_has_project_access_false_when_no_doc(monkeypatch):
    _stub_no_public_project(monkeypatch)
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    assert service.has_project_access(_fake_client(), "ghost@dp6.com.br", "proj-a") is False


def test_has_project_access_true_for_wildcard(monkeypatch):
    _stub_no_public_project(monkeypatch)
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"allowed_projects": ["*"]},
    )
    assert service.has_project_access(_fake_client(), "a@dp6.com.br", "any-project") is True


def test_has_project_access_true_for_explicit_project(monkeypatch):
    _stub_no_public_project(monkeypatch)
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"allowed_projects": ["proj-a", "proj-b"]},
    )
    assert service.has_project_access(_fake_client(), "a@dp6.com.br", "proj-a") is True


def test_has_project_access_false_for_project_not_in_list(monkeypatch):
    _stub_no_public_project(monkeypatch)
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"allowed_projects": ["proj-a"]},
    )
    assert service.has_project_access(_fake_client(), "a@dp6.com.br", "proj-c") is False


def test_has_project_access_true_when_project_is_public(monkeypatch):
    monkeypatch.setattr(
        service.repository, "get_project", lambda client, project_id: {"is_public": True}
    )
    get_user_mock = MagicMock()
    monkeypatch.setattr(service.repository, "get_user", get_user_mock)

    result = service.has_project_access(_fake_client(), "ghost@dp6.com.br", "proj-a")

    assert result is True
    # is_public já resolveu — nem precisa olhar o usuário.
    get_user_mock.assert_not_called()


def test_has_project_access_false_when_project_exists_but_not_public(monkeypatch):
    monkeypatch.setattr(
        service.repository, "get_project", lambda client, project_id: {"is_public": False}
    )
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    monkeypatch.setattr(service.repository, "list_groups", lambda client: [])

    assert service.has_project_access(_fake_client(), "ghost@dp6.com.br", "proj-a") is False


def test_has_project_access_true_via_group_wildcard_manual_member(monkeypatch):
    _stub_no_public_project(monkeypatch)
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    monkeypatch.setattr(
        service.repository,
        "list_groups",
        lambda client: [
            {"group_id": "cliente-a", "allowed_projects": ["*"], "manual_members": ["a@dp6.com.br"]}
        ],
    )
    monkeypatch.setattr(service.workspace_directory, "get_group_members", lambda group_id: [])
    assert service.has_project_access(_fake_client(), "a@dp6.com.br", "any-project") is True


def test_has_project_access_true_via_group_explicit_project_manual_member(monkeypatch):
    _stub_no_public_project(monkeypatch)
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    monkeypatch.setattr(
        service.repository,
        "list_groups",
        lambda client: [
            {
                "group_id": "cliente-a",
                "allowed_projects": ["proj-a"],
                "manual_members": ["a@dp6.com.br"],
            }
        ],
    )
    monkeypatch.setattr(service.workspace_directory, "get_group_members", lambda group_id: [])
    assert service.has_project_access(_fake_client(), "a@dp6.com.br", "proj-a") is True


def test_has_project_access_true_via_workspace_member(monkeypatch):
    """Membro real do grupo no Workspace, sem estar em manual_members —
    o eixo Workspace também libera, não só o cadastro manual."""
    _stub_no_public_project(monkeypatch)
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    monkeypatch.setattr(
        service.repository,
        "list_groups",
        lambda client: [
            {
                "group_id": "cliente-a@dp6.com.br",
                "allowed_projects": ["proj-a"],
                "manual_members": [],
            }
        ],
    )
    monkeypatch.setattr(
        service.workspace_directory, "get_group_members", lambda group_id: ["a@dp6.com.br"]
    )
    assert service.has_project_access(_fake_client(), "a@dp6.com.br", "proj-a") is True


def test_has_project_access_false_when_group_does_not_grant(monkeypatch):
    _stub_no_public_project(monkeypatch)
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    monkeypatch.setattr(
        service.repository,
        "list_groups",
        lambda client: [
            {
                "group_id": "cliente-a",
                "allowed_projects": ["proj-b"],
                "manual_members": ["a@dp6.com.br"],
            }
        ],
    )
    monkeypatch.setattr(service.workspace_directory, "get_group_members", lambda group_id: [])
    assert service.has_project_access(_fake_client(), "a@dp6.com.br", "proj-a") is False


def test_has_project_access_skips_workspace_lookup_when_group_does_not_grant_project(monkeypatch):
    """Otimização: só chama get_group_members pros grupos que já liberam
    este project_id — evita chamada externa (Workspace API) desnecessária."""
    _stub_no_public_project(monkeypatch)
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    monkeypatch.setattr(
        service.repository,
        "list_groups",
        lambda client: [
            {"group_id": "cliente-a", "allowed_projects": ["proj-b"], "manual_members": []}
        ],
    )
    workspace_mock = MagicMock()
    monkeypatch.setattr(service.workspace_directory, "get_group_members", workspace_mock)

    result = service.has_project_access(_fake_client(), "a@dp6.com.br", "proj-a")

    assert result is False
    workspace_mock.assert_not_called()


def test_has_project_access_true_from_own_grant_even_without_matching_group(monkeypatch):
    """Acesso individual (hub_users) e de grupo são independentes — um
    não precisa do outro, qualquer um dos dois libera."""
    _stub_no_public_project(monkeypatch)
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {"allowed_projects": ["proj-a"]},
    )
    groups_mock = MagicMock()
    monkeypatch.setattr(service.repository, "list_groups", groups_mock)

    result = service.has_project_access(_fake_client(), "a@dp6.com.br", "proj-a")

    assert result is True
    # Acesso individual já resolveu — nem precisa escanear grupos.
    groups_mock.assert_not_called()


# --- hub_groups (v1.4) --------------------------------------------------------------


def test_list_groups_builds_response_with_workspace_members(monkeypatch):
    raw = [
        {
            "group_id": "cliente-a@dp6.com.br",
            "manual_members": ["a@dp6.com.br"],
            "allowed_projects": ["proj-a"],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "updated_by": "admin@dp6.com.br",
        }
    ]
    monkeypatch.setattr(service.repository, "list_groups", lambda client: raw)
    monkeypatch.setattr(
        service.workspace_directory, "get_group_members", lambda group_id: ["b@dp6.com.br"]
    )

    result = service.list_groups(_fake_client())

    assert len(result.groups) == 1
    assert result.groups[0].group_id == "cliente-a@dp6.com.br"
    assert result.groups[0].manual_members == ["a@dp6.com.br"]
    # workspace_members nunca vem do Firestore — resolvido via
    # workspace_directory, injetado por cima do raw do repository.
    assert result.groups[0].workspace_members == ["b@dp6.com.br"]


def test_upsert_group_normalizes_member_emails_and_updated_by(monkeypatch):
    captured = {}

    def fake_upsert(client, group_id, manual_members, allowed_projects, updated_by):
        captured.update(
            group_id=group_id,
            manual_members=manual_members,
            allowed_projects=allowed_projects,
            updated_by=updated_by,
        )
        return {
            "group_id": group_id,
            "manual_members": manual_members,
            "allowed_projects": allowed_projects,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "updated_by": updated_by,
        }

    monkeypatch.setattr(service.repository, "get_group", lambda client, group_id: None)
    monkeypatch.setattr(service.repository, "upsert_group", fake_upsert)
    monkeypatch.setattr(service.workspace_directory, "get_group_members", lambda group_id: [])

    result = service.upsert_group(
        _fake_client(),
        "cliente-a",
        UpsertHubGroupRequest(manual_members=["A@DP6.com.br"], allowed_projects=["proj-a"]),
        updated_by="ADMIN@dp6.com.br",
    )

    assert captured["manual_members"] == ["a@dp6.com.br"]
    assert captured["updated_by"] == "admin@dp6.com.br"
    assert result.group_id == "cliente-a"


def test_delete_group_calls_repository(monkeypatch):
    delete_mock = MagicMock()
    monkeypatch.setattr(service.repository, "delete_group", delete_mock)
    client = _fake_client()

    service.delete_group(client, "cliente-a")

    delete_mock.assert_called_once_with(client, "cliente-a")


# --- hub_projects ------------------------------------------------------------------


def test_list_projects_builds_response(monkeypatch):
    raw = [
        {
            "project_id": "proj-a",
            "is_public": True,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_by": "admin@dp6.com.br",
        }
    ]
    monkeypatch.setattr(service.repository, "list_projects", lambda client: raw)

    result = service.list_projects(_fake_client())

    assert len(result.projects) == 1
    assert result.projects[0].project_id == "proj-a"


def test_upsert_project_delegates_to_repository(monkeypatch):
    captured = {}

    def fake_upsert(client, project_id, is_public, updated_by):
        captured.update(project_id=project_id, is_public=is_public, updated_by=updated_by)
        return {
            "project_id": project_id,
            "is_public": is_public,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_by": updated_by,
        }

    monkeypatch.setattr(service.repository, "upsert_project", fake_upsert)

    result = service.upsert_project(
        _fake_client(),
        "proj-a",
        UpsertHubProjectRequest(is_public=True),
        updated_by="ADMIN@dp6.com.br",
    )

    assert captured["project_id"] == "proj-a"
    assert captured["updated_by"] == "admin@dp6.com.br"
    assert result.is_public is True


def test_delete_project_delegates_to_repository(monkeypatch):
    delete_mock = MagicMock()
    monkeypatch.setattr(service.repository, "delete_project", delete_mock)

    service.delete_project(_fake_client(), "proj-a")

    assert delete_mock.call_args[0][1] == "proj-a"


def test_get_project_users_marks_wildcard_vs_explicit(monkeypatch):
    monkeypatch.setattr(
        service.repository, "get_project", lambda client, project_id: {"is_public": False}
    )
    monkeypatch.setattr(
        service.repository,
        "users_with_project_access",
        lambda client, project_id: [
            {"email": "explicit@dp6.com.br", "is_admin": False, "allowed_projects": ["proj-a"]},
            {"email": "wild@dp6.com.br", "is_admin": True, "allowed_projects": ["*"]},
        ],
    )

    result = service.get_project_users(_fake_client(), "proj-a")

    assert result.is_public is False
    by_email = {u.email: u for u in result.users}
    assert by_email["explicit@dp6.com.br"].granted_via == "explicit"
    assert by_email["wild@dp6.com.br"].granted_via == "wildcard"


def test_get_project_users_reflects_is_public(monkeypatch):
    monkeypatch.setattr(
        service.repository, "get_project", lambda client, project_id: {"is_public": True}
    )
    monkeypatch.setattr(
        service.repository, "users_with_project_access", lambda client, project_id: []
    )

    result = service.get_project_users(_fake_client(), "proj-a")

    assert result.is_public is True
    assert result.users == []


def test_grant_project_to_user_creates_new_user(monkeypatch):
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)
    captured = {}

    def fake_upsert(client, email, is_admin, allowed_projects, updated_by):
        captured.update(
            email=email, is_admin=is_admin, allowed_projects=allowed_projects, updated_by=updated_by
        )
        return {
            "email": email,
            "is_admin": is_admin,
            "allowed_projects": allowed_projects,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_by": updated_by,
        }

    monkeypatch.setattr(service.repository, "upsert_user", fake_upsert)

    result = service.grant_project_to_user(
        _fake_client(), "proj-a", "new@dp6.com.br", updated_by="admin@dp6.com.br"
    )

    assert captured["is_admin"] is False
    assert captured["allowed_projects"] == ["proj-a"]
    assert result.allowed_projects == ["proj-a"]


def test_grant_project_to_user_is_idempotent(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {
            "email": email,
            "is_admin": False,
            "allowed_projects": ["proj-a", "proj-b"],
        },
    )
    captured = {}

    def fake_upsert(client, email, is_admin, allowed_projects, updated_by):
        captured["allowed_projects"] = allowed_projects
        return {
            "email": email,
            "is_admin": is_admin,
            "allowed_projects": allowed_projects,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_by": updated_by,
        }

    monkeypatch.setattr(service.repository, "upsert_user", fake_upsert)

    service.grant_project_to_user(
        _fake_client(), "proj-a", "a@dp6.com.br", updated_by="admin@dp6.com.br"
    )

    assert captured["allowed_projects"] == ["proj-a", "proj-b"]


def test_revoke_project_from_user_removes_only_that_project(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_user",
        lambda client, email: {
            "email": email,
            "is_admin": False,
            "allowed_projects": ["proj-a", "proj-b"],
        },
    )
    captured = {}

    def fake_upsert(client, email, is_admin, allowed_projects, updated_by):
        captured["allowed_projects"] = allowed_projects
        return {
            "email": email,
            "is_admin": is_admin,
            "allowed_projects": allowed_projects,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
            "updated_by": updated_by,
        }

    monkeypatch.setattr(service.repository, "upsert_user", fake_upsert)

    result = service.revoke_project_from_user(
        _fake_client(), "proj-a", "a@dp6.com.br", updated_by="admin@dp6.com.br"
    )

    assert captured["allowed_projects"] == ["proj-b"]
    assert result.allowed_projects == ["proj-b"]


def test_revoke_project_from_user_returns_none_when_user_missing(monkeypatch):
    monkeypatch.setattr(service.repository, "get_user", lambda client, email: None)

    result = service.revoke_project_from_user(
        _fake_client(), "proj-a", "ghost@dp6.com.br", updated_by="admin@dp6.com.br"
    )

    assert result is None


# --- list_workspace_groups ------------------------------------------------------------


def test_list_workspace_groups_builds_response(monkeypatch):
    monkeypatch.setattr(
        service.workspace_directory,
        "list_domain_groups",
        lambda: [{"email": "cliente-a@dp6.com.br", "name": "Cliente A"}],
    )

    result = service.list_workspace_groups()

    assert result.groups == [WorkspaceGroupInfo(email="cliente-a@dp6.com.br", name="Cliente A")]


def test_list_workspace_groups_empty_when_integration_not_configured(monkeypatch):
    monkeypatch.setattr(service.workspace_directory, "list_domain_groups", list)

    assert service.list_workspace_groups().groups == []


# --- access_requests -----------------------------------------------------------------


def test_create_access_requests_skips_already_accessible_project(monkeypatch):
    monkeypatch.setattr(service, "has_project_access", lambda client, email, project_id: True)
    monkeypatch.setattr(
        service.repository,
        "has_pending_request",
        lambda client, email, project_id, request_type: False,
    )
    create_mock = MagicMock()
    monkeypatch.setattr(service.repository, "create_access_request", create_mock)

    result = service.create_access_requests(_fake_client(), "a@dp6.com.br", ["proj-a"])

    assert result.requests == []
    create_mock.assert_not_called()


def test_create_access_requests_skips_duplicate_pending(monkeypatch):
    monkeypatch.setattr(service, "has_project_access", lambda client, email, project_id: False)
    monkeypatch.setattr(
        service.repository,
        "has_pending_request",
        lambda client, email, project_id, request_type: True,
    )
    create_mock = MagicMock()
    monkeypatch.setattr(service.repository, "create_access_request", create_mock)

    result = service.create_access_requests(_fake_client(), "a@dp6.com.br", ["proj-a"])

    assert result.requests == []
    create_mock.assert_not_called()


def test_create_access_requests_creates_for_new_project(monkeypatch):
    monkeypatch.setattr(service, "has_project_access", lambda client, email, project_id: False)
    monkeypatch.setattr(
        service.repository,
        "has_pending_request",
        lambda client, email, project_id, request_type: False,
    )

    def fake_create(client, email, project_id, now, request_type):
        return {
            "request_id": "r1",
            "email": email,
            "project_id": project_id,
            "request_type": request_type,
            "status": "pending",
            "requested_at": now,
            "resolved_at": None,
            "resolved_by": None,
        }

    monkeypatch.setattr(service.repository, "create_access_request", fake_create)

    result = service.create_access_requests(_fake_client(), "A@DP6.com.br", ["proj-a"])

    assert len(result.requests) == 1
    assert result.requests[0].email == "a@dp6.com.br"
    assert result.requests[0].status == "pending"
    assert result.requests[0].request_type == "access"


def test_create_access_requests_passes_inclusion_type_through(monkeypatch):
    monkeypatch.setattr(service, "has_project_access", lambda client, email, project_id: False)
    captured = {}

    def fake_has_pending(client, email, project_id, request_type):
        captured["has_pending_request_type"] = request_type
        return False

    def fake_create(client, email, project_id, now, request_type):
        captured["create_request_type"] = request_type
        return {
            "request_id": "r1",
            "email": email,
            "project_id": project_id,
            "request_type": request_type,
            "status": "pending",
            "requested_at": now,
            "resolved_at": None,
            "resolved_by": None,
        }

    monkeypatch.setattr(service.repository, "has_pending_request", fake_has_pending)
    monkeypatch.setattr(service.repository, "create_access_request", fake_create)

    result = service.create_access_requests(
        _fake_client(), "a@dp6.com.br", ["proj-a"], request_type="inclusion"
    )

    assert captured["has_pending_request_type"] == "inclusion"
    assert captured["create_request_type"] == "inclusion"
    assert result.requests[0].request_type == "inclusion"


def test_list_access_requests_builds_response(monkeypatch):
    raw = [
        {
            "request_id": "r1",
            "email": "a@dp6.com.br",
            "project_id": "proj-a",
            "status": "pending",
            "requested_at": datetime(2026, 1, 1, tzinfo=UTC),
            "resolved_at": None,
            "resolved_by": None,
        }
    ]
    monkeypatch.setattr(service.repository, "list_access_requests", lambda client, status: raw)

    result = service.list_access_requests(_fake_client(), status="pending")

    assert len(result.requests) == 1
    assert result.requests[0].request_id == "r1"


def test_approve_access_request_grants_project_and_marks_approved(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_access_request",
        lambda client, request_id: {
            "request_id": request_id,
            "email": "a@dp6.com.br",
            "project_id": "proj-a",
            "status": "pending",
            "requested_at": datetime(2026, 1, 1, tzinfo=UTC),
            "resolved_at": None,
            "resolved_by": None,
        },
    )
    grant_mock = MagicMock()
    monkeypatch.setattr(service, "grant_project_to_user", grant_mock)
    upsert_mock = MagicMock()
    monkeypatch.setattr(service.repository, "upsert_project", upsert_mock)

    def fake_update(client, request_id, status, resolved_by, now):
        return {
            "request_id": request_id,
            "email": "a@dp6.com.br",
            "project_id": "proj-a",
            "status": status,
            "requested_at": datetime(2026, 1, 1, tzinfo=UTC),
            "resolved_at": now,
            "resolved_by": resolved_by,
        }

    monkeypatch.setattr(service.repository, "update_access_request_status", fake_update)

    result = service.approve_access_request(_fake_client(), "r1", resolved_by="admin@dp6.com.br")

    assert grant_mock.call_args[0][1:] == ("proj-a", "a@dp6.com.br", "admin@dp6.com.br")
    # Pedido "access" (default, sem request_type no doc) nunca registra o
    # projeto — só um pedido "inclusion" faz isso, ver teste abaixo.
    upsert_mock.assert_not_called()
    assert result.status == "approved"
    assert result.resolved_by == "admin@dp6.com.br"


def test_approve_inclusion_request_registers_project_and_grants_access(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_access_request",
        lambda client, request_id: {
            "request_id": request_id,
            "email": "a@dp6.com.br",
            "project_id": "proj-a",
            "request_type": "inclusion",
            "status": "pending",
            "requested_at": datetime(2026, 1, 1, tzinfo=UTC),
            "resolved_at": None,
            "resolved_by": None,
        },
    )
    calls = []
    monkeypatch.setattr(
        service.repository,
        "upsert_project",
        lambda client, project_id, is_public, updated_by: calls.append(
            ("upsert_project", project_id, is_public, updated_by)
        ),
    )
    monkeypatch.setattr(
        service,
        "grant_project_to_user",
        lambda client, project_id, email, updated_by: calls.append(
            ("grant_project_to_user", project_id, email, updated_by)
        ),
    )
    monkeypatch.setattr(
        service.repository,
        "update_access_request_status",
        lambda client, request_id, status, resolved_by, now: {
            "request_id": request_id,
            "email": "a@dp6.com.br",
            "project_id": "proj-a",
            "request_type": "inclusion",
            "status": status,
            "requested_at": datetime(2026, 1, 1, tzinfo=UTC),
            "resolved_at": now,
            "resolved_by": resolved_by,
        },
    )

    result = service.approve_access_request(_fake_client(), "r1", resolved_by="admin@dp6.com.br")

    # upsert_project (registra o projeto) roda ANTES de grant_project_to_user
    # (libera o solicitante) — um clique resolve os dois lados.
    assert [c[0] for c in calls] == ["upsert_project", "grant_project_to_user"]
    assert calls[0] == ("upsert_project", "proj-a", False, "admin@dp6.com.br")
    assert calls[1] == ("grant_project_to_user", "proj-a", "a@dp6.com.br", "admin@dp6.com.br")
    assert result.status == "approved"


def test_deny_access_request_does_not_grant_project(monkeypatch):
    monkeypatch.setattr(
        service.repository,
        "get_access_request",
        lambda client, request_id: {
            "request_id": request_id,
            "email": "a@dp6.com.br",
            "project_id": "proj-a",
            "status": "pending",
            "requested_at": datetime(2026, 1, 1, tzinfo=UTC),
            "resolved_at": None,
            "resolved_by": None,
        },
    )
    grant_mock = MagicMock()
    monkeypatch.setattr(service, "grant_project_to_user", grant_mock)

    def fake_update(client, request_id, status, resolved_by, now):
        return {
            "request_id": request_id,
            "email": "a@dp6.com.br",
            "project_id": "proj-a",
            "status": status,
            "requested_at": datetime(2026, 1, 1, tzinfo=UTC),
            "resolved_at": now,
            "resolved_by": resolved_by,
        }

    monkeypatch.setattr(service.repository, "update_access_request_status", fake_update)

    result = service.deny_access_request(_fake_client(), "r1", resolved_by="admin@dp6.com.br")

    grant_mock.assert_not_called()
    assert result.status == "denied"


def test_approve_access_request_raises_when_not_found(monkeypatch):
    monkeypatch.setattr(service.repository, "get_access_request", lambda client, request_id: None)

    with pytest.raises(AccessRequestNotFoundError):
        service.approve_access_request(_fake_client(), "ghost-id", resolved_by="admin@dp6.com.br")


# --- trigger_event_cache_refresh ----------------------------------------------


def test_trigger_event_cache_refresh_calls_run_client_with_environment_job_name(monkeypatch):
    monkeypatch.setattr(service, "get_runtime_project", lambda: "dp6-ci-polaris")
    monkeypatch.setattr(service.settings, "region", "us-central1")
    monkeypatch.setattr(service.settings, "environment", "dev")
    calls = []
    monkeypatch.setattr(service, "trigger_job_execution", lambda *a, **kw: calls.append((a, kw)))

    run_client = MagicMock()
    service.trigger_event_cache_refresh(run_client)

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (run_client, "dp6-ci-polaris", "us-central1", "backend-dev-refresh-cache")
    assert kwargs == {"force_full": False, "only_projects": None}


def test_trigger_event_cache_refresh_forwards_force_full(monkeypatch):
    monkeypatch.setattr(service, "get_runtime_project", lambda: "dp6-ci-polaris")
    monkeypatch.setattr(service.settings, "region", "us-central1")
    monkeypatch.setattr(service.settings, "environment", "dev")
    calls = []
    monkeypatch.setattr(service, "trigger_job_execution", lambda *a, **kw: calls.append((a, kw)))

    service.trigger_event_cache_refresh(MagicMock(), force_full=True)

    assert calls[0][1] == {"force_full": True, "only_projects": None}


def test_trigger_event_cache_refresh_forwards_project_selection(monkeypatch):
    monkeypatch.setattr(service, "get_runtime_project", lambda: "dp6-ci-polaris")
    monkeypatch.setattr(service.settings, "region", "us-central1")
    monkeypatch.setattr(service.settings, "environment", "dev")
    calls = []
    monkeypatch.setattr(service, "trigger_job_execution", lambda *a, **kw: calls.append((a, kw)))

    service.trigger_event_cache_refresh(MagicMock(), projects=["proj-a", "proj-b"])

    assert calls[0][1] == {"force_full": False, "only_projects": ["proj-a", "proj-b"]}


def test_trigger_event_cache_refresh_empty_project_list_means_all(monkeypatch):
    monkeypatch.setattr(service, "get_runtime_project", lambda: "dp6-ci-polaris")
    monkeypatch.setattr(service.settings, "region", "us-central1")
    monkeypatch.setattr(service.settings, "environment", "dev")
    calls = []
    monkeypatch.setattr(service, "trigger_job_execution", lambda *a, **kw: calls.append((a, kw)))

    service.trigger_event_cache_refresh(MagicMock(), projects=[])

    assert calls[0][1] == {"force_full": False, "only_projects": None}


def test_list_event_cache_runs_builds_runs_from_firestore(monkeypatch):
    client = MagicMock()

    captured_limit = {}

    def _list_cache_runs(c, limit=200):
        captured_limit["limit"] = limit
        return [
            {
                "run_id": "20260828T030000000000Z",
                "started_at": "2026-08-28T03:00:00Z",
                "finished_at": "2026-08-28T03:04:00Z",
                "status": "done",
                "project_count": 2,
                "projects": {
                    "proj-b": {"status": "quota_exceeded", "finished_at": "2026-08-28T03:02:00Z"},
                    "proj-a": {
                        "status": "ok",
                        "finished_at": "2026-08-28T03:01:00Z",
                        "job_events": 10,
                        "access_events": 4,
                        "scan_events": 7,
                        "storage_read_object_keys": 0,
                        "mode": "incremental",
                        "raw_entries": 42,
                    },
                },
            }
        ]

    monkeypatch.setattr(service.event_cache, "list_cache_runs", _list_cache_runs)

    result = service.list_event_cache_runs(client)

    # traz tudo que está retido (default do list_cache_runs), não só 5
    assert captured_limit["limit"] == 200
    assert len(result.runs) == 1
    run = result.runs[0]
    assert run.status == "done"
    # projetos ordenados (proj-a antes de proj-b)
    assert [p.project_id for p in run.projects] == ["proj-a", "proj-b"]
    assert run.projects[0].job_events == 10
    assert run.projects[0].mode == "incremental"
    assert run.projects[0].raw_entries == 42
    assert run.projects[1].status == "quota_exceeded"


def test_get_event_cache_status_builds_project_freshness_only(monkeypatch):
    client = MagicMock()

    monkeypatch.setattr(
        service.repository,
        "list_projects",
        lambda c: [{"project_id": "proj-b"}, {"project_id": "proj-a"}, {"project_id": "*"}],
    )

    def _meta(c, kind, project_id):
        if project_id == "proj-a" and kind == "lineage":
            return {
                "cached_at": "2026-08-28T03:01:00Z",
                "event_count": 10,
                "window_start": "2026-07-28T03:00:00Z",
                "last_full_scan_at": "2026-08-20T03:00:00Z",
                "mode": "incremental",
            }
        return None

    monkeypatch.setattr(service.event_cache, "get_cache_metadata", _meta)

    result = service.get_event_cache_status(client)

    # /status não carrega mais o histórico de execuções (foi pro /runs)
    assert not hasattr(result, "runs")
    # wildcard "*" NÃO entra na lista; só os hub_projects, ordenados
    assert [p.project_id for p in result.projects] == ["proj-a", "proj-b"]
    # 4 domínios por projeto, na ordem canônica
    assert [k.kind for k in result.projects[0].caches] == [
        "lineage",
        "access",
        "finops_scan_events",
        "storage_read_keys",
    ]
    assert result.projects[0].caches[0].event_count == 10
    assert result.projects[0].caches[1].cached_at is None

    # freshness distingue "nunca rodou" de janela conhecida + expõe modo
    lineage_cache = result.projects[0].caches[0]
    assert lineage_cache.never_run is False
    assert lineage_cache.mode == "incremental"
    assert lineage_cache.window_start is not None
    assert lineage_cache.window_start.year == 2026 and lineage_cache.window_start.month == 7
    assert lineage_cache.last_full_scan_at is not None
    assert result.projects[0].caches[1].never_run is True
