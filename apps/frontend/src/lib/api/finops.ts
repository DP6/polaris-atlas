import { httpClient } from '@/lib/http-client'
import type {
  BudgetGroupBy,
  BudgetResponse,
  ColumnTypeEstimateResponse,
  ColumnTypeSuggestionsResponse,
  MinDaysUnused,
  PartitionCandidatesResponse,
  UnusedTablesResponse,
} from '@/types/finops'

function datasetsQueryString(datasets: string[] | undefined): string {
  const params = new URLSearchParams()
  for (const dataset of datasets ?? []) params.append('datasets', dataset)
  return params.toString()
}

export const finopsApi = {
  getUnusedTables: (projectId: string, minDaysUnused: MinDaysUnused = 30, datasets?: string[]) => {
    const params = datasetsQueryString(datasets)
    return httpClient.get<UnusedTablesResponse>(
      `/api/v1/finops/${projectId}/unused-tables?min_days_unused=${minDaysUnused}${params ? `&${params}` : ''}`,
    )
  },

  getPartitionCandidates: (projectId: string, datasets?: string[]) => {
    const params = datasetsQueryString(datasets)
    return httpClient.get<PartitionCandidatesResponse>(
      `/api/v1/finops/${projectId}/partition-candidates${params ? `?${params}` : ''}`,
    )
  },

  getBudget: (projectId: string, groupBy: BudgetGroupBy = 'table', limit = 10) =>
    httpClient.get<BudgetResponse>(
      `/api/v1/finops/${projectId}/budget?group_by=${groupBy}&limit=${limit}`,
    ),

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
