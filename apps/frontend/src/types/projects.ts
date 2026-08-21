export interface ProjectValidateResponse {
  project_id: string
  accessible: boolean
  available_regions: string[]
  total_datasets: number
  is_native: boolean
}

// Projeto GCP que a service account de runtime alcança (Cloud Resource
// Manager) — has_access é sobre o usuário ATUAL, não a SA.
export interface AccessibleProject {
  project_id: string
  display_name: string | null
  has_access: boolean
}

export interface ProjectsListResponse {
  projects: AccessibleProject[]
}

export interface ApiErrorBody {
  error: string
  message: string
  fix?: string[]
  available_date_columns?: string[]
}
