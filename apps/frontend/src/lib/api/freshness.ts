import { httpClient } from '@/lib/http-client'
import type {
  FreshnessDatasetResponse,
  FreshnessProjectResponse,
  TableFreshness,
} from '@/types/freshness'

export const freshnessApi = {
  getProjectFreshness: (projectId: string) =>
    httpClient.get<FreshnessProjectResponse>(`/api/v1/freshness/${projectId}`),

  getDatasetFreshness: (projectId: string, datasetId: string) =>
    httpClient.get<FreshnessDatasetResponse>(
      `/api/v1/freshness/${projectId}/datasets/${datasetId}`,
    ),

  // Endpoint novo (v1.1) — pré-requisito de docs/specs/metadata.md, pra
  // embutir freshness na aba de metadados sem buscar o dataset inteiro.
  getTableFreshness: (projectId: string, datasetId: string, tableId: string) =>
    httpClient.get<TableFreshness>(`/api/v1/freshness/${projectId}/${datasetId}/${tableId}`),
}
