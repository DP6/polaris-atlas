import type { ProfilingRequest, QualityFlag } from '@/types/profiling'

export interface HistoryColumnSnapshot {
  column_name: string
  completeness_pct: number
  quality_flag: QualityFlag
}

export interface ProfilingHistoryRun {
  executed_at: string
  executed_by: string
  overall_density: number
  estimated_duplicate_pct: number
  columns: HistoryColumnSnapshot[]
  // null só pra runs gravados antes deste campo existir.
  parameters: ProfilingRequest | null
}

export interface ProfilingHistoryResponse {
  project_id: string
  dataset_id: string
  table_id: string
  runs: ProfilingHistoryRun[]
}

// --- Pastas de comparação (v1.4) -----------------------------------------------

export type FolderVisibility = 'private' | 'shared_all' | 'shared_emails'

export interface ProfilingFolder {
  folder_id: string
  name: string
  created_by: string
  created_at: string
  updated_at: string
  visibility: FolderVisibility
  shared_with: string[]
  entry_count: number
}

export interface ProfilingFolderEntry {
  entry_id: string
  project_id: string
  dataset_id: string
  table_id: string
  saved_at: string
  saved_by: string
  executed_at: string
  executed_by: string
  parameters: ProfilingRequest
  overall_density: number
  estimated_duplicate_pct: number
  columns: HistoryColumnSnapshot[]
}

export interface ProfilingFoldersListResponse {
  folders: ProfilingFolder[]
}

export interface ProfilingFolderDetailResponse {
  folder: ProfilingFolder
  entries: ProfilingFolderEntry[]
}

export interface CreateProfilingFolderRequest {
  name: string
}

export interface UpdateProfilingFolderRequest {
  name: string
  visibility: FolderVisibility
  shared_with: string[]
}

export interface SaveRunToFolderRequest {
  project_id: string
  dataset_id: string
  table_id: string
  executed_at: string
  executed_by: string
  parameters: ProfilingRequest
  overall_density: number
  estimated_duplicate_pct: number
  columns: HistoryColumnSnapshot[]
}
