from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class HubUser(BaseModel):
    email: str
    is_admin: bool = False
    # "*" (literal) libera qualquer project_id que a service account de
    # runtime alcançar — ver domains/admin/service.py::has_project_access.
    allowed_projects: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    updated_by: str


class HubUsersListResponse(BaseModel):
    users: list[HubUser]


class UpsertHubUserRequest(BaseModel):
    is_admin: bool = False
    allowed_projects: list[str] = Field(default_factory=list)


class HubProject(BaseModel):
    project_id: str
    # Libera o projeto pra QUALQUER usuário do Hub, inclusive quem ainda
    # não tem doc em hub_users (usuário futuro) — eixo independente do
    # allowed_projects de cada usuário, ver
    # domains/admin/service.py::has_project_access.
    is_public: bool = False
    created_at: datetime
    updated_at: datetime
    updated_by: str


class HubProjectsListResponse(BaseModel):
    projects: list[HubProject]


class UpsertHubProjectRequest(BaseModel):
    is_public: bool = False


class HubGroup(BaseModel):
    group_id: str
    # E-mails cadastrados manualmente na Hub — editável na UI, persistido
    # em hub_groups. Pra quem precisa de acesso via este grupo sem estar
    # no grupo real do Workspace.
    manual_members: list[str] = Field(default_factory=list)
    # Membros reais do grupo no Google Workspace (Admin SDK Directory
    # API, domain-wide delegation) — só leitura, nunca persistido em
    # Firestore, resolvido on-the-fly a cada leitura (com cache curto,
    # ver core/workspace_directory.py). Lista vazia se a integração
    # ainda não estiver configurada ou o grupo não existir/for
    # inacessível no Workspace — nunca um erro.
    workspace_members: list[str] = Field(default_factory=list)
    # Cada membro (manual OU do Workspace) herda estes projetos, além do
    # que já tiver individualmente em hub_users. Mesma semântica de
    # HubUser.allowed_projects, incluindo "*". Ver
    # domains/admin/service.py::has_project_access.
    allowed_projects: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    updated_by: str


class HubGroupsListResponse(BaseModel):
    groups: list[HubGroup]


class UpsertHubGroupRequest(BaseModel):
    manual_members: list[str] = Field(default_factory=list)
    allowed_projects: list[str] = Field(default_factory=list)


class WorkspaceGroupInfo(BaseModel):
    """Grupo existente no Google Workspace (não necessariamente
    importado como hub_group ainda) — pra popular o seletor de "criar
    grupo" na UI. Ver core/workspace_directory.py::list_domain_groups."""

    email: str
    name: str | None = None


class WorkspaceGroupsListResponse(BaseModel):
    groups: list[WorkspaceGroupInfo]


class ProjectAccessGrant(BaseModel):
    email: str
    is_admin: bool
    # "wildcard" = tem "*" em allowed_projects (acesso a tudo, não só
    # este projeto); "explicit" = este project_id está listado nominalmente.
    granted_via: Literal["explicit", "wildcard"]


class ProjectUsersResponse(BaseModel):
    project_id: str
    is_public: bool
    users: list[ProjectAccessGrant]


class AccessRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class AccessRequestType(str, Enum):
    ACCESS = "access"
    INCLUSION = "inclusion"


class AccessRequest(BaseModel):
    request_id: str
    email: str
    project_id: str
    # "access" = pedir acesso a um projeto já onboardado no Hub (fluxo
    # original); "inclusion" = pedir que o projeto seja registrado no
    # Hub — aprovar chama upsert_project além de grant_project_to_user.
    # Default cobre docs antigos no Firestore, gravados antes deste
    # campo existir.
    request_type: AccessRequestType = AccessRequestType.ACCESS
    status: AccessRequestStatus
    requested_at: datetime
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class AccessRequestsListResponse(BaseModel):
    requests: list[AccessRequest]


class CreateAccessRequestsRequest(BaseModel):
    project_ids: list[str] = Field(default_factory=list)
    request_type: AccessRequestType = AccessRequestType.ACCESS


class ChecklistItemName(str, Enum):
    BIGQUERY = "bigquery"
    LOGGING = "logging"
    STORAGE = "storage"
    AUDIT_LOGS = "audit_logs"


class ChecklistItemStatus(str, Enum):
    OK = "ok"
    DENIED = "denied"
    NOT_FOUND = "not_found"
    NOT_CHECKED = "not_checked"


class ChecklistItem(BaseModel):
    item: ChecklistItemName
    status: ChecklistItemStatus
    detail: str


class ProjectChecklistResponse(BaseModel):
    project_id: str
    items: list[ChecklistItem]


# --- Acompanhamento do cache de audit log (Administração → Caches) ------------


class EventCacheRunProject(BaseModel):
    project_id: str
    # "ok" | "access_denied" | "quota_exceeded" | "api_error" | "unexpected_error"
    status: str
    finished_at: datetime | None = None
    job_events: int | None = None
    access_events: int | None = None
    scan_events: int | None = None
    storage_read_object_keys: int | None = None
    # Modelo incremental (jobs/refresh_event_cache.py): "full" | "incremental"
    # deste projeto neste run, e o tamanho do delta lido (nº de LogEntry).
    mode: str | None = None
    raw_entries: int | None = None


class EventCacheRun(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str  # "running" | "done"
    project_count: int
    projects: list[EventCacheRunProject]


class EventCacheKindStatus(BaseModel):
    kind: str  # "lineage" | "access" | "finops_scan_events" | "storage_read_keys"
    label: str
    cached_at: datetime | None = None
    event_count: int | None = None
    # True = nenhum metadado no Firestore (o job nunca populou este
    # domínio pra este projeto) — a tela mostra "nunca rodou" em vez de
    # uma janela. Ver domains/admin/service.py::get_event_cache_status.
    never_run: bool = True
    # Piso da janela rolante do blob atual (evento mais antigo mantido) e
    # "full" | "incremental" do último write do job — modelo incremental,
    # ver jobs/refresh_event_cache.py.
    window_start: datetime | None = None
    last_full_scan_at: datetime | None = None
    mode: str | None = None


class EventCacheProjectStatus(BaseModel):
    project_id: str
    caches: list[EventCacheKindStatus]


class EventCacheStatusResponse(BaseModel):
    # Só freshness por projeto × domínio — o histórico de execuções vive
    # em GET /event-cache/runs (EventCacheRunsResponse), com cadência de
    # polling própria (ver docs/specs/admin.md, aba "Caches").
    projects: list[EventCacheProjectStatus]


class EventCacheRunsResponse(BaseModel):
    # Todas as execuções retidas (~200, ver core/event_cache.py
    # ::_CACHE_RUNS_KEEP) — a tela de Administração → Caches filtra e
    # pagina no cliente, mesmo padrão das outras seções de analytics do
    # admin (lista carregada inteira, corte no front).
    runs: list[EventCacheRun]


class ProjectAdmin(BaseModel):
    """hub_projects/{project_id}/project_admins/{email} — ver
    docs/specs/admin.md, "Admin de projeto". Diferente de HubUser/
    HubProject/HubGroup: este documento vive dentro do projeto, não do
    usuário — a pergunta mais frequente é "quem administra o projeto X"."""

    email: str
    # None = projeto inteiro (todos os datasets, presentes e futuros,
    # reavaliado a cada request). Lista = só esses datasets, estático até
    # alguém editar o grant. Ver core/auth.py::require_project_admin.
    datasets: list[str] | None = None
    granted_by: str
    granted_at: datetime
    updated_at: datetime


class ProjectAdminsListResponse(BaseModel):
    project_id: str
    admins: list[ProjectAdmin]


class UpsertProjectAdminRequest(BaseModel):
    datasets: list[str] | None = None
