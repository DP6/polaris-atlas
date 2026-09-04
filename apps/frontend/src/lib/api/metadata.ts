import { httpClient } from '@/lib/http-client'
import type {
  MetadataColumnUpsertRequest,
  MetadataHistoryResponse,
  MetadataOverviewResponse,
  MetadataTableResponse,
  MetadataTableUpsertRequest,
  ProjectAdmin,
  ProjectAdminsListResponse,
  SuggestedPiiResponse,
  UpsertProjectAdminRequest,
} from '@/types/metadata'

function overviewQueryString(opts: {
  certificationStatus?: string
  datasets?: string[]
  ownerEmail?: string
  q?: string
}): string {
  const params = new URLSearchParams()
  if (opts.certificationStatus) params.set('certification_status', opts.certificationStatus)
  for (const dataset of opts.datasets ?? []) params.append('datasets', dataset)
  if (opts.ownerEmail) params.set('owner_email', opts.ownerEmail)
  if (opts.q) params.set('q', opts.q)
  return params.toString()
}

export const metadataApi = {
  getOverview: (
    projectId: string,
    opts: {
      certificationStatus?: string
      datasets?: string[]
      ownerEmail?: string
      q?: string
    } = {},
  ) => {
    const qs = overviewQueryString(opts)
    return httpClient.get<MetadataOverviewResponse>(
      `/api/v1/metadata/${projectId}${qs ? `?${qs}` : ''}`,
    )
  },

  getTableMetadata: (projectId: string, datasetId: string, tableId: string) =>
    httpClient.get<MetadataTableResponse>(`/api/v1/metadata/${projectId}/${datasetId}/${tableId}`),

  upsertTableMetadata: (
    projectId: string,
    datasetId: string,
    tableId: string,
    request: MetadataTableUpsertRequest,
  ) =>
    httpClient.put<MetadataTableResponse>(
      `/api/v1/metadata/${projectId}/${datasetId}/${tableId}`,
      request,
    ),

  upsertColumnMetadata: (
    projectId: string,
    datasetId: string,
    tableId: string,
    columnName: string,
    request: MetadataColumnUpsertRequest,
  ) =>
    httpClient.put<MetadataTableResponse>(
      `/api/v1/metadata/${projectId}/${datasetId}/${tableId}/columns/${columnName}`,
      request,
    ),

  getSuggestedPii: (projectId: string, datasetId: string, tableId: string) =>
    httpClient.get<SuggestedPiiResponse>(
      `/api/v1/metadata/${projectId}/${datasetId}/${tableId}/suggested-pii`,
    ),

  getHistory: (projectId: string, datasetId: string, tableId: string) =>
    httpClient.get<MetadataHistoryResponse>(
      `/api/v1/metadata/${projectId}/${datasetId}/${tableId}/history`,
    ),

  // Admin de projeto (docs/specs/admin.md v1.11) — endpoint fica sob
  // /api/v1/projects, não /api/v1/metadata, mas o cliente mora aqui porque
  // a única UI que o consome é a de metadados.
  listProjectAdmins: (projectId: string) =>
    httpClient.get<ProjectAdminsListResponse>(`/api/v1/projects/${projectId}/admins`),

  grantProjectAdmin: (projectId: string, email: string, request: UpsertProjectAdminRequest) =>
    httpClient.put<ProjectAdmin>(`/api/v1/projects/${projectId}/admins/${email}`, request),

  revokeProjectAdmin: (projectId: string, email: string) =>
    httpClient.delete<void>(`/api/v1/projects/${projectId}/admins/${email}`),
}
