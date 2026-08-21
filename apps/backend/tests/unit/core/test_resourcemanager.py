from unittest.mock import MagicMock

from google.api_core.exceptions import PermissionDenied

from observability_hub.core import resourcemanager


def test_list_reachable_projects_returns_projects(monkeypatch):
    project_a = MagicMock(project_id="project-a", display_name="Project A")
    project_b = MagicMock(project_id="project-b", display_name="Project B")
    client = MagicMock()
    client.search_projects.return_value = [project_a, project_b]
    monkeypatch.setattr(resourcemanager, "get_client", lambda: client)

    result = resourcemanager.list_reachable_projects()

    assert result == [
        {"project_id": "project-a", "display_name": "Project A"},
        {"project_id": "project-b", "display_name": "Project B"},
    ]
    client.search_projects.assert_called_once_with(query="state:ACTIVE")


def test_list_reachable_projects_returns_empty_and_does_not_raise_on_api_error(monkeypatch):
    client = MagicMock()
    client.search_projects.side_effect = PermissionDenied("sem roles/browser")
    monkeypatch.setattr(resourcemanager, "get_client", lambda: client)

    result = resourcemanager.list_reachable_projects()

    assert result == []
