from datetime import date

from fastapi import APIRouter, Depends, Query
from google.cloud import bigquery, firestore, storage
from google.cloud import logging as cloud_logging

from atlas.core.auth import get_current_user, require_project_access
from atlas.core.bigquery import get_client
from atlas.core.firestore import get_firestore_client
from atlas.core.logging_client import get_logging_client
from atlas.core.storage_client import get_storage_client
from atlas.domains.auth.schemas import UserInfo
from atlas.domains.budget import service as budget_service
from atlas.domains.budget.schemas import (
    BudgetEntry,
    BudgetListResponse,
    BudgetScope,
    BudgetUpsertRequest,
)
from atlas.domains.finops import service
from atlas.domains.finops.schemas import (
    BudgetGroupBy,
    BudgetResponse,
    ColumnTypeEstimateResponse,
    ColumnTypeScanRequest,
    ColumnTypeSuggestionsResponse,
    CostSeriesGranularity,
    CostSeriesResponse,
    CostType,
    PartitionCandidatesResponse,
    TableScoresResponse,
)

router = APIRouter(
    prefix="/api/v1/finops", tags=["finops"], dependencies=[Depends(require_project_access)]
)


@router.get("/{project_id}/partition-candidates", response_model=PartitionCandidatesResponse)
def get_partition_candidates(
    project_id: str,
    datasets: list[str] | None = Query(default=None),
    tables: list[str] | None = Query(default=None),
    client: bigquery.Client = Depends(get_client),
    logging_client: cloud_logging.Client = Depends(get_logging_client),
    storage_client: storage.Client = Depends(get_storage_client),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> PartitionCandidatesResponse:
    return service.scan_partition_candidates(
        client,
        logging_client,
        storage_client,
        firestore_client,
        project_id,
        datasets=datasets,
        tables=tables,
    )


@router.get("/{project_id}/budget", response_model=BudgetResponse)
def get_budget(
    project_id: str,
    group_by: BudgetGroupBy = Query(default=BudgetGroupBy.TABLE),
    limit: int = Query(default=10, ge=1, le=50),
    lookback_days: int = Query(default=30, ge=1, le=31),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    include_storage: bool = Query(default=False),
    client: bigquery.Client = Depends(get_client),
    logging_client: cloud_logging.Client = Depends(get_logging_client),
    storage_client: storage.Client = Depends(get_storage_client),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> BudgetResponse:
    # budget_target_usd é compartilhado por projeto (v1.13) — não depende
    # mais de quem está logado, ver domains/finops/service.py::get_budget.
    return service.get_budget(
        logging_client,
        storage_client,
        firestore_client,
        project_id,
        group_by=group_by,
        limit=limit,
        lookback_days=lookback_days,
        from_date=from_date,
        to_date=to_date,
        client=client,
        include_storage=include_storage,
    )


@router.get("/{project_id}/cost-series", response_model=CostSeriesResponse)
def get_cost_series(
    project_id: str,
    granularity: CostSeriesGranularity = Query(default=CostSeriesGranularity.DAY),
    cost_type: CostType = Query(default=CostType.ALL),
    lookback_days: int = Query(default=30, ge=1, le=31),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    datasets: list[str] | None = Query(default=None),
    tables: list[str] | None = Query(default=None),
    client: bigquery.Client = Depends(get_client),
    logging_client: cloud_logging.Client = Depends(get_logging_client),
    storage_client: storage.Client = Depends(get_storage_client),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> CostSeriesResponse:
    return service.get_cost_series(
        client,
        logging_client,
        storage_client,
        firestore_client,
        project_id,
        granularity=granularity,
        cost_type=cost_type,
        lookback_days=lookback_days,
        from_date=from_date,
        to_date=to_date,
        datasets=datasets,
        tables=tables,
    )


@router.get("/{project_id}/table-scores", response_model=TableScoresResponse)
def get_table_scores(
    project_id: str,
    datasets: list[str] | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    client: bigquery.Client = Depends(get_client),
    logging_client: cloud_logging.Client = Depends(get_logging_client),
    storage_client: storage.Client = Depends(get_storage_client),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> TableScoresResponse:
    return service.compute_table_scores(
        client,
        logging_client,
        storage_client,
        firestore_client,
        project_id,
        datasets=datasets,
        limit=limit,
    )


@router.get("/{project_id}/budgets", response_model=BudgetListResponse)
def list_budgets(
    project_id: str,
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> BudgetListResponse:
    # Budget é compartilhado por projeto (v1.13) — leitura só exige
    # require_project_access (dependency do router), sem recorte por
    # usuário: qualquer um com acesso ao projeto vê o mesmo budget.
    return budget_service.list_budgets(firestore_client, project_id)


@router.put("/{project_id}/budgets", response_model=BudgetEntry)
def upsert_budget(
    project_id: str,
    request: BudgetUpsertRequest,
    user: UserInfo = Depends(get_current_user),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> BudgetEntry:
    # Escrita exige Admin de projeto/superadmin — checado dentro de
    # budget_service (o dataset_id relevante vem do body, não do path,
    # ver domains/budget/service.py::_require_project_admin).
    return budget_service.upsert_budget(firestore_client, project_id, request, user.email)


@router.delete("/{project_id}/budgets", status_code=204)
def remove_budget(
    project_id: str,
    scope: BudgetScope = Query(...),
    dataset_id: str | None = Query(default=None),
    table_id: str | None = Query(default=None),
    user: UserInfo = Depends(get_current_user),
    firestore_client: firestore.Client = Depends(get_firestore_client),
) -> None:
    budget_service.remove_budget(
        firestore_client,
        project_id,
        scope,
        user.email,
        dataset_id=dataset_id,
        table_id=table_id,
    )


@router.post(
    "/{project_id}/column-type-suggestions/estimate", response_model=ColumnTypeEstimateResponse
)
def estimate_column_type_suggestions(
    project_id: str,
    request: ColumnTypeScanRequest,
    client: bigquery.Client = Depends(get_client),
) -> ColumnTypeEstimateResponse:
    return service.estimate_column_type_suggestions(client, project_id, request)


@router.post(
    "/{project_id}/column-type-suggestions/run", response_model=ColumnTypeSuggestionsResponse
)
def run_column_type_suggestions(
    project_id: str,
    request: ColumnTypeScanRequest,
    client: bigquery.Client = Depends(get_client),
) -> ColumnTypeSuggestionsResponse:
    return service.run_column_type_suggestions(client, project_id, request)
