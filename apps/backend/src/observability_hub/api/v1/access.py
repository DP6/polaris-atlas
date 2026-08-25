from fastapi import APIRouter, Depends, Query
from google.cloud import firestore, storage
from google.cloud import logging as cloud_logging

from observability_hub.core.auth import require_project_access
from observability_hub.core.firestore import get_firestore_client
from observability_hub.core.logging_client import get_logging_client
from observability_hub.core.storage_client import get_storage_client
from observability_hub.domains.access import service
from observability_hub.domains.access.schemas import TableAccessResponse

router = APIRouter(
    prefix="/api/v1/access", tags=["access"], dependencies=[Depends(require_project_access)]
)


@router.get("/{project_id}/{dataset_id}/{table_id}", response_model=TableAccessResponse)
def get_table_access(
    project_id: str,
    dataset_id: str,
    table_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    logging_client: cloud_logging.Client = Depends(get_logging_client),
    storage_client: storage.Client = Depends(get_storage_client),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> TableAccessResponse:
    return service.get_table_access(
        logging_client,
        storage_client,
        firestore_client,
        project_id,
        dataset_id,
        table_id,
        limit=limit,
    )
