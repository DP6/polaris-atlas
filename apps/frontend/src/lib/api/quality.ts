import { httpClient } from '@/lib/http-client'
import type {
  CreateProfilingFolderRequest,
  ProfilingFolder,
  ProfilingFolderDetailResponse,
  ProfilingFolderEntry,
  ProfilingFoldersListResponse,
  ProfilingHistoryResponse,
  SaveRunToFolderRequest,
  UpdateProfilingFolderRequest,
} from '@/types/quality'

export const qualityApi = {
  getHistory: (projectId: string, datasetId: string, tableId: string) =>
    httpClient.get<ProfilingHistoryResponse>(
      `/api/v1/quality/history/${projectId}/${datasetId}/${tableId}`,
    ),

  createFolder: (request: CreateProfilingFolderRequest) =>
    httpClient.post<ProfilingFolder>('/api/v1/quality/folders', request),

  listFolders: () => httpClient.get<ProfilingFoldersListResponse>('/api/v1/quality/folders'),

  getFolder: (folderId: string) =>
    httpClient.get<ProfilingFolderDetailResponse>(
      `/api/v1/quality/folders/${encodeURIComponent(folderId)}`,
    ),

  updateFolder: (folderId: string, request: UpdateProfilingFolderRequest) =>
    httpClient.put<ProfilingFolder>(
      `/api/v1/quality/folders/${encodeURIComponent(folderId)}`,
      request,
    ),

  deleteFolder: (folderId: string) =>
    httpClient.delete<undefined>(`/api/v1/quality/folders/${encodeURIComponent(folderId)}`),

  saveRunToFolder: (folderId: string, request: SaveRunToFolderRequest) =>
    httpClient.post<ProfilingFolderEntry>(
      `/api/v1/quality/folders/${encodeURIComponent(folderId)}/entries`,
      request,
    ),

  deleteFolderEntry: (folderId: string, entryId: string) =>
    httpClient.delete<undefined>(
      `/api/v1/quality/folders/${encodeURIComponent(folderId)}/entries/${encodeURIComponent(entryId)}`,
    ),
}
