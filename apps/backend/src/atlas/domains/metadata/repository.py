"""Única camada que fala com Firestore/BigQuery para metadados de
tabela/coluna — service.py orquestra, nunca monta paths/queries
diretamente (mesmo racional de domains/admin/repository.py).

hub_projects/{project_id}/metadata_tables/{dataset_id}__{table_id} —
subcoleção do projeto (mesmo padrão de
domains/admin/project_admin_repository.py): a pergunta mais comum é
"quais tabelas deste projeto estão documentadas", não "quais tabelas o
usuário X documentou".

PII é lido (nunca escrito) de pii_scan_history — a mesma coleção que
domains/pii/history_repository.py grava. O path é duplicado aqui de
propósito: nenhum domínio deste projeto importa de outro (ver
domains/finops/repository.py::list_all_table_refs, mesmo racional).
list_all_table_refs/get_column_names abaixo são, pelo mesmo motivo, uma
cópia local da técnica já usada por catalog/freshness/finops — não uma
chamada a domains.catalog.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from google.api_core.exceptions import NotFound
from google.cloud import bigquery, firestore

from atlas.core.bigquery import get_table_cached

# Campos de nível tabela preservados quando o doc inteiro é regravado num
# patch parcial. `status`/`status_changed_by`/`status_changed_at`/
# `review_note` só mudam via set_status, mas precisam ser preservados nas
# regravações de conteúdo (e vice-versa) pra não sumirem.
_PRESERVED_TABLE_KEYS = (
    "description",
    "owner",
    "classification",
    "status",
    "status_changed_by",
    "status_changed_at",
    "review_note",
)


def _doc_id(dataset_id: str, table_id: str) -> str:
    return f"{dataset_id}__{table_id}"


def _metadata_collection(client: firestore.Client, project_id: str):
    return client.collection("hub_projects").document(project_id).collection("metadata_tables")


def get_table_metadata(
    client: firestore.Client, project_id: str, dataset_id: str, table_id: str
) -> dict | None:
    doc = _metadata_collection(client, project_id).document(_doc_id(dataset_id, table_id)).get()
    return doc.to_dict() if doc.exists else None


def _preserved(existing: dict) -> dict:
    return {key: existing.get(key) for key in _PRESERVED_TABLE_KEYS}


def upsert_table_metadata(
    client: firestore.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    fields: dict,
    updated_by: str,
) -> dict:
    """`fields` só contém as chaves explicitamente enviadas no request
    (service.py filtra via model_dump(exclude_unset=True)) — patch
    parcial de verdade, não substituição do doc inteiro. `columns` nunca
    é tocado aqui (upsert_column_metadata cuida disso), `created_at` é
    preservado. `status` e derivados só mudam via set_status."""
    now = datetime.now(UTC)
    doc_ref = _metadata_collection(client, project_id).document(_doc_id(dataset_id, table_id))
    existing = get_table_metadata(client, project_id, dataset_id, table_id) or {}
    data = {
        **_preserved(existing),
        "related_links": existing.get("related_links", []),
        "columns": existing.get("columns", {}),
        "created_at": existing.get("created_at", now),
        **fields,
        "updated_at": now,
        "updated_by": updated_by,
    }
    doc_ref.set(data)
    return data


def set_status(
    client: firestore.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    *,
    status: str,
    changed_by: str,
    review_note: str | None,
) -> dict:
    """Regrava só os campos de estado de governança — não mexe em
    `updated_by` (continua sendo "quem editou o conteúdo pela última
    vez"). `review_note=None` limpa a devolução anterior (ao aprovar ou
    reenviar), string preenche."""
    now = datetime.now(UTC)
    doc_ref = _metadata_collection(client, project_id).document(_doc_id(dataset_id, table_id))
    existing = get_table_metadata(client, project_id, dataset_id, table_id) or {}
    data = {
        **_preserved(existing),
        "related_links": existing.get("related_links", []),
        "columns": existing.get("columns", {}),
        "created_at": existing.get("created_at", now),
        "updated_at": existing.get("updated_at", now),
        "updated_by": existing.get("updated_by"),
        "status": status,
        "status_changed_by": changed_by,
        "status_changed_at": now,
        "review_note": review_note,
    }
    doc_ref.set(data)
    return data


def upsert_column_metadata(
    client: firestore.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    column_name: str,
    column_fields: dict,
    updated_by: str,
) -> dict:
    """Mesmo doc da tabela (columns é um mapa embutido, não subcoleção —
    ver docs/specs/metadata.md, ASM-004) — lê o doc inteiro, atualiza só
    a entrada da coluna, regrava o doc inteiro. `column_fields` já vem
    filtrado por model_dump(exclude_unset=True) em service.py."""
    now = datetime.now(UTC)
    doc_ref = _metadata_collection(client, project_id).document(_doc_id(dataset_id, table_id))
    existing = get_table_metadata(client, project_id, dataset_id, table_id) or {}
    columns = dict(existing.get("columns", {}))
    existing_column = dict(columns.get(column_name) or {})
    existing_column.update(column_fields)
    columns[column_name] = existing_column
    data = {
        **_preserved(existing),
        "related_links": existing.get("related_links", []),
        "columns": columns,
        "created_at": existing.get("created_at", now),
        "updated_at": now,
        "updated_by": updated_by,
    }
    doc_ref.set(data)
    return data


def _history_collection(client: firestore.Client, project_id: str, dataset_id: str, table_id: str):
    return (
        _metadata_collection(client, project_id)
        .document(_doc_id(dataset_id, table_id))
        .collection("history")
    )


def add_history_entry(
    client: firestore.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    field: str,
    old_value: str | None,
    new_value: str | None,
    changed_by: str,
    column_name: str | None = None,
    note: str | None = None,
) -> None:
    """Registra uma alteração no histórico. `column_name` presente =
    edição de coluna (descrição/glossário/PII); ausente = campo de nível
    tabela (description/owner/classification/status/related_links). `note`
    hoje só é preenchido pelas devoluções de revisão. Ver
    docs/specs/metadata.md v2.0, "Histórico"."""
    _history_collection(client, project_id, dataset_id, table_id).add(
        {
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "changed_by": changed_by,
            "changed_at": datetime.now(UTC),
            "column_name": column_name,
            "note": note,
        }
    )


def list_history(
    client: firestore.Client, project_id: str, dataset_id: str, table_id: str
) -> list[dict]:
    docs = (
        _history_collection(client, project_id, dataset_id, table_id)
        .order_by("changed_at", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [doc.to_dict() for doc in docs]


# --- leitura (read-only) do scan de PII já existente (domains/pii) -----------------


def _pii_scans_collection(
    client: firestore.Client, project_id: str, dataset_id: str, table_id: str
):
    doc_id = f"{project_id}_{dataset_id}_{table_id}"
    return client.collection("pii_scan_history").document(doc_id).collection("scans")


def get_latest_pii_scan(
    client: firestore.Client, project_id: str, dataset_id: str, table_id: str
) -> dict | None:
    """Mais recente por executed_at — nunca dispara um scan novo, só lê o
    que já existe. None se a tabela nunca foi escaneada."""
    docs = list(
        _pii_scans_collection(client, project_id, dataset_id, table_id)
        .order_by("executed_at", direction=firestore.Query.DESCENDING)
        .limit(1)
        .stream()
    )
    return docs[0].to_dict() if docs else None


# --- enumeração de tabelas e colunas via BigQuery (custo $0) ----------------------


def list_all_table_refs(
    client: bigquery.Client, project_id: str, regions: list[str], max_workers: int = 8
) -> list[tuple[str, str]]:
    """Todas as (dataset_id, table_id) do projeto, via
    INFORMATION_SCHEMA por região em paralelo — mesma técnica de
    domains/finops/repository.py::list_all_table_refs (duplicado, não
    importado — domínios isolados)."""
    if not regions:
        return []

    def _list_region(region: str) -> list[tuple[str, str]]:
        sql = f"""
            SELECT table_schema AS dataset_id, table_name AS table_id
            FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.TABLES`
        """
        rows = client.query(sql).result()
        return [(row.dataset_id, row.table_id) for row in rows]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(_list_region, regions))
    return [ref for region_rows in results for ref in region_rows]


def get_column_names(
    client: bigquery.Client, project_id: str, dataset_id: str, table_id: str
) -> list[str] | None:
    """None = tabela não existe mais no BigQuery. Usa get_table_cached
    (mesmo cache de 5min de catalog/freshness) — nenhuma query nova, só a
    API tipada do client, mesma fonte que já valida existência de tabela
    em todo o resto do produto."""
    try:
        bq_table = get_table_cached(client, f"{project_id}.{dataset_id}.{table_id}")
    except NotFound:
        return None
    return [field.name for field in bq_table.schema]
