from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class PartitionCandidate(BaseModel):
    dataset_id: str
    table_id: str
    size_bytes: int
    size_human: str
    row_count: int | None
    candidate_partition_columns: list[str]
    observed_billed_bytes_30d: int
    observed_cost_usd_30d: float
    estimated_savings_usd_conservative: float | None
    estimated_savings_usd_optimistic: float | None
    savings_disclaimer: str | None


class PartitionCandidatesResponse(BaseModel):
    project_id: str
    lookback_days: int
    candidates: list[PartitionCandidate]
    # Quando o cache de audit log lido foi gerado (job diário ou
    # write-through de outra requisição). None = dado veio ao vivo nesta
    # chamada (cache miss). Mesmo campo de LineageGraphResponse.
    cache_updated_at: datetime | None = None
    warning: str | None = None


class BudgetGroupBy(str, Enum):
    TABLE = "table"
    DATASET = "dataset"
    USER = "user"
    DAY = "day"
    MONTH = "month"
    YEAR = "year"


class CostGroup(BaseModel):
    key: str
    cost_usd: float
    billed_bytes: int
    job_count: int


class CostlyQuery(BaseModel):
    job_id: str
    principal_email: str
    executed_at: datetime
    billed_bytes: int
    cost_usd: float
    tables: list[str]
    query_text: str | None


class CostProjection(BaseModel):
    days_elapsed: int
    days_in_month: int
    cost_so_far_usd: float
    daily_average_usd: float
    projected_month_total_usd: float


class BudgetResponse(BaseModel):
    project_id: str
    period_start: datetime
    lookback_days: int
    group_by: BudgetGroupBy
    groups: list[CostGroup]
    total_cost_usd: float
    top_queries: list[CostlyQuery]
    projection: CostProjection
    # Meta de custo mensal do usuário logado pra este projeto (escopo=project),
    # lida do Firestore (domains/budget). None = nenhum budget cadastrado —
    # o gráfico do FinOps simplesmente não desenha a linha de referência.
    budget_target_usd: float | None = None
    cache_updated_at: datetime | None = None
    warning: str | None = None


class CostSeriesGranularity(str, Enum):
    DAY = "day"
    MONTH = "month"


class CostType(str, Enum):
    ALL = "all"
    QUERY = "query"
    STORAGE = "storage"


class CostSeriesPoint(BaseModel):
    # "2026-08-14" (day) ou "2026-08" (month) — ISO, ordenável como string.
    period: str
    query_cost_usd: float
    storage_cost_usd: float
    total_cost_usd: float


class CostSeriesResponse(BaseModel):
    project_id: str
    granularity: CostSeriesGranularity
    cost_type: CostType
    # Janela efetiva coberta pelos pontos (derivada do cache de audit log
    # de 31 dias + do que a timeline de storage devolveu).
    period_start: datetime
    period_end: datetime
    points: list[CostSeriesPoint]
    # False quando a INFORMATION_SCHEMA.TABLE_STORAGE_USAGE_TIMELINE_BY_PROJECT
    # não pôde ser lida (erro de permissão/schema/região) — os pontos ainda
    # trazem query_cost_usd, storage_cost_usd fica 0. Nunca vira 500.
    storage_available: bool
    cache_updated_at: datetime | None = None
    warning: str | None = None


class SuggestedColumnType(str, Enum):
    INT64 = "INT64"
    FLOAT64 = "FLOAT64"
    BOOL = "BOOL"
    DATE = "DATE"
    DATETIME = "DATETIME"
    TIMESTAMP = "TIMESTAMP"


class ColumnTypeScanRequest(BaseModel):
    sample_percent: float = 10
    # "dataset_id.table_id" — None (ou lista vazia) roda no projeto inteiro.
    # Em produção, listar toda tabela do projeto pra depois filtrar é
    # inviável (ver docs/specs/finops-column-types.md, "Escopo de
    # execução") — o frontend sempre manda um escopo explícito; None fica
    # só como capacidade da API (usado por testes e por quem chamar via
    # script).
    tables: list[str] | None = None


class ColumnTypeEstimateResponse(BaseModel):
    project_id: str
    tables_scanned: int
    tables_skipped_view: int
    columns_scanned: int
    estimated_bytes: int
    estimated_bytes_human: str
    estimated_cost_usd: float
    warning: str | None = None


class ColumnTypeSuggestion(BaseModel):
    column_name: str
    current_type: str
    suggested_type: SuggestedColumnType
    sample_non_null_count: int
    avg_current_bytes: float
    suggested_type_bytes: int
    estimated_storage_savings_usd_month: float


class ColumnTypeCandidate(BaseModel):
    dataset_id: str
    table_id: str
    size_bytes: int
    row_count: int | None
    suggestions: list[ColumnTypeSuggestion]


class ColumnTypeSuggestionsResponse(BaseModel):
    project_id: str
    executed_at: datetime
    sample_percent: float
    tables_scanned: int
    tables_skipped_view: int
    candidates: list[ColumnTypeCandidate]
    warning: str | None = None
