"""Entrypoint do Cloud Run Job de refresh do cache de audit log
(lineage + access + finops + storage) — roda 1x/dia (D-1) via Cloud
Scheduler (infra/terraform/modules/cloud-run-job) ou sob demanda via o
gatilho manual de admin (domains/admin::trigger_event_cache_refresh).
Mesma imagem Docker do backend, comando/entrypoint diferente (ver módulo
Terraform cloud-run-job) — `python -m observability_hub.jobs.refresh_event_cache`.

Não é um domínio — orquestra lineage, access, finops, storage e admin
(fonte da lista de projetos), mesma posição arquitetural de main.py.
Reaproveita as funções de scan já existentes (list_job_events/
list_access_events/list_scan_events/list_read_object_keys) sem duplicar
parsing; só adiciona a escrita no cache compartilhado
(core/event_cache.py). lineage e finops leem a mesma fonte de audit log
(jobservice.jobcompleted), com dois scans separados porque os dataclasses
diferem (JobEvent x ScanEvent) e domínios não compartilham parsing
(CLAUDE.md) — tradeoff aceito (1x/dia, fora do request path). O refresh
de storage é best-effort e isolado do de lineage/access/finops (ver
_refresh_storage_read_keys) porque Data Access audit logs do GCS podem
não estar habilitados no projeto (docs/specs/storage.md seção 6.2).
"""

import json
import logging as std_logging

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import firestore, storage
from google.cloud import logging as cloud_logging

from observability_hub.core import event_cache
from observability_hub.core.exceptions import LoggingAccessDeniedError
from observability_hub.core.firestore import get_firestore_client
from observability_hub.core.logging_client import get_logging_client
from observability_hub.core.storage_client import get_storage_client
from observability_hub.domains.access import repository as access_repository
from observability_hub.domains.admin import repository as admin_repository
from observability_hub.domains.finops import repository as finops_repository
from observability_hub.domains.lineage import repository as lineage_repository
from observability_hub.domains.storage import repository as storage_repository

logger = std_logging.getLogger("observability_hub.jobs.refresh_event_cache")


def _known_projects(firestore_client: firestore.Client) -> list[str]:
    """União de hub_projects (registro administrativo) com os projetos
    vistos via cache miss no request path (inclui os liberados só por
    wildcard "*", que nunca ganham doc em hub_projects — ver
    docs/specs/lineage.md, ASM)."""
    from_admin = {p["project_id"] for p in admin_repository.list_projects(firestore_client)}
    from_seen = set(event_cache.list_seen_projects(firestore_client))
    return sorted(from_admin | from_seen)


def _refresh_storage_read_keys(
    logging_client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
) -> int:
    """Best-effort, isolado do try/except principal de _refresh_project:
    Data Access audit logs (DATA_READ) do GCS podem não estar habilitados
    no projeto (ver docs/specs/storage.md seção 6.2 — ainda não habilitado
    em prod hoje), o que não deveria impedir o refresh de lineage/access
    do mesmo projeto. Retorna 0 nesses casos (mesmo efeito de cache vazio
    já tratado com grace pelo domains/storage/service.py)."""
    try:
        keys = storage_repository.list_read_object_keys(
            logging_client, project_id, storage_repository.LOOKBACK_DAYS
        )
    except LoggingAccessDeniedError:
        return 0
    except GoogleAPICallError as exc:
        logger.warning(
            json.dumps({"project_id": project_id, "status": "storage_api_error", "error": str(exc)})
        )
        return 0
    storage_repository.write_read_object_keys_cache(
        storage_client, firestore_client, project_id, keys
    )
    return len(keys)


def _refresh_project(
    logging_client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
) -> None:
    try:
        job_events = lineage_repository.list_job_events(logging_client, project_id)
        lineage_repository.write_job_events_cache(
            storage_client, firestore_client, project_id, job_events
        )

        access_events = access_repository.list_access_events(logging_client, project_id)
        access_repository.write_access_events_cache(
            storage_client, firestore_client, project_id, access_events
        )

        # finops lê a mesma fonte que lineage (jobservice.jobcompleted) —
        # se list_job_events passou, este passa. Fica no try principal (não
        # isolado como storage), já que não depende de audit log opcional.
        scan_events = finops_repository.list_scan_events(
            logging_client, project_id, finops_repository.LOOKBACK_DAYS
        )
        finops_repository.write_scan_events_cache(
            storage_client, firestore_client, project_id, scan_events
        )

        read_object_keys_count = _refresh_storage_read_keys(
            logging_client, storage_client, firestore_client, project_id
        )
    except LoggingAccessDeniedError:
        logger.warning(json.dumps({"project_id": project_id, "status": "access_denied"}))
        return
    except GoogleAPICallError as exc:
        # Cobre, entre outros, projeto inexistente/renomeado/deletado
        # (Cloud Logging devolve 404 NotFound em vez de 403 Forbidden
        # quando a SA do Hub não tem NENHUM binding de IAM no projeto —
        # `hub_projects`/"vistos" pode conter entradas obsoletas, ex:
        # projeto de cliente descontinuado). Um projeto com problema não
        # pode derrubar o refresh dos demais.
        logger.warning(
            json.dumps({"project_id": project_id, "status": "api_error", "error": str(exc)})
        )
        return
    except Exception as exc:  # noqa: BLE001 — rede de segurança final do job em lote
        logger.error(
            json.dumps({"project_id": project_id, "status": "unexpected_error", "error": str(exc)})
        )
        return

    logger.info(
        json.dumps(
            {
                "project_id": project_id,
                "status": "ok",
                "job_events": len(job_events),
                "access_events": len(access_events),
                "scan_events": len(scan_events),
                "storage_read_object_keys": read_object_keys_count,
            }
        )
    )


def main() -> None:
    logging_client = get_logging_client()
    storage_client = get_storage_client()
    firestore_client = get_firestore_client()

    projects = _known_projects(firestore_client)
    logger.info(json.dumps({"status": "start", "project_count": len(projects)}))
    for project_id in projects:
        _refresh_project(logging_client, storage_client, firestore_client, project_id)
    logger.info(json.dumps({"status": "done"}))


if __name__ == "__main__":
    main()
