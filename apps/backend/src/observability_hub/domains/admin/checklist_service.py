"""Checklist best-effort do onboarding de um projeto-alvo
(docs/onboarding-cliente.md) — usado por Admin → Por projeto antes de
registrar um projeto novo, e ao revisar um pedido de inclusão
(domains/admin/service.py::create_access_requests, request_type
"inclusion").

"Best-effort" de propósito: confirmar de verdade que uma role foi
concedida exigiria ler a IAM policy do projeto-alvo
(resourcemanager.projects.getIamPolicy), permissão que não faz parte do
checklist hoje — em vez disso, cada item tenta a operação real
(probing) e reporta se ela funcionou. Limitação conhecida e aceita:
`roles/logging.privateLogViewer` faltando não derruba a chamada de
Logging, só devolve vazio (mesma ambiguidade já documentada em
domains/lineage/domains/access) — o probe não distingue isso de "sem
atividade". O item de audit logs não é probável de jeito nenhum (não é
uma leitura de dado, é config do projeto) e fica sempre "not_checked".
"""

from google.api_core.exceptions import Forbidden, GoogleAPICallError, NotFound
from google.cloud import bigquery, storage
from google.cloud import logging as cloud_logging

from observability_hub.core.bigquery import discover_regions
from observability_hub.core.exceptions import ProjectAccessDeniedError, ProjectNotFoundError
from observability_hub.domains.admin.schemas import ChecklistItem, ProjectChecklistResponse

_AUDIT_LOGS_DETAIL = (
    "Não verificável automaticamente (não é uma permissão de leitura de "
    "dado, é configuração do projeto). Confirme manualmente: "
    "gcloud projects get-iam-policy {project_id} --format=json "
    "— procure 'auditConfigs' com service 'bigquery.googleapis.com' "
    "cobrindo DATA_READ/DATA_WRITE."
)


def _check_bigquery(client: bigquery.Client, project_id: str) -> ChecklistItem:
    try:
        discover_regions(project_id, client=client)
    except ProjectNotFoundError:
        return ChecklistItem(item="bigquery", status="not_found", detail="Projeto não encontrado.")
    except ProjectAccessDeniedError:
        return ChecklistItem(
            item="bigquery",
            status="denied",
            detail="Sem acesso — confira bigquery.metadataViewer/jobUser/dataViewer.",
        )
    return ChecklistItem(item="bigquery", status="ok", detail="INFORMATION_SCHEMA acessível.")


def _check_logging(client: cloud_logging.Client, project_id: str) -> ChecklistItem:
    detail_ok = (
        "Cloud Logging acessível (logging.viewer). Não dá pra confirmar "
        "por aqui se logging.privateLogViewer também está concedida — "
        "sem ela, lineage/mapa de acesso ficam sempre vazios sem erro "
        "nenhum (ver docs/onboarding-cliente.md)."
    )
    try:
        entries = client.list_entries(resource_names=[f"projects/{project_id}"], page_size=1)
        next(iter(entries), None)
    except NotFound:
        return ChecklistItem(item="logging", status="not_found", detail="Projeto não encontrado.")
    except Forbidden:
        return ChecklistItem(
            item="logging", status="denied", detail="Sem acesso — confira roles/logging.viewer."
        )
    return ChecklistItem(item="logging", status="ok", detail=detail_ok)


def _check_storage(client: storage.Client, project_id: str) -> ChecklistItem:
    try:
        buckets = client.list_buckets(project=project_id)
        next(iter(buckets), None)
    except NotFound:
        return ChecklistItem(item="storage", status="not_found", detail="Projeto não encontrado.")
    except Forbidden:
        return ChecklistItem(
            item="storage",
            status="denied",
            detail="Sem acesso — confira roles/storage.bucketViewer/objectViewer.",
        )
    except GoogleAPICallError as exc:
        return ChecklistItem(item="storage", status="denied", detail=str(exc))
    return ChecklistItem(item="storage", status="ok", detail="Cloud Storage acessível.")


def check_project_checklist(
    bq_client: bigquery.Client,
    logging_client: cloud_logging.Client,
    storage_client: storage.Client,
    project_id: str,
) -> ProjectChecklistResponse:
    items = [
        _check_bigquery(bq_client, project_id),
        _check_logging(logging_client, project_id),
        _check_storage(storage_client, project_id),
        ChecklistItem(
            item="audit_logs",
            status="not_checked",
            detail=_AUDIT_LOGS_DETAIL.format(project_id=project_id),
        ),
    ]
    return ProjectChecklistResponse(project_id=project_id, items=items)
