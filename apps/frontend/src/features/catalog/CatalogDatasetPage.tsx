import { AlignJustify, Clock, Eye, HardDrive, MapPin, Star, Table2 } from 'lucide-react'
import { useLocation, useParams } from 'react-router-dom'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { RefreshButton } from '@/components/RefreshButton'
import { AssetsTable } from '@/features/catalog/AssetsTable'
import { useDatasets, useTables } from '@/features/catalog/hooks'
import { KpiCards } from '@/features/catalog/KpiCards'
import { isFavoriteDataset, useFavorites, useToggleFavorite } from '@/features/favorites/hooks'
import { useProjectFreshness } from '@/features/freshness/hooks'
import { SLA_LABELS } from '@/features/freshness/sla'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { formatNumber } from '@/lib/format'

export function CatalogDatasetPage() {
  const { projectId } = useProjectContext()
  const { datasetId } = useParams<{ datasetId: string }>()
  const location = useLocation()
  const highlightTableId = (location.state as { highlightTable?: string } | null)?.highlightTable

  const tablesQuery = useTables(projectId, datasetId)
  const datasetsQuery = useDatasets(projectId)
  const freshnessQuery = useProjectFreshness(projectId)
  const favoritesQuery = useFavorites()
  const toggleFavorite = useToggleFavorite()

  if (tablesQuery.isLoading) {
    return <LoadingState />
  }

  if (tablesQuery.isError) {
    return <ApiErrorNotice error={tablesQuery.error} />
  }

  if (!tablesQuery.data) return null

  const datasetSummary = datasetsQuery.data?.datasets.find((d) => d.dataset_id === datasetId)
  const worstStatus = freshnessQuery.data?.datasets.find(
    (d) => d.dataset_id === datasetId,
  )?.worst_status
  const isRefreshing =
    tablesQuery.isFetching || datasetsQuery.isFetching || freshnessQuery.isFetching
  const isDatasetFavorite = isFavoriteDataset(
    favoritesQuery.data,
    projectId as string,
    tablesQuery.data.dataset_id,
  )

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={
          <span className="inline-flex items-center gap-2">
            {tablesQuery.data.dataset_id}
            <button
              type="button"
              onClick={() =>
                toggleFavorite.mutate({
                  projectId: projectId as string,
                  datasetId: tablesQuery.data.dataset_id,
                  tableId: null,
                  isFavorite: isDatasetFavorite,
                })
              }
              aria-label={isDatasetFavorite ? 'Remover dataset dos favoritos' : 'Favoritar dataset'}
              className="inline-flex size-6 items-center justify-center text-muted-foreground hover:text-foreground"
            >
              <Star
                size={18}
                className={isDatasetFavorite ? 'fill-primary text-primary' : undefined}
              />
            </button>
          </span>
        }
        description={`${tablesQuery.data.total_tables} ativos`}
        actions={
          <RefreshButton
            isRefreshing={isRefreshing}
            onRefresh={() => {
              tablesQuery.refetch()
              datasetsQuery.refetch()
              freshnessQuery.refetch()
            }}
          />
        }
      />

      <KpiCards
        items={[
          { label: 'Região', value: tablesQuery.data.location, icon: <MapPin size={14} /> },
          {
            label: 'Tabelas',
            value: String(datasetSummary?.total_tables ?? 0),
            icon: <Table2 size={14} />,
          },
          {
            label: 'Views',
            value: String(datasetSummary?.total_views ?? 0),
            icon: <Eye size={14} />,
          },
          {
            label: 'Tamanho',
            value: `${(datasetSummary?.total_size_gb ?? 0).toFixed(2)} GB`,
            icon: <HardDrive size={14} />,
          },
          {
            label: 'Linhas',
            value: formatNumber(datasetSummary?.total_rows ?? null),
            icon: <AlignJustify size={14} />,
          },
          {
            label: 'Freshness',
            value: worstStatus ? SLA_LABELS[worstStatus] : '—',
            icon: <Clock size={14} />,
            alert: worstStatus === 'stale' || worstStatus === 'warning_7d_1m',
          },
        ]}
      />

      <AssetsTable
        projectId={projectId as string}
        datasetId={datasetId as string}
        tables={tablesQuery.data.tables}
        highlightTableId={highlightTableId}
      />
    </div>
  )
}
