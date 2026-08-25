import { useMutation, useQuery } from '@tanstack/react-query'
import { finopsApi } from '@/lib/api/finops'
import type { BudgetGroupBy } from '@/types/finops'

// enabled: false até o usuário escolher o escopo (datasets/tabelas) no
// seletor e clicar em "Executar" — escanear o projeto inteiro sem gate
// é o que essa tela deixou de fazer.
export function usePartitionCandidates(
  projectId: string | undefined,
  options: { datasets?: string[]; tables?: string[]; enabled?: boolean } = {},
) {
  const { datasets, tables, enabled = true } = options
  return useQuery({
    queryKey: ['finops-partition-candidates', projectId, datasets, tables],
    queryFn: () => finopsApi.getPartitionCandidates(projectId as string, datasets, tables),
    enabled: Boolean(projectId) && enabled,
  })
}

export function useBudget(
  projectId: string | undefined,
  groupBy: BudgetGroupBy = 'table',
  limit = 10,
  enabled = true,
) {
  return useQuery({
    queryKey: ['finops-budget', projectId, groupBy, limit],
    queryFn: () => finopsApi.getBudget(projectId as string, groupBy, limit),
    enabled: Boolean(projectId) && enabled,
  })
}

interface ColumnTypeScanVariables {
  projectId: string
  samplePercent: number
  tables: string[]
}

export function useEstimateColumnTypeSuggestions() {
  return useMutation({
    mutationFn: ({ projectId, samplePercent, tables }: ColumnTypeScanVariables) =>
      finopsApi.estimateColumnTypeSuggestions(projectId, samplePercent, tables),
  })
}

export function useRunColumnTypeSuggestions() {
  return useMutation({
    mutationFn: ({ projectId, samplePercent, tables }: ColumnTypeScanVariables) =>
      finopsApi.runColumnTypeSuggestions(projectId, samplePercent, tables),
  })
}
