import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCurrentUser } from '@/features/auth/hooks'
import { metadataApi } from '@/lib/api/metadata'
import type {
  MetadataColumnUpsertRequest,
  MetadataTableUpsertRequest,
  UpsertProjectAdminRequest,
} from '@/types/metadata'

export function useMetadataOverview(
  projectId: string | undefined,
  opts: { certificationStatus?: string; datasets?: string[]; ownerEmail?: string; q?: string } = {},
) {
  return useQuery({
    queryKey: [
      'metadata-overview',
      projectId,
      opts.certificationStatus,
      opts.datasets,
      opts.ownerEmail,
      opts.q,
    ],
    queryFn: () => metadataApi.getOverview(projectId as string, opts),
    enabled: Boolean(projectId),
  })
}

function tableMetadataQueryKey(
  projectId: string | undefined,
  datasetId: string | undefined,
  tableId: string | undefined,
) {
  return ['metadata-table', projectId, datasetId, tableId]
}

export function useTableMetadata(
  projectId: string | undefined,
  datasetId: string | undefined,
  tableId: string | undefined,
) {
  return useQuery({
    queryKey: tableMetadataQueryKey(projectId, datasetId, tableId),
    queryFn: () =>
      metadataApi.getTableMetadata(projectId as string, datasetId as string, tableId as string),
    enabled: Boolean(projectId) && Boolean(datasetId) && Boolean(tableId),
  })
}

export function useUpsertTableMetadata(
  projectId: string | undefined,
  datasetId: string | undefined,
  tableId: string | undefined,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: MetadataTableUpsertRequest) =>
      metadataApi.upsertTableMetadata(
        projectId as string,
        datasetId as string,
        tableId as string,
        request,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: tableMetadataQueryKey(projectId, datasetId, tableId),
      })
      queryClient.invalidateQueries({
        queryKey: ['metadata-history', projectId, datasetId, tableId],
      })
      queryClient.invalidateQueries({ queryKey: ['metadata-overview', projectId] })
    },
  })
}

export function useUpsertColumnMetadata(
  projectId: string | undefined,
  datasetId: string | undefined,
  tableId: string | undefined,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      columnName,
      request,
    }: {
      columnName: string
      request: MetadataColumnUpsertRequest
    }) =>
      metadataApi.upsertColumnMetadata(
        projectId as string,
        datasetId as string,
        tableId as string,
        columnName,
        request,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: tableMetadataQueryKey(projectId, datasetId, tableId),
      })
    },
  })
}

export function useSuggestedPii(
  projectId: string | undefined,
  datasetId: string | undefined,
  tableId: string | undefined,
) {
  return useQuery({
    queryKey: ['metadata-suggested-pii', projectId, datasetId, tableId],
    queryFn: () =>
      metadataApi.getSuggestedPii(projectId as string, datasetId as string, tableId as string),
    enabled: Boolean(projectId) && Boolean(datasetId) && Boolean(tableId),
  })
}

export function useMetadataHistory(
  projectId: string | undefined,
  datasetId: string | undefined,
  tableId: string | undefined,
) {
  return useQuery({
    queryKey: ['metadata-history', projectId, datasetId, tableId],
    queryFn: () =>
      metadataApi.getHistory(projectId as string, datasetId as string, tableId as string),
    enabled: Boolean(projectId) && Boolean(datasetId) && Boolean(tableId),
  })
}

// --- Admin de projeto --------------------------------------------------------------

export function useProjectAdmins(projectId: string | undefined) {
  return useQuery({
    queryKey: ['project-admins', projectId],
    queryFn: () => metadataApi.listProjectAdmins(projectId as string),
    enabled: Boolean(projectId),
  })
}

export function useGrantProjectAdmin(projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ email, request }: { email: string; request: UpsertProjectAdminRequest }) =>
      metadataApi.grantProjectAdmin(projectId as string, email, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-admins', projectId] })
    },
  })
}

export function useRevokeProjectAdmin(projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (email: string) => metadataApi.revokeProjectAdmin(projectId as string, email),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-admins', projectId] })
    },
  })
}

// Superadmin sempre pode; senão, precisa de um grant cobrindo o dataset
// (datasets=null cobre qualquer um) — mesma regra de
// core/auth.py::require_project_admin, replicada aqui só pra UX (mostrar/
// esconder controles de edição sem esperar um 403). A escrita real
// sempre é validada de novo no backend.
export function useCanManageMetadata(
  projectId: string | undefined,
  datasetId: string | undefined,
): { canManage: boolean; isLoading: boolean } {
  const userQuery = useCurrentUser()
  const adminsQuery = useProjectAdmins(projectId)

  if (userQuery.data?.is_admin) return { canManage: true, isLoading: false }

  const isLoading = userQuery.isLoading || adminsQuery.isLoading
  const email = userQuery.data?.email
  const grant = adminsQuery.data?.admins.find((a) => a.email === email)
  const canManage = Boolean(
    grant && (grant.datasets === null || (datasetId ? grant.datasets.includes(datasetId) : false)),
  )
  return { canManage, isLoading }
}
