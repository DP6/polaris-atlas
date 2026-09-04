import { Cloud } from 'lucide-react'
import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Topbar } from '@/app/topbar'
import { Button } from '@/components/ui/button'
import { RequestAccessDialog } from '@/features/admin/RequestAccessDialog'
import { DatasetSidebar } from '@/features/catalog/DatasetSidebar'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { useSidebarCollapsed } from '@/hooks/useSidebarCollapsed'

// Rotas que não dependem de um projeto GCP selecionado — hoje só /admin
// (gerencia usuários/grupos/acesso, não dado de nenhum projeto). Sem essa
// checagem, RequireAdmin deixa passar mas o AppLayout barra o Outlet
// inteiro atrás do "digite um projeto", e /admin nunca abre pra quem
// ainda não validou nenhum projeto (bug real, ver CHANGELOG 2026-08-21).
function routeNeedsProject(pathname: string): boolean {
  return !pathname.startsWith('/admin')
}

export function AppLayout() {
  const { projectId } = useProjectContext()
  const location = useLocation()
  const [requestAccessOpen, setRequestAccessOpen] = useState(false)
  const { collapsed: sidebarCollapsed, toggle: toggleSidebar } = useSidebarCollapsed()
  const canRenderOutlet = Boolean(projectId) || !routeNeedsProject(location.pathname)

  return (
    <div className="flex h-screen flex-col">
      <Topbar
        onToggleSidebar={projectId ? toggleSidebar : undefined}
        sidebarCollapsed={sidebarCollapsed}
      />
      <div className="flex min-h-0 flex-1">
        {projectId && !sidebarCollapsed && <DatasetSidebar projectId={projectId} />}
        {/* pb maior que o resto: respiro no fim de toda página (ícone/card/
            texto não encostam na borda inferior ao rolar até o fim). */}
        <main className="min-w-0 flex-1 overflow-y-auto px-6 pt-6 pb-16">
          <div className="mx-auto h-full w-full max-w-[1400px]">
            {canRenderOutlet ? (
              <Outlet />
            ) : (
              <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-muted-foreground">
                <Cloud size={32} />
                <p className="text-lg">Digite um projeto GCP para começar</p>
                <p className="text-sm">
                  Não tem acesso a nenhum projeto ainda?{' '}
                  <Button
                    variant="link"
                    className="h-auto p-0"
                    onClick={() => setRequestAccessOpen(true)}
                  >
                    Solicite acesso
                  </Button>
                </p>
              </div>
            )}
          </div>
        </main>
      </div>
      <RequestAccessDialog open={requestAccessOpen} onOpenChange={setRequestAccessOpen} />
    </div>
  )
}
