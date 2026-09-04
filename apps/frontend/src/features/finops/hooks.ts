import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { finopsApi } from '@/lib/api/finops'
import type {
  BudgetGroupBy,
  BudgetScope,
  BudgetUpsertRequest,
  CostSeriesGranularity,
  CostType,
} from '@/types/finops'

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
  lookbackDays = 30,
  enabled = true,
  dateRange?: { from?: string; to?: string },
  includeStorage = false,
) {
  return useQuery({
    queryKey: [
      'finops-budget',
      projectId,
      groupBy,
      limit,
      lookbackDays,
      dateRange?.from,
      dateRange?.to,
      includeStorage,
    ],
    queryFn: () =>
      finopsApi.getBudget(
        projectId as string,
        groupBy,
        limit,
        lookbackDays,
        dateRange,
        includeStorage,
      ),
    enabled: Boolean(projectId) && enabled,
  })
}

export function useCostSeries(
  projectId: string | undefined,
  opts: {
    granularity?: CostSeriesGranularity
    costType?: CostType
    lookbackDays?: number
    from?: string
    to?: string
    datasets?: string[]
    tables?: string[]
    enabled?: boolean
  } = {},
) {
  return useQuery({
    queryKey: [
      'finops-cost-series',
      projectId,
      opts.granularity,
      opts.costType,
      opts.lookbackDays,
      opts.from,
      opts.to,
      opts.datasets,
      opts.tables,
    ],
    queryFn: () => finopsApi.getCostSeries(projectId as string, opts),
    enabled: Boolean(projectId) && (opts.enabled ?? true),
  })
}

export function useTableScores(projectId: string | undefined, datasets?: string[], limit = 100) {
  return useQuery({
    queryKey: ['finops-table-scores', projectId, datasets, limit],
    queryFn: () => finopsApi.getTableScores(projectId as string, datasets, limit),
    enabled: Boolean(projectId),
  })
}

export function useBudgets(projectId: string | undefined) {
  return useQuery({
    queryKey: ['finops-budgets', projectId],
    queryFn: () => finopsApi.listBudgets(projectId as string),
    enabled: Boolean(projectId),
  })
}

export function useUpsertBudget(projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: BudgetUpsertRequest) => finopsApi.upsertBudget(projectId as string, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['finops-budgets', projectId] })
      queryClient.invalidateQueries({ queryKey: ['finops-budget', projectId] })
    },
  })
}

export function useRemoveBudget(projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: {
      scope: BudgetScope
      datasetId?: string | null
      tableId?: string | null
    }) => finopsApi.removeBudget(projectId as string, vars.scope, vars.datasetId, vars.tableId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['finops-budgets', projectId] })
      queryClient.invalidateQueries({ queryKey: ['finops-budget', projectId] })
    },
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
