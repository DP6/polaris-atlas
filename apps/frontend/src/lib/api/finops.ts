import { httpClient } from '@/lib/http-client'
import type {
  BudgetGroupBy,
  BudgetResponse,
  ColumnTypeEstimateResponse,
  ColumnTypeSuggestionsResponse,
  PartitionCandidatesResponse,
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
