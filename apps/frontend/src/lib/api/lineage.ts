import { httpClient } from '@/lib/http-client'
import type { LineageGraphResponse, OrphansResponse } from '@/types/lineage'

export const lineageApi = {
  getLineage: (projectId: string, datasetId: string, tableId: string, maxHops = 8) =>
    httpClient.get<LineageGraphResponse>(
      `/api/v1/lineage/${projectId}/${datasetId}/${tableId}?max_hops=${maxHops}`,
    ),

  getOrphans: (projectId: string, options?: { datasets?: string[]; lookbackDays?: number }) => {
    const params = new URLSearchParams()
    for (const dataset of options?.datasets ?? []) params.append('datasets', dataset)
    if (options?.lookbackDays) params.set('lookback_days', String(options.lookbackDays))
    const query = params.toString()
    return httpClient.get<OrphansResponse>(
      `/api/v1/lineage/${projectId}/orphans${query ? `?${query}` : ''}`,
    )
  },
}
