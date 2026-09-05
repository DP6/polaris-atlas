from unittest.mock import MagicMock

from atlas.core import run_client


def test_trigger_job_execution_without_force_full_uses_plain_name():
    client = MagicMock()
    client.job_path.return_value = "projects/p/locations/r/jobs/j"

    run_client.trigger_job_execution(client, "p", "r", "j")

    client.job_path.assert_called_once_with("p", "r", "j")
    client.run_job.assert_called_once_with(name="projects/p/locations/r/jobs/j")


def test_trigger_job_execution_force_full_injects_env_override():
    client = MagicMock()
    client.job_path.return_value = "projects/p/locations/r/jobs/j"

    run_client.trigger_job_execution(client, "p", "r", "j", force_full=True)

    assert client.run_job.call_count == 1
    request = client.run_job.call_args.kwargs["request"]
    env = request.overrides.container_overrides[0].env
    assert [(e.name, e.value) for e in env] == [("ATLAS_CACHE_FORCE_FULL", "1")]
    assert request.name == "projects/p/locations/r/jobs/j"


def test_trigger_job_execution_only_projects_injects_env_override():
    client = MagicMock()
    client.job_path.return_value = "projects/p/locations/r/jobs/j"

    run_client.trigger_job_execution(client, "p", "r", "j", only_projects=["proj-a", "proj-b"])

    env = client.run_job.call_args.kwargs["request"].overrides.container_overrides[0].env
    assert [(e.name, e.value) for e in env] == [("ATLAS_CACHE_ONLY_PROJECTS", "proj-a,proj-b")]


def test_trigger_job_execution_combines_force_full_and_only_projects():
    client = MagicMock()
    client.job_path.return_value = "projects/p/locations/r/jobs/j"

    run_client.trigger_job_execution(
        client, "p", "r", "j", force_full=True, only_projects=["proj-a"]
    )

    env = client.run_job.call_args.kwargs["request"].overrides.container_overrides[0].env
    assert [(e.name, e.value) for e in env] == [
        ("ATLAS_CACHE_FORCE_FULL", "1"),
        ("ATLAS_CACHE_ONLY_PROJECTS", "proj-a"),
    ]


def test_trigger_job_execution_empty_only_projects_uses_plain_name():
    client = MagicMock()
    client.job_path.return_value = "projects/p/locations/r/jobs/j"

    run_client.trigger_job_execution(client, "p", "r", "j", only_projects=[])

    client.run_job.assert_called_once_with(name="projects/p/locations/r/jobs/j")
