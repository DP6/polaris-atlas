export interface BucketSummary {
  name: string
  location: string
  storage_class: string
  total_size_bytes: number
  object_count: number
  has_lifecycle_rule: boolean
  time_created: string
  updated: string
}

export interface BucketsListResponse {
  buckets: BucketSummary[]
}

export interface StorageObjectEntry {
  name: string
  size_bytes: number
  updated: string
  storage_class: string
}

export interface BucketObjectsResponse {
  bucket_name: string
  prefix: string | null
  objects: StorageObjectEntry[]
  // "Pastas" filhas do prefixo atual (caminho completo, não só o último
  // segmento) — GCS não tem pastas reais, é delimiter="/" simulando.
  prefixes: string[]
  next_page_token: string | null
}

export type WasteConfidence = 'config_based' | 'usage_confirmed'

export interface WasteCandidate {
  bucket_name: string
  eligible_object_count: number
  eligible_size_bytes: number
  oldest_object_age_days: number
  estimated_savings_usd_month_min: number
  estimated_savings_usd_month_max: number
  usage_confirmed_object_count: number
  usage_confirmed_size_bytes: number
  confidence: WasteConfidence
}

export interface WasteCandidatesResponse {
  project_id: string
  min_days_unused: number
  candidates: WasteCandidate[]
  savings_disclaimer: string
  usage_check_warning: string | null
}
