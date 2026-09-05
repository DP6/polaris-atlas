from datetime import date

from fastapi import APIRouter, Depends, Query
from google.cloud import bigquery, firestore, run_v2, storage
from google.cloud import logging as cloud_logging

from atlas.core.auth import require_admin
from atlas.core.bigquery import get_client
from atlas.core.firestore import get_firestore_client
from atlas.core.logging_client import get_logging_client
from atlas.core.run_client import get_run_client
from atlas.core.storage_client import get_storage_client
from atlas.domains.admin import analytics_service, checklist_service, service
from atlas.domains.admin.analytics_schemas import (
    AccessRequestAnalyticsResponse,
    FavoritesAnalyticsResponse,
    LoginAnalyticsResponse,
    NavigationAnalyticsResponse,
    PiiScanActivityResponse,
    ProfilingActivityResponse,
    RetentionFunnelResponse,
    UsageHeatmapResponse,
)
from atlas.domains.admin.schemas import (
    AccessRequest,
    AccessRequestsListResponse,
    AccessRequestStatus,
    EventCacheRunsResponse,
    EventCacheStatusResponse,
    HubGroup,
    HubGroupsListResponse,
    HubProject,
    HubProjectsListResponse,
    HubUser,
    HubUsersListResponse,
    ProjectChecklistResponse,
    ProjectUsersResponse,
    UpsertHubGroupRequest,
    UpsertHubProjectRequest,
    UpsertHubUserRequest,
    WorkspaceGroupsListResponse,
)
from atlas.domains.auth.schemas import UserInfo

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/users", response_model=HubUsersListResponse)
def list_users(client: firestore.Client = Depends(get_firestore_client)) -> HubUsersListResponse:
    return service.list_users(client)


@router.put("/users/{email}", response_model=HubUser)
def upsert_user(
    email: str,
    request: UpsertHubUserRequest,
    admin_user: UserInfo = Depends(require_admin),
    client: firestore.Client = Depends(get_firestore_client),
) -> HubUser:
    return service.upsert_user(client, email, request, updated_by=admin_user.email)


@router.delete("/users/{email}", status_code=204)
def delete_user(
    email: str,
    client: firestore.Client = Depends(get_firestore_client),
) -> None:
    service.delete_user(client, email)


@router.get("/projects", response_model=HubProjectsListResponse)
def list_projects(
    client: firestore.Client = Depends(get_firestore_client),
) -> HubProjectsListResponse:
    return service.list_projects(client)


@router.put("/projects/{project_id}", response_model=HubProject)
def upsert_project(
    project_id: str,
    request: UpsertHubProjectRequest,
    admin_user: UserInfo = Depends(require_admin),
    client: firestore.Client = Depends(get_firestore_client),
) -> HubProject:
    return service.upsert_project(client, project_id, request, updated_by=admin_user.email)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    client: firestore.Client = Depends(get_firestore_client),
) -> None:
    service.delete_project(client, project_id)


@router.get("/projects/{project_id}/checklist", response_model=ProjectChecklistResponse)
def get_project_checklist(
    project_id: str,
    bq_client: bigquery.Client = Depends(get_client),
    logging_client: cloud_logging.Client = Depends(get_logging_client),
    storage_client: storage.Client = Depends(get_storage_client),
) -> ProjectChecklistResponse:
    return checklist_service.check_project_checklist(
        bq_client, logging_client, storage_client, project_id
    )


@router.get("/projects/{project_id}/users", response_model=ProjectUsersResponse)
def get_project_users(
    project_id: str,
    client: firestore.Client = Depends(get_firestore_client),
) -> ProjectUsersResponse:
    return service.get_project_users(client, project_id)


@router.post("/projects/{project_id}/users/{email}", response_model=HubUser)
def grant_project(
    project_id: str,
    email: str,
    admin_user: UserInfo = Depends(require_admin),
    client: firestore.Client = Depends(get_firestore_client),
) -> HubUser:
    return service.grant_project_to_user(client, project_id, email, updated_by=admin_user.email)


@router.delete("/projects/{project_id}/users/{email}", status_code=204)
def revoke_project(
    project_id: str,
    email: str,
    admin_user: UserInfo = Depends(require_admin),
    client: firestore.Client = Depends(get_firestore_client),
) -> None:
    service.revoke_project_from_user(client, project_id, email, updated_by=admin_user.email)


@router.get("/groups", response_model=HubGroupsListResponse)
def list_groups(client: firestore.Client = Depends(get_firestore_client)) -> HubGroupsListResponse:
    return service.list_groups(client)


@router.put("/groups/{group_id}", response_model=HubGroup)
def upsert_group(
    group_id: str,
    request: UpsertHubGroupRequest,
    admin_user: UserInfo = Depends(require_admin),
    client: firestore.Client = Depends(get_firestore_client),
) -> HubGroup:
    return service.upsert_group(client, group_id, request, updated_by=admin_user.email)


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(
    group_id: str,
    client: firestore.Client = Depends(get_firestore_client),
) -> None:
    service.delete_group(client, group_id)


@router.get("/workspace-groups", response_model=WorkspaceGroupsListResponse)
def list_workspace_groups() -> WorkspaceGroupsListResponse:
    return service.list_workspace_groups()


@router.get("/access-requests", response_model=AccessRequestsListResponse)
def list_access_requests(
    status: AccessRequestStatus | None = Query(default=None),
    client: firestore.Client = Depends(get_firestore_client),
) -> AccessRequestsListResponse:
    return service.list_access_requests(client, status.value if status else None)


@router.post("/access-requests/{request_id}/approve", response_model=AccessRequest)
def approve_access_request(
    request_id: str,
    admin_user: UserInfo = Depends(require_admin),
    client: firestore.Client = Depends(get_firestore_client),
) -> AccessRequest:
    return service.approve_access_request(client, request_id, resolved_by=admin_user.email)


@router.post("/access-requests/{request_id}/deny", response_model=AccessRequest)
def deny_access_request(
    request_id: str,
    admin_user: UserInfo = Depends(require_admin),
    client: firestore.Client = Depends(get_firestore_client),
) -> AccessRequest:
    return service.deny_access_request(client, request_id, resolved_by=admin_user.email)


@router.get("/analytics/logins", response_model=LoginAnalyticsResponse)
def login_analytics(
    lookback_days: int = Query(default=90, ge=1, le=365),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    client: firestore.Client = Depends(get_firestore_client),
) -> LoginAnalyticsResponse:
    return analytics_service.get_login_analytics(client, lookback_days, from_date, to_date)


@router.get("/analytics/favorites", response_model=FavoritesAnalyticsResponse)
def favorites_analytics(
    client: firestore.Client = Depends(get_firestore_client),
) -> FavoritesAnalyticsResponse:
    return analytics_service.get_favorites_analytics(client)


@router.get("/analytics/profiling", response_model=ProfilingActivityResponse)
def profiling_activity(
    limit: int = Query(default=200, ge=1, le=1000),
    client: firestore.Client = Depends(get_firestore_client),
) -> ProfilingActivityResponse:
    return analytics_service.get_profiling_activity(client, limit)


@router.get("/analytics/access-requests", response_model=AccessRequestAnalyticsResponse)
def access_request_analytics(
    client: firestore.Client = Depends(get_firestore_client),
) -> AccessRequestAnalyticsResponse:
    return analytics_service.get_access_request_analytics(client)


@router.get("/analytics/navigation", response_model=NavigationAnalyticsResponse)
def navigation_analytics(
    client: firestore.Client = Depends(get_firestore_client),
) -> NavigationAnalyticsResponse:
    return analytics_service.get_navigation_analytics(client)


@router.get("/analytics/pii-scans", response_model=PiiScanActivityResponse)
def pii_scan_activity(
    limit: int = Query(default=200, ge=1, le=1000),
    client: firestore.Client = Depends(get_firestore_client),
) -> PiiScanActivityResponse:
    return analytics_service.get_pii_scan_activity(client, limit)


@router.get("/analytics/usage-heatmap", response_model=UsageHeatmapResponse)
def usage_heatmap(
    lookback_days: int = Query(default=90, ge=1, le=365),
    client: firestore.Client = Depends(get_firestore_client),
) -> UsageHeatmapResponse:
    return analytics_service.get_usage_heatmap(client, lookback_days)


@router.get("/analytics/retention-funnel", response_model=RetentionFunnelResponse)
def retention_funnel(
    lookback_days: int = Query(default=90, ge=1, le=365),
    client: firestore.Client = Depends(get_firestore_client),
) -> RetentionFunnelResponse:
    return analytics_service.get_retention_funnel(client, lookback_days)


@router.post("/event-cache/refresh", status_code=202)
def refresh_event_cache(
    force_full: bool = Query(default=False),
    project: list[str] = Query(default=[]),
    run_client: run_v2.JobsClient = Depends(get_run_client),
) -> None:
    """Dispara sob demanda o Cloud Run Job de refresh do cache de audit
    log (lineage, access, finops e storage) — mesmo Job do ciclo diário
    automático (ver docs/specs/lineage.md). 202 porque a execução do Job
    é assíncrona: este endpoint só confirma o disparo, não espera o
    resultado.

    - `force_full=true` (toggle "forçar completo" da tela) faz o Job
      re-escanear a janela inteira em vez do delta incremental.
    - `project=a&project=b` restringe o scan a esses projetos; ausente =
      todos (união hub_projects ∪ "vistos")."""
    service.trigger_event_cache_refresh(run_client, force_full=force_full, projects=project or None)


@router.get("/event-cache/status", response_model=EventCacheStatusResponse)
def get_event_cache_status(
    client: firestore.Client = Depends(get_firestore_client),
) -> EventCacheStatusResponse:
    """Freshness do cache de audit log por projeto × domínio (quando cada
    cache foi gerado, janela, modo, "nunca rodou"). Lido do Firestore, sem
    tocar Cloud Logging nem o Cloud Run Admin API. Polling frequente na
    tela Administração → Caches — o histórico de execuções vem do endpoint
    /event-cache/runs, com cadência própria."""
    return service.get_event_cache_status(client)


@router.get("/event-cache/runs", response_model=EventCacheRunsResponse)
def list_event_cache_runs(
    client: firestore.Client = Depends(get_firestore_client),
) -> EventCacheRunsResponse:
    """Histórico completo de execuções do Job de refresh (~200 retidas,
    mais recentes primeiro) — status por projeto (ok / sem acesso / cota
    estourada / erro), modo (full/incremental) e contagens. A tela filtra
    (status, projeto, período, só com falha) e pagina no cliente."""
    return service.list_event_cache_runs(client)
