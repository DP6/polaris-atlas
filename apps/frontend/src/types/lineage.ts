export interface TableRef {
  project_id: string
  dataset_id: string
  table_id: string
}

export type LineageNodeType = 'table' | 'bucket'

export interface LineageNode {
  id: string
  type: LineageNodeType
  // project_id/dataset_id/table_id só quando type="table"; bucket_name só
  // quando type="bucket" — extensão de 2026-08-18 (bucket como nó, ver
  // docs/specs/storage.md seção 7).
  project_id: string | null
  dataset_id: string | null
  table_id: string | null
  bucket_name: string | null
  // TABLE / VIEW / MATERIALIZED_VIEW / EXTERNAL — só nos nós de tabela do
  // projeto raiz (best-effort). null em nós cross-project / bucket.
  table_type: string | null
  hop_distance: number
  is_root: boolean
  access_denied: boolean
}

export interface LineageEdge {
  source: string
  target: string
  job_id: string
}

export interface LineageGraphResponse {
  root: TableRef
  nodes: LineageNode[]
  edges: LineageEdge[]
  lookback_days: number
  max_hops: number
  truncated: boolean
  warning: string | null
  // null = dado veio ao vivo nesta chamada (cache miss); preenchido = veio
  // do cache pré-computado (job diário ou fallback de outra requisição).
  cache_updated_at: string | null
}

export interface OrphanTable {
  dataset_id: string
  table_id: string
  size_bytes: number
  estimated_monthly_storage_cost_usd: number
}

export interface OrphansResponse {
  project_id: string
  orphans: OrphanTable[]
  lookback_days: number
  warning: string | null
  cache_updated_at: string | null
}
