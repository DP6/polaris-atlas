import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { RefreshButton } from '@/components/RefreshButton'
import { DatasetFreshnessTable } from '@/features/freshness/DatasetFreshnessTable'
import { useProjectFreshness } from '@/features/freshness/hooks'
import { SlaRow } from '@/features/freshness/SlaRow'
import { SLA_ORDER } from '@/features/freshness/sla'
import { useProjectContext } from '@/features/projects/ProjectContext'
import type { FreshnessCounts } from '@/types/freshness'

export function FreshnessPage() {
  const { projectId } = useProjectContext()
  const freshnessQuery = useProjectFreshness(projectId)

  if (freshnessQuery.isLoading) {
    return <LoadingState />
  }

  if (freshnessQuery.isError) {
    return <ApiErrorNotice error={freshnessQuery.error} />
  }

  if (!freshnessQuery.data) return null

  const totals: FreshnessCounts = freshnessQuery.data.datasets.reduce(
    (acc, dataset) => {
      acc.total_tables += dataset.total_tables
      for (const status of SLA_ORDER) acc[status] += dataset[status]
      return acc
    },
    {
      total_tables: 0,
      ok: 0,
      warning_12_24: 0,
      warning_24_48: 0,
      warning_48_7d: 0,
      warning_7d_1m: 0,
      stale: 0,
    },
  )

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Freshness"
        description={`${totals.total_tables} tabelas monitoradas em ${freshnessQuery.data.datasets.length} datasets`}
        actions={
          <RefreshButton
            isRefreshing={freshnessQuery.isFetching}
            onRefresh={() => freshnessQuery.refetch()}
          />
        }
      />

      <SlaRow counts={totals} />

      <DatasetFreshnessTable datasets={freshnessQuery.data.datasets} />
    </div>
  )
}
