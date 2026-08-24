import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { profilingApi } from '@/lib/api/profiling'
import { qualityApi } from '@/lib/api/quality'
import type { ProfilingRequest } from '@/types/profiling'
import type {
  CreateProfilingFolderRequest,
  SaveRunToFolderRequest,
  UpdateProfilingFolderRequest,
} from '@/types/quality'

const PROFILING_FOLDERS_QUERY_KEY = ['profiling-folders']

interface ProfilingTarget {
  projectId: string
  datasetId: string
  tableId: string
}

export function useEstimateProfiling() {
  return useMutation({
    mutationFn: ({ projectId, datasetId, tableId, ...body }: ProfilingTarget & ProfilingRequest) =>
      profilingApi.estimate(projectId, datasetId, tableId, body),
  })
}

export function useRunProfiling() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ projectId, datasetId, tableId, ...body }: ProfilingTarget & ProfilingRequest) =>
      profilingApi.run(projectId, datasetId, tableId, body),
    // Cada run grava um novo ponto no histórico (backend) — invalida a
    // query da aba Histórico pra ela aparecer sem precisar fechar/reabrir
    // o dialog.
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['quality-history', variables.projectId, variables.datasetId, variables.tableId],
      })
    },
  })
}

export function useQualityHistory(
  projectId: string | undefined,
  datasetId: string | undefined,
  tableId: string | undefined,
) {
  return useQuery({
    queryKey: ['quality-history', projectId, datasetId, tableId],
    queryFn: () =>
      qualityApi.getHistory(projectId as string, datasetId as string, tableId as string),
    enabled: Boolean(projectId) && Boolean(datasetId) && Boolean(tableId),
  })
}

// --- Pastas de comparação (v1.4) -----------------------------------------------

export function useProfilingFolders() {
  return useQuery({
    queryKey: PROFILING_FOLDERS_QUERY_KEY,
    queryFn: qualityApi.listFolders,
  })
}

export function useProfilingFolder(folderId: string | undefined) {
  return useQuery({
    queryKey: ['profiling-folder', folderId],
    queryFn: () => qualityApi.getFolder(folderId as string),
    enabled: Boolean(folderId),
  })
}

export function useCreateProfilingFolder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: CreateProfilingFolderRequest) => qualityApi.createFolder(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROFILING_FOLDERS_QUERY_KEY })
    },
  })
}

export function useUpdateProfilingFolder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      folderId,
      request,
    }: {
      folderId: string
      request: UpdateProfilingFolderRequest
    }) => qualityApi.updateFolder(folderId, request),
    onSuccess: (_data, { folderId }) => {
      queryClient.invalidateQueries({ queryKey: PROFILING_FOLDERS_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: ['profiling-folder', folderId] })
    },
  })
}

export function useDeleteProfilingFolder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (folderId: string) => qualityApi.deleteFolder(folderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROFILING_FOLDERS_QUERY_KEY })
    },
  })
}

export function useSaveRunToFolder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ folderId, request }: { folderId: string; request: SaveRunToFolderRequest }) =>
      qualityApi.saveRunToFolder(folderId, request),
    onSuccess: (_data, { folderId }) => {
      queryClient.invalidateQueries({ queryKey: PROFILING_FOLDERS_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: ['profiling-folder', folderId] })
    },
  })
}

export function useDeleteFolderEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ folderId, entryId }: { folderId: string; entryId: string }) =>
      qualityApi.deleteFolderEntry(folderId, entryId),
    onSuccess: (_data, { folderId }) => {
      queryClient.invalidateQueries({ queryKey: PROFILING_FOLDERS_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: ['profiling-folder', folderId] })
    },
  })
}
