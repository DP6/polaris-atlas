"""Única camada que fala com o Firestore pra budget — service.py
orquestra, nunca monta paths/queries diretamente (mesmo racional dos
demais domínios; espelha domains/favorites/repository.py).

Coleção: users/{email}/budgets/{doc_id}. O budget é POR USUÁRIO (não
compartilhado — ASM-005 de finops-budget.md), então mora sob o doc do
usuário igual aos favoritos, sem superfície de permissão nova.

doc_id é determinístico pelo alvo do budget:
  scope=project → "{project_id}"
  scope=dataset → "{project_id}__{dataset_id}"
  scope=table   → "{project_id}__{dataset_id}__{table_id}"
("__" pra reduzir colisão com o "_" que aparece normalmente em nome de
dataset/tabela.) Cadastrar o mesmo alvo duas vezes é idempotente (mesmo
doc) e o DELETE aponta pro doc exato sem query.
"""

from datetime import UTC, datetime

from google.cloud import firestore

from observability_hub.domains.budget.schemas import BudgetScope


def _budget_doc_id(
    project_id: str,
    scope: BudgetScope,
    dataset_id: str | None = None,
    table_id: str | None = None,
) -> str:
    if scope == BudgetScope.PROJECT:
        return project_id
    if scope == BudgetScope.DATASET:
        return f"{project_id}__{dataset_id}"
    return f"{project_id}__{dataset_id}__{table_id}"


def _budgets_collection(client: firestore.Client, email: str):
    return client.collection("users").document(email).collection("budgets")


def list_budgets(client: firestore.Client, email: str, project_id: str) -> list[dict]:
    """Todos os budgets do usuário no projeto pedido, mais recentes
    primeiro. O filtro por project_id é in-memory (a coleção é pequena —
    um punhado de budgets por usuário — e evita exigir índice composto no
    Firestore)."""
    docs = (
        _budgets_collection(client, email)
        .order_by("updated_at", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [d for doc in docs if (d := doc.to_dict()) and d.get("project_id") == project_id]


def upsert_budget(
    client: firestore.Client,
    email: str,
    project_id: str,
    scope: BudgetScope,
    amount_usd: float,
    dataset_id: str | None = None,
    table_id: str | None = None,
) -> dict:
    """created_at / created_by são PRESERVADOS num upsert repetido do
    mesmo alvo (mesmo racional de favorites.add_favorite pra added_at e de
    admin.upsert_user pra created_at) — reeditar só o valor não deve
    reordenar a lista (ordenada por updated_at desc) nem reatribuir a
    autoria original. updated_at sempre reflete a última escrita."""
    doc_id = _budget_doc_id(project_id, scope, dataset_id, table_id)
    doc_ref = _budgets_collection(client, email).document(doc_id)
    existing = doc_ref.get()
    existing_data = existing.to_dict() if existing.exists else None
    now = datetime.now(UTC)
    created_at = existing_data["created_at"] if existing_data else now
    created_by = existing_data["created_by"] if existing_data else email

    data = {
        "project_id": project_id,
        "scope": scope.value,
        "dataset_id": dataset_id,
        "table_id": table_id,
        "amount_usd": amount_usd,
        "period": "month",
        "created_by": created_by,
        "created_at": created_at,
        "updated_at": now,
    }
    doc_ref.set(data)
    return data


def remove_budget(
    client: firestore.Client,
    email: str,
    project_id: str,
    scope: BudgetScope,
    dataset_id: str | None = None,
    table_id: str | None = None,
) -> None:
    doc_id = _budget_doc_id(project_id, scope, dataset_id, table_id)
    _budgets_collection(client, email).document(doc_id).delete()


def get_project_budget_amount(
    client: firestore.Client, email: str, project_id: str
) -> float | None:
    """Só o valor do budget de escopo=project (o que a linha de budget do
    gráfico do FinOps desenha). None = usuário não cadastrou budget de
    projeto. Leitura direta pelo doc_id, sem query."""
    doc_id = _budget_doc_id(project_id, BudgetScope.PROJECT)
    snapshot = _budgets_collection(client, email).document(doc_id).get()
    if not snapshot.exists:
        return None
    data = snapshot.to_dict() or {}
    amount = data.get("amount_usd")
    return float(amount) if amount is not None else None
