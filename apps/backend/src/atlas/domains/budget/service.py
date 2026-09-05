"""Orquestra o domínio budget: CRUD de metas de custo compartilhadas por
projeto (v1.13 — projeto / dataset / tabela). api/v1 só chama estas
funções — CLAUDE.md proíbe lógica de negócio em api/. Espelha
domains/favorites/service.py.

Checagem de permissão de escrita mora aqui, não em core/auth.py: quem
pode escrever depende do `dataset_id` do PRÓPRIO corpo/query do request
(scope=project/dataset/table), não de um path param — mesmo racional já
usado por domains/quality/service.py::_can_manage_folder pra autorização
contextual a dado de domínio. `domains/admin` é domínio de plataforma,
importado diretamente por outros domínios pra isso (já era o padrão em
domains/quality/service.py e domains/catalog/service.py antes desta
mudança)."""

from google.cloud import firestore

from atlas.core.exceptions import ProjectAdminRequiredError
from atlas.domains.admin import service as admin_service
from atlas.domains.budget import repository
from atlas.domains.budget.schemas import (
    BudgetEntry,
    BudgetListResponse,
    BudgetScope,
    BudgetUpsertRequest,
)


def _require_project_admin(
    client: firestore.Client, project_id: str, dataset_id: str | None, user_email: str
) -> None:
    """Superadmin sempre passa. Senão, precisa de um grant em
    project_admins cobrindo dataset_id — None (scope=project) só passa
    pra quem tem `datasets: null` (projeto inteiro), mesma regra de
    core/auth.py::require_project_admin quando dataset_id não vem do
    path. Leitura sempre fresca do Firestore (nunca confia em
    UserInfo.is_admin — ver docs/specs/admin.md)."""
    if admin_service.is_admin(client, user_email):
        return
    if not admin_service.is_project_admin(client, user_email, project_id, dataset_id):
        raise ProjectAdminRequiredError(project_id)


def list_budgets(client: firestore.Client, project_id: str) -> BudgetListResponse:
    raw = repository.list_budgets(client, project_id)
    return BudgetListResponse(
        project_id=project_id, budgets=[BudgetEntry(project_id=project_id, **b) for b in raw]
    )


def upsert_budget(
    client: firestore.Client,
    project_id: str,
    request: BudgetUpsertRequest,
    user_email: str,
) -> BudgetEntry:
    _require_project_admin(client, project_id, request.dataset_id, user_email)
    raw = repository.upsert_budget(
        client,
        project_id,
        request.scope,
        request.amount_usd,
        user_email,
        dataset_id=request.dataset_id,
        table_id=request.table_id,
    )
    return BudgetEntry(project_id=project_id, **raw)


def remove_budget(
    client: firestore.Client,
    project_id: str,
    scope: BudgetScope,
    user_email: str,
    dataset_id: str | None = None,
    table_id: str | None = None,
) -> None:
    _require_project_admin(client, project_id, dataset_id, user_email)
    repository.remove_budget(client, project_id, scope, dataset_id=dataset_id, table_id=table_id)
