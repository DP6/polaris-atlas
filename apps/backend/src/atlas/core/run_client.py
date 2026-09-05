"""Client compartilhado da Cloud Run Admin API — usado só pelo gatilho
manual de admin (domains/admin) pra rodar sob demanda o Cloud Run Job de
refresh do cache de audit log (jobs/refresh_event_cache.py), fora do
ciclo diário automático do Cloud Scheduler (infra/terraform/modules/
cloud-run-job). Mesmo padrão de client cacheado por processo de
core/bigquery.py::get_client()/core/storage_client.py::get_storage_client().
"""

from functools import lru_cache

from google.cloud import run_v2


@lru_cache
def get_run_client() -> run_v2.JobsClient:
    return run_v2.JobsClient()


def trigger_job_execution(
    client: run_v2.JobsClient,
    project_id: str,
    region: str,
    job_name: str,
    *,
    force_full: bool = False,
    only_projects: list[str] | None = None,
) -> None:
    """Dispara uma execução do Cloud Run Job de forma assíncrona (não
    espera terminar) — a SA de runtime do backend precisa de
    roles/run.invoker sobre esse Job específico (ver módulo Terraform
    cloud-run-job, segundo IAM binding).

    Overrides de env injetados só nesta execução (RunJobRequest.Overrides),
    quando pedidos pelo gatilho manual de admin:
    - `force_full` → `ATLAS_CACHE_FORCE_FULL=1`: full scan da
      janela inteira em vez do delta incremental.
    - `only_projects` → `ATLAS_CACHE_ONLY_PROJECTS=a,b`: roda
      só esses projetos em vez da união hub_projects ∪ "vistos".

    Sem nenhum dos dois a execução usa a env config padrão do Job
    (incremental, todos os projetos) — igual ao ciclo diário do Scheduler."""
    job_path = client.job_path(project_id, region, job_name)
    env: list[run_v2.EnvVar] = []
    if force_full:
        env.append(run_v2.EnvVar(name="ATLAS_CACHE_FORCE_FULL", value="1"))
    if only_projects:
        env.append(run_v2.EnvVar(name="ATLAS_CACHE_ONLY_PROJECTS", value=",".join(only_projects)))
    if not env:
        client.run_job(name=job_path)
        return
    client.run_job(
        request=run_v2.RunJobRequest(
            name=job_path,
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[run_v2.RunJobRequest.Overrides.ContainerOverride(env=env)]
            ),
        )
    )
