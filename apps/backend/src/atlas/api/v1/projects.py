from fastapi import APIRouter, Depends
from google.cloud import bigquery, firestore

from atlas.core.auth import get_current_user, require_project_access
from atlas.core.bigquery import get_client
from atlas.core.firestore import get_firestore_client
from atlas.domains.auth.schemas import UserInfo
from atlas.domains.catalog import service
from atlas.domains.catalog.schemas import ProjectsListResponse, ProjectValidateResponse

router = APIRouter(
    prefix="/api/v1/projects", tags=["projects"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=ProjectsListResponse)
def list_projects(
    user: UserInfo = Depends(get_current_user),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> ProjectsListResponse:
    return service.list_accessible_projects(firestore_client, user.email)


@router.get(
    "/{project_id}/validate",
    response_model=ProjectValidateResponse,
    dependencies=[Depends(require_project_access)],
)
def validate_project(
    project_id: str, client: bigquery.Client = Depends(get_client)
) -> ProjectValidateResponse:
    return service.validate_project(client, project_id)
