import type { ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { CacheStalenessBadge } from '@/components/CacheStalenessBadge'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { Badge } from '@/components/ui/badge'
import { WarningCallout } from '@/components/WarningCallout'
import { useTableLineage } from '@/features/lineage/hooks'
import { LineageGraph } from '@/features/lineage/LineageGraph'
import { useProjectContext } from '@/features/projects/ProjectContext'
import type { LineageNode } from '@/types/lineage'

const VIEW_TYPES = new Set(['VIEW', 'MATERIALIZED_VIEW'])

function nodeLabel(n: LineageNode): string {
  if (n.type === 'bucket') return `GCS · ${n.bucket_name}`
  return `${n.dataset_id}.${n.table_id}`
}

function KvRow({ k, v }: { k: ReactNode; v: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-border border-t py-2 text-sm first:border-0">
      <span className="min-w-0 truncate text-muted-foreground">{k}</span>
      <span className="shrink-0 font-medium">{v}</span>
    </div>
  )
}

// Lineage em tela cheia (rodada 2 — antes era só uma aba do ProfilingDialog).
// Rota `/lineage/:datasetId/:tableId`.
export function LineagePage() {
  const { projectId } = useProjectContext()
  const { datasetId, tableId } = useParams<{ datasetId: string; tableId: string }>()
  const lineageQuery = useTableLineage(projectId, datasetId, tableId)

  if (lineageQuery.isLoading) return <LoadingState />
  if (lineageQuery.isError) return <ApiErrorNotice error={lineageQuery.error} />
  const data = lineageQuery.data
  if (!data) return null

  const downstream = data.nodes.filter((n) => n.hop_distance > 0)
  const upstream = data.nodes.filter((n) => n.hop_distance < 0)
  const sources = data.nodes.filter((n) => n.hop_distance === -1)
  const consumers = data.nodes.filter((n) => n.hop_distance === 1)
  const brokenViews = downstream.filter((n) => n.table_type && VIEW_TYPES.has(n.table_type))
  const typeCountsKnown = downstream.some((n) => n.table_type)

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: `/analyze/${datasetId}/${tableId}`, label: `${datasetId}.${tableId}` }}
        title="Lineage"
        description={
          <span className="inline-flex flex-wrap items-center gap-2">
            De onde os dados de {datasetId}.{tableId} vêm e para onde vão — reconstruído dos jobs
            LOAD / QUERY / EXTRACT do BigQuery.
            <CacheStalenessBadge cacheUpdatedAt={data.cache_updated_at} />
            <span className="text-muted-foreground text-xs">
              · profundidade limitada a {data.max_hops} hops
            </span>
          </span>
        }
      />

      {data.warning && <WarningCallout>{data.warning}</WarningCallout>}
      {data.truncated && (
        <WarningCallout variant="info">
          Grafo truncado em {data.max_hops} saltos — pode haver mais tabelas além do limite.
        </WarningCallout>
      )}

      <LineageGraph data={data} height={540} />

      <div className="grid gap-4 lg:grid-cols-3 [&>*]:min-w-0">
        <Panel title="Impacto de mudança de schema" subtitle="Se o schema desta tabela mudar">
          <KvRow k="Tabelas afetadas (a jusante)" v={downstream.length} />
          <KvRow k="Views que quebrariam" v={typeCountsKnown ? brokenViews.length : '—'} />
          <KvRow k="Jobs agendados" v="—" />
        </Panel>

        <Panel title="Fontes" subtitle="Origem direta dos dados">
          {sources.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sem fonte direta na janela.</p>
          ) : (
            sources.map((n) => (
              <KvRow
                key={n.id}
                k={nodeLabel(n)}
                v={
                  n.type === 'bucket' ? (
                    <Badge variant="secondary" className="border-status-ok/30 bg-status-ok/10">
                      bucket
                    </Badge>
                  ) : n.access_denied ? (
                    <Badge variant="outline">acesso negado</Badge>
                  ) : (
                    <Badge variant="secondary">{n.table_type ?? 'tabela'}</Badge>
                  )
                }
              />
            ))
          )}
        </Panel>

        <Panel title="Consumidores" subtitle="Quem lê esta tabela direto">
          {consumers.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sem consumidor direto na janela.</p>
          ) : (
            consumers.map((n) => (
              <KvRow
                key={n.id}
                k={nodeLabel(n)}
                v={<Badge variant="secondary">{n.table_type ?? 'tabela'}</Badge>}
              />
            ))
          )}
        </Panel>
      </div>

      <p className="text-muted-foreground text-xs">
        Baseado em audit logs dos últimos {data.lookback_days} dias · {upstream.length} nós a
        montante, {downstream.length} a jusante.
      </p>
    </div>
  )
}
