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
) -> None:
    """Dispara uma execução do Cloud Run Job de forma assíncrona (não
    espera terminar) — a SA de runtime do backend precisa de
    roles/run.invoker sobre esse Job específico (ver módulo Terraform
    cloud-run-job, segundo IAM binding).

    `force_full` injeta `OBSERVABILITY_HUB_CACHE_FORCE_FULL=1` só nesta
    execução (RunJobRequest.Overrides) — o job faz full scan da janela
    inteira em vez do delta incremental. Sem `force_full` a execução usa
    a env config padrão do Job (incremental)."""
    job_path = client.job_path(project_id, region, job_name)
    if not force_full:
        client.run_job(name=job_path)
        return
    client.run_job(
        request=run_v2.RunJobRequest(
            name=job_path,
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[
                    run_v2.RunJobRequest.Overrides.ContainerOverride(
                        env=[run_v2.EnvVar(name="OBSERVABILITY_HUB_CACHE_FORCE_FULL", value="1")]
                    )
                ]
            ),
        )
    )
