from unittest.mock import MagicMock

from observability_hub.core import workspace_directory


def setup_function():
    """Cache é um dict de módulo — limpa entre testes pra um não vazar
    resultado pro outro (mesmo cuidado de qualquer cache global em teste)."""
    workspace_directory._members_cache.clear()


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
