import { useQuery } from '@tanstack/react-query'
import { projectsApi } from '@/lib/api/projects'

export function useValidateProject(projectId: string | undefined) {
  return useQuery({
    queryKey: ['project-validate', projectId],
    queryFn: () => projectsApi.validate(projectId as string),
    enabled: Boolean(projectId),
    retry: false,
  })
}

// Projetos registrados no ADM (hub_projects) aos quais o usuário atual
// tem acesso — popula o seletor de projeto em vez do usuário digitar o
// project_id de cabeça. Lista vazia é normal (nenhum projeto cadastrado
// ou nenhum liberado pra este usuário) — o campo de texto livre continua
// funcionando como fallback nesse caso.
export function useAccessibleProjects() {
  return useQuery({
    queryKey: ['accessible-projects'],
    queryFn: projectsApi.list,
    staleTime: 60_000,
  })
}
