from fastapi import APIRouter, Depends, Query
from google.cloud import firestore, storage
from google.cloud import logging as cloud_logging

from atlas.core.auth import require_project_access
from atlas.core.firestore import get_firestore_client
from atlas.core.logging_client import get_logging_client
from atlas.core.storage_client import get_storage_client
from atlas.domains.storage import service
from atlas.domains.storage.schemas import (
    BucketObjectsResponse,
    BucketsListResponse,
    WasteCandidatesResponse,
)

router = APIRouter(
    prefix="/api/v1/storage", tags=["storage"], dependencies=[Depends(require_project_access)]
)


@router.get("/{project_id}/buckets", response_model=BucketsListResponse)
def list_buckets(
    project_id: str, client: storage.Client = Depends(get_storage_client)
) -> BucketsListResponse:
    return service.list_buckets(client, project_id)


@router.get("/{project_id}/{bucket_name}/objects", response_model=BucketObjectsResponse)
def browse_bucket_objects(
    project_id: str,
    bucket_name: str,
    prefix: str | None = Query(default=None),
    page_token: str | None = Query(default=None),
    client: storage.Client = Depends(get_storage_client),
) -> BucketObjectsResponse:
    return service.browse_bucket(client, project_id, bucket_name, prefix, page_token)


@router.get("/{project_id}/waste-candidates", response_model=WasteCandidatesResponse)
def get_waste_candidates(
    project_id: str,
    min_days_unused: int = Query(default=60, ge=1),
    client: storage.Client = Depends(get_storage_client),
    logging_client: cloud_logging.Client = Depends(get_logging_client),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> WasteCandidatesResponse:
    return service.get_waste_candidates(
        client, logging_client, firestore_client, project_id, min_days_unused
    )
