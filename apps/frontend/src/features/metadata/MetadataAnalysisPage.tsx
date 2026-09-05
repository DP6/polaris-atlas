import { ExternalLink, Link2, Plus, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
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
import { Textarea } from '@/components/ui/textarea'
import { useBudgets } from '@/features/finops/hooks'
import { useTableFreshness } from '@/features/freshness/hooks'
import { ColumnMetadataTable } from '@/features/metadata/ColumnMetadataTable'
import {
  useCanManageProject,
  useMetadataHistory,
  useTableMetadata,
  useUpsertTableMetadata,
} from '@/features/metadata/hooks'
import { ProjectAdminsPanel } from '@/features/metadata/ProjectAdminsPanel'
import { useAnalysisContext } from '@/features/quality/analysisContext'
import { formatUsd } from '@/lib/format'
import type { CertificationStatus, RelatedLink } from '@/types/metadata'

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

const CERTIFICATION_LABEL: Record<CertificationStatus, string> = {
  draft: 'Rascunho',
  in_review: 'Em revisão',
  approved: 'Aprovado',
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
  const freshnessQuery = useTableFreshness(projectId, datasetId, tableId)
  const budgetsQuery = useBudgets(projectId)
  const upsertTable = useUpsertTableMetadata(projectId, datasetId, tableId)

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
            ? 'Descrição, ownership, classificação e certificação desta tabela.'
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

      <TableFieldsPanel metadata={metadata} canManage={canManage} onSave={upsertTable.mutate} />

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

      <Panel title="Gerenciar acesso" subtitle="Quem pode editar metadados e budget deste projeto.">
        <ProjectAdminsPanel projectId={projectId} />
      </Panel>

      <Panel title="Histórico de edição">
        {historyQuery.data && historyQuery.data.entries.length > 0 ? (
          <ul className="flex flex-col gap-1.5 text-xs">
            {historyQuery.data.entries.map((entry, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: sem id próprio, lista append-only
              <li key={i} className="text-muted-foreground">
                <span className="font-medium text-foreground">{entry.changed_by}</span> alterou{' '}
                <span className="font-medium text-foreground">{entry.field}</span> de "
                {entry.old_value ?? '—'}" para "{entry.new_value ?? '—'}" em{' '}
                {new Date(entry.changed_at).toLocaleString('pt-BR')}
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

function TableFieldsPanel({
  metadata,
  canManage,
  onSave,
}: {
  metadata: NonNullable<ReturnType<typeof useTableMetadata>['data']>
  canManage: boolean
  onSave: ReturnType<typeof useUpsertTableMetadata>['mutate']
}) {
  const [description, setDescription] = useState(metadata.description ?? '')
  const [technicalOwner, setTechnicalOwner] = useState(metadata.owner?.technical_owner ?? '')
  const [steward, setSteward] = useState(metadata.owner?.steward ?? '')
  const [team, setTeam] = useState(metadata.owner?.team ?? '')
  const [domain, setDomain] = useState(metadata.classification?.domain ?? '')
  const [sensitivity, setSensitivity] = useState(metadata.classification?.sensitivity ?? '')
  const [links, setLinks] = useState<RelatedLink[]>(metadata.related_links)
  const [newLinkLabel, setNewLinkLabel] = useState('')
  const [newLinkUrl, setNewLinkUrl] = useState('')

  function saveOwner() {
    onSave({
      owner: {
        technical_owner: technicalOwner || null,
        steward: steward || null,
        team: team || null,
      },
    })
  }

  function saveClassification() {
    onSave({ classification: { domain: domain || null, sensitivity: sensitivity || null } })
  }

  function addLink() {
    if (!newLinkLabel.trim() || !newLinkUrl.trim()) return
    const next = [...links, { label: newLinkLabel.trim(), url: newLinkUrl.trim() }]
    setLinks(next)
    onSave({ related_links: next })
    setNewLinkLabel('')
    setNewLinkUrl('')
  }

  function removeLink(index: number) {
    const next = links.filter((_, i) => i !== index)
    setLinks(next)
    onSave({ related_links: next })
  }

  return (
    <Panel title="Metadados da tabela">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <span className="text-label text-muted-foreground">Descrição</span>
          {canManage ? (
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              onBlur={() => {
                if (description !== (metadata.description ?? '')) onSave({ description })
              }}
              placeholder="O que essa tabela representa…"
              rows={3}
            />
          ) : (
            <p className="text-sm">{metadata.description ?? '—'}</p>
          )}
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <span className="text-label text-muted-foreground">Dono técnico</span>
            {canManage ? (
              <Input
                value={technicalOwner}
                onChange={(e) => setTechnicalOwner(e.target.value)}
                onBlur={saveOwner}
                placeholder="email@dp6.com.br"
              />
            ) : (
              <p className="text-sm">{metadata.owner?.technical_owner ?? '—'}</p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-label text-muted-foreground">Steward</span>
            {canManage ? (
              <Input
                value={steward}
                onChange={(e) => setSteward(e.target.value)}
                onBlur={saveOwner}
              />
            ) : (
              <p className="text-sm">{metadata.owner?.steward ?? '—'}</p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-label text-muted-foreground">Time</span>
            {canManage ? (
              <Input value={team} onChange={(e) => setTeam(e.target.value)} onBlur={saveOwner} />
            ) : (
              <p className="text-sm">{metadata.owner?.team ?? '—'}</p>
            )}
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <span className="text-label text-muted-foreground">Domínio</span>
            {canManage ? (
              <Input
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                onBlur={saveClassification}
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
                onBlur={saveClassification}
                placeholder="ex: confidencial"
              />
            ) : (
              <p className="text-sm">{metadata.classification?.sensitivity ?? '—'}</p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-label text-muted-foreground">Certificação</span>
            {canManage ? (
              <Select
                value={metadata.certification_status ?? undefined}
                onValueChange={(value) =>
                  onSave({ certification_status: value as CertificationStatus })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Selecionar…" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="draft">Rascunho</SelectItem>
                  <SelectItem value="in_review">Em revisão</SelectItem>
                  <SelectItem value="approved">Aprovado</SelectItem>
                </SelectContent>
              </Select>
            ) : (
              <p className="text-sm">
                {metadata.certification_status
                  ? CERTIFICATION_LABEL[metadata.certification_status]
                  : '—'}
              </p>
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
