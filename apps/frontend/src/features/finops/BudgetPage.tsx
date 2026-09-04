import {
  Calendar,
  ChevronDown,
  ChevronUp,
  DollarSign,
  HardDrive,
  Target,
  TrendingUp,
} from 'lucide-react'
import { Fragment, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from 'recharts'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { ChoiceToggle } from '@/components/ChoiceToggle'
import { ComboChart } from '@/components/ComboChart'
import { LoadingState } from '@/components/LoadingState'
import { LookbackPicker } from '@/components/LookbackPicker'
import { MetricGrid, MetricTile } from '@/components/MetricTile'
import { PageHeader } from '@/components/PageHeader'
import { RefreshButton } from '@/components/RefreshButton'
import { SortableTableHead } from '@/components/SortableTableHead'
import { SqlPreview } from '@/components/SqlPreview'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { WarningCallout } from '@/components/WarningCallout'
import { useBudget, useBudgets, useCostSeries } from '@/features/finops/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import { formatBytes, formatDate, formatNumber, formatUsd } from '@/lib/format'
import { cn, linkClass } from '@/lib/utils'
import type {
  BudgetEntry,
  BudgetGroupBy,
  CostGroup,
  CostlyQuery,
  CostProjection,
  CostType,
} from '@/types/finops'

const COST_TAB = 'cost'
const QUERIES_TAB = 'queries'

const GROUP_BY_OPTIONS: { value: BudgetGroupBy; label: string }[] = [
  { value: 'table', label: 'Tabela' },
  { value: 'dataset', label: 'Dataset' },
  { value: 'user', label: 'Usuário' },
  { value: 'day', label: 'Dia' },
  { value: 'month', label: 'Mês' },
  { value: 'year', label: 'Ano' },
]

const COST_TYPE_OPTIONS: { value: CostType; label: string }[] = [
  { value: 'all', label: 'Tudo' },
  { value: 'query', label: 'Query' },
  { value: 'storage', label: 'Storage' },
]

const LIMIT_OPTIONS = [5, 10, 20, 50] as const
const LOOKBACK_OPTIONS = [7, 15, 30] as const

const GROUP_KEY_COLUMN_LABEL: Record<BudgetGroupBy, string> = {
  table: 'Tabela',
  dataset: 'Dataset',
  user: 'Usuário',
  day: 'Dia',
  month: 'Mês',
  year: 'Ano',
}

// Só table/dataset suportam split de storage (v1.12) — outras agregações
// (usuário/dia/mês/ano) não têm um "dono" de bytes de storage.
function supportsStorageSplit(groupBy: BudgetGroupBy): boolean {
  return groupBy === 'table' || groupBy === 'dataset'
}

type GroupSortKey =
  | 'key'
  | 'cost_usd'
  | 'billed_bytes'
  | 'job_count'
  | 'storage_cost_usd'
  | 'total_cost_usd'

function compareGroup(a: CostGroup, b: CostGroup, key: GroupSortKey): number {
  if (key === 'key') return a.key.localeCompare(b.key)
  return (a[key] ?? 0) - (b[key] ?? 0)
}

type QuerySortKey = 'executed_at' | 'cost_usd' | 'billed_bytes'

function compareQuery(a: CostlyQuery, b: CostlyQuery, key: QuerySortKey): number {
  if (key === 'cost_usd') return a.cost_usd - b.cost_usd
  if (key === 'billed_bytes') return a.billed_bytes - b.billed_bytes
  return a.executed_at.localeCompare(b.executed_at)
}

export function BudgetPage() {
  const { projectId } = useProjectContext()
  const [groupBy, setGroupBy] = useState<BudgetGroupBy>('table')
  const [limit, setLimit] = useState(10)
  const [lookbackDays, setLookbackDays] = useState(30)
  const [hasRun, setHasRun] = useState(false)
  const includeStorage = supportsStorageSplit(groupBy)
  const query = useBudget(
    projectId,
    groupBy,
    limit,
    lookbackDays,
    hasRun,
    undefined,
    includeStorage,
  )
  const budgetsQuery = useBudgets(projectId)
  const data = query.data

  if (!hasRun) {
    return (
      <div className="flex flex-col gap-4">
        <PageHeader
          title="FinOps — Detalhamento de custo"
          description="Estima o custo do período escolhido via audit logs de jobs do BigQuery (bytes cobrados) + preço público on-demand — sem depender do Cloud Billing Export. Agrupando por tabela ou dataset, mostra também o split de storage e a comparação com a meta cadastrada. A janela é limitada a 31 dias (retenção do cache de audit log)."
        />

        <div className="flex flex-col gap-4 rounded-lg border border-border p-4">
          <LookbackPicker
            options={LOOKBACK_OPTIONS}
            max={31}
            label="Janela — últimos N dias"
            value={lookbackDays}
            onChange={setLookbackDays}
          />

          <div>
            <span className="mb-1.5 block text-xs font-medium text-muted-foreground">
              Agrupar por
            </span>
            <ChoiceToggle
              aria-label="Agrupar por"
              options={GROUP_BY_OPTIONS}
              value={groupBy}
              onChange={setGroupBy}
            />
          </div>

          <div>
            <span className="mb-1.5 block text-xs font-medium text-muted-foreground">
              Limite de itens
            </span>
            <Select
              value={String(limit)}
              onValueChange={(value) => value && setLimit(Number(value))}
            >
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LIMIT_OPTIONS.map((option) => (
                  <SelectItem key={option} value={String(option)}>
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Button onClick={() => setHasRun(true)} disabled={query.isFetching}>
              {query.isFetching ? 'Executando…' : 'Executar'}
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="FinOps — Detalhamento de custo"
        description={`Custo por agrupamento e queries mais caras dos últimos ${data?.lookback_days ?? lookbackDays} dias — estimativa baseada em bytes escaneados, cobrança on-demand.`}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => setHasRun(false)}>
              Nova busca
            </Button>
            <RefreshButton isRefreshing={query.isFetching} onRefresh={() => query.refetch()} />
          </>
        }
      />

      {query.isLoading && <LoadingState />}
      {query.isError && <ApiErrorNotice error={query.error} />}

      {data && (
        <>
          {data.warning && <WarningCallout>{data.warning}</WarningCallout>}

          <MetricGrid>
            {[
              {
                label: 'Custo até agora',
                value: formatUsd(data.projection.cost_so_far_usd),
                icon: <DollarSign size={14} />,
              },
              {
                label: 'Média diária',
                value: formatUsd(data.projection.daily_average_usd),
                icon: <TrendingUp size={14} />,
              },
              {
                label: 'Projeção mensal',
                value: formatUsd(data.projection.projected_month_total_usd),
                icon: <Target size={14} />,
              },
              {
                label: 'Janela analisada',
                value: `${data.lookback_days} dias`,
                icon: <Calendar size={14} />,
              },
            ].map((item) => (
              <MetricTile key={item.label} label={item.label} value={item.value} icon={item.icon} />
            ))}
          </MetricGrid>

          <Tabs defaultValue={COST_TAB}>
            <TabsList className="w-fit">
              <TabsTrigger value={COST_TAB}>Custo por agrupamento</TabsTrigger>
              <TabsTrigger value={QUERIES_TAB}>Queries mais caras</TabsTrigger>
            </TabsList>

            <TabsContent value={COST_TAB}>
              <CostByGroupTab
                projectId={data.project_id}
                groups={data.groups}
                totalCostUsd={data.total_cost_usd}
                groupBy={groupBy}
                onGroupByChange={setGroupBy}
                projection={data.projection}
                budgets={budgetsQuery.data?.budgets ?? []}
              />
            </TabsContent>

            <TabsContent value={QUERIES_TAB}>
              <QueriesTab queries={data.top_queries} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  )
}

// Link pro dataset dono do grupo — funciona tanto pra group_by=table
// (key "project.dataset.table") quanto group_by=dataset (key
// "project.dataset", sem terceiro segmento): rest.split('.')[0] é o
// dataset_id nos dois casos. `label` (rest inteiro) também é o formato
// que o filtro datasets/tables de cost-series espera (sem o project_id à
// frente) — reaproveitado pro drill-down (v1.12).
function groupKeyLink(projectId: string, key: string): { datasetId: string; label: string } | null {
  if (!key.startsWith(`${projectId}.`)) return null
  const rest = key.slice(projectId.length + 1)
  const [datasetId] = rest.split('.')
  if (!datasetId) return null
  return { datasetId, label: rest }
}

// Meta cadastrada (BudgetConfigDialog) que corresponde a este grupo —
// escopo table casa por dataset_id+table_id, escopo dataset só por
// dataset_id. `label` vem de groupKeyLink ("dataset.table" ou "dataset").
function findBudgetTarget(
  budgets: BudgetEntry[],
  groupBy: BudgetGroupBy,
  label: string,
): BudgetEntry | undefined {
  if (groupBy === 'table') {
    const [datasetId, tableId] = label.split('.')
    return budgets.find(
      (b) => b.scope === 'table' && b.dataset_id === datasetId && b.table_id === tableId,
    )
  }
  if (groupBy === 'dataset') {
    return budgets.find((b) => b.scope === 'dataset' && b.dataset_id === label)
  }
  return undefined
}

function CostByGroupTab({
  projectId,
  groups,
  totalCostUsd,
  groupBy,
  onGroupByChange,
  projection,
  budgets,
}: {
  projectId: string
  groups: CostGroup[]
  totalCostUsd: number
  groupBy: BudgetGroupBy
  onGroupByChange: (value: BudgetGroupBy) => void
  projection: CostProjection
  budgets: BudgetEntry[]
}) {
  const [costType, setCostType] = useState<CostType>('all')
  const [expandedKey, setExpandedKey] = useState<string | null>(null)
  const hasStorage = supportsStorageSplit(groupBy) && groups.some((g) => g.storage_cost_usd != null)

  const {
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleGroups,
  } = useTableFilterSort<CostGroup, GroupSortKey>({
    rows: groups,
    initialSortKey: 'cost_usd',
    compare: compareGroup,
    matches: () => true,
  })

  // Só faz sentido com groupBy=day — groups[].key vira "YYYY-MM-DD",
  // ordenável direto como string. Só dias com atividade aparecem na
  // resposta (API não zera dias sem custo); sem preenchimento de gap,
  // mantém simples — o acumulado sobe em degraus nos dias com dado.
  let cumulativeChartData: { date: string; dia: number; acumulado: number; projecao: number }[] = []
  if (groupBy === 'day') {
    let running = 0
    cumulativeChartData = [...groups]
      .sort((a, b) => a.key.localeCompare(b.key))
      .map((group, index) => {
        running += group.cost_usd
        return {
          date: group.key.slice(5), // "MM-DD", ano é sempre o mês corrente
          dia: group.cost_usd,
          acumulado: running,
          projecao: projection.daily_average_usd * (index + 1),
        }
      })
  }

  // Top 10 por custo total (query+storage) pro ranking visual — só quando
  // a agregação suporta storage e a resposta trouxe o split (v1.12).
  const rankingChartData = hasStorage
    ? [...groups]
        .sort((a, b) => (b.total_cost_usd ?? b.cost_usd) - (a.total_cost_usd ?? a.cost_usd))
        .slice(0, 10)
        .map((g) => ({
          label: groupKeyLink(projectId, g.key)?.label ?? g.key,
          query: g.cost_usd,
          storage: g.storage_cost_usd ?? 0,
        }))
    : []

  return (
    <div className="mt-4 flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">
          {GROUP_BY_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => onGroupByChange(option.value)}
              className={cn(
                'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                groupBy === option.value
                  ? 'border-primary bg-primary/10 text-foreground'
                  : 'border-border text-muted-foreground hover:bg-muted',
              )}
            >
              {option.label}
            </button>
          ))}
        </div>

        {hasStorage && (
          <div className="flex flex-col gap-1">
            <span className="text-label text-muted-foreground">Tipo de custo</span>
            <ChoiceToggle
              aria-label="Tipo de custo"
              options={COST_TYPE_OPTIONS}
              value={costType}
              onChange={setCostType}
              size="sm"
            />
          </div>
        )}
      </div>

      {groupBy === 'day' && cumulativeChartData.length > 0 && (
        <div className="h-56 w-full shrink-0 rounded-lg border border-border bg-card p-4">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={cumulativeChartData}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis
                yAxisId="daily"
                tick={{ fontSize: 11 }}
                width={48}
                tickFormatter={(v) => formatUsd(v)}
              />
              <YAxis
                yAxisId="cumulative"
                orientation="right"
                tick={{ fontSize: 11 }}
                width={48}
                tickFormatter={(v) => formatUsd(v)}
              />
              <RechartsTooltip formatter={(value) => formatUsd(Number(value))} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar
                yAxisId="daily"
                dataKey="dia"
                name="Custo do dia"
                fill="var(--color-accent-blue)"
                barSize={16}
              />
              <Line
                yAxisId="cumulative"
                type="monotone"
                dataKey="acumulado"
                name="Custo acumulado"
                stroke="var(--color-primary)"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
              <Line
                yAxisId="cumulative"
                type="monotone"
                dataKey="projecao"
                name="Projeção"
                stroke="var(--color-muted-foreground)"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {hasStorage && rankingChartData.length > 0 && (
        <div className="h-64 w-full shrink-0 rounded-lg border border-border bg-card p-4">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rankingChartData}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10 }}
                interval={0}
                angle={-25}
                textAnchor="end"
                height={60}
              />
              <YAxis tick={{ fontSize: 11 }} width={56} tickFormatter={(v) => formatUsd(v)} />
              <RechartsTooltip formatter={(value) => formatUsd(Number(value))} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {costType !== 'storage' && (
                <Bar dataKey="query" name="Query" stackId="cost" fill="var(--color-status-info)" />
              )}
              {costType !== 'query' && (
                <Bar
                  dataKey="storage"
                  name="Storage"
                  stackId="cost"
                  fill="var(--color-accent-blue)"
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <SortableTableHead
              label={GROUP_KEY_COLUMN_LABEL[groupBy]}
              active={sortKey === 'key'}
              direction={sortDir}
              onClick={() => toggleSort('key')}
            />
            <SortableTableHead
              label="Bytes cobrados"
              active={sortKey === 'billed_bytes'}
              direction={sortDir}
              onClick={() => toggleSort('billed_bytes')}
              align="right"
            />
            <SortableTableHead
              label="Jobs"
              active={sortKey === 'job_count'}
              direction={sortDir}
              onClick={() => toggleSort('job_count')}
              align="right"
            />
            {hasStorage ? (
              <>
                <SortableTableHead
                  label="Custo query"
                  active={sortKey === 'cost_usd'}
                  direction={sortDir}
                  onClick={() => toggleSort('cost_usd')}
                  align="right"
                />
                <SortableTableHead
                  label="Custo storage"
                  active={sortKey === 'storage_cost_usd'}
                  direction={sortDir}
                  onClick={() => toggleSort('storage_cost_usd')}
                  align="right"
                />
                <SortableTableHead
                  label="Custo total"
                  active={sortKey === 'total_cost_usd'}
                  direction={sortDir}
                  onClick={() => toggleSort('total_cost_usd')}
                  align="right"
                />
                <TableHead>Meta</TableHead>
              </>
            ) : (
              <SortableTableHead
                label="Custo"
                active={sortKey === 'cost_usd'}
                direction={sortDir}
                onClick={() => toggleSort('cost_usd')}
                align="right"
              />
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleGroups.map((group) => {
            const link =
              groupBy === 'table' || groupBy === 'dataset'
                ? groupKeyLink(projectId, group.key)
                : null
            const target = link ? findBudgetTarget(budgets, groupBy, link.label) : undefined
            const totalForGroup = group.total_cost_usd ?? group.cost_usd
            const isOverBudget = target != null && totalForGroup > target.amount_usd
            const isExpanded = expandedKey === group.key

            return (
              <Fragment key={group.key}>
                <TableRow
                  className={hasStorage && link ? 'cursor-pointer' : undefined}
                  onClick={
                    hasStorage && link
                      ? () => setExpandedKey(isExpanded ? null : group.key)
                      : undefined
                  }
                >
                  <TableCell className="font-medium">
                    <span className="inline-flex items-center gap-1.5">
                      {hasStorage && link && (
                        <ChevronDown
                          size={13}
                          className={cn(
                            'shrink-0 transition-transform',
                            !isExpanded && '-rotate-90',
                          )}
                        />
                      )}
                      {link ? (
                        <Link
                          to={`/datasets/${link.datasetId}`}
                          className={linkClass}
                          onClick={(e) => e.stopPropagation()}
                        >
                          {link.label}
                        </Link>
                      ) : (
                        group.key
                      )}
                    </span>
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {formatBytes(group.billed_bytes)}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {formatNumber(group.job_count)}
                  </TableCell>
                  {hasStorage ? (
                    <>
                      <TableCell className="text-right text-muted-foreground">
                        {formatUsd(group.cost_usd)}
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground">
                        {formatUsd(group.storage_cost_usd ?? 0)}
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {formatUsd(totalForGroup)}
                      </TableCell>
                      <TableCell>
                        {target ? (
                          <Badge variant={isOverBudget ? 'error' : 'success'}>
                            {isOverBudget ? 'Acima da meta' : 'Dentro da meta'}
                            {' · '}
                            {formatUsd(target.amount_usd)}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    </>
                  ) : (
                    <TableCell className="text-right font-medium">
                      {formatUsd(group.cost_usd)}
                    </TableCell>
                  )}
                </TableRow>
                {isExpanded && link && (
                  <TableRow>
                    <TableCell colSpan={7} className="bg-muted/40">
                      <GroupDrillDown
                        projectId={projectId}
                        groupBy={groupBy}
                        groupLabel={link.label}
                      />
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            )
          })}
          {visibleGroups.length === 0 && (
            <TableRow>
              <TableCell colSpan={hasStorage ? 7 : 4} className="text-center text-muted-foreground">
                Nenhum custo registrado no período.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
        {visibleGroups.length > 0 && (
          <TableFooter>
            <TableRow>
              <TableCell>Total</TableCell>
              <TableCell />
              <TableCell />
              {hasStorage ? (
                <>
                  <TableCell className="text-right">{formatUsd(totalCostUsd)}</TableCell>
                  <TableCell className="text-right">
                    {formatUsd(groups.reduce((sum, g) => sum + (g.storage_cost_usd ?? 0), 0))}
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {formatUsd(
                      totalCostUsd + groups.reduce((sum, g) => sum + (g.storage_cost_usd ?? 0), 0),
                    )}
                  </TableCell>
                  <TableCell />
                </>
              ) : (
                <TableCell className="text-right">{formatUsd(totalCostUsd)}</TableCell>
              )}
            </TableRow>
          </TableFooter>
        )}
      </Table>
    </div>
  )
}

// Drill-down por tabela/dataset (v1.12) — busca sob demanda (só quando a
// linha está expandida) a série diária filtrada pra essa chave, via o
// mesmo cost-series já usado na Visão Geral. `groupLabel` já vem no
// formato "dataset.table"/"dataset" que o filtro espera (sem project_id).
function GroupDrillDown({
  projectId,
  groupBy,
  groupLabel,
}: {
  projectId: string
  groupBy: BudgetGroupBy
  groupLabel: string
}) {
  const seriesQuery = useCostSeries(projectId, {
    granularity: 'day',
    tables: groupBy === 'table' ? [groupLabel] : undefined,
    datasets: groupBy === 'dataset' ? [groupLabel] : undefined,
  })

  if (seriesQuery.isLoading) return <LoadingState />
  if (seriesQuery.isError) return <ApiErrorNotice error={seriesQuery.error} />

  const points = seriesQuery.data?.points ?? []
  if (points.length === 0 || points.every((p) => p.total_cost_usd === 0)) {
    return (
      <p className="py-2 text-body text-muted-foreground">
        Sem custo diário registrado pra {groupLabel} na janela.
      </p>
    )
  }

  return (
    <div className="py-2">
      <p className="mb-2 flex items-center gap-1.5 text-label text-muted-foreground">
        <HardDrive size={13} /> Série diária — {groupLabel}
      </p>
      <ComboChart
        data={points.map((p) => ({
          period: p.period,
          query: p.query_cost_usd,
          storage: p.storage_cost_usd,
        }))}
        xKey="period"
        bar={{ key: 'query', name: 'Query', color: 'var(--color-status-info)' }}
        lines={[{ key: 'storage', name: 'Storage', color: 'var(--color-accent-blue)' }]}
        height={180}
        valueFormat={formatUsd}
      />
    </div>
  )
}

function QueriesTab({ queries }: { queries: CostlyQuery[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  function toggleExpanded(jobId: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(jobId)) {
        next.delete(jobId)
      } else {
        next.add(jobId)
      }
      return next
    })
  }

  const {
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleQueries,
  } = useTableFilterSort<CostlyQuery, QuerySortKey>({
    rows: queries,
    initialSortKey: 'cost_usd',
    compare: compareQuery,
    matches: () => true,
  })

  return (
    <div className="mt-4 flex flex-col gap-4">
      <Table>
        <TableHeader>
          <TableRow>
            <SortableTableHead
              label="Custo"
              active={sortKey === 'cost_usd'}
              direction={sortDir}
              onClick={() => toggleSort('cost_usd')}
              align="right"
            />
            <TableHead>Usuário</TableHead>
            <SortableTableHead
              label="Data"
              active={sortKey === 'executed_at'}
              direction={sortDir}
              onClick={() => toggleSort('executed_at')}
            />
            <TableHead>Tabelas</TableHead>
            <SortableTableHead
              label="Bytes cobrados"
              active={sortKey === 'billed_bytes'}
              direction={sortDir}
              onClick={() => toggleSort('billed_bytes')}
              align="right"
            />
            <TableHead>Query</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleQueries.map((q) => {
            const isExpanded = expanded.has(q.job_id)
            return (
              <Fragment key={q.job_id}>
                <TableRow>
                  <TableCell className="text-right font-medium">{formatUsd(q.cost_usd)}</TableCell>
                  <TableCell>{q.principal_email}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(q.executed_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex max-w-[220px] flex-wrap gap-1">
                      {q.tables.map((t) => (
                        <Badge key={t} variant="outline" className="truncate" title={t}>
                          {t.split('.').slice(1).join('.')}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {formatBytes(q.billed_bytes)}
                  </TableCell>
                  <TableCell>
                    {q.query_text ? (
                      <Button size="sm" variant="ghost" onClick={() => toggleExpanded(q.job_id)}>
                        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        {isExpanded ? 'Ocultar query' : 'Ver query'}
                      </Button>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                </TableRow>
                {isExpanded && q.query_text && (
                  <TableRow>
                    <TableCell colSpan={6} className="bg-background/50">
                      <SqlPreview sql={q.query_text} defaultOpen />
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            )
          })}
          {visibleQueries.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-muted-foreground">
                Nenhuma query com custo no período.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
