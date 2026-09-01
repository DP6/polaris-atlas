import { Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Panel } from '@/components/Panel'
import { SlaDistributionBar } from '@/components/SlaDistributionBar'
import { SortableTableHead } from '@/components/SortableTableHead'
import { StatusBadge } from '@/components/StatusBadge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  SLA_FILL_COLOR,
  SLA_LABELS,
  SLA_ORDER,
  SLA_SEVERITY,
  SLA_SHORT_LABELS,
  SLA_TEXT_COLOR,
} from '@/features/freshness/sla'
import { cn, linkClass } from '@/lib/utils'
import type { DatasetFreshnessSummary, SLAStatus } from '@/types/freshness'

type SortKey = 'dataset_id' | 'location' | 'total_tables' | 'worst_status' | SLAStatus
type SortDirection = 'asc' | 'desc'

function compare(a: DatasetFreshnessSummary, b: DatasetFreshnessSummary, key: SortKey): number {
  if (key === 'total_tables') return a.total_tables - b.total_tables
  if (key === 'worst_status') {
    const rank = (d: DatasetFreshnessSummary) =>
      d.worst_status ? SLA_ORDER.indexOf(d.worst_status) : -1
    return rank(a) - rank(b)
  }
  if (key === 'dataset_id' || key === 'location') return a[key].localeCompare(b[key])
  // key é um SLAStatus — ordena pela contagem daquela faixa específica.
  return a[key] - b[key]
}

export function DatasetFreshnessTable({ datasets }: { datasets: DatasetFreshnessSummary[] }) {
  const [nameFilter, setNameFilter] = useState('')
  // Multi-seleção de faixas + mínimo de tabelas: um dataset só aparece
  // se a SOMA das contagens dele nas faixas selecionadas for >= o
  // mínimo. Nenhuma faixa selecionada = sem filtro (mostra tudo),
  // independente do valor de minCount.
  const [selectedBuckets, setSelectedBuckets] = useState<Set<SLAStatus>>(new Set())
  const [minCount, setMinCount] = useState(1)
  const [sortKey, setSortKey] = useState<SortKey>('worst_status')
  const [sortDir, setSortDir] = useState<SortDirection>('desc')

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((direction) => (direction === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  function toggleBucket(status: SLAStatus) {
    setSelectedBuckets((current) => {
      const next = new Set(current)
      if (next.has(status)) {
        next.delete(status)
      } else {
        next.add(status)
      }
      return next
    })
  }

  const visibleDatasets = useMemo(() => {
    const filtered = datasets.filter((dataset) => {
      const matchesName = dataset.dataset_id.toLowerCase().includes(nameFilter.toLowerCase())
      if (selectedBuckets.size === 0) return matchesName
      const matchingCount = SLA_ORDER.reduce(
        (sum, status) => sum + (selectedBuckets.has(status) ? dataset[status] : 0),
        0,
      )
      return matchesName && matchingCount >= minCount
    })
    const sign = sortDir === 'asc' ? 1 : -1
    return [...filtered].sort((a, b) => sign * compare(a, b, sortKey))
  }, [datasets, nameFilter, selectedBuckets, minCount, sortKey, sortDir])

  return (
    <Panel
      filterRow={
        <div className="flex flex-col gap-2">
          <div className="relative min-w-[220px] flex-1">
            <Search
              size={14}
              className="-translate-y-1/2 absolute top-1/2 left-2.5 text-muted-foreground"
            />
            <Input
              value={nameFilter}
              onChange={(e) => setNameFilter(e.target.value)}
              placeholder="Filtrar por dataset…"
              className="pl-8"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-muted-foreground text-xs">Faixas de SLA (uma ou mais):</span>
            {SLA_ORDER.map((status) => (
              <button
                key={status}
                type="button"
                onClick={() => toggleBucket(status)}
                className={cn(
                  'flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                  selectedBuckets.has(status)
                    ? 'border-primary bg-primary/10 text-foreground'
                    : 'border-border text-muted-foreground hover:bg-muted',
                )}
              >
                <span className={cn('size-2 rounded-full', SLA_FILL_COLOR[status])} />
                {SLA_SHORT_LABELS[status]}
              </button>
            ))}
            {selectedBuckets.size > 0 && (
              <div className="flex items-center gap-1.5">
                <Label htmlFor="freshness-min-count" className="text-muted-foreground text-xs">
                  Mínimo de tabelas nessa condição
                </Label>
                <Input
                  id="freshness-min-count"
                  type="number"
                  min={1}
                  className="h-7 w-16 text-xs"
                  value={minCount}
                  onChange={(e) => setMinCount(Number(e.target.value))}
                />
              </div>
            )}
          </div>
        </div>
      }
    >
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
              label="Região"
              active={sortKey === 'location'}
              direction={sortDir}
              onClick={() => toggleSort('location')}
            />
            <SortableTableHead
              label="Tabelas"
              active={sortKey === 'total_tables'}
              direction={sortDir}
              onClick={() => toggleSort('total_tables')}
              align="right"
            />
            <TableHead>Distribuição</TableHead>
            {SLA_ORDER.map((status) => (
              <SortableTableHead
                key={status}
                label={SLA_SHORT_LABELS[status]}
                active={sortKey === status}
                direction={sortDir}
                onClick={() => toggleSort(status)}
                align="right"
              />
            ))}
            <SortableTableHead
              label="Pior status"
              active={sortKey === 'worst_status'}
              direction={sortDir}
              onClick={() => toggleSort('worst_status')}
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleDatasets.map((dataset) => (
            <TableRow key={dataset.dataset_id}>
              <TableCell className="font-medium">
                <Link to={`/freshness/${dataset.dataset_id}`} className={linkClass}>
                  {dataset.dataset_id}
                </Link>
              </TableCell>
              <TableCell>{dataset.location}</TableCell>
              <TableCell className="text-right">{dataset.total_tables}</TableCell>
              <TableCell className="min-w-[90px]">
                <SlaDistributionBar counts={dataset} height="h-8" />
              </TableCell>
              {SLA_ORDER.map((status) => {
                const value = dataset[status]
                return (
                  <TableCell key={status} className="text-right">
                    {value > 0 ? (
                      <span className={cn('font-medium', SLA_TEXT_COLOR[status])}>{value}</span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                )
              })}
              <TableCell>
                {dataset.worst_status ? (
                  <StatusBadge status={SLA_SEVERITY[dataset.worst_status]}>
                    {SLA_LABELS[dataset.worst_status]}
                  </StatusBadge>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </TableCell>
            </TableRow>
          ))}
          {visibleDatasets.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={5 + SLA_ORDER.length}
                className="text-center text-muted-foreground"
              >
                Nenhum dataset encontrado com esse filtro.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </Panel>
  )
}
