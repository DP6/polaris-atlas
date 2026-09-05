"""Papel delegável "Admin de projeto" (ver docs/specs/admin.md, "Admin de
projeto"). Mesmo prefixo /api/v1/projects de api/v1/projects.py, router
separado (não colide: /admins não é /validate nem a listagem raiz).

Leitura (GET) exige só require_project_access — qualquer um com acesso ao
projeto vê quem o administra, não precisa ser admin pra consultar.
Escrita (PUT/DELETE) exige require_project_admin — superadmin ou Admin de
projeto existente escopado ao dataset relevante.
"""

from fastapi import APIRouter, Depends
from google.cloud import firestore

from atlas.core.auth import require_project_access, require_project_admin
from atlas.core.firestore import get_firestore_client
from atlas.domains.admin import service
from atlas.domains.admin.schemas import (
    ProjectAdmin,
    ProjectAdminsListResponse,
    UpsertProjectAdminRequest,
)
from atlas.domains.auth.schemas import UserInfo

router = APIRouter(prefix="/api/v1/projects", tags=["project-admins"])


@router.get(
    "/{project_id}/admins",
    response_model=ProjectAdminsListResponse,
    dependencies=[Depends(require_project_access)],
)
def list_project_admins(
    project_id: str, client: firestore.Client = Depends(get_firestore_client)
) -> ProjectAdminsListResponse:
    return service.list_project_admins(client, project_id)


@router.put("/{project_id}/admins/{email}", response_model=ProjectAdmin)
def grant_project_admin(
    project_id: str,
    email: str,
    request: UpsertProjectAdminRequest,
    # Sem dataset_id — conceder o papel é ação de escopo de projeto, ainda
    # que o grant resultante seja restrito a datasets (ver
    # docs/specs/admin.md, "Endpoints").
    granting_user: UserInfo = Depends(require_project_admin),
    client: firestore.Client = Depends(get_firestore_client),
) -> ProjectAdmin:
    return service.grant_project_admin(
        client, project_id, email, request, granted_by=granting_user.email
    )


@router.delete("/{project_id}/admins/{email}", status_code=204)
def revoke_project_admin(
    project_id: str,
    email: str,
    _revoking_user: UserInfo = Depends(require_project_admin),
    client: firestore.Client = Depends(get_firestore_client),
) -> None:
    service.revoke_project_admin(client, project_id, email)
