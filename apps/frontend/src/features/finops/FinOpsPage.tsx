import { ChevronDown, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { RefreshButton } from '@/components/RefreshButton'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { WarningCallout } from '@/components/WarningCallout'
import { ColumnTypeScopePicker } from '@/features/finops/ColumnTypeScopePicker'
import {
  useEstimateColumnTypeSuggestions,
  usePartitionCandidates,
  useRunColumnTypeSuggestions,
} from '@/features/finops/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import { formatBytes, formatNumber } from '@/lib/format'
import { ApiError } from '@/lib/http-client'
import { cn } from '@/lib/utils'
import type { ColumnTypeCandidate, ColumnTypeSuggestion, PartitionCandidate } from '@/types/finops'

const PARTITION_TAB = 'partition'
const COLUMN_TYPES_TAB = 'column-types'
const DATASET_FILTER_ALL = 'all'
const ESTIMATE_FILTER_ALL = 'all'
const ESTIMATE_FILTER_WITH = 'with'
const ESTIMATE_FILTER_WITHOUT = 'without'
type EstimateFilter =
  | typeof ESTIMATE_FILTER_ALL
  | typeof ESTIMATE_FILTER_WITH
  | typeof ESTIMATE_FILTER_WITHOUT

function formatUsd(value: number): string {
  return `US$ ${value.toFixed(value < 0.01 ? 6 : 2)}`
}

function matchesSearch(datasetId: string, tableId: string, term: string): boolean {
  const needle = term.toLowerCase()
  return tableId.toLowerCase().includes(needle) || datasetId.toLowerCase().includes(needle)
}

export function FinOpsPage() {
  const { projectId } = useProjectContext()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">FinOps — Scanner de desperdício</h1>
        <p className="text-sm text-muted-foreground">
          Candidatas a particionamento e sugestões de tipo de coluna, com estimativa de custo.
          Tabelas sem uso ficou só em Governança &gt; "Tabelas sem consumidor", pra não duplicar a
          mesma informação em dois lugares.
        </p>
      </div>

      <Tabs defaultValue={PARTITION_TAB}>
        <TabsList className="w-fit">
          <TabsTrigger value={PARTITION_TAB}>Candidatas a particionamento</TabsTrigger>
          <TabsTrigger value={COLUMN_TYPES_TAB}>Tipos de coluna</TabsTrigger>
        </TabsList>

        <TabsContent value={PARTITION_TAB}>
          <PartitionCandidatesTab projectId={projectId} />
        </TabsContent>

        <TabsContent value={COLUMN_TYPES_TAB}>
          <ColumnTypesTab projectId={projectId} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

type PartitionSortKey =
  | 'table_id'
  | 'size_bytes'
  | 'observed_cost_usd_30d'
  | 'estimated_savings_usd_conservative'

function comparePartition(
  a: PartitionCandidate,
  b: PartitionCandidate,
  key: PartitionSortKey,
): number {
  if (key === 'size_bytes') return a.size_bytes - b.size_bytes
  if (key === 'observed_cost_usd_30d') return a.observed_cost_usd_30d - b.observed_cost_usd_30d
  if (key === 'estimated_savings_usd_conservative') {
    return (
      (a.estimated_savings_usd_conservative ?? -1) - (b.estimated_savings_usd_conservative ?? -1)
    )
  }
  return a.table_id.localeCompare(b.table_id)
}

function PartitionCandidatesTab({ projectId }: { projectId: string | undefined }) {
  const [selectedScope, setSelectedScope] = useState<Set<string>>(new Set())
  const [scopeOpen, setScopeOpen] = useState(true)
  const [hasRun, setHasRun] = useState(false)
  const scopeTables = Array.from(selectedScope)
  const query = usePartitionCandidates(projectId, { tables: scopeTables, enabled: hasRun })
  const data = query.data
  const [estimateFilter, setEstimateFilter] = useState<EstimateFilter>(ESTIMATE_FILTER_ALL)

  const datasets = useMemo(
    () => [...new Set(data?.candidates.map((c) => c.dataset_id) ?? [])].sort(),
    [data],
  )
  const [datasetFilter, setDatasetFilter] = useState(DATASET_FILTER_ALL)

  const {
    search,
    setSearch,
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleCandidates,
  } = useTableFilterSort<PartitionCandidate, PartitionSortKey>({
    rows: data?.candidates ?? [],
    initialSortKey: 'observed_cost_usd_30d',
    compare: comparePartition,
    matches: (candidate, term) => {
      const hasEstimate = candidate.estimated_savings_usd_conservative !== null
      const matchesEstimate =
        estimateFilter === ESTIMATE_FILTER_ALL ||
        (estimateFilter === ESTIMATE_FILTER_WITH && hasEstimate) ||
        (estimateFilter === ESTIMATE_FILTER_WITHOUT && !hasEstimate)
      const matchesDataset =
        datasetFilter === DATASET_FILTER_ALL || candidate.dataset_id === datasetFilter
      return (
        matchesSearch(candidate.dataset_id, candidate.table_id, term) &&
        matchesEstimate &&
        matchesDataset
      )
    },
  })

  return (
    <div className="mt-4 flex flex-col gap-4">
      <Collapsible open={scopeOpen} onOpenChange={setScopeOpen}>
        <CollapsibleTrigger className="flex items-center gap-1.5 text-sm font-medium hover:text-primary">
          <ChevronDown
            size={14}
            className={cn('transition-transform', !scopeOpen && '-rotate-90')}
          />
          Escopo —{' '}
          {scopeTables.length === 0
            ? 'nenhuma tabela selecionada'
            : `${scopeTables.length} tabela${scopeTables.length === 1 ? '' : 's'} selecionada${scopeTables.length === 1 ? '' : 's'}`}
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-2 flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            Sinaliza tabelas ainda não particionadas, com pelo menos 1GB, que têm ao menos uma
            coluna DATE/DATETIME/TIMESTAMP candidata a chave de partição. A economia estimada
            (quando exibida) usa o custo real observado nos últimos 30 dias de jobs que
            referenciaram a tabela — sem atividade recente, a tabela ainda aparece como candidata,
            só sem estimativa de economia.
          </p>
          <ColumnTypeScopePicker
            projectId={projectId}
            selected={selectedScope}
            onChange={setSelectedScope}
          />
          <div>
            <Button
              onClick={() => {
                setHasRun(true)
                setScopeOpen(false)
              }}
              disabled={scopeTables.length === 0 || query.isFetching}
            >
              {query.isFetching ? 'Executando…' : 'Executar'}
            </Button>
          </div>
        </CollapsibleContent>
      </Collapsible>

      {!hasRun && (
        <p className="text-sm text-muted-foreground">
          Selecione ao menos uma tabela acima e clique em "Executar".
        </p>
      )}

      {hasRun && query.isLoading && <p className="text-sm text-muted-foreground">Carregando…</p>}

      {hasRun && query.isError && <ApiErrorNotice error={query.error} />}

      {hasRun && data && (
        <>
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
            <Button variant="outline" size="sm" onClick={() => setScopeOpen(true)}>
              Alterar escopo
            </Button>
            <Select
              value={estimateFilter}
              onValueChange={(value) =>
                setEstimateFilter((value as EstimateFilter) ?? ESTIMATE_FILTER_ALL)
              }
            >
              <SelectTrigger className="w-52">
                <SelectValue>
                  {(value: EstimateFilter) =>
                    value === ESTIMATE_FILTER_WITH
                      ? 'Com estimativa de economia'
                      : value === ESTIMATE_FILTER_WITHOUT
                        ? 'Sem estimativa de economia'
                        : 'Todas'
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ESTIMATE_FILTER_ALL}>Todas</SelectItem>
                <SelectItem value={ESTIMATE_FILTER_WITH}>Com estimativa de economia</SelectItem>
                <SelectItem value={ESTIMATE_FILTER_WITHOUT}>Sem estimativa de economia</SelectItem>
              </SelectContent>
            </Select>
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
            <span className="text-sm text-muted-foreground">
              {visibleCandidates.length} de {data.candidates.length} candidata
              {data.candidates.length === 1 ? '' : 's'} — custo observado nos últimos{' '}
              {data.lookback_days} dias
            </span>
            <div className="ml-auto">
              <RefreshButton isRefreshing={query.isFetching} onRefresh={() => query.refetch()} />
            </div>
          </div>

          {data.warning && <WarningCallout>{data.warning}</WarningCallout>}

          <Table>
            <TableHeader>
              <TableRow>
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
                <TableHead>Coluna candidata</TableHead>
                <SortableTableHead
                  label="Custo observado (30d)"
                  active={sortKey === 'observed_cost_usd_30d'}
                  direction={sortDir}
                  onClick={() => toggleSort('observed_cost_usd_30d')}
                  align="right"
                />
                <SortableTableHead
                  label="Economia estimada"
                  active={sortKey === 'estimated_savings_usd_conservative'}
                  direction={sortDir}
                  onClick={() => toggleSort('estimated_savings_usd_conservative')}
                  align="right"
                />
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibleCandidates.map((candidate) => (
                <TableRow key={`${data.project_id}.${candidate.dataset_id}.${candidate.table_id}`}>
                  <TableCell>
                    <Link to={`/datasets/${candidate.dataset_id}`} className="hover:text-primary">
                      {data.project_id}.{candidate.dataset_id}
                    </Link>
                    .{candidate.table_id}
                    <span className="ml-2 text-xs text-muted-foreground">
                      {formatNumber(candidate.row_count)} linhas
                    </span>
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {formatBytes(candidate.size_bytes)}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {candidate.candidate_partition_columns.map((col) => (
                        <Badge key={col} variant="outline">
                          {col}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {formatUsd(candidate.observed_cost_usd_30d)}
                  </TableCell>
                  <TableCell className="text-right">
                    {candidate.estimated_savings_usd_conservative !== null &&
                    candidate.estimated_savings_usd_optimistic !== null ? (
                      <span
                        className="font-medium text-status-ok-foreground"
                        title={candidate.savings_disclaimer ?? undefined}
                      >
                        {formatUsd(candidate.estimated_savings_usd_conservative)} –{' '}
                        {formatUsd(candidate.estimated_savings_usd_optimistic)}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">Sem dado suficiente</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {visibleCandidates.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    {data.candidates.length === 0
                      ? 'Nenhuma candidata a particionamento encontrada.'
                      : 'Nenhuma candidata encontrada com esse filtro.'}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </>
      )}
    </div>
  )
}

type ColumnTypeSortKey = 'table_id' | 'size_bytes' | 'total_savings_usd_month'

function totalSavings(candidate: ColumnTypeCandidate): number {
  return candidate.suggestions.reduce((sum, s) => sum + s.estimated_storage_savings_usd_month, 0)
}

function compareColumnType(
  a: ColumnTypeCandidate,
  b: ColumnTypeCandidate,
  key: ColumnTypeSortKey,
): number {
  if (key === 'size_bytes') return a.size_bytes - b.size_bytes
  if (key === 'total_savings_usd_month') return totalSavings(a) - totalSavings(b)
  return a.table_id.localeCompare(b.table_id)
}

function ColumnTypeSuggestionsList({ suggestions }: { suggestions: ColumnTypeSuggestion[] }) {
  return (
    <div className="flex flex-col gap-1">
      {suggestions.map((s) => (
        <div key={s.column_name} className="flex items-center gap-1.5 text-xs">
          <span className="font-medium">{s.column_name}</span>
          <span className="text-muted-foreground">{s.current_type}</span>
          <span className="text-muted-foreground">→</span>
          <Badge variant="outline">{s.suggested_type}</Badge>
        </div>
      ))}
    </div>
  )
}

function ColumnTypesTab({ projectId }: { projectId: string | undefined }) {
  const [samplePercent, setSamplePercent] = useState(10)
  const [selectedScope, setSelectedScope] = useState<Set<string>>(new Set())
  const [scopeOpen, setScopeOpen] = useState(true)
  const estimateMutation = useEstimateColumnTypeSuggestions()
  const runMutation = useRunColumnTypeSuggestions()
  const scopeTables = Array.from(selectedScope)
  const canRun = Boolean(projectId) && scopeTables.length > 0

  const activeError = estimateMutation.error ?? runMutation.error
  const errorMessage =
    activeError instanceof ApiError
      ? activeError.message
      : activeError instanceof Error
        ? activeError.message
        : null

  const candidates = runMutation.data?.candidates ?? []

  const {
    search,
    setSearch,
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleCandidates,
  } = useTableFilterSort<ColumnTypeCandidate, ColumnTypeSortKey>({
    rows: candidates,
    initialSortKey: 'total_savings_usd_month',
    compare: compareColumnType,
    matches: (candidate, term) => matchesSearch(candidate.dataset_id, candidate.table_id, term),
  })

  return (
    <div className="mt-4 flex flex-col gap-4">
      <p className="text-xs text-muted-foreground">
        Diferente das outras abas, este scan amostra dado real via <code>TABLESAMPLE</code> e tem
        custo real de BigQuery — escolha o escopo, estime antes de escanear.
      </p>

      <Collapsible open={scopeOpen} onOpenChange={setScopeOpen}>
        <CollapsibleTrigger className="flex items-center gap-1.5 text-sm font-medium hover:text-primary">
          <ChevronDown
            size={14}
            className={cn('transition-transform', !scopeOpen && '-rotate-90')}
          />
          Escopo (datasets/tabelas) —{' '}
          {scopeTables.length === 0
            ? 'nenhuma tabela selecionada'
            : `${scopeTables.length} tabela${scopeTables.length === 1 ? '' : 's'} selecionada${scopeTables.length === 1 ? '' : 's'}`}
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-2">
          <ColumnTypeScopePicker
            projectId={projectId}
            selected={selectedScope}
            onChange={setSelectedScope}
          />
        </CollapsibleContent>
      </Collapsible>

      <div className="flex flex-wrap items-end gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="column-type-sample-percent">Amostragem (%)</Label>
          <Input
            id="column-type-sample-percent"
            type="number"
            min={1}
            max={100}
            className="w-24"
            value={samplePercent}
            onChange={(e) => setSamplePercent(Number(e.target.value))}
          />
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            disabled={estimateMutation.isPending || !canRun}
            onClick={() =>
              projectId &&
              estimateMutation.mutate({ projectId, samplePercent, tables: scopeTables })
            }
          >
            {estimateMutation.isPending ? 'Estimando…' : 'Estimar custo'}
          </Button>
          <Button
            disabled={runMutation.isPending || !canRun}
            onClick={() => {
              if (!projectId) return
              runMutation.mutate({ projectId, samplePercent, tables: scopeTables })
              setScopeOpen(false)
            }}
          >
            {runMutation.isPending ? 'Escaneando…' : 'Escanear'}
          </Button>
        </div>
      </div>

      {errorMessage && <p className="text-sm text-status-error-foreground">{errorMessage}</p>}

      {estimateMutation.data && !runMutation.data && (
        <div className="flex flex-wrap gap-6 rounded-lg border border-border bg-card p-4 text-sm">
          <div>
            <p className="text-xs text-muted-foreground uppercase">Tabelas elegíveis</p>
            <p className="text-lg font-bold">{estimateMutation.data.tables_scanned}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase">Views puladas</p>
            <p className="text-lg font-bold">{estimateMutation.data.tables_skipped_view}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase">Bytes estimados</p>
            <p className="text-lg font-bold">{estimateMutation.data.estimated_bytes_human}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase">Custo estimado</p>
            <p className="text-lg font-bold">
              US$ {estimateMutation.data.estimated_cost_usd.toFixed(8)}
            </p>
          </div>
        </div>
      )}

      {runMutation.data && (
        <>
          {runMutation.data.warning && <WarningCallout>{runMutation.data.warning}</WarningCallout>}

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
            <span className="text-sm text-muted-foreground">
              {visibleCandidates.length} de {candidates.length} tabela
              {candidates.length === 1 ? '' : 's'} com sugestão — {runMutation.data.tables_scanned}{' '}
              escaneadas, {runMutation.data.tables_skipped_view} views puladas
            </span>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
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
                <TableHead>Tipo atual → sugerido</TableHead>
                <SortableTableHead
                  label="Economia estimada/mês"
                  active={sortKey === 'total_savings_usd_month'}
                  direction={sortDir}
                  onClick={() => toggleSort('total_savings_usd_month')}
                  align="right"
                />
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibleCandidates.map((candidate) => (
                <TableRow key={`${projectId}.${candidate.dataset_id}.${candidate.table_id}`}>
                  <TableCell>
                    <Link to={`/datasets/${candidate.dataset_id}`} className="hover:text-primary">
                      {projectId}.{candidate.dataset_id}
                    </Link>
                    .{candidate.table_id}
                    {candidate.row_count !== null && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        {formatNumber(candidate.row_count)} linhas
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {formatBytes(candidate.size_bytes)}
                  </TableCell>
                  <TableCell>
                    <ColumnTypeSuggestionsList suggestions={candidate.suggestions} />
                  </TableCell>
                  <TableCell className="text-right font-medium text-status-ok-foreground">
                    {formatUsd(totalSavings(candidate))}
                  </TableCell>
                </TableRow>
              ))}
              {visibleCandidates.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    {candidates.length === 0
                      ? 'Nenhuma sugestão de tipo de coluna encontrada.'
                      : 'Nenhuma tabela encontrada com esse filtro.'}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </>
      )}
    </div>
  )
}
