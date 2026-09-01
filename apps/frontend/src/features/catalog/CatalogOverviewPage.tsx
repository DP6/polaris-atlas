import { Database, HardDrive, Search, Table2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { EmptyState } from '@/components/EmptyState'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { RefreshButton } from '@/components/RefreshButton'
import { Input } from '@/components/ui/input'
import { DatasetOverviewCard } from '@/features/catalog/DatasetOverviewCard'
import { useDatasets } from '@/features/catalog/hooks'
import { KpiCards } from '@/features/catalog/KpiCards'
import { TableSearchPanel } from '@/features/catalog/TableSearchPanel'
import { useProjectFreshness } from '@/features/freshness/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { formatBytes, formatNumber } from '@/lib/format'
import type { FreshnessCounts } from '@/types/freshness'

// Visão geral do Catálogo de Dados — rota índice `/`. Antes era só um
// EmptyState "selecione um dataset"; agora é a tela de overview do domínio
// (brief: "clicar num item de nível 1 abre uma tela de opções/overview").
// A sidebar continua com a lista de datasets pra navegação direta.
export function CatalogOverviewPage() {
  const { projectId } = useProjectContext()
  const datasetsQuery = useDatasets(projectId)
  const freshnessQuery = useProjectFreshness(projectId)
  const [query, setQuery] = useState('')

  const freshnessByDataset = useMemo(() => {
    const map = new Map<string, FreshnessCounts>()
    for (const dataset of freshnessQuery.data?.datasets ?? []) {
      map.set(dataset.dataset_id, dataset)
    }
    return map
  }, [freshnessQuery.data])

  if (datasetsQuery.isLoading) return <LoadingState />
  if (datasetsQuery.isError) return <ApiErrorNotice error={datasetsQuery.error} />
  if (!datasetsQuery.data) return null

  const datasets = datasetsQuery.data.datasets
  const totalTables = datasets.reduce((sum, dataset) => sum + dataset.total_tables, 0)
  const totalBytes = datasets.reduce((sum, dataset) => sum + dataset.total_size_bytes, 0)
  const term = query.trim().toLowerCase()
  const visible = term
    ? datasets.filter((dataset) => dataset.dataset_id.toLowerCase().includes(term))
    : datasets

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Catálogo de Dados"
        description={`${datasets.length} datasets · ${formatNumber(totalTables)} tabelas no projeto`}
        actions={
          <RefreshButton
            isRefreshing={datasetsQuery.isFetching || freshnessQuery.isFetching}
            onRefresh={() => {
              datasetsQuery.refetch()
              freshnessQuery.refetch()
            }}
          />
        }
      />

      <KpiCards
        items={[
          { label: 'Datasets', value: String(datasets.length), icon: <Database size={14} /> },
          { label: 'Tabelas', value: formatNumber(totalTables), icon: <Table2 size={14} /> },
          { label: 'Volume', value: formatBytes(totalBytes), icon: <HardDrive size={14} /> },
        ]}
      />

      <TableSearchPanel />

      <div className="flex flex-col gap-1">
        <span className="text-label text-muted-foreground uppercase tracking-wide">
          Navegar por dataset
        </span>
        <div className="relative max-w-md">
          <Search
            size={14}
            className="-translate-y-1/2 absolute top-1/2 left-2.5 text-muted-foreground"
          />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filtrar dataset por nome…"
            className="pl-8"
          />
        </div>
      </div>

      {visible.length === 0 ? (
        <EmptyState
          icon={Database}
          title="Nenhum dataset encontrado"
          description="Ajuste a busca ou confira o projeto selecionado."
        />
      ) : (
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(20rem,1fr))]">
          {visible.map((dataset) => (
            <DatasetOverviewCard
              key={dataset.dataset_id}
              dataset={dataset}
              freshness={freshnessByDataset.get(dataset.dataset_id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
