import { X } from 'lucide-react'
import { useState } from 'react'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  useCanManageProject,
  useGrantProjectAdmin,
  useProjectAdmins,
  useRevokeProjectAdmin,
} from '@/features/metadata/hooks'

// "Gerenciar acesso" — conceder/revogar o papel Admin de projeto
// (docs/specs/admin.md v1.11). Não vive em features/admin/ (exclusivo de
// superadmin, RequireAdmin) — o propósito do papel é justamente permitir
// que alguém sem ser superadmin administre. Leitura sempre visível
// (qualquer um com acesso ao projeto vê quem o administra); concessão/
// revogação só aparecem pra quem já é Admin de projeto/superadmin.
export function ProjectAdminsPanel({ projectId }: { projectId: string }) {
  const adminsQuery = useProjectAdmins(projectId)
  const { canManage } = useCanManageProject(projectId, undefined)
  const grantMutation = useGrantProjectAdmin(projectId)
  const revokeMutation = useRevokeProjectAdmin(projectId)
  const [email, setEmail] = useState('')
  const [datasetsInput, setDatasetsInput] = useState('')

  function grant() {
    const value = email.trim()
    if (!value) return
    const datasets = datasetsInput
      .split(',')
      .map((d) => d.trim())
      .filter(Boolean)
    grantMutation.mutate(
      { email: value, request: { datasets: datasets.length > 0 ? datasets : null } },
      { onSuccess: () => setEmail('') },
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {adminsQuery.isError && <ApiErrorNotice error={adminsQuery.error} />}

      {adminsQuery.data && (
        <div className="flex flex-col gap-1.5">
          {adminsQuery.data.admins.length === 0 && (
            <p className="text-muted-foreground text-xs">
              Nenhum Admin de projeto além do(s) administrador(es) do Atlas.
            </p>
          )}
          {adminsQuery.data.admins.map((admin) => (
            <div key={admin.email} className="flex items-center gap-2 text-xs">
              <span className="flex-1">{admin.email}</span>
              <Badge variant="outline">
                {admin.datasets === null ? 'projeto inteiro' : admin.datasets.join(', ')}
              </Badge>
              {canManage && (
                <button
                  type="button"
                  onClick={() => revokeMutation.mutate(admin.email)}
                  aria-label={`Revogar acesso de ${admin.email}`}
                  className="text-muted-foreground hover:text-status-error-foreground"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {canManage && (
        <div className="flex flex-wrap items-center gap-2 border-border border-t pt-3">
          <Input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="e-mail…"
            className="h-8 w-48 text-xs"
          />
          <Input
            value={datasetsInput}
            onChange={(e) => setDatasetsInput(e.target.value)}
            placeholder="datasets (vazio = todos)"
            className="h-8 w-48 text-xs"
          />
          <Button
            size="sm"
            variant="outline"
            disabled={!email.trim() || grantMutation.isPending}
            onClick={grant}
          >
            Conceder
          </Button>
        </div>
      )}
      {grantMutation.isError && <ApiErrorNotice error={grantMutation.error} />}
    </div>
  )
}
