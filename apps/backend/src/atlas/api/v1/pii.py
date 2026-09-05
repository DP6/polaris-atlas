from fastapi import APIRouter, Depends
from google.cloud import bigquery, firestore

from atlas.core.auth import get_current_user, require_project_access
from atlas.core.bigquery import get_client
from atlas.core.firestore import get_firestore_client
from atlas.domains.auth.schemas import UserInfo
from atlas.domains.pii import service
from atlas.domains.pii.schemas import (
    PiiEstimateResponse,
    PiiScanRequest,
    PiiScanResponse,
)

router = APIRouter(
    prefix="/api/v1/pii", tags=["pii"], dependencies=[Depends(require_project_access)]
)


@router.post(
    "/{project_id}/{dataset_id}/{table_id}/estimate",
    response_model=PiiEstimateResponse,
)
def estimate(
    project_id: str,
    dataset_id: str,
    table_id: str,
    request: PiiScanRequest,
    client: bigquery.Client = Depends(get_client),
) -> PiiEstimateResponse:
    return service.estimate_pii_scan(client, project_id, dataset_id, table_id, request)


@router.post(
    "/{project_id}/{dataset_id}/{table_id}/run",
    response_model=PiiScanResponse,
)
def run(
    project_id: str,
    dataset_id: str,
    table_id: str,
    request: PiiScanRequest,
    client: bigquery.Client = Depends(get_client),
    user: UserInfo = Depends(get_current_user),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> PiiScanResponse:
    return service.run_pii_scan(
        client, firestore_client, project_id, dataset_id, table_id, request, user.email
    )
