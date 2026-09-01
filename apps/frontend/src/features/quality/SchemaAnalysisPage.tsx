import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/badge'
import { useAnalysisContext } from '@/features/quality/analysisContext'
import { SchemaTable } from '@/features/quality/SchemaTable'

export function SchemaAnalysisPage() {
  const { datasetId, tableId, tableDetail } = useAnalysisContext()
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: '..', label: `${datasetId}.${tableId}` }}
        title="Schema"
        description={`${datasetId}.${tableId} — colunas, tipos e nullability.`}
      />
      {(tableDetail?.is_partitioned || tableDetail?.is_clustered) && (
        <div className="flex flex-wrap gap-2">
          {tableDetail?.is_partitioned && (
            <Badge>Particionada por {tableDetail.partition_column}</Badge>
          )}
          {tableDetail?.is_clustered && (
            <Badge variant="outline">
              Clusterizada por {tableDetail.clustering_columns.join(', ')}
            </Badge>
          )}
        </div>
      )}
      <SchemaTable
        columns={tableDetail?.columns ?? []}
        isLoading={!tableDetail}
        partitionColumn={tableDetail?.partition_column ?? null}
      />
    </div>
  )
}
