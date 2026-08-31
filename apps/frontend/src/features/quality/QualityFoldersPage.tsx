import { FolderPlus, Globe, Lock, Mail } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { RefreshButton } from '@/components/RefreshButton'
import { Badge } from '@/components/ui/badge'
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
import { useCurrentUser } from '@/features/auth/hooks'
import { useCreateProfilingFolder, useProfilingFolders } from '@/features/quality/hooks'
import { ApiError } from '@/lib/http-client'
import type { FolderVisibility, ProfilingFolder } from '@/types/quality'

const VISIBILITY_BADGE: Record<
  FolderVisibility,
  { label: string; icon: typeof Lock; variant: 'outline' | 'secondary' }
> = {
  private: { label: 'Privada', icon: Lock, variant: 'outline' },
  shared_all: { label: 'Todos', icon: Globe, variant: 'secondary' },
  shared_emails: { label: 'E-mails específicos', icon: Mail, variant: 'secondary' },
}

// Lista as pastas de comparação de profiling que o usuário pode ver
// (dono, admin, ou compartilhada com ele — filtro de visibilidade já
// aplicado pelo backend em list_folders_for_user). Ponto de entrada da
// nova subseção "Profiling" da sidebar.
export function QualityFoldersPage() {
  const foldersQuery = useProfilingFolders()
  const userQuery = useCurrentUser()
  const [createOpen, setCreateOpen] = useState(false)
  const isAdmin = Boolean(userQuery.data?.is_admin)
  const userEmail = userQuery.data?.email

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Pastas de profiling"
        description="Recortes salvos de runs de profiling pra comparar depois — ex: diferentes métodos de unicidade ou janelas de data pra uma mesma tabela."
        actions={
          <>
            <RefreshButton
              isRefreshing={foldersQuery.isFetching}
              onRefresh={() => foldersQuery.refetch()}
            />
            <Button onClick={() => setCreateOpen(true)}>
              <FolderPlus size={16} />
              Nova pasta
            </Button>
          </>
        }
      />

      {foldersQuery.isLoading && <LoadingState />}
      {foldersQuery.isError && <ApiErrorNotice error={foldersQuery.error} />}

      {foldersQuery.data && (
        <div className="flex flex-col gap-2">
          {foldersQuery.data.folders.map((folder) => (
            <FolderRow
              key={folder.folder_id}
              folder={folder}
              userEmail={userEmail}
              isAdmin={isAdmin}
            />
          ))}
          {foldersQuery.data.folders.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Nenhuma pasta visível ainda. Crie uma acima, ou salve o resultado de um profiling numa
              pasta pelo botão "Salvar em pasta" na tela de análise de qualidade.
            </p>
          )}
        </div>
      )}

      <CreateFolderDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  )
}

function FolderRow({
  folder,
  userEmail,
  isAdmin,
}: {
  folder: ProfilingFolder
  userEmail: string | undefined
  isAdmin: boolean
}) {
  const visibility = VISIBILITY_BADGE[folder.visibility]
  const VisibilityIcon = visibility.icon
  const canManage = isAdmin || folder.created_by === userEmail

  return (
    <Link
      to={`/quality/folders/${encodeURIComponent(folder.folder_id)}`}
      className="flex items-center gap-3 rounded-md border border-border px-3 py-2.5 transition-colors hover:bg-muted"
    >
      <span className="flex-1 truncate font-medium text-sm">{folder.name}</span>
      <span className="text-muted-foreground text-xs">
        {folder.entry_count} {folder.entry_count === 1 ? 'entrada' : 'entradas'}
      </span>
      <Badge variant={visibility.variant} className="gap-1">
        <VisibilityIcon size={10} />
        {visibility.label}
      </Badge>
      {canManage && (
        <Badge variant="outline" className="text-[10px]">
          {folder.created_by === userEmail ? 'Sua pasta' : 'Gerenciável (admin)'}
        </Badge>
      )}
    </Link>
  )
}

function CreateFolderDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [name, setName] = useState('')
  const createMutation = useCreateProfilingFolder()

  function reset() {
    setName('')
    createMutation.reset()
  }

  function handleSubmit() {
    const trimmed = name.trim()
    if (!trimmed) return
    createMutation.mutate(
      { name: trimmed },
      {
        onSuccess: () => {
          reset()
          onOpenChange(false)
        },
      },
    )
  }

  const errorMessage =
    createMutation.error instanceof ApiError ? createMutation.error.message : null

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
          <DialogTitle>Nova pasta de profiling</DialogTitle>
          <DialogDescription>
            Começa privada, só você (e admins) vê. Dá pra mudar o compartilhamento depois, na tela
            da pasta.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="new-folder-name">Nome</Label>
          <Input
            id="new-folder-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                handleSubmit()
              }
            }}
            placeholder="ex: unicidade exata e 1 ano de consulta"
          />
        </div>
        {errorMessage && <p className="text-sm text-status-error-foreground">{errorMessage}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button disabled={createMutation.isPending || !name.trim()} onClick={handleSubmit}>
            {createMutation.isPending ? 'Criando…' : 'Criar'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
