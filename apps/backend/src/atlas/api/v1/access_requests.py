from fastapi import APIRouter, Depends
from google.cloud import firestore

from atlas.core.auth import get_current_user
from atlas.core.firestore import get_firestore_client
from atlas.domains.admin import service
from atlas.domains.admin.schemas import (
    AccessRequestsListResponse,
    CreateAccessRequestsRequest,
)
from atlas.domains.auth.schemas import UserInfo

# Não é /admin/... — qualquer usuário autenticado pede acesso pra si
# mesmo (dependency é só get_current_user, não require_admin nem
# require_project_access: pedir acesso a um projeto que você ainda não
# tem é exatamente o caso que este endpoint existe pra cobrir).
router = APIRouter(
    prefix="/api/v1/access-requests",
    tags=["access-requests"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=AccessRequestsListResponse)
def create_access_requests(
    request: CreateAccessRequestsRequest,
    user: UserInfo = Depends(get_current_user),
    client: firestore.Client = Depends(get_firestore_client),
) -> AccessRequestsListResponse:
    return service.create_access_requests(
        client, user.email, request.project_ids, request.request_type.value
    )
