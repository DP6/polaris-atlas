"""Orquestra domains/metadata: metadados editáveis de tabela/coluna
(descrição, ownership, classificação, certificação, links, histórico de
edição; PII confirmado e glossário livre por coluna).

Princípio central da spec (docs/specs/metadata.md): linkar o que já
existe (lineage, qualidade, freshness, budget) em vez de duplicar — este
módulo NUNCA importa de outro domínio. PII é a única exceção parcial:
lê (nunca escreve) a mesma coleção Firestore que domains/pii já grava,
sem importar o módulo Python (mesmo padrão já usado por
domains/admin/analytics_service.py pra profiling/PII cross-domain).
"""

from datetime import UTC, datetime

from google.cloud import bigquery, firestore

from atlas.core.bigquery import discover_regions
from atlas.core.exceptions import ColumnNotFoundError
from atlas.domains.metadata import repository
from atlas.domains.metadata.schemas import (
    MetadataClassification,
    MetadataColumn,
    MetadataColumnUpsertRequest,
    MetadataHistoryEntry,
    MetadataHistoryResponse,
    MetadataOverviewEntry,
    MetadataOverviewResponse,
    MetadataOwner,
    MetadataTableResponse,
    MetadataTableUpsertRequest,
    RelatedLink,
    SuggestedPiiColumn,
    SuggestedPiiResponse,
)

# Campos de nível tabela que geram entrada de histórico — colunas não
# geram (ver docs/specs/metadata.md, "Fora do escopo").
_HISTORY_FIELDS = (
    "description",
    "owner",
    "classification",
    "certification_status",
    "related_links",
)


def _stringify(value) -> str | None:
    return None if value is None else str(value)


def _owner_from_raw(raw: dict | None) -> MetadataOwner | None:
    return MetadataOwner(**raw) if raw else None


def _classification_from_raw(raw: dict | None) -> MetadataClassification | None:
    return MetadataClassification(**raw) if raw else None


def _build_table_response(
    project_id: str, dataset_id: str, table_id: str, raw: dict | None
) -> MetadataTableResponse:
    raw = raw or {}
    return MetadataTableResponse(
        project_id=project_id,
        dataset_id=dataset_id,
        table_id=table_id,
        description=raw.get("description"),
        owner=_owner_from_raw(raw.get("owner")),
        classification=_classification_from_raw(raw.get("classification")),
        certification_status=raw.get("certification_status"),
        related_links=[RelatedLink(**link) for link in raw.get("related_links", [])],
        columns={name: MetadataColumn(**col) for name, col in raw.get("columns", {}).items()},
        updated_at=raw.get("updated_at"),
        updated_by=raw.get("updated_by"),
        has_metadata=bool(raw),
    )


def get_table_metadata(
    client: firestore.Client, project_id: str, dataset_id: str, table_id: str
) -> MetadataTableResponse:
    raw = repository.get_table_metadata(client, project_id, dataset_id, table_id)
    return _build_table_response(project_id, dataset_id, table_id, raw)


def upsert_table_metadata(
    client: firestore.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    request: MetadataTableUpsertRequest,
    updated_by: str,
) -> MetadataTableResponse:
    provided = request.model_dump(exclude_unset=True, mode="json")
    existing = repository.get_table_metadata(client, project_id, dataset_id, table_id) or {}

    for field in _HISTORY_FIELDS:
        if field in provided and provided[field] != existing.get(field):
            repository.add_history_entry(
                client,
                project_id,
                dataset_id,
                table_id,
                field=field,
                old_value=_stringify(existing.get(field)),
                new_value=_stringify(provided[field]),
                changed_by=updated_by,
            )

    raw = repository.upsert_table_metadata(
        client, project_id, dataset_id, table_id, provided, updated_by
    )
    return _build_table_response(project_id, dataset_id, table_id, raw)


def _scanner_signal_for_column(
    scan: dict | None, column_name: str
) -> tuple[bool | None, str | None]:
    """(scanner_flagged, scanner_confidence) da coluna no scan mais
    recente — (None, None) se a tabela nunca foi escaneada ou a coluna
    não aparece no scan (ex: coluna nova, criada depois do último scan)."""
    if not scan:
        return None, None
    for column in scan.get("columns", []):
        if column.get("column_name") == column_name:
            return column.get("flagged"), column.get("confidence")
    return None, None


def upsert_column_metadata(
    bq_client: bigquery.Client,
    firestore_client: firestore.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    column_name: str,
    request: MetadataColumnUpsertRequest,
    updated_by: str,
) -> MetadataTableResponse:
    column_names = repository.get_column_names(bq_client, project_id, dataset_id, table_id)
    if column_names is None or column_name not in column_names:
        raise ColumnNotFoundError(project_id, dataset_id, table_id, column_name)

    provided = request.model_dump(exclude_unset=True)
    fields: dict = {}
    if "description" in provided:
        fields["description"] = provided["description"]
    if "glossary_term" in provided:
        fields["glossary_term"] = provided["glossary_term"]
    if "pii_flag" in provided:
        scan = repository.get_latest_pii_scan(firestore_client, project_id, dataset_id, table_id)
        scanner_flagged, scanner_confidence = _scanner_signal_for_column(scan, column_name)
        fields["pii"] = {
            "flag": provided["pii_flag"],
            "source": "manual",
            "scanner_flagged": scanner_flagged,
            "scanner_confidence": scanner_confidence,
            "confirmed_by": updated_by,
            "confirmed_at": datetime.now(UTC),
        }

    raw = repository.upsert_column_metadata(
        firestore_client, project_id, dataset_id, table_id, column_name, fields, updated_by
    )
    return _build_table_response(project_id, dataset_id, table_id, raw)


def get_history(
    client: firestore.Client, project_id: str, dataset_id: str, table_id: str
) -> MetadataHistoryResponse:
    raw = repository.list_history(client, project_id, dataset_id, table_id)
    return MetadataHistoryResponse(entries=[MetadataHistoryEntry(**e) for e in raw])


def get_suggested_pii(
    client: firestore.Client, project_id: str, dataset_id: str, table_id: str
) -> SuggestedPiiResponse:
    scan = repository.get_latest_pii_scan(client, project_id, dataset_id, table_id)
    if not scan:
        return SuggestedPiiResponse(
            project_id=project_id, dataset_id=dataset_id, table_id=table_id, scanned=False
        )
    columns = [
        SuggestedPiiColumn(
            column_name=c["column_name"], flagged=c["flagged"], confidence=c.get("confidence")
        )
        for c in scan.get("columns", [])
    ]
    return SuggestedPiiResponse(
        project_id=project_id,
        dataset_id=dataset_id,
        table_id=table_id,
        scanned=True,
        columns=columns,
    )


def get_metadata_overview(
    bq_client: bigquery.Client,
    firestore_client: firestore.Client,
    project_id: str,
    certification_status: str | None = None,
    datasets: list[str] | None = None,
    owner_email: str | None = None,
    q: str | None = None,
) -> MetadataOverviewResponse:
    """Enumera via BigQuery ($0), junta em memória com os docs do
    Firestore que existirem — tabela sem doc entra com has_metadata=False,
    nunca é excluída da lista (ver docs/specs/metadata.md, AC-META-007)."""
    regions = discover_regions(project_id, client=bq_client)
    refs = repository.list_all_table_refs(bq_client, project_id, regions)

    entries: list[MetadataOverviewEntry] = []
    for dataset_id, table_id in refs:
        if datasets and dataset_id not in datasets:
            continue
        raw = (
            repository.get_table_metadata(firestore_client, project_id, dataset_id, table_id) or {}
        )

        if certification_status and raw.get("certification_status") != certification_status:
            continue
        owner = _owner_from_raw(raw.get("owner"))
        if owner_email and (owner is None or owner.technical_owner != owner_email):
            continue
        if q and q.lower() not in (raw.get("description") or "").lower():
            continue

        entries.append(
            MetadataOverviewEntry(
                dataset_id=dataset_id,
                table_id=table_id,
                has_metadata=bool(raw),
                certification_status=raw.get("certification_status"),
                owner=owner,
                classification=_classification_from_raw(raw.get("classification")),
                updated_at=raw.get("updated_at"),
            )
        )

    entries.sort(key=lambda e: (e.dataset_id, e.table_id))
    documented_count = sum(1 for e in entries if e.has_metadata)
    return MetadataOverviewResponse(
        project_id=project_id,
        tables=entries,
        total_tables=len(entries),
        documented_count=documented_count,
    )
