import {
  Check,
  ChevronDown,
  ChevronRight,
  ChevronsUpDown,
  Plus,
  ShieldCheck,
  Trash2,
} from 'lucide-react'
import { useState } from 'react'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { RefreshButton } from '@/components/RefreshButton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
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
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import {
  useDeleteHubGroup,
  useHubGroups,
  useUpsertHubGroup,
  useWorkspaceGroups,
} from '@/features/admin/hooks'
import { ProjectChipEditor } from '@/features/admin/ProjectChipEditor'
import { ApiError } from '@/lib/http-client'
import { cn } from '@/lib/utils'
import type { HubGroup } from '@/types/admin'

const CUSTOM_GROUP_OPTION = '__custom__'

// Terceiro eixo de acesso (v1.4), ao lado de "Por usuário" e "Por
// projeto": um grupo tem membros e projetos liberados — cada membro
// herda o acesso do grupo, além do que já tiver individualmente. Modelo
// híbrido: membros do Workspace (workspace_members) vêm ao vivo do
// Google Workspace via domain-wide delegation, só leitura aqui; membros
// manuais (manual_members) são cadastro direto na Hub, editável — os
// dois se somam. Usar o e-mail de um grupo real do Workspace como
// group_id ativa o lado automático; um group_id qualquer funciona só
// com manual_members (workspace_members fica sempre vazio).
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
        Cada membro de um grupo (do Workspace ou cadastrado manualmente) herda os projetos liberados
        dele, além do que já tiver individualmente na aba "Por usuário" — os eixos se somam, nenhum
        substitui o outro. Use o e-mail de um grupo real do Workspace como nome pra puxar os membros
        automaticamente.
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

      <CreateGroupDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        existingGroupIds={new Set((groupsQuery.data?.groups ?? []).map((g) => g.group_id))}
      />

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
  existingGroupIds,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  existingGroupIds: Set<string>
}) {
  const [selected, setSelected] = useState('')
  const [customGroupId, setCustomGroupId] = useState('')
  const [groupPickerOpen, setGroupPickerOpen] = useState(false)
  const upsertMutation = useUpsertHubGroup()
  const workspaceGroupsQuery = useWorkspaceGroups(open)

  const availableWorkspaceGroups = (workspaceGroupsQuery.data?.groups ?? []).filter(
    (g) => !existingGroupIds.has(g.email),
  )

  const selectedWorkspaceGroup = availableWorkspaceGroups.find((g) => g.email === selected)
  const selectedLabel =
    selected === CUSTOM_GROUP_OPTION
      ? 'Nome livre (não é um grupo do Workspace)'
      : selectedWorkspaceGroup &&
        (selectedWorkspaceGroup.name
          ? `${selectedWorkspaceGroup.name} (${selectedWorkspaceGroup.email})`
          : selectedWorkspaceGroup.email)

  const groupId = selected === CUSTOM_GROUP_OPTION ? customGroupId.trim() : selected

  function reset() {
    setSelected('')
    setCustomGroupId('')
    upsertMutation.reset()
  }

  function handleSubmit() {
    if (!groupId) return
    upsertMutation.mutate(
      { groupId, request: { manual_members: [], allowed_projects: [] } },
      {
        onSuccess: () => {
          reset()
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
        if (!next) reset()
        onOpenChange(next)
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Criar grupo</DialogTitle>
          <DialogDescription>
            Escolha um grupo existente no Workspace pra puxar os membros automaticamente, ou crie um
            grupo com nome livre (só com membros manuais). Projetos liberados são adicionados
            depois, expandindo o grupo na lista.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="new-group-trigger">Grupo</Label>
          <Popover open={groupPickerOpen} onOpenChange={setGroupPickerOpen}>
            <PopoverTrigger
              render={
                <Button
                  id="new-group-trigger"
                  variant="outline"
                  role="combobox"
                  aria-expanded={groupPickerOpen}
                  className="w-full justify-between font-normal"
                />
              }
            >
              <span className={cn('truncate text-left', !selectedLabel && 'text-muted-foreground')}>
                {selectedLabel || 'Selecione um grupo do Workspace…'}
              </span>
              <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
            </PopoverTrigger>
            <PopoverContent className="w-(--anchor-width) p-0" align="start">
              <Command>
                <CommandInput placeholder="Buscar por trecho do nome ou e-mail…" />
                <CommandList>
                  {workspaceGroupsQuery.isLoading && (
                    <div className="px-2 py-1.5 text-sm text-muted-foreground">Carregando…</div>
                  )}
                  {workspaceGroupsQuery.isError && (
                    <div className="px-2 py-1.5 text-sm text-muted-foreground">
                      Não foi possível listar os grupos do Workspace.
                    </div>
                  )}
                  <CommandEmpty>Nenhum grupo encontrado.</CommandEmpty>
                  <CommandGroup>
                    {availableWorkspaceGroups.map((g) => (
                      <CommandItem
                        key={g.email}
                        value={`${g.name ?? ''} ${g.email}`}
                        onSelect={() => {
                          setSelected(g.email)
                          setGroupPickerOpen(false)
                        }}
                      >
                        <Check
                          className={cn(
                            'size-4 shrink-0',
                            selected === g.email ? 'opacity-100' : 'opacity-0',
                          )}
                        />
                        <span className="flex-1 break-words whitespace-normal">
                          {g.name ? `${g.name} (${g.email})` : g.email}
                        </span>
                      </CommandItem>
                    ))}
                    <CommandItem
                      value={CUSTOM_GROUP_OPTION}
                      onSelect={() => {
                        setSelected(CUSTOM_GROUP_OPTION)
                        setGroupPickerOpen(false)
                      }}
                    >
                      <Check
                        className={cn(
                          'size-4 shrink-0',
                          selected === CUSTOM_GROUP_OPTION ? 'opacity-100' : 'opacity-0',
                        )}
                      />
                      Nome livre (não é um grupo do Workspace)
                    </CommandItem>
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
        </div>
        {selected === CUSTOM_GROUP_OPTION && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="new-group-id">Nome do grupo</Label>
            <Input
              id="new-group-id"
              value={customGroupId}
              onChange={(e) => setCustomGroupId(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  handleSubmit()
                }
              }}
              placeholder="ex: consultores-cliente-a"
            />
          </div>
        )}
        {errorMessage && <p className="text-sm text-status-error">{errorMessage}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button disabled={upsertMutation.isPending || !groupId} onClick={handleSubmit}>
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
  const effectiveCount = new Set([...group.workspace_members, ...group.manual_members]).size

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
          {effectiveCount} membro{effectiveCount === 1 ? '' : 's'}
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

  function saveManualMembers(manualMembers: string[]) {
    upsertMutation.mutate({
      groupId: group.group_id,
      request: { manual_members: manualMembers, allowed_projects: group.allowed_projects },
    })
  }

  function saveProjects(allowedProjects: string[]) {
    upsertMutation.mutate({
      groupId: group.group_id,
      request: { manual_members: group.manual_members, allowed_projects: allowedProjects },
    })
  }

  return (
    <div className="flex flex-col gap-4 border-t border-border bg-muted/30 px-3 py-3">
      <div className="flex flex-col gap-1.5">
        <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <ShieldCheck size={12} />
          Membros do Workspace (via delegação — só leitura)
        </span>
        <div className="flex flex-wrap gap-1">
          {group.workspace_members.length === 0 && (
            <span className="text-xs text-muted-foreground">
              Nenhum — ou a integração com o Workspace ainda não foi configurada.
            </span>
          )}
          {group.workspace_members.map((email) => (
            <Badge key={email} variant="outline">
              {email}
            </Badge>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`group-manual-members-${group.group_id}`} className="text-xs">
          Membros adicionados manualmente
        </Label>
        <ProjectChipEditor
          inputId={`group-manual-members-${group.group_id}`}
          chips={group.manual_members}
          onChange={saveManualMembers}
          placeholder="email@dominio.com"
          emptyLabel="Nenhum membro manual — só os do Workspace acima (se houver)."
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
