from unittest.mock import MagicMock

from observability_hub.core import run_client


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
    assert [(e.name, e.value) for e in env] == [("OBSERVABILITY_HUB_CACHE_FORCE_FULL", "1")]
    assert request.name == "projects/p/locations/r/jobs/j"
