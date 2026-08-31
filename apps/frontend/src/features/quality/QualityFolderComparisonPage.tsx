import { Globe, Lock, Mail, Pencil, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from 'recharts'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { RefreshButton } from '@/components/RefreshButton'
import { SectionHeading } from '@/components/SectionHeading'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ProjectChipEditor } from '@/features/admin/ProjectChipEditor'
import { useCurrentUser } from '@/features/auth/hooks'
import {
  useDeleteFolderEntry,
  useDeleteProfilingFolder,
  useProfilingFolder,
  useUpdateProfilingFolder,
} from '@/features/quality/hooks'
import { formatDate, formatPercent } from '@/lib/format'
import { ApiError } from '@/lib/http-client'
import type { UniquenessMethod } from '@/types/profiling'
import type { FolderVisibility, ProfilingFolderEntry } from '@/types/quality'

// Mesmos rótulos de HistoryTab.tsx/ProfilingDialog.tsx — duplicado de
// propósito, ver comentário lá (não vale a pena extrair pra 2 linhas).
const UNIQUENESS_METHOD_LABELS: Record<UniquenessMethod, string> = {
  approx: 'Aproximado (HLL)',
  exact: 'Exato',
}

const VISIBILITY_BADGE: Record<
  FolderVisibility,
  { label: string; icon: typeof Lock; variant: 'outline' | 'secondary' }
> = {
  private: { label: 'Privada', icon: Lock, variant: 'outline' },
  shared_all: { label: 'Todos', icon: Globe, variant: 'secondary' },
  shared_emails: { label: 'E-mails específicos', icon: Mail, variant: 'secondary' },
}

const VISIBILITY_OPTIONS: { value: FolderVisibility; label: string }[] = [
  { value: 'private', label: 'Privada (só você e admins)' },
  { value: 'shared_all', label: 'Todos os usuários do Hub' },
  { value: 'shared_emails', label: 'Lista de e-mails específica' },
]

// Diferença de completude entre entries da mesma tabela acima disso é
// destacada na tabela de diff — mesmo limiar (pontos percentuais) do
// alerta de degradação em HistoryTab.tsx, por consistência.
const DIFF_HIGHLIGHT_THRESHOLD_PP = 10

// Cores cicladas por índice do entry no gráfico de barras — mesmos
// accent tokens de docs/frontend/design-system.md, sem limite de entries por
// pasta (acima de 5 entries repete a cor, aceitável pra esse volume).
const ENTRY_BAR_COLORS = [
  'var(--color-primary)',
  'var(--color-accent-blue)',
  'var(--color-accent-purple)',
  'var(--color-accent-green)',
  'var(--color-accent-orange)',
]

function tableKey(entry: ProfilingFolderEntry): string {
  return `${entry.project_id}.${entry.dataset_id}.${entry.table_id}`
}

function formatEntryParameters(parameters: ProfilingFolderEntry['parameters']): string {
  const parts = [
    `Amostragem: ${parameters.sample_percent}%`,
    `Unicidade: ${UNIQUENESS_METHOD_LABELS[parameters.uniqueness_method]}`,
    parameters.date_column
      ? `Data: ${parameters.date_column} (últimos ${parameters.date_window_days} dias)`
      : 'Sem filtro de data',
  ]
  return parts.join(' · ')
}

export function QualityFolderComparisonPage() {
  const { folderId } = useParams<{ folderId: string }>()
  const navigate = useNavigate()
  const userQuery = useCurrentUser()
  const folderQuery = useProfilingFolder(folderId)
  const deleteFolderMutation = useDeleteProfilingFolder()
  const [editOpen, setEditOpen] = useState(false)
  const [deletingFolder, setDeletingFolder] = useState(false)
  const [deletingEntryId, setDeletingEntryId] = useState<string | null>(null)
  const deleteEntryMutation = useDeleteFolderEntry()

  if (folderQuery.isLoading) {
    return <LoadingState />
  }

  if (folderQuery.isError) {
    return <ApiErrorNotice error={folderQuery.error} />
  }

  if (!folderQuery.data || !folderId) return null

  const { folder, entries } = folderQuery.data
  const isAdmin = Boolean(userQuery.data?.is_admin)
  const userEmail = userQuery.data?.email
  const canManage = isAdmin || folder.created_by === userEmail
  const visibility = VISIBILITY_BADGE[folder.visibility]
  const VisibilityIcon = visibility.icon

  const groups = new Map<string, ProfilingFolderEntry[]>()
  for (const entry of entries) {
    const key = tableKey(entry)
    const group = groups.get(key)
    if (group) {
      group.push(entry)
    } else {
      groups.set(key, [entry])
    }
  }
  const comparableGroups = [...groups.entries()].filter(([, group]) => group.length >= 2)

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={folder.name}
        description={
          <span className="inline-flex flex-wrap items-center gap-2 text-xs">
            <span>Criada por {folder.created_by}</span>
            <Badge variant={visibility.variant} className="gap-1">
              <VisibilityIcon size={10} />
              {visibility.label}
            </Badge>
            <span>
              {entries.length} {entries.length === 1 ? 'entrada' : 'entradas'}
            </span>
          </span>
        }
        actions={
          <>
            <RefreshButton
              isRefreshing={folderQuery.isFetching}
              onRefresh={() => folderQuery.refetch()}
            />
            {canManage && (
              <>
                <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
                  <Pencil size={14} />
                  Editar
                </Button>
                <Button variant="outline" size="sm" onClick={() => setDeletingFolder(true)}>
                  <Trash2 size={14} />
                  Apagar pasta
                </Button>
              </>
            )}
          </>
        }
      />

      {entries.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Nenhuma entrada salva ainda nesta pasta. Salve um resultado de profiling nela pelo botão
          "Salvar em pasta" na tela de análise de qualidade.
        </p>
      )}

      {entries.length > 0 && (
        <div className="flex flex-col gap-2">
          <SectionHeading as="h3">Entradas salvas</SectionHeading>
          <div className="flex flex-col gap-2">
            {entries.map((entry) => (
              <div
                key={entry.entry_id}
                className="flex flex-col gap-1.5 rounded-md border border-border p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium text-sm">
                      {entry.project_id}.{entry.dataset_id}.{entry.table_id}
                    </span>
                    <span className="text-muted-foreground text-xs">
                      Executado em {formatDate(entry.executed_at)} por {entry.executed_by} · Salvo
                      em {formatDate(entry.saved_at)} por {entry.saved_by}
                    </span>
                  </div>
                  <div className="flex shrink-0 items-center gap-3 text-xs">
                    <span>Densidade: {formatPercent(entry.overall_density)}</span>
                    <span>Duplicatas: {formatPercent(entry.estimated_duplicate_pct)}</span>
                    {canManage && (
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        aria-label={`Remover entrada de ${entry.saved_at}`}
                        onClick={() => setDeletingEntryId(entry.entry_id)}
                      >
                        <Trash2 size={14} />
                      </Button>
                    )}
                  </div>
                </div>
                <p className="text-muted-foreground text-xs">
                  {formatEntryParameters(entry.parameters)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {comparableGroups.length > 0 && (
        <div className="flex flex-col gap-4">
          <SectionHeading as="h3">Comparação coluna a coluna</SectionHeading>
          {comparableGroups.map(([key, group]) => (
            <ColumnDiffTable key={key} tableName={key} entries={group} />
          ))}
        </div>
      )}

      {canManage && (
        <EditFolderDialog
          open={editOpen}
          onOpenChange={setEditOpen}
          folderId={folderId}
          name={folder.name}
          visibility={folder.visibility}
          sharedWith={folder.shared_with}
        />
      )}

      <Dialog open={deletingFolder} onOpenChange={setDeletingFolder}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Apagar pasta</DialogTitle>
            <DialogDescription>
              Remove "{folder.name}" e todas as {entries.length}{' '}
              {entries.length === 1 ? 'entrada salva' : 'entradas salvas'} nela. Os runs originais
              no histórico de profiling não são afetados.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeletingFolder(false)}>
              Cancelar
            </Button>
            <Button
              disabled={deleteFolderMutation.isPending}
              onClick={() =>
                deleteFolderMutation.mutate(folderId, {
                  onSuccess: () => navigate('/quality/folders'),
                })
              }
            >
              {deleteFolderMutation.isPending ? 'Apagando…' : 'Apagar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={deletingEntryId !== null}
        onOpenChange={(open) => !open && setDeletingEntryId(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remover entrada</DialogTitle>
            <DialogDescription>
              Remove este resultado salvo da pasta. O run original no histórico de profiling não é
              afetado.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeletingEntryId(null)}>
              Cancelar
            </Button>
            <Button
              disabled={deleteEntryMutation.isPending}
              onClick={() => {
                if (!deletingEntryId) return
                deleteEntryMutation.mutate(
                  { folderId, entryId: deletingEntryId },
                  { onSuccess: () => setDeletingEntryId(null) },
                )
              }}
            >
              {deleteEntryMutation.isPending ? 'Removendo…' : 'Remover'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function entryLabel(entry: ProfilingFolderEntry): string {
  const date = new Date(entry.saved_at)
  const short = Number.isNaN(date.getTime())
    ? entry.saved_at
    : new Intl.DateTimeFormat('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      }).format(date)
  return short
}

function ColumnDiffTable({
  tableName,
  entries,
}: {
  tableName: string
  entries: ProfilingFolderEntry[]
}) {
  const columnNames = [
    ...new Set(entries.flatMap((e) => e.columns.map((c) => c.column_name))),
  ].sort()

  const barData = columnNames.map((columnName) => {
    const row: Record<string, string | number | null> = { column: columnName }
    for (const entry of entries) {
      row[entry.entry_id] =
        entry.columns.find((c) => c.column_name === columnName)?.completeness_pct ?? null
    }
    return row
  })

  return (
    <div className="flex flex-col gap-2">
      <span className="text-muted-foreground text-xs">{tableName}</span>

      <div className="h-56 w-full shrink-0 rounded-lg border border-border bg-card p-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={barData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis
              dataKey="column"
              tick={{ fontSize: 10 }}
              interval={0}
              angle={-30}
              textAnchor="end"
            />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} width={36} />
            <RechartsTooltip
              formatter={(value) => (value === null ? '—' : `${Number(value).toFixed(1)}%`)}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {entries.map((entry, index) => (
              <Bar
                key={entry.entry_id}
                dataKey={entry.entry_id}
                name={entryLabel(entry)}
                fill={ENTRY_BAR_COLORS[index % ENTRY_BAR_COLORS.length]}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Coluna</TableHead>
            {entries.map((entry) => (
              <TableHead key={entry.entry_id} className="text-right">
                {entryLabel(entry)}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow className="bg-muted/30">
            <TableCell className="text-xs font-medium">Parâmetros</TableCell>
            {entries.map((entry) => (
              <TableCell
                key={entry.entry_id}
                className="text-right text-[11px] text-muted-foreground"
              >
                {formatEntryParameters(entry.parameters)}
              </TableCell>
            ))}
          </TableRow>
          <TableRow>
            <TableCell className="text-xs font-medium">Densidade geral</TableCell>
            {entries.map((entry) => (
              <TableCell key={entry.entry_id} className="text-right text-xs">
                {formatPercent(entry.overall_density)}
              </TableCell>
            ))}
          </TableRow>
          {columnNames.map((columnName) => {
            const values = entries.map(
              (entry) =>
                entry.columns.find((c) => c.column_name === columnName)?.completeness_pct ?? null,
            )
            const present = values.filter((v): v is number => v !== null)
            const diff = present.length > 1 ? Math.max(...present) - Math.min(...present) : 0
            const highlight = diff > DIFF_HIGHLIGHT_THRESHOLD_PP

            return (
              <TableRow key={columnName}>
                <TableCell className="text-xs font-medium">{columnName}</TableCell>
                {values.map((value, index) => (
                  <TableCell
                    key={entries[index].entry_id}
                    className={
                      highlight
                        ? 'text-right text-xs font-medium text-status-error-foreground'
                        : 'text-right text-xs'
                    }
                  >
                    {value === null ? '—' : formatPercent(value)}
                  </TableCell>
                ))}
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

function EditFolderDialog({
  open,
  onOpenChange,
  folderId,
  name: initialName,
  visibility: initialVisibility,
  sharedWith: initialSharedWith,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  folderId: string
  name: string
  visibility: FolderVisibility
  sharedWith: string[]
}) {
  const [name, setName] = useState(initialName)
  const [visibility, setVisibility] = useState<FolderVisibility>(initialVisibility)
  const [sharedWith, setSharedWith] = useState<string[]>(initialSharedWith)
  const updateMutation = useUpdateProfilingFolder()

  function reset() {
    setName(initialName)
    setVisibility(initialVisibility)
    setSharedWith(initialSharedWith)
    updateMutation.reset()
  }

  function handleSubmit() {
    const trimmed = name.trim()
    if (!trimmed) return
    updateMutation.mutate(
      {
        folderId,
        request: {
          name: trimmed,
          visibility,
          shared_with: visibility === 'shared_emails' ? sharedWith : [],
        },
      },
      { onSuccess: () => onOpenChange(false) },
    )
  }

  const errorMessage =
    updateMutation.error instanceof ApiError ? updateMutation.error.message : null

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
          <DialogTitle>Editar pasta</DialogTitle>
          <DialogDescription>
            Compartilhamento controla quem além de você (e admins) pode ver e comparar esta pasta —
            só quem gerencia (você ou um admin) pode editar ou salvar novas entradas.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="edit-folder-name">Nome</Label>
          <Input id="edit-folder-name" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="edit-folder-visibility">Compartilhamento</Label>
          <Select
            value={visibility}
            onValueChange={(value) => value && setVisibility(value as FolderVisibility)}
          >
            <SelectTrigger id="edit-folder-visibility">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {VISIBILITY_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {visibility === 'shared_emails' && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit-folder-shared-with">E-mails com acesso</Label>
            <ProjectChipEditor
              inputId="edit-folder-shared-with"
              chips={sharedWith}
              onChange={setSharedWith}
              placeholder="email@dominio.com"
              emptyLabel="Nenhum e-mail adicionado ainda."
            />
          </div>
        )}
        {errorMessage && <p className="text-sm text-status-error-foreground">{errorMessage}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button disabled={updateMutation.isPending || !name.trim()} onClick={handleSubmit}>
            {updateMutation.isPending ? 'Salvando…' : 'Salvar'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
