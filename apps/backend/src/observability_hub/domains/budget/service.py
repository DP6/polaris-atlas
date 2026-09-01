"""Orquestra o domínio budget: CRUD de metas de custo por usuário
(projeto / dataset / tabela). api/v1 só chama estas funções — CLAUDE.md
proíbe lógica de negócio em api/. Espelha domains/favorites/service.py.
"""

from google.cloud import firestore

from observability_hub.domains.budget import repository
from observability_hub.domains.budget.schemas import (
    BudgetEntry,
    BudgetListResponse,
    BudgetScope,
    BudgetUpsertRequest,
)


def list_budgets(client: firestore.Client, email: str, project_id: str) -> BudgetListResponse:
    raw = repository.list_budgets(client, email, project_id)
    return BudgetListResponse(project_id=project_id, budgets=[BudgetEntry(**b) for b in raw])


def upsert_budget(
    client: firestore.Client,
    email: str,
    project_id: str,
    request: BudgetUpsertRequest,
) -> BudgetEntry:
    raw = repository.upsert_budget(
        client,
        email,
        project_id,
        request.scope,
        request.amount_usd,
        dataset_id=request.dataset_id,
        table_id=request.table_id,
    )
    return BudgetEntry(**raw)


def remove_budget(
    client: firestore.Client,
    email: str,
    project_id: str,
    scope: BudgetScope,
    dataset_id: str | None = None,
    table_id: str | None = None,
) -> None:
    repository.remove_budget(
        client, email, project_id, scope, dataset_id=dataset_id, table_id=table_id
    )
