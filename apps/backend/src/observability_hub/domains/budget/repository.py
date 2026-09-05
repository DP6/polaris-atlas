"""Única camada que fala com o Firestore pra budget — service.py
orquestra, nunca monta paths/queries diretamente (mesmo racional dos
demais domínios; espelha domains/favorites/repository.py).

Coleção: hub_projects/{project_id}/budgets/{doc_id} — budget compartilhado
por PROJETO desde a v1.13 (`docs/specs/finops-budget.md`), reverte a v1.5
(era `users/{email}/budgets`, por usuário — ASM-FIN-RV-02, revertida).
Mesmo padrão de subcoleção de domains/admin/project_admin_repository.py:
a pergunta mais comum é "qual o budget deste projeto", não "quais budgets
o usuário X tem em algum lugar".

doc_id é determinístico pelo alvo do budget (sem o segmento de projeto,
que já é o documento-pai):
  scope=project → "_project" (fixo — sem segmento de dataset/tabela pra
                  usar como ID)
  scope=dataset → "{dataset_id}"
  scope=table   → "{dataset_id}__{table_id}"
Cadastrar o mesmo alvo duas vezes é idempotente (mesmo doc) e o DELETE
aponta pro doc exato sem query.
"""

from datetime import UTC, datetime

from google.cloud import firestore

from observability_hub.domains.budget.schemas import BudgetScope

_PROJECT_SCOPE_DOC_ID = "_project"


def _budget_doc_id(
    scope: BudgetScope,
    dataset_id: str | None = None,
    table_id: str | None = None,
) -> str:
    if scope == BudgetScope.PROJECT:
        return _PROJECT_SCOPE_DOC_ID
    if scope == BudgetScope.DATASET:
        return f"{dataset_id}"
    return f"{dataset_id}__{table_id}"


def _budgets_collection(client: firestore.Client, project_id: str):
    return client.collection("hub_projects").document(project_id).collection("budgets")


def list_budgets(client: firestore.Client, project_id: str) -> list[dict]:
    """Todos os budgets do projeto, mais recentes primeiro. Sem filtro em
    memória — a coleção já é escopada ao projeto pelo caminho do
    documento (diferente da v1.5, que filtrava project_id em Python
    porque a coleção era por usuário)."""
    docs = _budgets_collection(client, project_id).order_by(
        "updated_at", direction=firestore.Query.DESCENDING
    )
    return [doc.to_dict() for doc in docs.stream()]


def upsert_budget(
    client: firestore.Client,
    project_id: str,
    scope: BudgetScope,
    amount_usd: float,
    updated_by: str,
    dataset_id: str | None = None,
    table_id: str | None = None,
) -> dict:
    """created_at / created_by são PRESERVADOS num upsert repetido do
    mesmo alvo (mesmo racional de favorites.add_favorite pra added_at e de
    admin.upsert_user pra created_at) — reeditar só o valor não deve
    reordenar a lista (ordenada por updated_at desc) nem reatribuir a
    autoria original. `updated_by` (novo na v1.13) sempre reflete quem
    editou por último — com múltiplos Admins de projeto possíveis,
    `created_by` deixa de significar "dono", vira só "quem criou primeiro"."""
    doc_id = _budget_doc_id(scope, dataset_id, table_id)
    doc_ref = _budgets_collection(client, project_id).document(doc_id)
    existing = doc_ref.get()
    existing_data = existing.to_dict() if existing.exists else None
    now = datetime.now(UTC)
    created_at = existing_data["created_at"] if existing_data else now
    created_by = existing_data["created_by"] if existing_data else updated_by

    data = {
        "scope": scope.value,
        "dataset_id": dataset_id,
        "table_id": table_id,
        "amount_usd": amount_usd,
        "period": "month",
        "created_by": created_by,
        "created_at": created_at,
        "updated_at": now,
        "updated_by": updated_by,
    }
    doc_ref.set(data)
    return data


def remove_budget(
    client: firestore.Client,
    project_id: str,
    scope: BudgetScope,
    dataset_id: str | None = None,
    table_id: str | None = None,
) -> None:
    doc_id = _budget_doc_id(scope, dataset_id, table_id)
    _budgets_collection(client, project_id).document(doc_id).delete()


def get_project_budget_amount(client: firestore.Client, project_id: str) -> float | None:
    """Só o valor do budget de escopo=project (o que a linha de budget do
    gráfico do FinOps desenha). None = ninguém cadastrou budget de
    projeto ainda. Leitura direta pelo doc_id, sem query."""
    snapshot = _budgets_collection(client, project_id).document(_PROJECT_SCOPE_DOC_ID).get()
    if not snapshot.exists:
        return None
    data = snapshot.to_dict() or {}
    amount = data.get("amount_usd")
    return float(amount) if amount is not None else None
