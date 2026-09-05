from unittest.mock import MagicMock

from atlas.core import workspace_directory


def setup_function():
    """Cache é um dict de módulo — limpa entre testes pra um não vazar
    resultado pro outro (mesmo cuidado de qualquer cache global em teste)."""
    workspace_directory._members_cache.clear()
    workspace_directory._domain_groups_cache.clear()


def test_get_group_members_returns_empty_when_integration_not_configured(monkeypatch):
    monkeypatch.setattr(workspace_directory.settings, "workspace_impersonate_email", None)

    result = workspace_directory.get_group_members("cliente-a@dp6.com.br")

    assert result == []


def test_get_group_members_returns_empty_and_does_not_raise_on_credentials_error(monkeypatch):
    monkeypatch.setattr(
        workspace_directory.settings, "workspace_impersonate_email", "admin@dp6.com.br"
    )

    def boom():
        raise RuntimeError("google.auth.default() falhou")

    monkeypatch.setattr(workspace_directory, "_build_delegated_credentials", boom)

    result = workspace_directory.get_group_members("cliente-a@dp6.com.br")

    assert result == []


def test_get_group_members_returns_empty_and_does_not_raise_on_http_error(monkeypatch):
    monkeypatch.setattr(
        workspace_directory.settings, "workspace_impersonate_email", "admin@dp6.com.br"
    )
    monkeypatch.setattr(workspace_directory, "_build_delegated_credentials", lambda: MagicMock())

    session_mock = MagicMock()
    session_mock.get.side_effect = RuntimeError("Workspace indisponível")
    monkeypatch.setattr(workspace_directory, "AuthorizedSession", lambda credentials: session_mock)

    result = workspace_directory.get_group_members("cliente-a@dp6.com.br")

    assert result == []


def test_get_group_members_paginates_and_normalizes_email_case(monkeypatch):
    monkeypatch.setattr(
        workspace_directory.settings, "workspace_impersonate_email", "admin@dp6.com.br"
    )
    monkeypatch.setattr(workspace_directory, "_build_delegated_credentials", lambda: MagicMock())

    page_1 = MagicMock()
    page_1.json.return_value = {
        "members": [{"email": "A@DP6.com.br"}],
        "nextPageToken": "page-2",
    }
    page_2 = MagicMock()
    page_2.json.return_value = {"members": [{"email": "b@dp6.com.br"}]}

    session_mock = MagicMock()
    session_mock.get.side_effect = [page_1, page_2]
    monkeypatch.setattr(workspace_directory, "AuthorizedSession", lambda credentials: session_mock)

    result = workspace_directory.get_group_members("cliente-a@dp6.com.br")

    assert result == ["a@dp6.com.br", "b@dp6.com.br"]
    assert session_mock.get.call_count == 2


def test_get_group_members_uses_cache_on_second_call(monkeypatch):
    monkeypatch.setattr(
        workspace_directory.settings, "workspace_impersonate_email", "admin@dp6.com.br"
    )
    build_mock = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(workspace_directory, "_build_delegated_credentials", build_mock)

    page = MagicMock()
    page.json.return_value = {"members": [{"email": "a@dp6.com.br"}]}
    session_mock = MagicMock()
    session_mock.get.return_value = page
    monkeypatch.setattr(workspace_directory, "AuthorizedSession", lambda credentials: session_mock)

    first = workspace_directory.get_group_members("cliente-a@dp6.com.br")
    second = workspace_directory.get_group_members("cliente-a@dp6.com.br")

    assert first == second == ["a@dp6.com.br"]
    # Segunda chamada veio do cache — não repetiu a chamada externa.
    build_mock.assert_called_once()


# --- list_domain_groups -------------------------------------------------------------


def test_list_domain_groups_returns_empty_when_integration_not_configured(monkeypatch):
    monkeypatch.setattr(workspace_directory.settings, "workspace_impersonate_email", None)

    assert workspace_directory.list_domain_groups() == []


def test_list_domain_groups_returns_empty_and_does_not_raise_on_http_error(monkeypatch):
    monkeypatch.setattr(
        workspace_directory.settings, "workspace_impersonate_email", "admin@dp6.com.br"
    )
    monkeypatch.setattr(workspace_directory, "_build_delegated_credentials", lambda: MagicMock())

    session_mock = MagicMock()
    session_mock.get.side_effect = RuntimeError("Workspace indisponível")
    monkeypatch.setattr(workspace_directory, "AuthorizedSession", lambda credentials: session_mock)

    assert workspace_directory.list_domain_groups() == []


def test_list_domain_groups_uses_domain_from_impersonate_email(monkeypatch):
    monkeypatch.setattr(
        workspace_directory.settings, "workspace_impersonate_email", "admin@dp6.com.br"
    )
    monkeypatch.setattr(workspace_directory, "_build_delegated_credentials", lambda: MagicMock())

    page = MagicMock()
    page.json.return_value = {
        "groups": [
            {"email": "Cliente-A@DP6.com.br", "name": "Cliente A", "directMembersCount": "3"}
        ]
    }
    session_mock = MagicMock()
    session_mock.get.return_value = page
    monkeypatch.setattr(workspace_directory, "AuthorizedSession", lambda credentials: session_mock)

    result = workspace_directory.list_domain_groups()

    assert result == [{"email": "cliente-a@dp6.com.br", "name": "Cliente A"}]
    called_params = session_mock.get.call_args.kwargs["params"]
    assert called_params["domain"] == "dp6.com.br"


def test_list_domain_groups_paginates(monkeypatch):
    monkeypatch.setattr(
        workspace_directory.settings, "workspace_impersonate_email", "admin@dp6.com.br"
    )
    monkeypatch.setattr(workspace_directory, "_build_delegated_credentials", lambda: MagicMock())

    page_1 = MagicMock()
    page_1.json.return_value = {
        "groups": [{"email": "a@dp6.com.br", "name": "A", "directMembersCount": "2"}],
        "nextPageToken": "page-2",
    }
    page_2 = MagicMock()
    page_2.json.return_value = {
        "groups": [{"email": "b@dp6.com.br", "name": "B", "directMembersCount": "5"}]
    }

    session_mock = MagicMock()
    session_mock.get.side_effect = [page_1, page_2]
    monkeypatch.setattr(workspace_directory, "AuthorizedSession", lambda credentials: session_mock)

    result = workspace_directory.list_domain_groups()

    assert result == [
        {"email": "a@dp6.com.br", "name": "A"},
        {"email": "b@dp6.com.br", "name": "B"},
    ]
    assert session_mock.get.call_count == 2


def test_list_domain_groups_uses_cache_on_second_call(monkeypatch):
    monkeypatch.setattr(
        workspace_directory.settings, "workspace_impersonate_email", "admin@dp6.com.br"
    )
    build_mock = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(workspace_directory, "_build_delegated_credentials", build_mock)

    page = MagicMock()
    page.json.return_value = {
        "groups": [{"email": "a@dp6.com.br", "name": "A", "directMembersCount": "2"}]
    }
    session_mock = MagicMock()
    session_mock.get.return_value = page
    monkeypatch.setattr(workspace_directory, "AuthorizedSession", lambda credentials: session_mock)

    first = workspace_directory.list_domain_groups()
    second = workspace_directory.list_domain_groups()

    assert first == second
    build_mock.assert_called_once()


def test_list_domain_groups_excludes_groups_with_one_or_fewer_direct_members(monkeypatch):
    """directMembersCount <= 1 é grupo pessoal auto-criado por
    funcionário (comum em domínios reais), não grupo de time/acesso —
    não deve poluir o seletor de "criar grupo"."""
    monkeypatch.setattr(
        workspace_directory.settings, "workspace_impersonate_email", "admin@dp6.com.br"
    )
    monkeypatch.setattr(workspace_directory, "_build_delegated_credentials", lambda: MagicMock())

    page = MagicMock()
    page.json.return_value = {
        "groups": [
            {"email": "sem-membros@dp6.com.br", "name": "Sem membros", "directMembersCount": "0"},
            {"email": "pessoal@dp6.com.br", "name": "Fulano Silva", "directMembersCount": "1"},
            {"email": "time@dp6.com.br", "name": "Time X", "directMembersCount": "2"},
            {"email": "sem-campo@dp6.com.br", "name": "Sem campo"},
        ]
    }
    session_mock = MagicMock()
    session_mock.get.return_value = page
    monkeypatch.setattr(workspace_directory, "AuthorizedSession", lambda credentials: session_mock)

    result = workspace_directory.list_domain_groups()

    assert result == [{"email": "time@dp6.com.br", "name": "Time X"}]
