import { httpClient } from '@/lib/http-client'
import type { ProjectsListResponse, ProjectValidateResponse } from '@/types/projects'

export const projectsApi = {
  list: () => httpClient.get<ProjectsListResponse>('/api/v1/projects'),

  validate: (projectId: string) =>
    httpClient.get<ProjectValidateResponse>(`/api/v1/projects/${projectId}/validate`),
}
