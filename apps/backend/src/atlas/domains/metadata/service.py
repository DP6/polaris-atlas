"""Orquestra domains/metadata: metadados editáveis de tabela/coluna
(descrição, ownership, classificação, estado de governança, links,
histórico de edição de tabela e coluna; PII confirmado e glossário livre
por coluna).

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
from atlas.core.exceptions import ColumnNotFoundError, InvalidStatusTransitionError
from atlas.domains.metadata import repository
from atlas.domains.metadata.schemas import (
    GovernanceStatus,
    MetadataClassification,
    MetadataColumn,
    MetadataColumnUpsertRequest,
    MetadataHistoryEntry,
    MetadataHistoryResponse,
    MetadataOverviewEntry,
    MetadataOverviewResponse,
    MetadataOwner,
    MetadataStatusUpdateRequest,
    MetadataTableResponse,
    MetadataTableUpsertRequest,
    RelatedLink,
    SuggestedPiiColumn,
    SuggestedPiiResponse,
)

# Campos de nível tabela que geram entrada de histórico via PUT de campos.
# `status` NÃO está aqui — muda só por update_status (que escreve o
# próprio histórico). Ver docs/specs/metadata.md v2.0.
_HISTORY_FIELDS = (
    "description",
    "owner",
    "classification",
    "related_links",
)

# Campos de coluna que geram entrada de histórico (com column_name
# preenchido) — novidade da v2.0, antes edição de coluna não deixava
# rastro.
_COLUMN_HISTORY_FIELDS = (
    "description",
    "glossary_term",
    "pii_flag",
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
        status=raw.get("status"),
        status_changed_by=raw.get("status_changed_by"),
        status_changed_at=raw.get("status_changed_at"),
        review_note=raw.get("review_note"),
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


# --- fluxo de revisão do estado de governança -----------------------------------


def _resolve_status_transition(current: str | None, target: str, *, is_superadmin: bool) -> str:
    """Devolve o estado final (pode diferir de `target`: superadmin que
    envia pra revisão auto-aprova). Levanta InvalidStatusTransitionError
    se a transição não for permitida pra quem pediu.

    Regras (docs/specs/metadata.md v2.0, "Fluxo de revisão"):
    - superadmin: qualquer transição; `in_review` vira `approved` na hora.
    - Admin de projeto: `draft`↔`in_review` livre; `approved` só a partir
      de `in_review`; `approved → draft`/`in_review` (reabrir) permitido.
      Pular `draft → approved` direto é bloqueado.
    """
    current_norm = current or GovernanceStatus.DRAFT.value

    if is_superadmin:
        if target == GovernanceStatus.IN_REVIEW.value:
            return GovernanceStatus.APPROVED.value
        return target

    if (
        target == GovernanceStatus.APPROVED.value
        and current_norm != GovernanceStatus.IN_REVIEW.value
    ):
        raise InvalidStatusTransitionError(current, target)
    return target


def update_status(
    client: firestore.Client,
    project_id: str,
    dataset_id: str,
    table_id: str,
    request: MetadataStatusUpdateRequest,
    *,
    actor: str,
    is_superadmin: bool,
) -> MetadataTableResponse:
    existing = repository.get_table_metadata(client, project_id, dataset_id, table_id) or {}
    current = existing.get("status")
    target = request.target.value
    current_norm = current or GovernanceStatus.DRAFT.value

    if target == current_norm:
        # No-op — não regrava nem gera histórico (nem valida transição:
        # "já está onde você pediu" nunca é erro). Mesma premissa do
        # skip-history de upsert_table_metadata quando o valor não muda.
        return _build_table_response(project_id, dataset_id, table_id, existing)

    final = _resolve_status_transition(current, target, is_superadmin=is_superadmin)

    if final == current_norm:
        # Superadmin pediu in_review estando já em approved: auto-aprovar
        # devolveria ao mesmo estado — nada a fazer.
        return _build_table_response(project_id, dataset_id, table_id, existing)

    # `note` só sobrevive numa devolução para ajustes (in_review → draft);
    # aprovar ou reenviar limpa a devolução anterior.
    is_return_for_changes = (
        current_norm == GovernanceStatus.IN_REVIEW.value and final == GovernanceStatus.DRAFT.value
    )
    note = request.note if is_return_for_changes else None

    repository.add_history_entry(
        client,
        project_id,
        dataset_id,
        table_id,
        field="status",
        old_value=current,
        new_value=final,
        changed_by=actor,
        note=note,
    )
    raw = repository.set_status(
        client,
        project_id,
        dataset_id,
        table_id,
        status=final,
        changed_by=actor,
        review_note=note,
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

    existing_raw = repository.get_table_metadata(firestore_client, project_id, dataset_id, table_id)
    existing_column = (existing_raw or {}).get("columns", {}).get(column_name) or {}
    existing_column_values = {
        "description": existing_column.get("description"),
        "glossary_term": existing_column.get("glossary_term"),
        "pii_flag": (existing_column.get("pii") or {}).get("flag"),
    }
    for field in _COLUMN_HISTORY_FIELDS:
        if field in provided and provided[field] != existing_column_values[field]:
            repository.add_history_entry(
                firestore_client,
                project_id,
                dataset_id,
                table_id,
                field=field,
                old_value=_stringify(existing_column_values[field]),
                new_value=_stringify(provided[field]),
                changed_by=updated_by,
                column_name=column_name,
            )

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
    status: str | None = None,
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

        if status and raw.get("status") != status:
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
                status=raw.get("status"),
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
