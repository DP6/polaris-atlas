import { httpClient } from '@/lib/http-client'
import type {
  BudgetEntry,
  BudgetGroupBy,
  BudgetListResponse,
  BudgetResponse,
  BudgetScope,
  BudgetUpsertRequest,
  ColumnTypeEstimateResponse,
  ColumnTypeSuggestionsResponse,
  CostSeriesGranularity,
  CostSeriesResponse,
  CostType,
  PartitionCandidatesResponse,
  TableScoresResponse,
} from '@/types/finops'

function scopeQueryString(datasets: string[] | undefined, tables: string[] | undefined): string {
  const params = new URLSearchParams()
  for (const dataset of datasets ?? []) params.append('datasets', dataset)
  for (const table of tables ?? []) params.append('tables', table)
  return params.toString()
}

export const finopsApi = {
  getPartitionCandidates: (projectId: string, datasets?: string[], tables?: string[]) => {
    const params = scopeQueryString(datasets, tables)
    return httpClient.get<PartitionCandidatesResponse>(
      `/api/v1/finops/${projectId}/partition-candidates${params ? `?${params}` : ''}`,
    )
  },

  getBudget: (projectId: string, groupBy: BudgetGroupBy = 'table', limit = 10, lookbackDays = 30) =>
    httpClient.get<BudgetResponse>(
      `/api/v1/finops/${projectId}/budget?group_by=${groupBy}&limit=${limit}&lookback_days=${lookbackDays}`,
    ),

  getCostSeries: (
    projectId: string,
    opts: {
      granularity?: CostSeriesGranularity
      costType?: CostType
      lookbackDays?: number
      datasets?: string[]
      tables?: string[]
    } = {},
  ) => {
    const params = new URLSearchParams()
    if (opts.granularity) params.set('granularity', opts.granularity)
    if (opts.costType) params.set('cost_type', opts.costType)
    if (opts.lookbackDays) params.set('lookback_days', String(opts.lookbackDays))
    for (const d of opts.datasets ?? []) params.append('datasets', d)
    for (const t of opts.tables ?? []) params.append('tables', t)
    const qs = params.toString()
    return httpClient.get<CostSeriesResponse>(
      `/api/v1/finops/${projectId}/cost-series${qs ? `?${qs}` : ''}`,
    )
  },

  getTableScores: (projectId: string, datasets?: string[], limit = 100) => {
    const params = new URLSearchParams()
    for (const d of datasets ?? []) params.append('datasets', d)
    params.set('limit', String(limit))
    return httpClient.get<TableScoresResponse>(
      `/api/v1/finops/${projectId}/table-scores?${params.toString()}`,
    )
  },

  listBudgets: (projectId: string) =>
    httpClient.get<BudgetListResponse>(`/api/v1/finops/${projectId}/budgets`),

  upsertBudget: (projectId: string, body: BudgetUpsertRequest) =>
    httpClient.put<BudgetEntry>(`/api/v1/finops/${projectId}/budgets`, body),

  removeBudget: (
    projectId: string,
    scope: BudgetScope,
    datasetId?: string | null,
    tableId?: string | null,
  ) => {
    const params = new URLSearchParams({ scope })
    if (datasetId) params.set('dataset_id', datasetId)
    if (tableId) params.set('table_id', tableId)
    return httpClient.delete<void>(`/api/v1/finops/${projectId}/budgets?${params.toString()}`)
  },

  estimateColumnTypeSuggestions: (projectId: string, samplePercent: number, tables: string[]) =>
    httpClient.post<ColumnTypeEstimateResponse>(
      `/api/v1/finops/${projectId}/column-type-suggestions/estimate`,
      { sample_percent: samplePercent, tables },
    ),

  runColumnTypeSuggestions: (projectId: string, samplePercent: number, tables: string[]) =>
    httpClient.post<ColumnTypeSuggestionsResponse>(
      `/api/v1/finops/${projectId}/column-type-suggestions/run`,
      { sample_percent: samplePercent, tables },
    ),
}
