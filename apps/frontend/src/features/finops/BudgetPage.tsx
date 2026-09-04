import { Calendar, ChevronDown, ChevronUp, DollarSign, Target, TrendingUp } from 'lucide-react'
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
import { useBudget } from '@/features/finops/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import { formatBytes, formatDate, formatNumber, formatUsd } from '@/lib/format'
import { cn, linkClass } from '@/lib/utils'
import type { BudgetGroupBy, CostGroup, CostlyQuery, CostProjection } from '@/types/finops'

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

type GroupSortKey = 'key' | 'cost_usd' | 'billed_bytes' | 'job_count'

function compareGroup(a: CostGroup, b: CostGroup, key: GroupSortKey): number {
  if (key === 'key') return a.key.localeCompare(b.key)
  return a[key] - b[key]
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
  const query = useBudget(projectId, groupBy, limit, lookbackDays, hasRun)
  const data = query.data

  if (!hasRun) {
    return (
      <div className="flex flex-col gap-4">
        <PageHeader
          title="FinOps — Budget de custo"
          description="Estima o custo do período escolhido via audit logs de jobs do BigQuery (bytes cobrados) + preço público on-demand — sem depender do Cloud Billing Export. A janela é limitada a 31 dias (retenção do cache de audit log)."
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
        title="FinOps — Budget de custo"
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
// dataset_id nos dois casos.
function groupKeyLink(projectId: string, key: string): { datasetId: string; label: string } | null {
  if (!key.startsWith(`${projectId}.`)) return null
  const rest = key.slice(projectId.length + 1)
  const [datasetId] = rest.split('.')
  if (!datasetId) return null
  return { datasetId, label: rest }
}

function CostByGroupTab({
  projectId,
  groups,
  totalCostUsd,
  groupBy,
  onGroupByChange,
  projection,
}: {
  projectId: string
  groups: CostGroup[]
  totalCostUsd: number
  groupBy: BudgetGroupBy
  onGroupByChange: (value: BudgetGroupBy) => void
  projection: CostProjection
}) {
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

  return (
    <div className="mt-4 flex flex-col gap-4">
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
            <SortableTableHead
              label="Custo"
              active={sortKey === 'cost_usd'}
              direction={sortDir}
              onClick={() => toggleSort('cost_usd')}
              align="right"
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleGroups.map((group) => {
            const link =
              groupBy === 'table' || groupBy === 'dataset'
                ? groupKeyLink(projectId, group.key)
                : null
            return (
              <TableRow key={group.key}>
                <TableCell className="font-medium">
                  {link ? (
                    <Link to={`/datasets/${link.datasetId}`} className={linkClass}>
                      {link.label}
                    </Link>
                  ) : (
                    group.key
                  )}
                </TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {formatBytes(group.billed_bytes)}
                </TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {formatNumber(group.job_count)}
                </TableCell>
                <TableCell className="text-right font-medium">
                  {formatUsd(group.cost_usd)}
                </TableCell>
              </TableRow>
            )
          })}
          {visibleGroups.length === 0 && (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-muted-foreground">
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
              <TableCell className="text-right">{formatUsd(totalCostUsd)}</TableCell>
            </TableRow>
          </TableFooter>
        )}
      </Table>
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
