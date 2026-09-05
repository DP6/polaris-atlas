from fastapi import APIRouter, Depends, Query
from google.cloud import bigquery, firestore, storage
from google.cloud import logging as cloud_logging

from atlas.core.auth import require_project_access
from atlas.core.bigquery import get_client
from atlas.core.firestore import get_firestore_client
from atlas.core.logging_client import get_logging_client
from atlas.core.storage_client import get_storage_client
from atlas.domains.lineage import service
from atlas.domains.lineage.schemas import (
    LineageGraphResponse,
    OrphansResponse,
)

router = APIRouter(
    prefix="/api/v1/lineage", tags=["lineage"], dependencies=[Depends(require_project_access)]
)


@router.get("/{project_id}/orphans", response_model=OrphansResponse)
def get_orphans(
    project_id: str,
    datasets: list[str] | None = Query(default=None),
    lookback_days: int = Query(default=30, ge=1),
    client: bigquery.Client = Depends(get_client),
    logging_client: cloud_logging.Client = Depends(get_logging_client),
    storage_client: storage.Client = Depends(get_storage_client),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> OrphansResponse:
    return service.get_orphans(
        client,
        logging_client,
        storage_client,
        firestore_client,
        project_id,
        datasets=datasets,
        lookback_days=lookback_days,
    )


@router.get("/{project_id}/{dataset_id}/{table_id}", response_model=LineageGraphResponse)
def get_lineage(
    project_id: str,
    dataset_id: str,
    table_id: str,
    max_hops: int = Query(default=8, ge=1, le=15),
    client: bigquery.Client = Depends(get_client),
    logging_client: cloud_logging.Client = Depends(get_logging_client),
    storage_client: storage.Client = Depends(get_storage_client),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> LineageGraphResponse:
    return service.get_table_lineage(
        client,
        logging_client,
        storage_client,
        firestore_client,
        project_id,
        dataset_id,
        table_id,
        max_hops=max_hops,
    )
