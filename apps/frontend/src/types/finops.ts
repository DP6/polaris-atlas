export interface PartitionCandidate {
  dataset_id: string
  table_id: string
  size_bytes: number
  size_human: string
  row_count: number | null
  candidate_partition_columns: string[]
  observed_billed_bytes_30d: number
  observed_cost_usd_30d: number
  estimated_savings_usd_conservative: number | null
  estimated_savings_usd_optimistic: number | null
  savings_disclaimer: string | null
}

export interface PartitionCandidatesResponse {
  project_id: string
  lookback_days: number
  candidates: PartitionCandidate[]
  warning: string | null
}

export type BudgetGroupBy = 'table' | 'dataset' | 'user' | 'day' | 'month' | 'year'

export interface CostGroup {
  key: string
  cost_usd: number
  billed_bytes: number
  job_count: number
  // Só populados quando getBudget(includeStorage=true) e groupBy é
  // table/dataset (v1.12) — null nos demais casos.
  storage_cost_usd: number | null
  total_cost_usd: number | null
}

export interface CostlyQuery {
  job_id: string
  principal_email: string
  executed_at: string
  billed_bytes: number
  cost_usd: number
  tables: string[]
  query_text: string | null
}

export interface CostProjection {
  days_elapsed: number
  days_in_month: number
  cost_so_far_usd: number
  daily_average_usd: number
  projected_month_total_usd: number
}

export interface BudgetResponse {
  project_id: string
  period_start: string
  period_end: string
  lookback_days: number
  group_by: BudgetGroupBy
  groups: CostGroup[]
  total_cost_usd: number
  top_queries: CostlyQuery[]
  projection: CostProjection
  // Meta de custo mensal do usuário logado pra este projeto (escopo=project),
  // ou null se não cadastrada — desenha a linha de referência do gráfico.
  budget_target_usd: number | null
  cache_updated_at: string | null
  warning: string | null
}

// --- Série temporal de custo (R2-10) --------------------------------------

export type CostSeriesGranularity = 'day' | 'month'
export type CostType = 'all' | 'query' | 'storage'

export interface CostSeriesPoint {
  period: string
  query_cost_usd: number
  storage_cost_usd: number
  total_cost_usd: number
}

export interface CostSeriesResponse {
  project_id: string
  granularity: CostSeriesGranularity
  cost_type: CostType
  period_start: string
  period_end: string
  points: CostSeriesPoint[]
  // Soma de points[].total_cost_usd (v1.11) — fonte do card "Gasto no
  // período filtrado" da FinOpsOverviewPage, já respeita cost_type/janela.
  total_cost_usd: number
  storage_available: boolean
  cache_updated_at: string | null
  warning: string | null
}

// --- Score de eficiência de custo por tabela (R2-11) ---------------------

export interface TableScoreFactor {
  name: string
  value: number
  weight: number
  detail: string
}

export interface TableScore {
  dataset_id: string
  table_id: string
  score: number
  size_bytes: number
  observed_cost_usd_30d: number
  is_partitioned: boolean
  factors: TableScoreFactor[]
}

export interface TableScoresResponse {
  project_id: string
  lookback_days: number
  project_efficiency_score: number
  tables: TableScore[]
  cache_updated_at: string | null
  warning: string | null
}

// --- Cadastro de budget (R2-9) -----------------------------------------

export type BudgetScope = 'project' | 'dataset' | 'table'

export interface BudgetEntry {
  project_id: string
  scope: BudgetScope
  dataset_id: string | null
  table_id: string | null
  amount_usd: number
  period: string
  created_by: string
  created_at: string
  updated_at: string
}

export interface BudgetListResponse {
  project_id: string
  budgets: BudgetEntry[]
}

export interface BudgetUpsertRequest {
  scope: BudgetScope
  dataset_id?: string | null
  table_id?: string | null
  amount_usd: number
}

export type SuggestedColumnType = 'INT64' | 'FLOAT64' | 'BOOL' | 'DATE' | 'DATETIME' | 'TIMESTAMP'

export interface ColumnTypeEstimateResponse {
  project_id: string
  tables_scanned: number
  tables_skipped_view: number
  columns_scanned: number
  estimated_bytes: number
  estimated_bytes_human: string
  estimated_cost_usd: number
  warning: string | null
}

export interface ColumnTypeSuggestion {
  column_name: string
  current_type: string
  suggested_type: SuggestedColumnType
  sample_non_null_count: number
  avg_current_bytes: number
  suggested_type_bytes: number
  estimated_storage_savings_usd_month: number
}

export interface ColumnTypeCandidate {
  dataset_id: string
  table_id: string
  size_bytes: number
  row_count: number | null
  suggestions: ColumnTypeSuggestion[]
}

export interface ColumnTypeSuggestionsResponse {
  project_id: string
  executed_at: string
  sample_percent: number
  tables_scanned: number
  tables_skipped_view: number
  candidates: ColumnTypeCandidate[]
  warning: string | null
}
