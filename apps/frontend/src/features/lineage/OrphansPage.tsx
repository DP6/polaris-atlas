import { Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { DatasetScopeGate } from '@/components/DatasetScopeGate'
import { RefreshButton } from '@/components/RefreshButton'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { useOrphans } from '@/features/lineage/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import { formatBytes } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { OrphanTable } from '@/types/lineage'

const DATASET_FILTER_ALL = 'all'
const LOOKBACK_OPTIONS = [30, 60, 90, 365] as const

type SortKey = 'dataset_id' | 'table_id' | 'size_bytes' | 'estimated_monthly_storage_cost_usd'

function formatUsd(value: number): string {
  return `US$ ${value.toFixed(value < 0.01 ? 6 : 2)}`
}

function compare(a: OrphanTable, b: OrphanTable, key: SortKey): number {
  if (key === 'size_bytes' || key === 'estimated_monthly_storage_cost_usd') {
    return a[key] - b[key]
  }
  return a[key].localeCompare(b[key])
}

function LookbackPicker({ value, onChange }: { value: number; onChange: (days: number) => void }) {
  const isPreset = (LOOKBACK_OPTIONS as readonly number[]).includes(value)
  const [showCustom, setShowCustom] = useState(!isPreset)

  return (
    <div>
      <span className="mb-1.5 block text-xs font-medium text-muted-foreground">
        Período analisado (dias)
      </span>
      <div className="flex flex-wrap items-center gap-2">
        {LOOKBACK_OPTIONS.map((days) => (
          <button
            key={days}
            type="button"
            onClick={() => {
              onChange(days)
              setShowCustom(false)
            }}
            className={cn(
              'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
              value === days && !showCustom
                ? 'border-primary bg-primary/10 text-foreground'
                : 'border-border text-muted-foreground hover:bg-muted',
            )}
          >
            {days}
          </button>
        ))}
        <button
          type="button"
          onClick={() => setShowCustom(true)}
          className={cn(
            'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
            showCustom
              ? 'border-primary bg-primary/10 text-foreground'
              : 'border-border text-muted-foreground hover:bg-muted',
          )}
        >
          Outro
        </button>
        {showCustom && (
          <Input
            type="number"
            min={1}
            className="h-7 w-20 text-xs"
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
          />
        )}
      </div>
    </div>
  )
}

export function OrphansPage() {
  const { projectId } = useProjectContext()
  const [hasRun, setHasRun] = useState(false)
  const [scopeDatasets, setScopeDatasets] = useState<string[]>([])
  const [lookbackDays, setLookbackDays] = useState<number>(30)

  const orphansQuery = useOrphans(projectId, {
    datasets: scopeDatasets,
    lookbackDays,
    enabled: hasRun,
  })
  const data = orphansQuery.data

  const datasets = useMemo(
    () => [...new Set(data?.orphans.map((o) => o.dataset_id) ?? [])].sort(),
    [data],
  )
  const [datasetFilter, setDatasetFilter] = useState(DATASET_FILTER_ALL)

  const {
    search,
    setSearch,
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleOrphans,
  } = useTableFilterSort<OrphanTable, SortKey>({
    rows: data?.orphans ?? [],
    initialSortKey: 'dataset_id',
    compare,
    matches: (orphan, term) =>
      orphan.table_id.toLowerCase().includes(term.toLowerCase()) &&
      (datasetFilter === DATASET_FILTER_ALL || orphan.dataset_id === datasetFilter),
  })

  if (!hasRun) {
    return (
      <DatasetScopeGate
        projectId={projectId}
        title="Tabelas sem consumidor"
        description={
          'Uma tabela é considerada "sem consumidor" quando não aparece como tabela lida em ' +
          'nenhum job do BigQuery dentro do período analisado — mesmo que só tenha sido ' +
          'escrita/carregada e nunca consultada, com o custo de storage estimado de cada uma. ' +
          'Escolha os datasets e o período antes de rodar; escanear o projeto inteiro pode ser ' +
          'lento em produção.'
        }
        extraControls={<LookbackPicker value={lookbackDays} onChange={setLookbackDays} />}
        onRun={(datasets) => {
          setScopeDatasets(datasets)
          setHasRun(true)
        }}
        isRunning={orphansQuery.isFetching}
      />
    )
  }

  if (orphansQuery.isLoading) {
    return <p className="text-muted-foreground">Carregando…</p>
  }

  if (orphansQuery.isError) {
    return <ApiErrorNotice error={orphansQuery.error} />
  }

  if (!data) return null

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">Tabelas sem consumidor</h1>
          <p className="text-sm text-muted-foreground">
            {data.orphans.length} tabelas sem consumidor conhecido nos últimos {data.lookback_days}{' '}
            dias
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setHasRun(false)}>
            Nova busca
          </Button>
          <RefreshButton
            isRefreshing={orphansQuery.isFetching}
            onRefresh={() => orphansQuery.refetch()}
          />
        </div>
      </div>

      {data.warning && (
        <div className="rounded-lg border border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">
          {data.warning}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search
            size={14}
            className="-translate-y-1/2 absolute top-1/2 left-2.5 text-muted-foreground"
          />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filtrar por nome da tabela…"
            className="pl-8"
          />
        </div>
        <Select
          value={datasetFilter}
          onValueChange={(value) => setDatasetFilter(value ?? DATASET_FILTER_ALL)}
        >
          <SelectTrigger className="w-52">
            <SelectValue>
              {(value: string) => (value === DATASET_FILTER_ALL ? 'Todos os datasets' : value)}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={DATASET_FILTER_ALL}>Todos os datasets</SelectItem>
            {datasets.map((dataset) => (
              <SelectItem key={dataset} value={dataset}>
                {dataset}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <SortableTableHead
              label="Dataset"
              active={sortKey === 'dataset_id'}
              direction={sortDir}
              onClick={() => toggleSort('dataset_id')}
            />
            <SortableTableHead
              label="Tabela"
              active={sortKey === 'table_id'}
              direction={sortDir}
              onClick={() => toggleSort('table_id')}
            />
            <SortableTableHead
              label="Tamanho"
              active={sortKey === 'size_bytes'}
              direction={sortDir}
              onClick={() => toggleSort('size_bytes')}
              align="right"
            />
            <SortableTableHead
              label="Custo de storage estimado/mês"
              active={sortKey === 'estimated_monthly_storage_cost_usd'}
              direction={sortDir}
              onClick={() => toggleSort('estimated_monthly_storage_cost_usd')}
              align="right"
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleOrphans.map((orphan) => (
            <TableRow key={`${data.project_id}.${orphan.dataset_id}.${orphan.table_id}`}>
              <TableCell>
                <Link to={`/datasets/${orphan.dataset_id}`} className="hover:text-primary">
                  {data.project_id}.{orphan.dataset_id}
                </Link>
              </TableCell>
              <TableCell className="font-medium">{orphan.table_id}</TableCell>
              <TableCell className="text-right text-muted-foreground">
                {formatBytes(orphan.size_bytes)}
              </TableCell>
              <TableCell className="text-right font-medium">
                {formatUsd(orphan.estimated_monthly_storage_cost_usd)}
              </TableCell>
            </TableRow>
          ))}
          {visibleOrphans.length === 0 && (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-muted-foreground">
                {data.orphans.length === 0
                  ? 'Nenhuma tabela sem consumidor encontrada.'
                  : 'Nenhuma tabela encontrada com esse filtro.'}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
