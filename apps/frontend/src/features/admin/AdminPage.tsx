import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AdminAccessRequestsTab } from '@/features/admin/AdminAccessRequestsTab'
import { AdminCachesTab } from '@/features/admin/AdminCachesTab'
import { AdminGroupsTab } from '@/features/admin/AdminGroupsTab'
import { AdminProjectsTab } from '@/features/admin/AdminProjectsTab'
import { AdminUsageTab } from '@/features/admin/AdminUsageTab'
import { AdminUsersTab } from '@/features/admin/AdminUsersTab'
import { usePendingAccessRequests } from '@/features/admin/hooks'

const USERS_TAB = 'users'
const PROJECTS_TAB = 'projects'
const GROUPS_TAB = 'groups'
const REQUESTS_TAB = 'requests'
const CACHES_TAB = 'caches'
const USAGE_TAB = 'usage'

export function AdminPage() {
  const pendingQuery = usePendingAccessRequests()
  const pendingCount = pendingQuery.data?.requests.length ?? 0

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: '/', label: 'Voltar' }}
        title="Administração — usuários e acesso"
        description="Controla quem é administrador do Hub e a quais projetos GCP cada usuário tem acesso. O login em si continua controlado pela allowlist do OAuth (fora daqui) — isto aqui só controla acesso a projeto dentro do Hub."
      />

      <Tabs defaultValue={USERS_TAB}>
        <TabsList className="w-fit">
          <TabsTrigger value={USERS_TAB}>Por usuário</TabsTrigger>
          <TabsTrigger value={PROJECTS_TAB}>Por projeto</TabsTrigger>
          <TabsTrigger value={GROUPS_TAB}>Grupos</TabsTrigger>
          <TabsTrigger value={REQUESTS_TAB} className="gap-1.5">
            Solicitações
            {pendingCount > 0 && (
              <Badge
                variant="outline"
                className="border-status-warn/30 bg-status-warn/10 text-status-warn-foreground"
              >
                {pendingCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value={CACHES_TAB}>Caches</TabsTrigger>
          <TabsTrigger value={USAGE_TAB}>Uso do Hub</TabsTrigger>
        </TabsList>

        <TabsContent value={USERS_TAB}>
          <AdminUsersTab />
        </TabsContent>

        <TabsContent value={PROJECTS_TAB}>
          <AdminProjectsTab />
        </TabsContent>

        <TabsContent value={GROUPS_TAB}>
          <AdminGroupsTab />
        </TabsContent>

        <TabsContent value={REQUESTS_TAB}>
          <AdminAccessRequestsTab />
        </TabsContent>

        <TabsContent value={CACHES_TAB}>
          <AdminCachesTab />
        </TabsContent>

        <TabsContent value={USAGE_TAB}>
          <AdminUsageTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
