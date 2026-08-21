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


class AccessRequest(BaseModel):
    request_id: str
    email: str
    project_id: str
    status: AccessRequestStatus
    requested_at: datetime
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class AccessRequestsListResponse(BaseModel):
    requests: list[AccessRequest]


class CreateAccessRequestsRequest(BaseModel):
    project_ids: list[str] = Field(default_factory=list)
