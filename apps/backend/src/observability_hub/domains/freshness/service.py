"""Orquestra o domínio freshness: descobre regiões via core.bigquery, busca
dados via repository, monta os schemas de response. api/v1 só chama estas
funções — CLAUDE.md proíbe lógica de negócio em api/.
"""

from datetime import UTC, datetime

from google.cloud import bigquery

from observability_hub.core.bigquery import discover_regions, resolve_dataset_region
from observability_hub.core.exceptions import TableNotFoundError
from observability_hub.domains.freshness import repository
from observability_hub.domains.freshness.schemas import (
    DatasetFreshnessSummary,
    FreshnessCounts,
    FreshnessDatasetResponse,
    FreshnessProjectResponse,
    SLAStatus,
    TableFreshness,
)

# Ordem crescente de severidade (SLAStatus, spec freshness.md) — usada para
# achar o pior status presente num conjunto de contagens.
_SLA_SEVERITY_ORDER = [
    SLAStatus.OK,
    SLAStatus.WARNING_12_24,
    SLAStatus.WARNING_24_48,
    SLAStatus.WARNING_48_7D,
    SLAStatus.WARNING_7D_1M,
    SLAStatus.STALE,
]


def _worst_status(counts: dict) -> SLAStatus | None:
    for status in reversed(_SLA_SEVERITY_ORDER):
        if counts[status.value] > 0:
            return status
    return None


def _build_counts(raw_tables: list[dict]) -> FreshnessCounts:
    counts = dict.fromkeys((s.value for s in _SLA_SEVERITY_ORDER), 0)
    for table in raw_tables:
        status = table["sla_status"]
        if status is not None:
            counts[status] += 1
    return FreshnessCounts(total_tables=len(raw_tables), **counts)


def get_project_freshness(client: bigquery.Client, project_id: str) -> FreshnessProjectResponse:
    regions = discover_regions(project_id, client=client)
    raw_datasets = repository.get_freshness_summary_by_dataset(client, project_id, regions)
    datasets = [DatasetFreshnessSummary(**d, worst_status=_worst_status(d)) for d in raw_datasets]
    return FreshnessProjectResponse(
        project_id=project_id,
        evaluated_at=datetime.now(UTC),
        datasets=datasets,
    )


def get_dataset_freshness(
    client: bigquery.Client, project_id: str, dataset_id: str
) -> FreshnessDatasetResponse:
    regions = discover_regions(project_id, client=client)
    location = resolve_dataset_region(client, project_id, dataset_id, regions)
    raw_tables = repository.get_table_freshness(client, project_id, dataset_id, location)
    return FreshnessDatasetResponse(
        project_id=project_id,
        dataset_id=dataset_id,
        location=location,
        evaluated_at=datetime.now(UTC),
        summary=_build_counts(raw_tables),
        tables=[TableFreshness(**t) for t in raw_tables],
    )


def get_table_freshness(
    client: bigquery.Client, project_id: str, dataset_id: str, table_id: str
) -> TableFreshness:
    """Endpoint novo pequeno (v1.1, ver docs/specs/freshness.md) — pré-
    requisito de docs/specs/metadata.md pra embutir freshness na aba de
    metadados sem sobre-buscar o dataset inteiro no frontend. Reaproveita
    repository.get_table_freshness (mesma fonte $0 de get_dataset_freshness)
    e filtra em Python — nenhuma query BQ nova, o custo já era o mesmo pra
    listar uma tabela ou o dataset inteiro (INFORMATION_SCHEMA.TABLES +
    get_tables_metadata, ambos metadado)."""
    regions = discover_regions(project_id, client=client)
    location = resolve_dataset_region(client, project_id, dataset_id, regions)
    raw_tables = repository.get_table_freshness(client, project_id, dataset_id, location)
    match = next((t for t in raw_tables if t["table_id"] == table_id), None)
    if match is None:
        raise TableNotFoundError(project_id, dataset_id, table_id)
    return TableFreshness(**match)
