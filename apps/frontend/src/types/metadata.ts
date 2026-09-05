export type CertificationStatus = 'draft' | 'in_review' | 'approved'

export interface MetadataOwner {
  technical_owner: string | null
  steward: string | null
  team: string | null
}

export interface MetadataClassification {
  domain: string | null
  // Texto livre nesta v1 — ver docs/specs/metadata.md.
  sensitivity: string | null
}

export interface RelatedLink {
  label: string
  url: string
}

export interface ColumnPiiInfo {
  flag: boolean
  source: 'scanner' | 'manual' | null
  scanner_flagged: boolean | null
  scanner_confidence: 'high' | 'medium' | null
  confirmed_by: string | null
  confirmed_at: string | null
}

export interface MetadataColumn {
  description: string | null
  glossary_term: string | null
  pii: ColumnPiiInfo | null
}

export interface MetadataTableResponse {
  project_id: string
  dataset_id: string
  table_id: string
  description: string | null
  owner: MetadataOwner | null
  classification: MetadataClassification | null
  certification_status: CertificationStatus | null
  related_links: RelatedLink[]
  columns: Record<string, MetadataColumn>
  updated_at: string | null
  updated_by: string | null
  has_metadata: boolean
}

export interface MetadataTableUpsertRequest {
  description?: string | null
  owner?: MetadataOwner | null
  classification?: MetadataClassification | null
  certification_status?: CertificationStatus | null
  related_links?: RelatedLink[] | null
}

export interface MetadataColumnUpsertRequest {
  description?: string | null
  glossary_term?: string | null
  pii_flag?: boolean | null
}

export interface MetadataHistoryEntry {
  field: string
  old_value: string | null
  new_value: string | null
  changed_by: string
  changed_at: string
}

export interface MetadataHistoryResponse {
  entries: MetadataHistoryEntry[]
}

export interface SuggestedPiiColumn {
  column_name: string
  flagged: boolean
  confidence: 'high' | 'medium' | null
}

export interface SuggestedPiiResponse {
  project_id: string
  dataset_id: string
  table_id: string
  scanned: boolean
  columns: SuggestedPiiColumn[]
}

export interface MetadataOverviewEntry {
  dataset_id: string
  table_id: string
  has_metadata: boolean
  certification_status: CertificationStatus | null
  owner: MetadataOwner | null
  classification: MetadataClassification | null
  updated_at: string | null
}

export interface MetadataOverviewResponse {
  project_id: string
  tables: MetadataOverviewEntry[]
  total_tables: number
  documented_count: number
}

// --- Admin de projeto (docs/specs/admin.md v1.11) --------------------------------
// Tipos vivem aqui (não em types/admin.ts) porque a UI de gestão mora em
// features/metadata/ — ver docs/specs/metadata.md, "Frontend".

export interface ProjectAdmin {
  email: string
  // null = projeto inteiro (todos os datasets). Lista = só esses datasets.
  datasets: string[] | null
  granted_by: string
  granted_at: string
  updated_at: string
}

export interface ProjectAdminsListResponse {
  project_id: string
  admins: ProjectAdmin[]
}

export interface UpsertProjectAdminRequest {
  datasets: string[] | null
}
