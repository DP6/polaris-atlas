from fastapi import APIRouter, Depends, Query
from google.cloud import bigquery, firestore

from observability_hub.core.auth import require_project_access, require_project_admin
from observability_hub.core.bigquery import get_client
from observability_hub.core.firestore import get_firestore_client
from observability_hub.domains.auth.schemas import UserInfo
from observability_hub.domains.metadata import service
from observability_hub.domains.metadata.schemas import (
    MetadataColumnUpsertRequest,
    MetadataHistoryResponse,
    MetadataOverviewResponse,
    MetadataTableResponse,
    MetadataTableUpsertRequest,
    SuggestedPiiResponse,
)

router = APIRouter(
    prefix="/api/v1/metadata", tags=["metadata"], dependencies=[Depends(require_project_access)]
)


@router.get("/{project_id}", response_model=MetadataOverviewResponse)
def get_metadata_overview(
    project_id: str,
    certification_status: str | None = Query(default=None),
    datasets: list[str] | None = Query(default=None),
    owner_email: str | None = Query(default=None),
    q: str | None = Query(default=None),
    bq_client: bigquery.Client = Depends(get_client),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> MetadataOverviewResponse:
    return service.get_metadata_overview(
        bq_client,
        firestore_client,
        project_id,
        certification_status=certification_status,
        datasets=datasets,
        owner_email=owner_email,
        q=q,
    )


@router.get("/{project_id}/{dataset_id}/{table_id}", response_model=MetadataTableResponse)
def get_table_metadata(
    project_id: str,
    dataset_id: str,
    table_id: str,
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> MetadataTableResponse:
    return service.get_table_metadata(firestore_client, project_id, dataset_id, table_id)


@router.put("/{project_id}/{dataset_id}/{table_id}", response_model=MetadataTableResponse)
def upsert_table_metadata(
    project_id: str,
    dataset_id: str,
    table_id: str,
    request: MetadataTableUpsertRequest,
    admin_user: UserInfo = Depends(require_project_admin),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> MetadataTableResponse:
    return service.upsert_table_metadata(
        firestore_client, project_id, dataset_id, table_id, request, updated_by=admin_user.email
    )


@router.put(
    "/{project_id}/{dataset_id}/{table_id}/columns/{column_name}",
    response_model=MetadataTableResponse,
)
def upsert_column_metadata(
    project_id: str,
    dataset_id: str,
    table_id: str,
    column_name: str,
    request: MetadataColumnUpsertRequest,
    admin_user: UserInfo = Depends(require_project_admin),
    bq_client: bigquery.Client = Depends(get_client),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> MetadataTableResponse:
    return service.upsert_column_metadata(
        bq_client,
        firestore_client,
        project_id,
        dataset_id,
        table_id,
        column_name,
        request,
        updated_by=admin_user.email,
    )


@router.get(
    "/{project_id}/{dataset_id}/{table_id}/suggested-pii", response_model=SuggestedPiiResponse
)
def get_suggested_pii(
    project_id: str,
    dataset_id: str,
    table_id: str,
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> SuggestedPiiResponse:
    return service.get_suggested_pii(firestore_client, project_id, dataset_id, table_id)


@router.get("/{project_id}/{dataset_id}/{table_id}/history", response_model=MetadataHistoryResponse)
def get_history(
    project_id: str,
    dataset_id: str,
    table_id: str,
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> MetadataHistoryResponse:
    return service.get_history(firestore_client, project_id, dataset_id, table_id)
