import { useQuery } from '@tanstack/react-query'
import { lineageApi } from '@/lib/api/lineage'

export function useTableLineage(
  projectId: string | undefined,
  datasetId: string | undefined,
  tableId: string | undefined,
  maxHops = 8,
) {
  return useQuery({
    queryKey: ['lineage', projectId, datasetId, tableId, maxHops],
    queryFn: () =>
      lineageApi.getLineage(projectId as string, datasetId as string, tableId as string, maxHops),
    enabled: Boolean(projectId) && Boolean(datasetId) && Boolean(tableId),
  })
}

// enabled: false até o usuário escolher o escopo (datasets) e clicar em
// "Executar" no DatasetScopeGate — escanear o projeto inteiro sem gate é
// o que essa tela deixou de fazer.
export function useOrphans(
  projectId: string | undefined,
  options: { datasets?: string[]; lookbackDays?: number; enabled?: boolean } = {},
) {
  const { datasets, lookbackDays, enabled = true } = options
  return useQuery({
    queryKey: ['orphans', projectId, datasets, lookbackDays],
    queryFn: () => lineageApi.getOrphans(projectId as string, { datasets, lookbackDays }),
    enabled: Boolean(projectId) && enabled,
  })
}
