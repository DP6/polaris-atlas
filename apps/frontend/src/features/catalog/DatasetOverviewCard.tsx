import { Boxes, MapPin, Table2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { SlaDistributionBar } from '@/components/SlaDistributionBar'
import { formatBytes } from '@/lib/format'
import type { DatasetSummary } from '@/types/catalog'
import type { FreshnessCounts } from '@/types/freshness'

// Card de dataset na visão geral do Catálogo de Dados (rota `/`). Clicar
// abre `/datasets/:id` (o detalhe já existente). Mini-gráfico = mesma
// SlaDistributionBar do Freshness (Q-003, sem query nova).
export function DatasetOverviewCard({
  dataset,
  freshness,
}: {
  dataset: DatasetSummary
  freshness: FreshnessCounts | undefined
}) {
  return (
    <Link
      to={`/datasets/${dataset.dataset_id}`}
      className="dp6-hoverable flex flex-col gap-3 rounded-lg border border-border bg-card p-4"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2">
          <span
            aria-hidden="true"
            className="inline-flex size-6 shrink-0 items-center justify-center rounded-md border border-primary/25 bg-primary/10 text-primary"
          >
            <Boxes size={14} />
          </span>
          <span className="truncate font-medium text-subtitle" title={dataset.dataset_id}>
            {dataset.dataset_id}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-1 text-label text-muted-foreground">
          <MapPin size={12} aria-hidden="true" />
          {dataset.location}
        </span>
      </div>

      {/* description do dataset ainda não vem do backend (PR 7 do refresh
          visual — DatasetSummary não expõe o campo hoje). */}
      <p className="text-body text-muted-foreground">Sem descrição cadastrada no BigQuery</p>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-label text-muted-foreground">
        <span className="flex items-center gap-1">
          <Table2 size={12} aria-hidden="true" />
          {assetCounts(dataset)}
        </span>
        <span>{formatBytes(dataset.total_size_bytes)}</span>
      </div>

      {freshness && (
        <div className="flex flex-col gap-1">
          <span className="text-label text-muted-foreground uppercase tracking-wide">
            Distribuição de SLA
          </span>
          <SlaDistributionBar counts={freshness} />
        </div>
      )}
    </Link>
  )
}

function assetCounts(dataset: DatasetSummary): string {
  const tables = `${dataset.total_tables} ${dataset.total_tables === 1 ? 'tabela' : 'tabelas'}`
  if (dataset.total_views === 0) return tables
  return `${tables} · ${dataset.total_views} ${dataset.total_views === 1 ? 'view' : 'views'}`
}
