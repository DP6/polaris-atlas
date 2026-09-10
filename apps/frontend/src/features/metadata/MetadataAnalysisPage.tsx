import { ExternalLink, Link2, Plus, X } from 'lucide-react'
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
import { Textarea } from '@/components/ui/textarea'
import { useCurrentUser } from '@/features/auth/hooks'
import { useBudgets } from '@/features/finops/hooks'
import { useTableFreshness } from '@/features/freshness/hooks'
import { ColumnMetadataTable } from '@/features/metadata/ColumnMetadataTable'
import {
  useCanManageProject,
  useMetadataHistory,
  useTableMetadata,
  useUpdateMetadataStatus,
  useUpsertTableMetadata,
} from '@/features/metadata/hooks'
import { useAnalysisContext } from '@/features/quality/analysisContext'
import { formatUsd } from '@/lib/format'
import type { GovernanceStatus, MetadataTableUpsertRequest, RelatedLink } from '@/types/metadata'

// Defesa em profundidade pro CodeQL js/xss-through-dom: o backend já
// valida `url` contra ^https?:// no schema de request (Pydantic), mas o
// front não deve confiar cegamente num dado que pode ter chegado por
// outro caminho (edição direta no Firestore, bug de validação futuro).
// O `href` do <a> abaixo usa o RETORNO desta função, nunca `link.url`
// diretamente — duas tentativas anteriores guardavam o valor original
// atrás de uma condição externa (`isSafeHttpUrl(url) ? <a href={url}>`),
// o que o CodeQL não reconhece como sanitização (o dado "sujo" ainda
// chega no sink); o rastreamento de taint só considera limpo o valor
// que É o retorno de uma função sanitizadora usado direto no sink.
const SAFE_HTTP_URL_PATTERN = /^https?:\/\//i

function toSafeHref(url: string): string | undefined {
  return SAFE_HTTP_URL_PATTERN.test(url) ? url : undefined
}

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

// 8º card do chooser de análise (`/analyze/:dataset/:table/metadata`) —
// edição de metadados de tabela/coluna. Reaproveita AnalysisContext
// (tableDetail já carregado pelo AnalysisLayout) pra não refazer a
// leitura do schema; lineage/qualidade são só links (rotas já existentes),
// freshness/budget mostram um valor ao vivo pequeno — princípio central
// da spec: linkar, não duplicar.
export function MetadataAnalysisPage() {
  const { projectId, datasetId, tableId, tableDetail } = useAnalysisContext()
  const base = `/analyze/${datasetId}/${tableId}`

  const metadataQuery = useTableMetadata(projectId, datasetId, tableId)
  const historyQuery = useMetadataHistory(projectId, datasetId, tableId)
  const { canManage } = useCanManageProject(projectId, datasetId)
  const isSuperadmin = Boolean(useCurrentUser().data?.is_admin)
  const freshnessQuery = useTableFreshness(projectId, datasetId, tableId)
  const budgetsQuery = useBudgets(projectId)
  const upsertTable = useUpsertTableMetadata(projectId, datasetId, tableId)
  const updateStatus = useUpdateMetadataStatus(projectId, datasetId, tableId)

  const tableBudget = budgetsQuery.data?.budgets.find(
    (b) =>
      (b.scope === 'table' && b.dataset_id === datasetId && b.table_id === tableId) ||
      (b.scope === 'dataset' && b.dataset_id === datasetId && b.table_id === null),
  )

  if (metadataQuery.isLoading) return <LoadingState />
  if (metadataQuery.isError) return <ApiErrorNotice error={metadataQuery.error} />
  if (!metadataQuery.data) return null

  const metadata = metadataQuery.data

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: base, label: 'Voltar' }}
        title={`Metadados — ${datasetId}.${tableId}`}
        description={
          canManage
            ? 'Descrição, ownership, classificação e estado de governança desta tabela.'
            : 'Somente leitura — você não é Admin de projeto neste dataset.'
        }
      />

      <div className="grid gap-4 md:grid-cols-4">
        <Link
          to={`/lineage/${datasetId}/${tableId}`}
          className="dp6-opt-card flex items-center gap-2 rounded-lg border border-border bg-card p-3 text-sm hover:bg-muted"
        >
          <Link2 size={14} className="text-primary" />
          Lineage
          <ExternalLink size={12} className="ml-auto text-muted-foreground" />
        </Link>
        <Link
          to={`${base}/quality`}
          className="dp6-opt-card flex items-center gap-2 rounded-lg border border-border bg-card p-3 text-sm hover:bg-muted"
        >
          <Link2 size={14} className="text-primary" />
          Análise de qualidade
          <ExternalLink size={12} className="ml-auto text-muted-foreground" />
        </Link>
        <div className="flex items-center gap-2 rounded-lg border border-border bg-card p-3 text-sm">
          <span className="text-muted-foreground">Freshness</span>
          <span className="ml-auto font-medium">
            {freshnessQuery.data?.sla_status ?? (freshnessQuery.isLoading ? '…' : '—')}
          </span>
        </div>
        <Link
          to="/finops/budget"
          className="dp6-opt-card flex items-center gap-2 rounded-lg border border-border bg-card p-3 text-sm hover:bg-muted"
        >
          <span className="text-muted-foreground">Budget</span>
          <span className="ml-auto font-medium">
            {tableBudget ? formatUsd(tableBudget.amount_usd) : '—'}
          </span>
          <ExternalLink size={12} className="text-muted-foreground" />
        </Link>
      </div>

      <StatusPanel
        metadata={metadata}
        canManage={canManage}
        isSuperadmin={isSuperadmin}
        pending={updateStatus.isPending}
        error={updateStatus.error}
        onTransition={(target, note) =>
          updateStatus
            .mutateAsync({ target, note })
            .then((res) => toast.success(`Status: ${STATUS_LABEL[res.status ?? 'draft']}`))
            .catch(() => toast.error('Não foi possível mudar o status'))
        }
      />

      <TableFieldsPanel
        key={metadata.updated_at ?? 'new'}
        metadata={metadata}
        canManage={canManage}
        upsert={upsertTable}
      />

      <Panel title="Colunas">
        <ColumnMetadataTable
          projectId={projectId}
          datasetId={datasetId}
          tableId={tableId}
          bqColumns={tableDetail?.columns ?? []}
          metadata={metadata}
          canManage={canManage}
        />
      </Panel>

      <p className="text-muted-foreground text-xs">
        Quem pode editar metadados e budget deste projeto é gerenciado na{' '}
        <Link to="/metadados" className="text-primary hover:underline">
          visão geral de Metadados
        </Link>
        .
      </p>

      <Panel title="Histórico de edição">
        {historyQuery.data && historyQuery.data.entries.length > 0 ? (
          <ul className="flex flex-col gap-1.5 text-xs">
            {historyQuery.data.entries.map((entry, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: sem id próprio, lista append-only
              <li key={i} className="text-muted-foreground">
                <span className="font-medium text-foreground">{entry.changed_by}</span> alterou{' '}
                <span className="font-medium text-foreground">
                  {entry.column_name
                    ? `${entry.field} da coluna ${entry.column_name}`
                    : entry.field}
                </span>{' '}
                de "{entry.old_value ?? '—'}" para "{entry.new_value ?? '—'}" em{' '}
                {new Date(entry.changed_at).toLocaleString('pt-BR')}
                {entry.note ? ` — "${entry.note}"` : ''}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted-foreground text-xs">Nenhuma edição registrada ainda.</p>
        )}
      </Panel>
    </div>
  )
}

function StatusBadge({ status }: { status: GovernanceStatus | null }) {
  if (!status) {
    return (
      <Badge variant="outline" className="text-muted-foreground">
        Sem status
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

function StatusPanel({
  metadata,
  canManage,
  isSuperadmin,
  pending,
  error,
  onTransition,
}: {
  metadata: NonNullable<ReturnType<typeof useTableMetadata>['data']>
  canManage: boolean
  isSuperadmin: boolean
  pending: boolean
  error: unknown
  onTransition: (target: GovernanceStatus, note?: string) => void
}) {
  const [returnNote, setReturnNote] = useState('')
  const [returning, setReturning] = useState(false)
  const status = metadata.status
  const changedAt = metadata.status_changed_at
    ? new Date(metadata.status_changed_at).toLocaleString('pt-BR')
    : null

  return (
    <Panel title="Estado de governança">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <StatusBadge status={status} />
          {metadata.status_changed_by && (
            <span className="text-muted-foreground text-xs">
              por {metadata.status_changed_by}
              {changedAt ? ` em ${changedAt}` : ''}
            </span>
          )}
        </div>

        {status === 'draft' && metadata.review_note && (
          <p className="rounded-md border border-status-warn/40 bg-status-warn/5 p-2 text-xs">
            Devolvido para ajustes: "{metadata.review_note}"
          </p>
        )}

        {canManage && (
          <div className="flex flex-col gap-2 border-border border-t pt-3">
            <div className="flex flex-wrap gap-2">
              {isSuperadmin
                ? status !== 'approved' && (
                    <Button size="sm" disabled={pending} onClick={() => onTransition('approved')}>
                      Aprovar
                    </Button>
                  )
                : status !== 'in_review' &&
                  status !== 'approved' && (
                    <Button size="sm" disabled={pending} onClick={() => onTransition('in_review')}>
                      Enviar para revisão
                    </Button>
                  )}

              {!isSuperadmin && status === 'in_review' && (
                <>
                  <Button size="sm" disabled={pending} onClick={() => onTransition('approved')}>
                    Aprovar
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={pending}
                    onClick={() => setReturning((v) => !v)}
                  >
                    Devolver para ajustes
                  </Button>
                </>
              )}

              {status === 'approved' && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={pending}
                  onClick={() => onTransition('draft')}
                >
                  Reabrir para edição
                </Button>
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
                  disabled={pending || !returnNote.trim()}
                  onClick={() => {
                    onTransition('draft', returnNote.trim())
                    setReturnNote('')
                    setReturning(false)
                  }}
                >
                  Confirmar devolução
                </Button>
              </div>
            )}
          </div>
        )}

        {Boolean(error) && <ApiErrorNotice error={error} />}
      </div>
    </Panel>
  )
}

function TableFieldsPanel({
  metadata,
  canManage,
  upsert,
}: {
  metadata: NonNullable<ReturnType<typeof useTableMetadata>['data']>
  canManage: boolean
  upsert: ReturnType<typeof useUpsertTableMetadata>
}) {
  const [description, setDescription] = useState(metadata.description ?? '')
  const [technicalOwner, setTechnicalOwner] = useState(metadata.owner?.technical_owner ?? '')
  const [team, setTeam] = useState(metadata.owner?.team ?? '')
  const [domain, setDomain] = useState(metadata.classification?.domain ?? '')
  const [sensitivity, setSensitivity] = useState(metadata.classification?.sensitivity ?? '')
  const [links, setLinks] = useState<RelatedLink[]>(metadata.related_links)
  const [newLinkLabel, setNewLinkLabel] = useState('')
  const [newLinkUrl, setNewLinkUrl] = useState('')

  const descriptionDirty = description !== (metadata.description ?? '')
  const ownerDirty =
    technicalOwner !== (metadata.owner?.technical_owner ?? '') ||
    team !== (metadata.owner?.team ?? '')
  const classificationDirty =
    domain !== (metadata.classification?.domain ?? '') ||
    sensitivity !== (metadata.classification?.sensitivity ?? '')
  const dirty = descriptionDirty || ownerDirty || classificationDirty

  function save() {
    const payload: MetadataTableUpsertRequest = {}
    if (descriptionDirty) payload.description = description || null
    if (ownerDirty) payload.owner = { technical_owner: technicalOwner || null, team: team || null }
    if (classificationDirty)
      payload.classification = { domain: domain || null, sensitivity: sensitivity || null }
    upsert
      .mutateAsync(payload)
      .then(() => toast.success('Metadados salvos'))
      .catch(() => toast.error('Não foi possível salvar'))
  }

  function addLink() {
    if (!newLinkLabel.trim() || !newLinkUrl.trim()) return
    const next = [...links, { label: newLinkLabel.trim(), url: newLinkUrl.trim() }]
    setLinks(next)
    upsert
      .mutateAsync({ related_links: next })
      .then(() => toast.success('Link adicionado'))
      .catch(() => {
        setLinks(links)
        toast.error('Não foi possível adicionar o link')
      })
    setNewLinkLabel('')
    setNewLinkUrl('')
  }

  function removeLink(index: number) {
    const next = links.filter((_, i) => i !== index)
    const previous = links
    setLinks(next)
    upsert
      .mutateAsync({ related_links: next })
      .then(() => toast.success('Link removido'))
      .catch(() => {
        setLinks(previous)
        toast.error('Não foi possível remover o link')
      })
  }

  return (
    <Panel
      title="Metadados da tabela"
      actions={
        canManage ? (
          <Button size="sm" disabled={!dirty || upsert.isPending} onClick={save}>
            Salvar
          </Button>
        ) : undefined
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <span className="text-label text-muted-foreground">Descrição</span>
          {canManage ? (
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="O que essa tabela representa…"
              rows={3}
            />
          ) : (
            <p className="text-sm">{metadata.description ?? '—'}</p>
          )}
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <span className="text-label text-muted-foreground">Dono técnico</span>
            {canManage ? (
              <Input
                value={technicalOwner}
                onChange={(e) => setTechnicalOwner(e.target.value)}
                placeholder="email@dp6.com.br"
              />
            ) : (
              <p className="text-sm">{metadata.owner?.technical_owner ?? '—'}</p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-label text-muted-foreground">Time</span>
            {canManage ? (
              <Input value={team} onChange={(e) => setTeam(e.target.value)} />
            ) : (
              <p className="text-sm">{metadata.owner?.team ?? '—'}</p>
            )}
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <span className="text-label text-muted-foreground">Domínio</span>
            {canManage ? (
              <Input
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="ex: e-commerce"
              />
            ) : (
              <p className="text-sm">{metadata.classification?.domain ?? '—'}</p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-label text-muted-foreground">Sensibilidade</span>
            {canManage ? (
              <Input
                value={sensitivity}
                onChange={(e) => setSensitivity(e.target.value)}
                placeholder="ex: confidencial"
              />
            ) : (
              <p className="text-sm">{metadata.classification?.sensitivity ?? '—'}</p>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <span className="text-label text-muted-foreground">Links relacionados</span>
          <div className="flex flex-col gap-1">
            {links.map((link, i) => {
              // href vem do retorno de toSafeHref, nunca de link.url
              // direto — ver comentário na definição da função.
              const safeHref = toSafeHref(link.url)
              return (
                <div key={link.url} className="flex items-center gap-2 text-sm">
                  {safeHref !== undefined ? (
                    <a
                      href={safeHref}
                      target="_blank"
                      rel="noreferrer"
                      className="text-primary hover:underline"
                    >
                      {link.label}
                    </a>
                  ) : (
                    <span
                      className="text-muted-foreground line-through"
                      title="URL inválida (só http/https é aceito) — não renderizada como link"
                    >
                      {link.label}
                    </span>
                  )}
                  {canManage && (
                    <button
                      type="button"
                      onClick={() => removeLink(i)}
                      aria-label={`Remover link ${link.label}`}
                      className="text-muted-foreground hover:text-status-error-foreground"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              )
            })}
            {links.length === 0 && (
              <p className="text-muted-foreground text-xs">Nenhum link ainda.</p>
            )}
          </div>
          {canManage && (
            <div className="mt-1 flex gap-2">
              <Input
                value={newLinkLabel}
                onChange={(e) => setNewLinkLabel(e.target.value)}
                placeholder="rótulo"
                className="h-8 max-w-[10rem] text-xs"
              />
              <Input
                value={newLinkUrl}
                onChange={(e) => setNewLinkUrl(e.target.value)}
                placeholder="https://…"
                className="h-8 text-xs"
              />
              <Button
                size="sm"
                variant="outline"
                disabled={!newLinkLabel.trim() || !newLinkUrl.trim()}
                onClick={addLink}
              >
                <Plus size={14} />
              </Button>
            </div>
          )}
        </div>

        {!metadata.has_metadata && (
          <Badge variant="outline" className="w-fit text-muted-foreground">
            Ainda não documentada
          </Badge>
        )}
      </div>
    </Panel>
  )
}
