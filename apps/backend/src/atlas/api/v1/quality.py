from fastapi import APIRouter, Depends
from google.cloud import firestore

from atlas.core.auth import get_current_user, require_project_access
from atlas.core.firestore import get_firestore_client
from atlas.domains.admin import service as admin_service
from atlas.domains.auth.schemas import UserInfo
from atlas.domains.quality import service
from atlas.domains.quality.schemas import (
    CreateProfilingFolderRequest,
    ProfilingFolder,
    ProfilingFolderDetailResponse,
    ProfilingFolderEntry,
    ProfilingFoldersListResponse,
    ProfilingHistoryResponse,
    SaveRunToFolderRequest,
    UpdateProfilingFolderRequest,
)

router = APIRouter(
    prefix="/api/v1/quality", tags=["quality"], dependencies=[Depends(require_project_access)]
)


@router.get(
    "/history/{project_id}/{dataset_id}/{table_id}", response_model=ProfilingHistoryResponse
)
def get_history(
    project_id: str,
    dataset_id: str,
    table_id: str,
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> ProfilingHistoryResponse:
    return service.get_quality_history(firestore_client, project_id, dataset_id, table_id)


# Pastas não são presas a um project_id de path (podem juntar runs de
# projetos diferentes) — router separado, dependency de router é só
# get_current_user, não require_project_access (que exige project_id
# no path pra resolver, mesmo caso de GET /api/v1/projects).
router_folders = APIRouter(
    prefix="/api/v1/quality/folders",
    tags=["quality-folders"],
    dependencies=[Depends(get_current_user)],
)


@router_folders.post("", response_model=ProfilingFolder)
def create_folder(
    request: CreateProfilingFolderRequest,
    user: UserInfo = Depends(get_current_user),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> ProfilingFolder:
    return service.create_folder(firestore_client, request, created_by=user.email)


@router_folders.get("", response_model=ProfilingFoldersListResponse)
def list_folders(
    user: UserInfo = Depends(get_current_user),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> ProfilingFoldersListResponse:
    is_admin = admin_service.is_admin(firestore_client, user.email)
    return service.list_folders_for_user(firestore_client, user.email, is_admin)


@router_folders.get("/{folder_id}", response_model=ProfilingFolderDetailResponse)
def get_folder_detail(
    folder_id: str,
    user: UserInfo = Depends(get_current_user),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> ProfilingFolderDetailResponse:
    is_admin = admin_service.is_admin(firestore_client, user.email)
    return service.get_folder_detail(firestore_client, folder_id, user.email, is_admin)


@router_folders.put("/{folder_id}", response_model=ProfilingFolder)
def update_folder(
    folder_id: str,
    request: UpdateProfilingFolderRequest,
    user: UserInfo = Depends(get_current_user),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> ProfilingFolder:
    is_admin = admin_service.is_admin(firestore_client, user.email)
    return service.update_folder(firestore_client, folder_id, request, user.email, is_admin)


@router_folders.delete("/{folder_id}", status_code=204)
def delete_folder(
    folder_id: str,
    user: UserInfo = Depends(get_current_user),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> None:
    is_admin = admin_service.is_admin(firestore_client, user.email)
    service.delete_folder(firestore_client, folder_id, user.email, is_admin)


@router_folders.post("/{folder_id}/entries", response_model=ProfilingFolderEntry)
def save_run_to_folder(
    folder_id: str,
    request: SaveRunToFolderRequest,
    user: UserInfo = Depends(get_current_user),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> ProfilingFolderEntry:
    is_admin = admin_service.is_admin(firestore_client, user.email)
    return service.save_run_to_folder(firestore_client, folder_id, request, user.email, is_admin)


@router_folders.delete("/{folder_id}/entries/{entry_id}", status_code=204)
def delete_folder_entry(
    folder_id: str,
    entry_id: str,
    user: UserInfo = Depends(get_current_user),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> None:
    is_admin = admin_service.is_admin(firestore_client, user.email)
    service.delete_folder_entry(firestore_client, folder_id, entry_id, user.email, is_admin)
