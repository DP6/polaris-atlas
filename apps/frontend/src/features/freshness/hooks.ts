import { useQuery } from '@tanstack/react-query'
import { freshnessApi } from '@/lib/api/freshness'

export function useProjectFreshness(projectId: string | undefined) {
  return useQuery({
    queryKey: ['freshness-project', projectId],
    queryFn: () => freshnessApi.getProjectFreshness(projectId as string),
    enabled: Boolean(projectId),
  })
}

export function useDatasetFreshness(projectId: string | undefined, datasetId: string | undefined) {
  return useQuery({
    queryKey: ['freshness-dataset', projectId, datasetId],
    queryFn: () => freshnessApi.getDatasetFreshness(projectId as string, datasetId as string),
    enabled: Boolean(projectId) && Boolean(datasetId),
  })
}

export function useTableFreshness(
  projectId: string | undefined,
  datasetId: string | undefined,
  tableId: string | undefined,
) {
  return useQuery({
    queryKey: ['freshness-table', projectId, datasetId, tableId],
    queryFn: () =>
      freshnessApi.getTableFreshness(projectId as string, datasetId as string, tableId as string),
    enabled: Boolean(projectId) && Boolean(datasetId) && Boolean(tableId),
  })
}
