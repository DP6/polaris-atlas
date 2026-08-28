import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { CacheStalenessBadge } from '@/components/CacheStalenessBadge'
import { WarningCallout } from '@/components/WarningCallout'
import { useTableLineage } from '@/features/lineage/hooks'
import { LineageGraph } from '@/features/lineage/LineageGraph'

interface LineageTabProps {
  projectId: string
  datasetId: string
  tableId: string | null
}

export function LineageTab({ projectId, datasetId, tableId }: LineageTabProps) {
  const lineageQuery = useTableLineage(projectId, datasetId, tableId ?? undefined)

  if (lineageQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando lineage…</p>
  }

  if (lineageQuery.isError) {
    return <ApiErrorNotice error={lineageQuery.error} />
  }

  const data = lineageQuery.data
  if (!data) return null

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Reconstrói de onde os dados desta tabela vêm e para onde vão, a partir dos jobs de
        LOAD/QUERY/EXTRACT do BigQuery — útil para avaliar o impacto de mudar o schema ou
        descontinuar a tabela antes de fazer isso.
      </p>

      {data.warning && <WarningCallout>{data.warning}</WarningCallout>}

      {data.truncated && (
        <WarningCallout variant="info">
          Grafo truncado em {data.max_hops} saltos — pode haver mais tabelas além do limite.
        </WarningCallout>
      )}

      <LineageGraph data={data} />

      <div className="flex items-center gap-2">
        <p className="text-xs text-muted-foreground">
          Baseado em audit logs dos últimos {data.lookback_days} dias.
        </p>
        <CacheStalenessBadge cacheUpdatedAt={data.cache_updated_at} />
      </div>
    </div>
  )
}
