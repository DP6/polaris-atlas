import { useParams } from 'react-router-dom'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { RefreshButton } from '@/components/RefreshButton'
import { useDatasetFreshness } from '@/features/freshness/hooks'
import { SlaRow } from '@/features/freshness/SlaRow'
import { TableFreshnessTable } from '@/features/freshness/TableFreshnessTable'
import { useProjectContext } from '@/features/projects/ProjectContext'

export function DatasetFreshnessPage() {
  const { projectId } = useProjectContext()
  const { datasetId } = useParams<{ datasetId: string }>()
  const freshnessQuery = useDatasetFreshness(projectId, datasetId)

  if (freshnessQuery.isLoading) {
    return <LoadingState />
  }

  if (freshnessQuery.isError) {
    return <ApiErrorNotice error={freshnessQuery.error} />
  }

  if (!freshnessQuery.data) return null

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={freshnessQuery.data.dataset_id}
        description={`Freshness de ${freshnessQuery.data.tables.length} ${
          freshnessQuery.data.tables.length === 1 ? 'tabela' : 'tabelas'
        } — ${freshnessQuery.data.location}`}
        actions={
          <RefreshButton
            isRefreshing={freshnessQuery.isFetching}
            onRefresh={() => freshnessQuery.refetch()}
          />
        }
      />

      <SlaRow counts={freshnessQuery.data.summary} />

      <TableFreshnessTable tables={freshnessQuery.data.tables} />
    </div>
  )
}
