import { Search } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
import {
  useCanManageProject,
  useMetadataOverview,
  useUpdateMetadataStatus,
} from '@/features/metadata/hooks'
import { ProjectAdminsPanel } from '@/features/metadata/ProjectAdminsPanel'
import { useProjectContext } from '@/features/projects/ProjectContext'
import type { GovernanceStatus, MetadataOverviewEntry } from '@/types/metadata'

const STATUS_LABEL: Record<GovernanceStatus, string> = {
  draft: 'Rascunho',
  in_review: 'Em revisão',
  approved: 'Aprovado',
}

const STATUS_COLOR: Record<GovernanceStatus, string> = {
  draft: 'var(--color-muted-foreground)',
  in_review: 'var(--color-status-warn)',
  approved: 'var(--color-status-ok)',
}

function StatusBadge({ status }: { status: GovernanceStatus | null }) {
  if (!status) {
    return (
      <Badge variant="outline" className="text-muted-foreground">
        Não documentada
      </Badge>
    )
  }
  return (
    <Badge
      variant="outline"
      style={{ borderColor: STATUS_COLOR[status], color: STATUS_COLOR[status] }}
    >
      {STATUS_LABEL[status]}
    </Badge>
  )
}

// Visão geral de metadados do projeto — 3º item da seção Governança
// (junto de Freshness e Tabelas sem consumidor). Lista todas as tabelas
// do projeto (via catalog, $0), com estado de governança/dono/tags de
// quem já tem metadado cadastrado — tabela sem metadado aparece como
// "Não documentada", nunca é escondida (ver docs/specs/metadata.md,
// AC-META-007). É também onde se gerencia quem administra o projeto.
export function MetadataOverviewPage() {
  const { projectId } = useProjectContext()
  const [status, setStatus] = useState<string>('all')
  const [q, setQ] = useState('')

  const overviewQuery = useMetadataOverview(projectId, {
    status: status === 'all' ? undefined : status,
    q: q || undefined,
  })

  const pending = (overviewQuery.data?.tables ?? []).filter((t) => t.status === 'in_review')

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Metadados"
        description="Descrição, ownership, classificação e estado de governança por tabela — quais tabelas do projeto já estão documentadas."
      />

      {pending.length > 0 && (
        <Panel
          title="Pendentes de revisão"
          subtitle="Tabelas aguardando aprovação — qualquer Admin de projeto pode aprovar ou devolver."
        >
          <ul className="flex flex-col gap-2">
            {pending.map((t) => (
              <PendingReviewRow
                key={`${t.dataset_id}.${t.table_id}`}
                projectId={projectId}
                entry={t}
              />
            ))}
          </ul>
        </Panel>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-xs">
          <Search
            size={14}
            className="-translate-y-1/2 absolute top-1/2 left-2.5 text-muted-foreground"
          />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por descrição…"
            className="pl-8"
          />
        </div>
        <Select value={status} onValueChange={(value) => setStatus(value ?? 'all')}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos os status</SelectItem>
            <SelectItem value="draft">Rascunho</SelectItem>
            <SelectItem value="in_review">Em revisão</SelectItem>
            <SelectItem value="approved">Aprovado</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {overviewQuery.isLoading && <LoadingState />}
      {overviewQuery.isError && <ApiErrorNotice error={overviewQuery.error} />}

      {overviewQuery.data && (
        <>
          <p className="text-muted-foreground text-sm">
            {overviewQuery.data.documented_count} de {overviewQuery.data.total_tables} tabelas
            documentadas
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tabela</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Dono técnico</TableHead>
                <TableHead>Domínio</TableHead>
                <TableHead>Sensibilidade</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {overviewQuery.data.tables.map((t) => (
                <TableRow key={`${t.dataset_id}.${t.table_id}`}>
                  <TableCell>
                    <Link
                      to={`/analyze/${t.dataset_id}/${t.table_id}/metadata`}
                      className="font-medium hover:underline"
                    >
                      {t.dataset_id}.{t.table_id}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={t.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {t.owner?.technical_owner ?? '—'}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {t.classification?.domain ?? '—'}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {t.classification?.sensitivity ?? '—'}
                  </TableCell>
                </TableRow>
              ))}
              {overviewQuery.data.tables.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    Nenhuma tabela encontrada com esse filtro.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </>
      )}

      {projectId && (
        <Panel
          title="Gerenciar acesso"
          subtitle="Quem pode editar metadados e budget deste projeto. Só Admins de projeto e administradores do Atlas podem conceder ou revogar."
        >
          <ProjectAdminsPanel projectId={projectId} />
        </Panel>
      )}
    </div>
  )
}

function PendingReviewRow({
  projectId,
  entry,
}: {
  projectId: string | undefined
  entry: MetadataOverviewEntry
}) {
  const { canManage } = useCanManageProject(projectId, entry.dataset_id)
  const updateStatus = useUpdateMetadataStatus(projectId, entry.dataset_id, entry.table_id)
  const [returnNote, setReturnNote] = useState('')
  const [returning, setReturning] = useState(false)

  function transition(target: GovernanceStatus, note?: string) {
    updateStatus
      .mutateAsync({ target, note })
      .then((res) =>
        toast.success(
          `${entry.dataset_id}.${entry.table_id}: ${STATUS_LABEL[res.status ?? 'draft']}`,
        ),
      )
      .catch(() => toast.error('Não foi possível mudar o status'))
  }

  return (
    <li className="flex flex-col gap-2 border-border border-b pb-2 last:border-b-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Link
          to={`/analyze/${entry.dataset_id}/${entry.table_id}/metadata`}
          className="font-medium hover:underline"
        >
          {entry.dataset_id}.{entry.table_id}
        </Link>
        {entry.owner?.technical_owner && (
          <span className="text-muted-foreground text-xs">dono: {entry.owner.technical_owner}</span>
        )}
        {canManage && (
          <div className="ml-auto flex gap-2">
            <Button
              size="sm"
              disabled={updateStatus.isPending}
              onClick={() => transition('approved')}
            >
              Aprovar
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={updateStatus.isPending}
              onClick={() => setReturning((v) => !v)}
            >
              Devolver
            </Button>
          </div>
        )}
      </div>
      {returning && (
        <div className="flex flex-wrap items-center gap-2">
          <Input
            value={returnNote}
            onChange={(e) => setReturnNote(e.target.value)}
            placeholder="O que precisa de ajuste…"
            className="h-8 max-w-sm text-xs"
          />
          <Button
            size="sm"
            variant="outline"
            disabled={updateStatus.isPending || !returnNote.trim()}
            onClick={() => {
              transition('draft', returnNote.trim())
              setReturnNote('')
              setReturning(false)
            }}
          >
            Confirmar devolução
          </Button>
        </div>
      )}
    </li>
  )
}
