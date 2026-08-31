export interface ProjectValidateResponse {
  project_id: string
  accessible: boolean
  available_regions: string[]
  total_datasets: number
  is_native: boolean
}

// Projeto registrado em hub_projects (aba Admin → Projetos) ao qual o
// usuário atual tem acesso liberado no Hub. A lista já vem filtrada por
// acesso pelo backend — todo item é acessível.
export interface AccessibleProject {
  project_id: string
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
