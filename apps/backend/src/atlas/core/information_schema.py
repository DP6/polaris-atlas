"""Leitura de `INFORMATION_SCHEMA.JOBS_BY_PROJECT` — fonte complementar
ao Cloud Logging pros domínios que leem job completado do BigQuery
(lineage, access, finops scan-events), usada só no full scan inicial de
cada projeto (ver jobs/refresh_event_cache.py). Ver ADR-013.

Motivação: o Cloud Logging do projeto-cliente por padrão só retém 30
dias de Data Access audit log (`_Default` log bucket, config fora do
nosso acesso) — não é retroativo, e não temos como pedir pro cliente
mudar. `INFORMATION_SCHEMA.JOBS_BY_PROJECT` é uma fonte independente,
mantida pelo próprio BigQuery, com retenção nativa de 180 dias fixada
pelo Google (não é parâmetro, não muda com plano/tier) — usada só na
"fotografia inicial" do onboarding pra maximizar o histórico resgatável,
nunca no delta incremental diário (que continua só Cloud Logging, mais
barato e já com o high-water-mark certo).

Diferença importante em relação ao Cloud Logging: esta view **não expõe**
`jobConfiguration.load.sourceUris`/`extract.destinationUris` — só
`referenced_tables`/`destination_table` (tabelas BigQuery). A extensão de
lineage pra bucket do GCS (`JobEvent.source_buckets`/`destination_buckets`,
ver docs/specs/storage.md seção 7) não é reconstruível por esta via —
lacuna documentada, não um bug do parser.

**IAM — a confirmar em rollout real**: `JOBS_BY_PROJECT` (diferente de
`JOBS_BY_USER`) lista jobs de **todos** os usuários do projeto, não só o
do caller — pode exigir `bigquery.jobs.listAll` além de
`roles/bigquery.metadataViewer`/`jobUser` já pedidos hoje em
docs/onboarding-cliente.md (que cobrem `INFORMATION_SCHEMA.TABLES`/
`SCHEMATA`, não necessariamente `JOBS_BY_PROJECT`). Não verificado ao
vivo ainda. Sem a permissão certa, `list_recent_jobs` degrada sozinho
pra lista vazia por região (`Forbidden` capturado abaixo) — não quebra o
full scan, só deixa de contribuir com histórico extra. Confirmar contra
um projeto real e atualizar o checklist de onboarding se precisar de
role nova.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from google.api_core.exceptions import Forbidden, NotFound
from google.cloud import bigquery

# Teto de retenção da própria view, fixado pelo Google — não é
# configurável, não muda com plano/tier do BigQuery. Diferente de
# `_JOB_WINDOW_DAYS`/`_FINOPS_CACHE_MAX_DAYS` (retenção do CACHE do
# atlas, essa sim ajustável), este número é um fato da plataforma.
JOBS_BY_PROJECT_MAX_LOOKBACK_DAYS = 180

_JOB_ROW_FIELDS = (
    "job_id",
    "user_email",
    "creation_time",
    "start_time",
    "end_time",
    "query",
    "job_type",
    "destination_table",
    "referenced_tables",
    "total_bytes_billed",
)


def _row_to_dict(row: bigquery.table.Row) -> dict[str, Any]:
    return {field: row.get(field) for field in _JOB_ROW_FIELDS}


def list_recent_jobs(
    client: bigquery.Client,
    project_id: str,
    regions: list[str],
    *,
    lookback_days: int = JOBS_BY_PROJECT_MAX_LOOKBACK_DAYS,
    max_workers: int = 8,
) -> list[dict[str, Any]]:
    """Jobs completados (`state = "DONE"`, sucesso ou falha — mesmo
    critério do audit log `jobservice.jobcompleted`) nos últimos
    `lookback_days` (clampado no service/job chamador a
    `JOBS_BY_PROJECT_MAX_LOOKBACK_DAYS` — não reforçado aqui). Uma query
    por região com dataset (mesma técnica de
    `discover_regions`/`domains/lineage/repository.py::list_all_table_refs`
    — `JOBS_BY_PROJECT` também exige qualificador de região).

    Cada item é um dict com as chaves de `_JOB_ROW_FIELDS` — timestamps já
    vêm como `datetime` (tz-aware, UTC) do client, não string ISO.
    `destination_table`/cada item de `referenced_tables` são dicts
    `{"project_id", "dataset_id", "table_id"}` (snake_case — diferente do
    payload de audit log do Cloud Logging, que usa camelCase).

    Região sem permissão (`Forbidden`) ou sem a view populada ainda
    (`NotFound`, projeto sem job algum na região) é ignorada — best-effort
    por região, mesmo espírito de `discover_regions` mas sem propagar erro
    forte: esta função só alimenta o full scan inicial, não deve derrubar
    o refresh inteiro do projeto por causa de uma região vazia."""
    if not regions:
        return []

    def _list_region(region: str) -> list[dict[str, Any]]:
        sql = f"""
            SELECT
                job_id, user_email, creation_time, start_time, end_time,
                query, job_type, destination_table, referenced_tables,
                total_bytes_billed
            FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
            WHERE state = "DONE"
              AND creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @lookback_days DAY)
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("lookback_days", "INT64", lookback_days)]
        )
        try:
            rows = list(client.query(sql, job_config=job_config).result())
        except (Forbidden, NotFound):
            return []
        return [_row_to_dict(row) for row in rows]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_list_region, region) for region in regions]
        results = [future.result() for future in as_completed(futures)]
    return [row for region_rows in results for row in region_rows]


def parse_table_ref_snake(ref: dict | None) -> tuple[str, str, str] | None:
    """Mesma forma de `_parse_table_ref` de cada domínio, mas pras chaves
    snake_case que `INFORMATION_SCHEMA.JOBS_BY_PROJECT` devolve
    (`project_id`/`dataset_id`/`table_id`) em vez do camelCase do payload
    de audit log do Cloud Logging (`projectId`/`datasetId`/`tableId`).
    Compartilhada aqui porque é só formatação de struct, não lógica de
    domínio — cada domínio ainda decide o que fazer com o resultado
    (filtro de dataset anônimo, filtro de INFORMATION_SCHEMA.*, etc.)."""
    if not ref:
        return None
    project_id = ref.get("project_id")
    dataset_id = ref.get("dataset_id")
    table_id = ref.get("table_id")
    if not project_id or not dataset_id or not table_id:
        return None
    return project_id, dataset_id, table_id


def most_recent_timestamp(row: dict[str, Any]) -> datetime | None:
    """`end_time or start_time or creation_time` — mesmo fallback usado
    pelos parsers de audit log de cada domínio (job sem `end_time`
    registrado, ex. falha antes de terminar)."""
    return row.get("end_time") or row.get("start_time") or row.get("creation_time")
