import { ChevronDown, ChevronRight, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { RefreshButton } from '@/components/RefreshButton'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useDeleteHubGroup, useHubGroups, useUpsertHubGroup } from '@/features/admin/hooks'
import { ProjectChipEditor } from '@/features/admin/ProjectChipEditor'
import { ApiError } from '@/lib/http-client'
import type { HubGroup } from '@/types/admin'

// Terceiro eixo de acesso (v1.4), ao lado de "Por usuário" e "Por
// projeto": um grupo tem membros (e-mails) e projetos liberados — cada
// membro herda o acesso do grupo, além do que já tiver individualmente.
// Diferente da aba "Por projeto" (que edita concessões pontuais), aqui a
// edição é direto nas duas listas do grupo (mesmo padrão de
// UpsertUserDialog, só que com dois ProjectChipEditor em vez de um).
export function AdminGroupsTab() {
  const groupsQuery = useHubGroups()
  const deleteMutation = useDeleteHubGroup()
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [createOpen, setCreateOpen] = useState(false)
  const [deletingGroupId, setDeletingGroupId] = useState<string | null>(null)

  function toggleExpanded(groupId: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(groupId)) {
        next.delete(groupId)
      } else {
        next.add(groupId)
      }
      return next
    })
  }

  return (
    <div className="mt-4 flex flex-col gap-4">
      <p className="text-xs text-muted-foreground">
        Cada membro de um grupo herda os projetos liberados dele, além do que já tiver
        individualmente na aba "Por usuário" — os dois eixos se somam, nenhum substitui o outro.
      </p>

      <div className="flex items-center justify-end gap-2">
        <RefreshButton
          isRefreshing={groupsQuery.isFetching}
          onRefresh={() => groupsQuery.refetch()}
        />
        <Button onClick={() => setCreateOpen(true)}>
          <Plus size={16} />
          Criar grupo
        </Button>
      </div>

      {groupsQuery.isLoading && <p className="text-sm text-muted-foreground">Carregando…</p>}
      {groupsQuery.isError && <ApiErrorNotice error={groupsQuery.error} />}

      {groupsQuery.data && (
        <div className="flex flex-col gap-1">
          {groupsQuery.data.groups.map((group) => (
            <GroupRow
              key={group.group_id}
              group={group}
              expanded={expanded.has(group.group_id)}
              onToggleExpanded={() => toggleExpanded(group.group_id)}
              onRequestDelete={() => setDeletingGroupId(group.group_id)}
            />
          ))}
          {groupsQuery.data.groups.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Nenhum grupo criado ainda — crie um acima.
            </p>
          )}
        </div>
      )}

      <CreateGroupDialog open={createOpen} onOpenChange={setCreateOpen} />

      <Dialog
        open={deletingGroupId !== null}
        onOpenChange={(open) => !open && setDeletingGroupId(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remover grupo</DialogTitle>
            <DialogDescription>
              Os membros de "{deletingGroupId}" perdem o acesso concedido por este grupo. Acesso
              individual (aba "Por usuário") não é afetado.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeletingGroupId(null)}>
              Cancelar
            </Button>
            <Button
              disabled={deleteMutation.isPending}
              onClick={() => {
                if (!deletingGroupId) return
                deleteMutation.mutate(deletingGroupId, {
                  onSuccess: () => setDeletingGroupId(null),
                })
              }}
            >
              {deleteMutation.isPending ? 'Removendo…' : 'Remover'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function CreateGroupDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [groupId, setGroupId] = useState('')
  const upsertMutation = useUpsertHubGroup()

  function handleSubmit() {
    const value = groupId.trim()
    if (!value) return
    upsertMutation.mutate(
      { groupId: value, request: { members: [], allowed_projects: [] } },
      {
        onSuccess: () => {
          setGroupId('')
          upsertMutation.reset()
          onOpenChange(false)
        },
      },
    )
  }

  const errorMessage =
    upsertMutation.error instanceof ApiError ? upsertMutation.error.message : null

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setGroupId('')
          upsertMutation.reset()
        }
        onOpenChange(next)
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Criar grupo</DialogTitle>
          <DialogDescription>
            Membros e projetos liberados são adicionados depois, expandindo o grupo na lista.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="new-group-id">Nome do grupo</Label>
          <Input
            id="new-group-id"
            value={groupId}
            onChange={(e) => setGroupId(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                handleSubmit()
              }
            }}
            placeholder="cliente-a-consultores"
          />
        </div>
        {errorMessage && <p className="text-sm text-status-error">{errorMessage}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button disabled={upsertMutation.isPending || !groupId.trim()} onClick={handleSubmit}>
            {upsertMutation.isPending ? 'Criando…' : 'Criar'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function GroupRow({
  group,
  expanded,
  onToggleExpanded,
  onRequestDelete,
}: {
  group: HubGroup
  expanded: boolean
  onToggleExpanded: () => void
  onRequestDelete: () => void
}) {
  return (
    <div className="rounded-md border border-border">
      <div className="flex items-center gap-3 px-3 py-2">
        <button
          type="button"
          onClick={onToggleExpanded}
          className="text-muted-foreground hover:text-foreground"
          aria-label={expanded ? `Recolher ${group.group_id}` : `Expandir ${group.group_id}`}
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        <span className="flex-1 text-sm font-medium">{group.group_id}</span>
        <span className="text-xs text-muted-foreground">
          {group.members.length} membro{group.members.length === 1 ? '' : 's'}
        </span>
        <Button
          size="sm"
          variant="ghost"
          aria-label={`Remover grupo ${group.group_id}`}
          onClick={onRequestDelete}
        >
          <Trash2 size={14} />
        </Button>
      </div>
      {expanded && <GroupDetail group={group} />}
    </div>
  )
}

function GroupDetail({ group }: { group: HubGroup }) {
  const upsertMutation = useUpsertHubGroup()

  const errorMessage =
    upsertMutation.error instanceof ApiError ? upsertMutation.error.message : null

  function saveMembers(members: string[]) {
    upsertMutation.mutate({
      groupId: group.group_id,
      request: { members, allowed_projects: group.allowed_projects },
    })
  }

  function saveProjects(allowedProjects: string[]) {
    upsertMutation.mutate({
      groupId: group.group_id,
      request: { members: group.members, allowed_projects: allowedProjects },
    })
  }

  return (
    <div className="flex flex-col gap-4 border-t border-border bg-muted/30 px-3 py-3">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`group-members-${group.group_id}`} className="text-xs">
          Membros
        </Label>
        <ProjectChipEditor
          inputId={`group-members-${group.group_id}`}
          chips={group.members}
          onChange={saveMembers}
          placeholder="email@dominio.com"
          emptyLabel="Nenhum membro ainda."
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`group-projects-${group.group_id}`} className="text-xs">
          Projetos liberados pro grupo
        </Label>
        <ProjectChipEditor
          inputId={`group-projects-${group.group_id}`}
          chips={group.allowed_projects}
          onChange={saveProjects}
          emptyLabel="Nenhum projeto liberado pro grupo."
        />
      </div>

      {errorMessage && <p className="text-xs text-status-error">{errorMessage}</p>}
    </div>
  )
}
