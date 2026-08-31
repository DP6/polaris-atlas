import { useState } from 'react'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCurrentUser } from '@/features/auth/hooks'
import {
  useCreateProfilingFolder,
  useProfilingFolders,
  useSaveRunToFolder,
} from '@/features/quality/hooks'
import { ApiError } from '@/lib/http-client'
import type { ProfilingRunResponse } from '@/types/profiling'

const NEW_FOLDER_OPTION = '__new__'

interface SaveRunToFolderDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  run: ProfilingRunResponse
}

// Diálogo acionado pelo botão "Salvar em pasta" em ProfilingDialog.tsx,
// assim que um run termina — junta criar pasta (se for nova, mesmo
// padrão Select+"Outro" de AdminGroupsTab.tsx/ProjectSelector.tsx) e
// salvar o snapshot do run nela num fluxo só.
export function SaveRunToFolderDialog({ open, onOpenChange, run }: SaveRunToFolderDialogProps) {
  const [selected, setSelected] = useState('')
  const [newFolderName, setNewFolderName] = useState('')
  const userQuery = useCurrentUser()
  const foldersQuery = useProfilingFolders()
  const createFolderMutation = useCreateProfilingFolder()
  const saveRunMutation = useSaveRunToFolder()

  const isAdmin = Boolean(userQuery.data?.is_admin)
  const userEmail = userQuery.data?.email
  // Só pastas que o usuário pode gerenciar (dono ou admin) — quem só tem
  // acesso de visualização não pode adicionar entries.
  const manageableFolders = (foldersQuery.data?.folders ?? []).filter(
    (f) => isAdmin || f.created_by === userEmail,
  )

  const isPending = createFolderMutation.isPending || saveRunMutation.isPending
  const errorMessage = [createFolderMutation.error, saveRunMutation.error]
    .map((error) => (error instanceof ApiError ? error.message : null))
    .find((message) => message !== null)

  function reset() {
    setSelected('')
    setNewFolderName('')
    createFolderMutation.reset()
    saveRunMutation.reset()
  }

  function buildEntryRequest(folderId: string) {
    saveRunMutation.mutate(
      {
        folderId,
        request: {
          project_id: run.project_id,
          dataset_id: run.dataset_id,
          table_id: run.table_id,
          executed_at: run.executed_at,
          executed_by: userEmail ?? 'desconhecido',
          parameters: run.parameters,
          overall_density: run.table_summary.overall_density,
          estimated_duplicate_pct: run.table_summary.estimated_duplicate_pct,
          columns: run.columns.map((c) => ({
            column_name: c.column_name,
            completeness_pct: c.completeness_pct,
            quality_flag: c.quality_flag,
          })),
        },
      },
      {
        onSuccess: () => {
          reset()
          onOpenChange(false)
        },
      },
    )
  }

  function handleSubmit() {
    if (selected === NEW_FOLDER_OPTION) {
      const name = newFolderName.trim()
      if (!name) return
      createFolderMutation.mutate(
        { name },
        {
          onSuccess: (folder) => buildEntryRequest(folder.folder_id),
        },
      )
      return
    }
    if (!selected) return
    buildEntryRequest(selected)
  }

  const canSubmit =
    selected === NEW_FOLDER_OPTION ? newFolderName.trim().length > 0 : selected.length > 0

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
          <DialogTitle>Salvar em pasta</DialogTitle>
          <DialogDescription>
            Guarda este resultado (métricas + parâmetros usados) numa pasta pra comparar depois com
            outros runs.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="save-run-folder-select">Pasta</Label>
          <Select value={selected} onValueChange={(value) => setSelected(value ?? '')}>
            <SelectTrigger id="save-run-folder-select">
              <SelectValue placeholder="Selecione uma pasta…" />
            </SelectTrigger>
            <SelectContent>
              {manageableFolders.map((folder) => (
                <SelectItem key={folder.folder_id} value={folder.folder_id}>
                  {folder.name} ({folder.entry_count})
                </SelectItem>
              ))}
              <SelectItem value={NEW_FOLDER_OPTION}>Nova pasta</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {selected === NEW_FOLDER_OPTION && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="save-run-new-folder-name">Nome da pasta</Label>
            <Input
              id="save-run-new-folder-name"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="ex: unicidade exata e 1 ano de consulta"
            />
          </div>
        )}

        {errorMessage && <p className="text-sm text-status-error-foreground">{errorMessage}</p>}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button disabled={!canSubmit || isPending} onClick={handleSubmit}>
            {isPending ? 'Salvando…' : 'Salvar'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
