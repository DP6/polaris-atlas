"""Orquestra o domínio finops: scanner de desperdício (tabelas sem uso,
candidatas a particionamento) e budget (custo agrupável por
tabela/usuário/dia/mês/ano, queries mais caras, projeção do mês) —
combina enumeração de tabelas (BigQuery INFORMATION_SCHEMA +
client.get_table() via core/bigquery.py) com audit logs de jobs (Cloud
Logging, via repository). api/v1 só chama estas funções — CLAUDE.md
proíbe lógica de negócio em api/.
"""

import calendar
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta

from google.cloud import bigquery, firestore, storage
from google.cloud import logging as cloud_logging

from atlas.core.bigquery import (
    discover_regions,
    get_tables_metadata,
    resolve_dataset_region,
)
from atlas.core.config import settings
from atlas.core.exceptions import (
    EventCacheNotReadyError,
    InvalidSamplePercentError,
    LoggingQuotaExceededError,
)
from atlas.domains.budget import repository as budget_repository
from atlas.domains.finops import repository, sql_builder
from atlas.domains.finops.repository import ScanEvent, TableRefTuple
from atlas.domains.finops.schemas import (
    BudgetGroupBy,
    BudgetResponse,
    ColumnTypeCandidate,
    ColumnTypeEstimateResponse,
    ColumnTypeScanRequest,
    ColumnTypeSuggestion,
    ColumnTypeSuggestionsResponse,
    CostGroup,
    CostlyQuery,
    CostProjection,
    CostSeriesGranularity,
    CostSeriesPoint,
    CostSeriesResponse,
    CostType,
    PartitionCandidate,
    PartitionCandidatesResponse,
    SuggestedColumnType,
    TableScore,
    TableScoreFactor,
    TableScoresResponse,
)

_PARTITION_CANDIDATE_LOOKBACK_DAYS = repository.LOOKBACK_DAYS
_MIN_TABLE_SIZE_BYTES_FOR_PARTITION_CANDIDATE = 1_073_741_824  # 1 GB
_CONSERVATIVE_REDUCTION = 0.30
_OPTIMISTIC_REDUCTION = 0.70
_BUDGET_TOP_N_DEFAULT = 10
# Teto de retenção do cache de audit log — nem "últimos N dias" nem um
# filtro de data explícito (from/to) conseguem alcançar mais que isso.
# Era duas constantes (uma por endpoint); unificada porque é o mesmo
# limite físico dos dois (_resolve_date_window).
_FINOPS_CACHE_MAX_DAYS = 31
# Janela default do budget quando nenhum filtro é passado: "últimos N
# dias", N = 30 (comportamento próximo do mês corrente).
_BUDGET_DEFAULT_LOOKBACK_DAYS = 30
_COLUMN_TYPE_SCAN_TIMEOUT_SECONDS = 120.0
_COLUMN_TYPE_SCAN_MAX_WORKERS = 4
_STORAGE_BYTES_OVERHEAD = (
    2  # overhead fixo de STRING no storage do BQ, ver docs/specs/finops-column-types.md
)

_EMPTY_RESULT_WARNING = (
    "Nenhum evento de job encontrado nos audit logs dos últimos {days} dias. "
    "Isso pode significar (a) que não houve atividade na janela, (b) que os "
    "Data Access audit logs estão desabilitados no projeto '{project_id}' "
    "ou (c) que a service account do Hub tem roles/logging.viewer mas não "
    "roles/logging.privateLogViewer no projeto. Verifique auditConfigs com: "
    "gcloud projects get-iam-policy {project_id} --format=json."
)

_SAVINGS_DISCLAIMER = (
    "Estimativa especulativa baseada no custo de scan REAL observado nos "
    "últimos 30 dias — não confirma que as queries filtram pela coluna de "
    "data candidata (o que de fato reduziria bytes escaneados via "
    "partition pruning). Se a query faz JOIN com outras tabelas grandes, o "
    "custo mostrado é o da query inteira, não isolado só desta tabela."
)

_BUDGET_RETENTION_CAVEAT = (
    "Já estamos {days} dias dentro do mês, e Data Access audit logs no "
    "Cloud Logging têm retenção padrão de 30 dias (salvo bucket/sink "
    "customizado). Se esse for o caso aqui, o início do mês pode estar "
    "faltando neste relatório — custo agrupado, top queries e projeção "
    "ficariam subestimados."
)

_COLUMN_TYPE_PARTIAL_RESULT_WARNING = (
    "Orçamento de tempo do scan ({budget}s) esgotou antes de escanear todas "
    "as tabelas elegíveis — resultado parcial, baseado em {scanned} de "
    "{total} tabelas."
)

_QUOTA_WARNING = (
    "O limite de leitura de audit logs do projeto '{project_id}' foi atingido "
    "temporariamente (cota do Cloud Logging, compartilhada entre ambientes). "
    "Os números voltam assim que o cache for atualizado — um admin do Hub "
    "pode forçar agora em Administração → Caches; senão, recarregue em alguns "
    "minutos."
)

_CACHE_NOT_READY_WARNING = (
    "O cache de audit log do projeto '{project_id}' ainda não foi gerado. Um "
    "admin do Hub pode disparar agora em Administração → Caches → 'Atualizar "
    "agora'; o ciclo diário também popula sozinho."
)


def _scan_events_or_quota_warning(
    logging_client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
) -> tuple[list[ScanEvent], datetime | None, str | None]:
    """Cota do Cloud Logging saturada, ou cache ainda não gerado (modelo
    incremental) → degrada pra resultado vazio com aviso em vez de 503
    (mesmo tratamento de domains/access/service.py e do waste scanner 6.2
    de storage). Retorna (events, cache_updated_at, warning)."""
    try:
        events, cache_updated_at = repository.get_scan_events_cached(
            logging_client, storage_client, firestore_client, project_id
        )
        return events, cache_updated_at, None
    except LoggingQuotaExceededError:
        return [], None, _QUOTA_WARNING.format(project_id=project_id)
    except EventCacheNotReadyError:
        return [], None, _CACHE_NOT_READY_WARNING.format(project_id=project_id)


def _human_bytes(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1000:
            return f"{value:.2f} {unit}"
        value /= 1000
    return f"{value:.2f} TB"


def _estimate_query_cost_usd(num_bytes: int) -> float:
    tib = num_bytes / (1024**4)
    return round(tib * settings.bigquery_price_usd_per_tib, 6)


def scan_partition_candidates(
    client: bigquery.Client,
    logging_client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
    datasets: list[str] | None = None,
    tables: list[str] | None = None,
) -> PartitionCandidatesResponse:
    regions = discover_regions(project_id, client=client)
    all_tables = repository.list_all_table_refs(client, project_id, regions, datasets=datasets)
    if tables:
        requested = set(_parse_scoped_tables(tables))
        all_tables = [t for t in all_tables if t in requested]
    table_refs = [f"{project_id}.{d}.{t}" for d, t in all_tables]
    metadata = get_tables_metadata(client, table_refs)

    size_candidates: list[tuple[str, str, bigquery.Table]] = []
    for dataset_id, table_id in all_tables:
        bq_table = metadata.get(f"{project_id}.{dataset_id}.{table_id}")
        if bq_table is None:
            continue
        if bq_table.time_partitioning is not None or bq_table.range_partitioning is not None:
            continue  # já particionada
        if (bq_table.num_bytes or 0) < _MIN_TABLE_SIZE_BYTES_FOR_PARTITION_CANDIDATE:
            continue  # pequena demais pra valer a pena sinalizar
        size_candidates.append((dataset_id, table_id, bq_table))

    events, cache_updated_at, quota_warning = _scan_events_or_quota_warning(
        logging_client, storage_client, firestore_client, project_id
    )
    billed_bytes_by_table: dict[tuple[str, str], int] = {}
    for event in events:
        if event.timestamp is None:
            continue
        for ref in event.referenced_tables:
            if ref[0] != project_id:
                continue
            key = ref[1:]
            billed_bytes_by_table[key] = (
                billed_bytes_by_table.get(key, 0) + event.total_billed_bytes
            )

    dataset_regions: dict[str, str] = {}
    candidates: list[PartitionCandidate] = []
    for dataset_id, table_id, bq_table in size_candidates:
        if dataset_id not in dataset_regions:
            dataset_regions[dataset_id] = resolve_dataset_region(
                client, project_id, dataset_id, regions
            )
        location = dataset_regions[dataset_id]

        date_columns = repository.get_date_like_columns(
            client, project_id, dataset_id, table_id, location
        )
        if not date_columns:
            continue  # sem coluna candidata, não é uma sugestão viável

        billed = billed_bytes_by_table.get((dataset_id, table_id), 0)
        observed_cost = _estimate_query_cost_usd(billed)
        conservative = round(observed_cost * _CONSERVATIVE_REDUCTION, 6) if billed > 0 else None
        optimistic = round(observed_cost * _OPTIMISTIC_REDUCTION, 6) if billed > 0 else None
        size_bytes = bq_table.num_bytes or 0

        candidates.append(
            PartitionCandidate(
                dataset_id=dataset_id,
                table_id=table_id,
                size_bytes=size_bytes,
                size_human=_human_bytes(size_bytes),
                row_count=bq_table.num_rows,
                candidate_partition_columns=date_columns,
                observed_billed_bytes_30d=billed,
                observed_cost_usd_30d=observed_cost,
                estimated_savings_usd_conservative=conservative,
                estimated_savings_usd_optimistic=optimistic,
                savings_disclaimer=_SAVINGS_DISCLAIMER if billed > 0 else None,
            )
        )

    candidates.sort(key=lambda c: c.observed_cost_usd_30d, reverse=True)

    return PartitionCandidatesResponse(
        project_id=project_id,
        lookback_days=_PARTITION_CANDIDATE_LOOKBACK_DAYS,
        candidates=candidates,
        cache_updated_at=cache_updated_at,
        warning=quota_warning
        or (
            _EMPTY_RESULT_WARNING.format(
                days=_PARTITION_CANDIDATE_LOOKBACK_DAYS, project_id=project_id
            )
            if not events
            else None
        ),
    )


def _group_keys(
    group_by: BudgetGroupBy, event: ScanEvent, real_tables: list[TableRefTuple]
) -> list[str]:
    """Uma chave por tabela (ou dataset) real tocado (fan-out — uma query
    com JOIN entre tabelas/datasets conta em cada um) pra group_by=TABLE/
    DATASET; uma chave só pras demais dimensões, que são por evento, não
    por tabela."""
    if group_by == BudgetGroupBy.TABLE:
        return sorted({f"{p}.{d}.{t}" for p, d, t in real_tables})
    if group_by == BudgetGroupBy.DATASET:
        return sorted({f"{p}.{d}" for p, d, _t in real_tables})
    if group_by == BudgetGroupBy.USER:
        return [event.principal_email]
    assert event.timestamp is not None  # já filtrado antes de chamar
    if group_by == BudgetGroupBy.DAY:
        return [event.timestamp.date().isoformat()]
    if group_by == BudgetGroupBy.MONTH:
        return [event.timestamp.strftime("%Y-%m")]
    return [str(event.timestamp.year)]  # YEAR


def _resolve_date_window(
    now: datetime,
    lookback_days: int,
    from_date: date | None,
    to_date: date | None,
) -> tuple[date, date, int, str | None]:
    """Resolve a janela efetiva de dados pra get_budget/get_cost_series —
    dois modos:

    - Legado (from_date/to_date ambos None): "últimos N dias" a partir de
      hoje, N = lookback_days clampado em 1.._FINOPS_CACHE_MAX_DAYS.
    - Filtro de data explícito (rodada 3, AC-FIN-RV-02): to_date clampado
      pra não ficar no futuro; from_date clampado pro piso do cache (hoje
      - (_FINOPS_CACHE_MAX_DAYS - 1) dias); se invertido depois dos
      clamps, troca defensivamente — nunca 422, mesma filosofia do
      lookback_days de hoje (o service resolve, não empurra erro pro
      chamador por um parâmetro fora do alcance).

    Retorna (start, end, lookback_days_efetivo, warning|None) — warning só
    quando algum clamp mudou o que foi pedido; nunca trunca em silêncio.
    """
    today = now.date()
    cache_floor = today - timedelta(days=_FINOPS_CACHE_MAX_DAYS - 1)

    if from_date is None and to_date is None:
        lookback_days = max(1, min(lookback_days, _FINOPS_CACHE_MAX_DAYS))
        end = today
        start = end - timedelta(days=lookback_days - 1)
        return start, end, lookback_days, None

    warnings: list[str] = []

    end = to_date or today
    if end > today:
        warnings.append(
            f"Data final pedida ({end.isoformat()}) é no futuro — ajustada para hoje "
            f"({today.isoformat()})."
        )
        end = today

    start = from_date or cache_floor
    if start < cache_floor:
        warnings.append(
            f"Data inicial pedida ({start.isoformat()}) é anterior ao que o cache de "
            f"audit log guarda ({_FINOPS_CACHE_MAX_DAYS} dias) — ajustada para "
            f"{cache_floor.isoformat()}."
        )
        start = cache_floor

    if start > end:
        start, end = end, start

    return start, end, (end - start).days + 1, (" ".join(warnings) or None)


def _merge_storage_into_groups(
    client: bigquery.Client,
    project_id: str,
    group_by: BudgetGroupBy,
    group_bytes: dict[str, int],
    group_jobs: dict[str, int],
    start_date: date,
    end_date: date,
) -> tuple[list[CostGroup], str | None]:
    """Só chamada quando include_storage=True e group_by é table/dataset —
    une as chaves vindas de eventos de query (group_bytes/group_jobs) com
    TODAS as tabelas que têm bytes de storage > 0 (mesmo as nunca
    consultadas na janela — decisão do usuário: mostrar tabela abandonada
    custando storage é o sinal mais útil de FinOps aqui). Fonte $0
    (INFORMATION_SCHEMA.TABLE_STORAGE via repository.get_storage_bytes_by_table).
    Nunca lança: se nenhuma região responder, devolve os groups só-de-query
    inalterados + warning."""
    regions = discover_regions(project_id, client=client)
    bytes_by_table, reason = repository.get_storage_bytes_by_table(client, project_id, regions)

    if bytes_by_table is None:
        storage_warning = _STORAGE_UNAVAILABLE_WARNING.format(project_id=project_id)
        if reason:
            storage_warning = f"{storage_warning} Motivo do BigQuery: {reason}."
        fallback_groups = sorted(
            (
                CostGroup(
                    key=key,
                    cost_usd=_estimate_query_cost_usd(billed),
                    billed_bytes=billed,
                    job_count=group_jobs[key],
                )
                for key, billed in group_bytes.items()
            ),
            key=lambda g: g.cost_usd,
            reverse=True,
        )
        return fallback_groups, storage_warning

    days_count = (end_date - start_date).days + 1
    storage_cost_by_key: dict[str, float] = {}
    for (dataset_id, table_id), byte_count in bytes_by_table.items():
        cost = sum(
            _storage_cost_for_day(byte_count, start_date + timedelta(days=i))
            for i in range(days_count)
        )
        key = (
            f"{project_id}.{dataset_id}.{table_id}"
            if group_by == BudgetGroupBy.TABLE
            else f"{project_id}.{dataset_id}"
        )
        storage_cost_by_key[key] = storage_cost_by_key.get(key, 0.0) + cost

    all_keys = set(group_bytes) | set(storage_cost_by_key)
    groups = sorted(
        (
            CostGroup(
                key=key,
                cost_usd=_estimate_query_cost_usd(group_bytes.get(key, 0)),
                billed_bytes=group_bytes.get(key, 0),
                job_count=group_jobs.get(key, 0),
                storage_cost_usd=round(storage_cost_by_key.get(key, 0.0), 6),
                total_cost_usd=round(
                    _estimate_query_cost_usd(group_bytes.get(key, 0))
                    + storage_cost_by_key.get(key, 0.0),
                    6,
                ),
            )
            for key in all_keys
        ),
        key=lambda g: g.total_cost_usd or 0.0,
        reverse=True,
    )
    return groups, None


def get_budget(
    logging_client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
    group_by: BudgetGroupBy = BudgetGroupBy.TABLE,
    limit: int = _BUDGET_TOP_N_DEFAULT,
    lookback_days: int = _BUDGET_DEFAULT_LOOKBACK_DAYS,
    from_date: date | None = None,
    to_date: date | None = None,
    client: bigquery.Client | None = None,
    include_storage: bool = False,
) -> BudgetResponse:
    now = datetime.now(UTC)
    start_date, end_date, lookback_days, clamp_warning = _resolve_date_window(
        now, lookback_days, from_date, to_date
    )
    period_start = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
    period_end = datetime.combine(end_date, datetime.min.time(), tzinfo=UTC)

    today = now.date()
    month_start = today.replace(day=1)
    days_elapsed_in_month = (today - month_start).days + 1

    # Fonte é o mesmo cache de ~30 dias de scan_partition_candidates; o
    # recorte pra janela sai do filtro de start_date/end_date abaixo.
    events, cache_updated_at, quota_warning = _scan_events_or_quota_warning(
        logging_client, storage_client, firestore_client, project_id
    )

    group_bytes: dict[str, int] = {}
    group_jobs: dict[str, int] = {}
    queries: list[CostlyQuery] = []
    total_billed_bytes = 0
    # A projeção mensal é sempre month-to-date real (dia 1 do mês corrente
    # até hoje) — independente da janela lookback_days/from-to escolhida
    # pro resto da resposta (groups/top_queries/total_cost_usd). Antes a
    # projeção reusava a janela escolhida como base, e como lookback_days
    # (default 30) e days_in_month (28-31) ficavam sempre próximos,
    # projected_month_total_usd colapsava pra ≈ cost_so_far (ver
    # CHANGELOG "finops-overview-date-range"). Cabe sempre no cache de
    # _FINOPS_CACHE_MAX_DAYS porque nenhum mês tem mais de 31 dias
    # (ASM-001 em docs/specs/finops-budget.md).
    month_to_date_billed_bytes = 0

    for event in events:
        if event.timestamp is None:
            continue
        if event.total_billed_bytes <= 0:
            continue

        real_tables = [ref for ref in event.referenced_tables if ref[0] == project_id]
        if not real_tables:
            # Só referencia INFORMATION_SCHEMA (já filtrado em
            # repository._parse_table_ref) ou tabela de outro projeto —
            # não é atividade de dado real deste projeto, não entra em
            # nenhuma agregação de budget (ver docs/specs/finops-budget.md,
            # "Casos de borda").
            continue

        event_date = event.timestamp.date()

        if month_start <= event_date <= today:
            month_to_date_billed_bytes += event.total_billed_bytes

        if event_date < start_date or event_date > end_date:
            continue

        total_billed_bytes += event.total_billed_bytes

        for key in _group_keys(group_by, event, real_tables):
            group_bytes[key] = group_bytes.get(key, 0) + event.total_billed_bytes
            group_jobs[key] = group_jobs.get(key, 0) + 1

        queries.append(
            CostlyQuery(
                job_id=event.job_id,
                principal_email=event.principal_email,
                executed_at=event.timestamp,
                billed_bytes=event.total_billed_bytes,
                cost_usd=_estimate_query_cost_usd(event.total_billed_bytes),
                tables=[f"{p}.{d}.{t}" for p, d, t in real_tables],
                query_text=event.query_text,
            )
        )

    groups = sorted(
        (
            CostGroup(
                key=key,
                cost_usd=_estimate_query_cost_usd(billed),
                billed_bytes=billed,
                job_count=group_jobs[key],
            )
            for key, billed in group_bytes.items()
        ),
        key=lambda g: g.cost_usd,
        reverse=True,
    )

    storage_warning: str | None = None
    if (
        include_storage
        and group_by in (BudgetGroupBy.TABLE, BudgetGroupBy.DATASET)
        and client is not None
    ):
        groups, storage_warning = _merge_storage_into_groups(
            client, project_id, group_by, group_bytes, group_jobs, start_date, end_date
        )

    top_queries = sorted(queries, key=lambda q: q.cost_usd, reverse=True)[:limit]

    total_cost_usd = _estimate_query_cost_usd(total_billed_bytes)

    # Projeção mensal month-to-date: média diária do gasto já acumulado
    # no mês corrente (dia 1 até hoje), extrapolada pros dias restantes.
    cost_so_far_usd = _estimate_query_cost_usd(month_to_date_billed_bytes)
    daily_average = cost_so_far_usd / days_elapsed_in_month if days_elapsed_in_month else 0.0
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    projection = CostProjection(
        days_elapsed=days_elapsed_in_month,
        days_in_month=days_in_month,
        cost_so_far_usd=cost_so_far_usd,
        daily_average_usd=round(daily_average, 6),
        projected_month_total_usd=round(daily_average * days_in_month, 6),
    )

    warning_parts = [w for w in (clamp_warning,) if w]
    if quota_warning is not None:
        warning_parts.append(quota_warning)
    elif not events:
        warning_parts.append(
            _EMPTY_RESULT_WARNING.format(days=lookback_days, project_id=project_id)
        )
    elif lookback_days > 30:
        warning_parts.append(_BUDGET_RETENTION_CAVEAT.format(days=lookback_days))
    if storage_warning:
        warning_parts.append(storage_warning)
    warning = " ".join(warning_parts) or None

    # Compartilhado por projeto (v1.13) — não depende mais de quem está
    # logado (era `if user_email` antes; agora sempre consultado).
    budget_target_usd = budget_repository.get_project_budget_amount(firestore_client, project_id)

    return BudgetResponse(
        project_id=project_id,
        period_start=period_start,
        period_end=period_end,
        lookback_days=lookback_days,
        group_by=group_by,
        groups=groups,
        total_cost_usd=total_cost_usd,
        top_queries=top_queries,
        projection=projection,
        budget_target_usd=budget_target_usd,
        cache_updated_at=cache_updated_at,
        warning=warning,
    )


_STORAGE_UNAVAILABLE_WARNING = (
    "A linha de custo de storage não pôde ser montada: "
    "INFORMATION_SCHEMA.TABLE_STORAGE não respondeu no projeto "
    "'{project_id}'. A linha de custo de query continua válida."
)


def _period_key(d: date, granularity: CostSeriesGranularity) -> str:
    if granularity == CostSeriesGranularity.MONTH:
        return d.strftime("%Y-%m")
    return d.isoformat()


def _iter_periods(start: date, end: date, granularity: CostSeriesGranularity) -> list[str]:
    """Lista contígua de chaves de período de start a end (inclusive) — o
    gráfico precisa de pontos sem buraco mesmo em dias/meses sem custo."""
    keys: list[str] = []
    seen: set[str] = set()
    cursor = start
    while cursor <= end:
        key = _period_key(cursor, granularity)
        if key not in seen:
            seen.add(key)
            keys.append(key)
        cursor += timedelta(days=1)
    return keys


def _storage_cost_for_day(logical_bytes: int, day: date) -> float:
    """Custo de storage *incorrido naquele dia* = custo mensal daquele
    volume dividido pelos dias do mês. Usa a tarifa `active` (ignora o
    desconto de long-term → a linha de storage é um teto suave) e assume
    cobrança lógica/on-demand, mesma premissa do resto do Hub (ver
    docs/specs/finops-budget.md, 'É uma estimativa')."""
    gb = logical_bytes / (1024**3)
    days_in_month = calendar.monthrange(day.year, day.month)[1]
    monthly = gb * settings.bigquery_storage_price_usd_per_gb_month_active
    return monthly / days_in_month


def get_cost_series(
    client: bigquery.Client,
    logging_client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
    granularity: CostSeriesGranularity = CostSeriesGranularity.DAY,
    cost_type: CostType = CostType.ALL,
    lookback_days: int = 30,
    from_date: date | None = None,
    to_date: date | None = None,
    datasets: list[str] | None = None,
    tables: list[str] | None = None,
) -> CostSeriesResponse:
    """Série temporal de custo (query + storage) pro gráfico combo da
    visão geral de FinOps (AC-FIN-RV-02). Custo de query vem do mesmo
    cache de audit log de get_budget (nenhum scan novo); custo de storage
    é uma linha plana no nível atual, de INFORMATION_SCHEMA.TABLE_STORAGE
    (metadado, $0), que degrada pra `storage_available=False` se
    indisponível — nunca 500."""
    now = datetime.now(UTC)
    start_date, end_date, _lookback_days, clamp_warning = _resolve_date_window(
        now, lookback_days, from_date, to_date
    )

    want_query = cost_type in (CostType.ALL, CostType.QUERY)
    want_storage = cost_type in (CostType.ALL, CostType.STORAGE)

    dataset_filter = set(datasets) if datasets else None
    table_filter = set(tables) if tables else None

    # --- custo de query, do cache de audit log ------------------------------
    query_cost_by_period: dict[str, float] = {}
    cache_updated_at: datetime | None = None
    warning: str | None = clamp_warning
    if want_query:
        events, cache_updated_at, quota_warning = _scan_events_or_quota_warning(
            logging_client, storage_client, firestore_client, project_id
        )
        if quota_warning:
            warning = f"{warning} {quota_warning}".strip() if warning else quota_warning
        for event in events:
            if event.timestamp is None:
                continue
            event_date = event.timestamp.date()
            if event_date < start_date or event_date > end_date:
                continue
            if event.total_billed_bytes <= 0:
                continue
            real_tables = [ref for ref in event.referenced_tables if ref[0] == project_id]
            if not real_tables:
                continue
            if dataset_filter is not None and not any(
                d in dataset_filter for _p, d, _t in real_tables
            ):
                continue
            if table_filter is not None and not any(
                f"{d}.{t}" in table_filter for _p, d, t in real_tables
            ):
                continue
            key = _period_key(event.timestamp.date(), granularity)
            cost = _estimate_query_cost_usd(event.total_billed_bytes)
            query_cost_by_period[key] = query_cost_by_period.get(key, 0.0) + cost

    # --- custo de storage: linha plana no nível ATUAL --------------------
    # (não a timeline histórica — schema de coluna instável; em ~30 dias o
    # storage quase não varia, ver repository.get_current_storage_bytes.)
    storage_cost_by_period: dict[str, float] = {}
    storage_available = True
    if want_storage:
        # discover_regions propaga ProjectNotFound/AccessDenied igual aos
        # outros endpoints de finops (scan_partition_candidates) — se a SA
        # não alcança o projeto, é 404/403, não série vazia silenciosa.
        regions = discover_regions(project_id, client=client)
        current_bytes, storage_reason = repository.get_current_storage_bytes(
            client, project_id, regions, datasets=datasets, tables=tables
        )
        if current_bytes is None:
            storage_available = False
            storage_warning = _STORAGE_UNAVAILABLE_WARNING.format(project_id=project_id)
            if storage_reason:
                storage_warning = f"{storage_warning} Motivo do BigQuery: {storage_reason}."
            warning = f"{warning} {storage_warning}".strip() if warning else storage_warning
        else:
            cursor = start_date
            while cursor <= end_date:
                key = _period_key(cursor, granularity)
                storage_cost_by_period[key] = storage_cost_by_period.get(
                    key, 0.0
                ) + _storage_cost_for_day(current_bytes, cursor)
                cursor += timedelta(days=1)
    else:
        storage_available = False

    points = [
        CostSeriesPoint(
            period=key,
            query_cost_usd=round(query_cost_by_period.get(key, 0.0), 6),
            storage_cost_usd=round(storage_cost_by_period.get(key, 0.0), 6),
            total_cost_usd=round(
                query_cost_by_period.get(key, 0.0) + storage_cost_by_period.get(key, 0.0), 6
            ),
        )
        for key in _iter_periods(start_date, end_date, granularity)
    ]

    return CostSeriesResponse(
        project_id=project_id,
        granularity=granularity,
        cost_type=cost_type,
        period_start=datetime.combine(start_date, datetime.min.time(), tzinfo=UTC),
        period_end=datetime.combine(end_date, datetime.min.time(), tzinfo=UTC),
        points=points,
        total_cost_usd=round(sum(p.total_cost_usd for p in points), 6),
        storage_available=storage_available,
        cache_updated_at=cache_updated_at,
        warning=warning,
    )


# --- Score de eficiência de custo por tabela (AC-FIN-RV-03 / AC-WASTE-RV-01)
#
# Fórmula PROVISÓRIA — os pesos e os fatores são um ponto de partida a
# calibrar no review (ver docs/specs/finops-budget.md Q-002). Só usa
# sinais que o próprio domínio finops já tem: nada de "drift de schema"
# (domains/quality) nem "é órfã" (domains/lineage) — domínios são
# isolados (CLAUDE.md). Quando esses sinais forem desejados, entram por
# um campo novo alimentado por um job que cruza os domínios, não por
# import cross-domain aqui.
_SCORE_WEIGHT_PARTITION = 0.45
_SCORE_WEIGHT_UTILIZATION = 0.30
_SCORE_WEIGHT_SCAN_EFFICIENCY = 0.25
# Tabela nunca escaneada em 30d perde utilização proporcionalmente ao
# tamanho: zera em >= este limite (paga storage sem retorno nenhum).
_SCORE_UNUSED_ZERO_AT_GB = 100.0
# scan_efficiency: escanear a tabela N vezes o próprio tamanho em 30d.
# Meia nota quando N == este valor.
_SCORE_SCAN_RATIO_HALF_LIFE = 10.0
# scan_efficiency é neutro (1.0) pra tabelas abaixo deste tamanho — mesma
# linha de "não vale a pena otimizar" do candidato a particionamento
# (_MIN_TABLE_SIZE_BYTES_FOR_PARTITION_CANDIDATE): re-scan de tabela
# pequena custa centavos, não é sinal de desperdício.
_SCORE_SCAN_MIN_SIZE_BYTES = _MIN_TABLE_SIZE_BYTES_FOR_PARTITION_CANDIDATE


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _table_efficiency_score(
    size_bytes: int,
    is_partitioned: bool,
    billed_bytes_30d: int,
    partition_savings_usd: float,
    observed_cost_usd_30d: float,
) -> tuple[int, list[TableScoreFactor]]:
    """Score 0..100 (maior = mais eficiente) + a decomposição em fatores
    pro drill-down. Função pura — testada direto, sem I/O."""
    size_gb = size_bytes / (1024**3)

    # 1. Particionamento: quanto do custo observado dá pra economizar
    #    particionando (só faz sentido se há economia estimada > 0).
    if is_partitioned or partition_savings_usd <= 0 or observed_cost_usd_30d <= 0:
        partition_value = 1.0
        partition_detail = (
            "Particionada" if is_partitioned else "Sem oportunidade de particionamento detectada"
        )
    else:
        partition_value = _clamp01(1 - partition_savings_usd / observed_cost_usd_30d)
        partition_detail = (
            f"Economia estimada de US$ {partition_savings_usd:.2f} sobre US$ "
            f"{observed_cost_usd_30d:.2f} de scan observado em 30d se particionada"
        )

    # 2. Utilização: escaneada ao menos uma vez em 30d? Se não, penaliza
    #    proporcional ao tamanho (storage pago sem uso).
    if billed_bytes_30d > 0:
        utilization_value = 1.0
        utilization_detail = "Consultada nos últimos 30 dias"
    else:
        utilization_value = _clamp01(1 - size_gb / _SCORE_UNUSED_ZERO_AT_GB)
        utilization_detail = f"Sem nenhuma consulta em 30d; {size_gb:.1f} GB de storage sem retorno"

    # 3. Eficiência de scan: quantas vezes o próprio tamanho foi escaneado
    #    em 30d — re-scan repetido de tabela inteira (sem pruning/cache).
    #    Tabela pequena (< 1 GB) não entra nessa conta.
    if size_bytes < _SCORE_SCAN_MIN_SIZE_BYTES or billed_bytes_30d <= 0:
        scan_value = 1.0
        scan_detail = (
            "Tabela pequena (< 1 GB) — re-scan não é material"
            if 0 < size_bytes < _SCORE_SCAN_MIN_SIZE_BYTES
            else "Sem scans onerosos em 30d"
        )
    else:
        ratio = billed_bytes_30d / size_bytes
        scan_value = _clamp01(1 / (1 + ratio / _SCORE_SCAN_RATIO_HALF_LIFE))
        scan_detail = f"Bytes escaneados em 30d = {ratio:.1f}× o tamanho da tabela"

    factors = [
        TableScoreFactor(
            name="partitioning",
            value=round(partition_value, 4),
            weight=_SCORE_WEIGHT_PARTITION,
            detail=partition_detail,
        ),
        TableScoreFactor(
            name="utilization",
            value=round(utilization_value, 4),
            weight=_SCORE_WEIGHT_UTILIZATION,
            detail=utilization_detail,
        ),
        TableScoreFactor(
            name="scan_efficiency",
            value=round(scan_value, 4),
            weight=_SCORE_WEIGHT_SCAN_EFFICIENCY,
            detail=scan_detail,
        ),
    ]
    score = round(100 * sum(f.value * f.weight for f in factors))
    return score, factors


def compute_table_scores(
    client: bigquery.Client,
    logging_client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
    datasets: list[str] | None = None,
    limit: int = 100,
) -> TableScoresResponse:
    """Score de eficiência de custo por tabela + agregado do projeto
    (AC-FIN-RV-03). Reaproveita scan_partition_candidates pro sinal de
    particionamento; todo o resto vem de metadado ($0) e do cache de
    audit log — nenhuma query BQ nova."""
    regions = discover_regions(project_id, client=client)
    all_tables = repository.list_all_table_refs(client, project_id, regions, datasets=datasets)
    table_refs = [f"{project_id}.{d}.{t}" for d, t in all_tables]
    metadata = get_tables_metadata(client, table_refs)

    events, cache_updated_at, warning = _scan_events_or_quota_warning(
        logging_client, storage_client, firestore_client, project_id
    )
    billed_bytes_by_table: dict[tuple[str, str], int] = {}
    for event in events:
        if event.timestamp is None:
            continue
        for ref in event.referenced_tables:
            if ref[0] != project_id:
                continue
            key = ref[1:]
            billed_bytes_by_table[key] = (
                billed_bytes_by_table.get(key, 0) + event.total_billed_bytes
            )

    pc_response = scan_partition_candidates(
        client, logging_client, storage_client, firestore_client, project_id, datasets=datasets
    )
    candidate_by_key = {(c.dataset_id, c.table_id): c for c in pc_response.candidates}

    scored: list[TableScore] = []
    for dataset_id, table_id in all_tables:
        bq_table = metadata.get(f"{project_id}.{dataset_id}.{table_id}")
        if bq_table is None:
            continue
        size_bytes = bq_table.num_bytes or 0
        is_partitioned = (
            bq_table.time_partitioning is not None or bq_table.range_partitioning is not None
        )
        billed_30d = billed_bytes_by_table.get((dataset_id, table_id), 0)
        cand = candidate_by_key.get((dataset_id, table_id))
        savings = (cand.estimated_savings_usd_optimistic or 0.0) if cand else 0.0
        observed_cost = cand.observed_cost_usd_30d if cand else _estimate_query_cost_usd(billed_30d)

        score, factors = _table_efficiency_score(
            size_bytes, is_partitioned, billed_30d, savings, observed_cost
        )
        scored.append(
            TableScore(
                dataset_id=dataset_id,
                table_id=table_id,
                score=score,
                size_bytes=size_bytes,
                observed_cost_usd_30d=round(observed_cost, 6),
                is_partitioned=is_partitioned,
                factors=factors,
            )
        )

    total_size = sum(t.size_bytes for t in scored)
    if scored and total_size > 0:
        project_score = round(sum(t.score * t.size_bytes for t in scored) / total_size)
    elif scored:
        project_score = round(sum(t.score for t in scored) / len(scored))
    else:
        project_score = 100

    scored.sort(key=lambda t: (t.score, -t.size_bytes))

    return TableScoresResponse(
        project_id=project_id,
        lookback_days=_PARTITION_CANDIDATE_LOOKBACK_DAYS,
        project_efficiency_score=project_score,
        tables=scored[:limit],
        cache_updated_at=cache_updated_at or pc_response.cache_updated_at,
        warning=warning or pc_response.warning,
    )


# Tabela elegível pra sugestão de tipo de coluna: (dataset_id, table_id,
# location, string_columns, bq_table). string_columns nunca vazio aqui —
# tabelas sem coluna STRING já são descartadas em _resolve_eligible_tables.
_EligibleTable = tuple[str, str, str, list[str], bigquery.Table]


def _validate_sample_percent(sample_percent: float) -> None:
    if sample_percent < 1:
        raise InvalidSamplePercentError(sample_percent)


def _parse_scoped_tables(tables: list[str]) -> list[tuple[str, str]]:
    """ "dataset_id.table_id" -> (dataset_id, table_id). partition() no
    primeiro ponto — nome de dataset/tabela do BigQuery não aceita ponto
    (só letra, número, underscore), então é seguro."""
    parsed: list[tuple[str, str]] = []
    for entry in tables:
        dataset_id, _sep, table_id = entry.partition(".")
        if dataset_id and table_id:
            parsed.append((dataset_id, table_id))
    return parsed


def _resolve_eligible_tables(
    client: bigquery.Client, project_id: str, scope: list[str] | None = None
) -> tuple[list[_EligibleTable], int]:
    """Descobre, em paralelo por tabela (INFORMATION_SCHEMA, custo $0 —
    mesmo racional de repository.list_all_table_refs), quais tabelas têm
    pelo menos uma coluna STRING e não são VIEW/MATERIALIZED VIEW.
    Retorna (elegíveis, tables_skipped_view) — usado tanto por estimate
    quanto por run, pra garantir que os dois concordam em quais tabelas
    entram na conta.

    scope=None (ou lista vazia) enumera TODAS as tabelas do projeto via
    repository.list_all_table_refs — inviável em produção (ver
    docs/specs/finops-column-types.md, "Escopo de execução"), mas
    suportado pra flexibilidade da API/testes. Com scope, pula
    list_all_table_refs inteiramente (não enumera o projeto todo só pra
    filtrar depois) e resolve region/is_view/colunas só pras tabelas
    pedidas."""
    regions = discover_regions(project_id, client=client)
    if scope:
        all_tables = _parse_scoped_tables(scope)
    else:
        all_tables = repository.list_all_table_refs(client, project_id, regions)
    table_refs = [f"{project_id}.{d}.{t}" for d, t in all_tables]
    metadata = get_tables_metadata(client, table_refs)

    dataset_regions: dict[str, str] = {}
    for dataset_id, _table_id in all_tables:
        if dataset_id not in dataset_regions:
            dataset_regions[dataset_id] = resolve_dataset_region(
                client, project_id, dataset_id, regions
            )

    def _resolve_one(item: tuple[str, str]) -> tuple[str, _EligibleTable | None, bool]:
        dataset_id, table_id = item
        bq_table = metadata.get(f"{project_id}.{dataset_id}.{table_id}")
        if bq_table is None:
            return "skip", None, False
        location = dataset_regions[dataset_id]
        if repository.is_view(client, project_id, dataset_id, table_id, location):
            return "view", None, True
        string_columns = repository.get_string_columns(
            client, project_id, dataset_id, table_id, location
        )
        if not string_columns:
            return "skip", None, False
        return "eligible", (dataset_id, table_id, location, string_columns, bq_table), False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_resolve_one, all_tables))

    eligible: list[_EligibleTable] = []
    tables_skipped_view = 0
    for status, table, is_view_row in results:
        if status == "eligible" and table is not None:
            eligible.append(table)
        elif is_view_row:
            tables_skipped_view += 1

    return eligible, tables_skipped_view


def _pick_suggestion(
    column_name: str, result_row: dict, row_count: int | None
) -> ColumnTypeSuggestion | None:
    """Primeiro tipo candidato (em sql_builder.CANDIDATE_TYPES, do mais
    estreito pro mais largo) com 100% de match no não-nulo amostrado
    vence — nunca "a maioria bate". Só vira sugestão se além disso
    houver economia de bytes real (avg_current_bytes > bytes fixos do
    tipo sugerido) — ver docs/specs/finops-column-types.md, "Critério de
    sugestão"."""
    non_null_count: int = result_row[f"{column_name}__non_null"]
    if non_null_count <= 0:
        return None

    avg_current_bytes = _STORAGE_BYTES_OVERHEAD + (result_row[f"{column_name}__avg_bytes"] or 0.0)

    matched_type: str | None = None
    for candidate_type in sql_builder.CANDIDATE_TYPES:
        if result_row[f"{column_name}__{candidate_type}"] == non_null_count:
            matched_type = candidate_type
            break
    if matched_type is None:
        return None

    suggested_bytes = sql_builder.TYPE_FIXED_BYTES[matched_type]
    if avg_current_bytes <= suggested_bytes:
        return None  # trocar não economizaria — ver "Casos de borda"

    savings_gb = (avg_current_bytes - suggested_bytes) * (row_count or 0) / (1024**3)
    savings_usd = round(savings_gb * settings.bigquery_storage_price_usd_per_gb_month_active, 6)

    return ColumnTypeSuggestion(
        column_name=column_name,
        current_type="STRING",
        suggested_type=SuggestedColumnType(matched_type),
        sample_non_null_count=non_null_count,
        avg_current_bytes=round(avg_current_bytes, 2),
        suggested_type_bytes=suggested_bytes,
        estimated_storage_savings_usd_month=savings_usd,
    )


def estimate_column_type_suggestions(
    client: bigquery.Client,
    project_id: str,
    request: ColumnTypeScanRequest,
) -> ColumnTypeEstimateResponse:
    """Dry-run gratuito (nenhuma query paga) — soma os bytes que seriam
    processados por cada query de scan elegível."""
    _validate_sample_percent(request.sample_percent)
    eligible, tables_skipped_view = _resolve_eligible_tables(client, project_id, request.tables)

    total_bytes = 0
    columns_scanned = 0
    for dataset_id, table_id, _location, string_columns, _bq_table in eligible:
        sql = sql_builder.build_scan_query(
            project_id, dataset_id, table_id, string_columns, request.sample_percent, False
        )
        assert sql is not None  # string_columns nunca vazio em _EligibleTable
        total_bytes += repository.dry_run(client, project_id, sql)
        columns_scanned += len(string_columns)

    return ColumnTypeEstimateResponse(
        project_id=project_id,
        tables_scanned=len(eligible),
        tables_skipped_view=tables_skipped_view,
        columns_scanned=columns_scanned,
        estimated_bytes=total_bytes,
        estimated_bytes_human=_human_bytes(total_bytes),
        estimated_cost_usd=_estimate_query_cost_usd(total_bytes),
    )


def run_column_type_suggestions(
    client: bigquery.Client,
    project_id: str,
    request: ColumnTypeScanRequest,
) -> ColumnTypeSuggestionsResponse:
    """Executa de fato — uma query TABLESAMPLE por tabela elegível, em
    paralelo, com orçamento total de _COLUMN_TYPE_SCAN_TIMEOUT_SECONDS
    pro lote inteiro. Se o tempo acabar no meio, retorna as tabelas já
    escaneadas com warning de resultado parcial em vez de lançar erro —
    parcial ainda tem valor aqui (lista de oportunidades), diferente de
    um scan de tabela única em pii/quality."""
    _validate_sample_percent(request.sample_percent)
    started = time.monotonic()
    eligible, tables_skipped_view = _resolve_eligible_tables(client, project_id, request.tables)

    def _scan_one(item: _EligibleTable) -> ColumnTypeCandidate | None:
        dataset_id, table_id, _location, string_columns, bq_table = item
        sql = sql_builder.build_scan_query(
            project_id, dataset_id, table_id, string_columns, request.sample_percent, False
        )
        assert sql is not None
        remaining = _COLUMN_TYPE_SCAN_TIMEOUT_SECONDS - (time.monotonic() - started)
        result_row = repository.execute_scan_query(client, project_id, sql, max(remaining, 1.0))
        suggestions = [
            suggestion
            for column_name in string_columns
            if (suggestion := _pick_suggestion(column_name, result_row, bq_table.num_rows))
            is not None
        ]
        if not suggestions:
            return None
        return ColumnTypeCandidate(
            dataset_id=dataset_id,
            table_id=table_id,
            size_bytes=bq_table.num_bytes or 0,
            row_count=bq_table.num_rows,
            suggestions=suggestions,
        )

    candidates: list[ColumnTypeCandidate] = []
    tables_scanned = 0
    partial = False

    if eligible:
        # shutdown(wait=False, cancel_futures=True) em vez do `with` padrão
        # (que bloqueia em shutdown(wait=True) até TODAS as futures
        # terminarem, mesmo as ainda não iniciadas) — sem isso o timeout do
        # as_completed() não encurta o tempo total de verdade. client é
        # module-level (@lru_cache em core/bigquery.py), sobrevive à
        # resposta, então deixar futures em voo terminando em background é
        # seguro.
        pool = ThreadPoolExecutor(max_workers=_COLUMN_TYPE_SCAN_MAX_WORKERS)
        futures = {pool.submit(_scan_one, item): item for item in eligible}
        try:
            budget = max(_COLUMN_TYPE_SCAN_TIMEOUT_SECONDS - (time.monotonic() - started), 0.0)
            for future in as_completed(futures, timeout=budget):
                result = future.result()
                tables_scanned += 1
                if result is not None:
                    candidates.append(result)
        except TimeoutError:
            partial = True
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    candidates.sort(
        key=lambda c: sum(s.estimated_storage_savings_usd_month for s in c.suggestions),
        reverse=True,
    )

    warning = None
    if partial:
        warning = _COLUMN_TYPE_PARTIAL_RESULT_WARNING.format(
            budget=int(_COLUMN_TYPE_SCAN_TIMEOUT_SECONDS),
            scanned=tables_scanned,
            total=len(eligible),
        )

    return ColumnTypeSuggestionsResponse(
        project_id=project_id,
        executed_at=datetime.now(UTC),
        sample_percent=request.sample_percent,
        tables_scanned=tables_scanned,
        tables_skipped_view=tables_skipped_view,
        candidates=candidates,
        warning=warning,
    )
