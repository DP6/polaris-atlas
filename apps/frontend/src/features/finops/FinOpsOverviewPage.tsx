import { ChevronDown, DollarSign, Gauge, Search, Target, TrendingUp } from 'lucide-react'
import { Fragment, type ReactNode, useMemo, useState } from 'react'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { CacheStalenessBadge } from '@/components/CacheStalenessBadge'
import { ChoiceToggle } from '@/components/ChoiceToggle'
import { ComboChart } from '@/components/ComboChart'
import { CompositeScoreRing } from '@/components/CompositeScoreRing'
import { LoadingState } from '@/components/LoadingState'
import { OptionCard, OptionCardGrid } from '@/components/OptionCard'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { RefreshButton } from '@/components/RefreshButton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { WarningCallout } from '@/components/WarningCallout'
import { BudgetConfigDialog } from '@/features/finops/BudgetConfigDialog'
import { useBudget, useCostSeries, useTableScores } from '@/features/finops/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { formatBytes, formatUsd } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { CostSeriesGranularity, CostType, TableScore } from '@/types/finops'

const GRANULARITY_OPTIONS: { value: CostSeriesGranularity; label: string }[] = [
  { value: 'day', label: 'Dia' },
  { value: 'month', label: 'Mês' },
]
const COST_TYPE_OPTIONS: { value: CostType; label: string }[] = [
  { value: 'all', label: 'Tudo' },
  { value: 'query', label: 'Query' },
  { value: 'storage', label: 'Storage' },
]

function pickValue(
  point: { query_cost_usd: number; storage_cost_usd: number; total_cost_usd: number },
  costType: CostType,
): number {
  if (costType === 'query') return point.query_cost_usd
  if (costType === 'storage') return point.storage_cost_usd
  return point.total_cost_usd
}

function scoreBand(score: number): string {
  if (score >= 80) return 'var(--color-status-ok)'
  if (score >= 50) return 'var(--color-status-warn)'
  return 'var(--color-status-error)'
}

export function FinOpsOverviewPage() {
  const { projectId } = useProjectContext()
  const [granularity, setGranularity] = useState<CostSeriesGranularity>('day')
  const [costType, setCostType] = useState<CostType>('all')
  const [configOpen, setConfigOpen] = useState(false)

  const budgetQuery = useBudget(projectId)
  const seriesQuery = useCostSeries(projectId, { granularity, costType })
  const scoresQuery = useTableScores(projectId)

  const chartData = useMemo(() => {
    const points = seriesQuery.data?.points ?? []
    let running = 0
    return points.map((p) => {
      const value = pickValue(p, costType)
      running += value
      return { period: p.period, value, accumulated: running }
    })
  }, [seriesQuery.data, costType])

  if (budgetQuery.isLoading || scoresQuery.isLoading) return <LoadingState />
  if (budgetQuery.isError) return <ApiErrorNotice error={budgetQuery.error} />
  if (scoresQuery.isError) return <ApiErrorNotice error={scoresQuery.error} />

  const budget = budgetQuery.data
  const scores = scoresQuery.data
  const lowScoreCount = scores?.tables.filter((t) => t.score < 50).length ?? 0
  const projectedOverBudget =
    budget?.budget_target_usd != null &&
    budget.projection.projected_month_total_usd > budget.budget_target_usd

  const refreshing = budgetQuery.isFetching || seriesQuery.isFetching || scoresQuery.isFetching

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        showBrandBars
        title="FinOps — Visão geral"
        description="Gasto do mês, projeção, eficiência de custo e as funções do domínio."
        actions={
          <RefreshButton
            isRefreshing={refreshing}
            onRefresh={() => {
              budgetQuery.refetch()
              seriesQuery.refetch()
              scoresQuery.refetch()
            }}
          />
        }
      />

      {budget?.warning && <WarningCallout>{budget.warning}</WarningCallout>}

      <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(13rem,1fr))]">
        <BigNumber
          icon={<DollarSign size={14} />}
          label="Gasto no mês"
          value={budget ? formatUsd(budget.total_cost_usd) : '—'}
        />
        <BigNumber
          icon={<Target size={14} />}
          label="Meta mensal"
          value={budget?.budget_target_usd != null ? formatUsd(budget.budget_target_usd) : '—'}
        />
        <BigNumber
          icon={<TrendingUp size={14} />}
          label="Projeção do mês"
          value={budget ? formatUsd(budget.projection.projected_month_total_usd) : '—'}
          alert={projectedOverBudget}
        />
        <BigNumber
          icon={<Gauge size={14} />}
          label="Tabelas de baixo score"
          value={String(lowScoreCount)}
          alert={lowScoreCount > 0}
        />
      </div>

      <Panel
        title="Custo ao longo do período"
        subtitle={
          seriesQuery.data && !seriesQuery.data.storage_available && costType !== 'query'
            ? 'Linha de storage indisponível neste projeto — só o custo de query está no gráfico.'
            : undefined
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <ChoiceToggle
              aria-label="Granularidade"
              options={GRANULARITY_OPTIONS}
              value={granularity}
              onChange={setGranularity}
            />
            <ChoiceToggle
              aria-label="Tipo de custo"
              options={COST_TYPE_OPTIONS}
              value={costType}
              onChange={setCostType}
            />
          </div>
        }
      >
        {seriesQuery.isLoading ? (
          <LoadingState />
        ) : seriesQuery.isError ? (
          <ApiErrorNotice error={seriesQuery.error} />
        ) : (
          <>
            {seriesQuery.data?.warning && (
              <WarningCallout variant="info">{seriesQuery.data.warning}</WarningCallout>
            )}
            <ComboChart
              data={chartData}
              xKey="period"
              bar={{ key: 'value', name: 'Por período', color: 'var(--color-status-info)' }}
              lines={[
                {
                  key: 'accumulated',
                  name: 'Acumulado',
                  color: 'var(--color-primary)',
                },
              ]}
              refLine={
                budget?.budget_target_usd != null
                  ? { y: budget.budget_target_usd, label: 'Meta' }
                  : undefined
              }
              height={260}
              valueFormat={formatUsd}
            />
            <p className="mt-2 flex flex-wrap items-center gap-2 text-muted-foreground text-xs">
              Custo estimado (on-demand).{' '}
              <CacheStalenessBadge cacheUpdatedAt={budget?.cache_updated_at ?? null} />
            </p>
          </>
        )}
      </Panel>

      <div className="grid gap-4 lg:grid-cols-[auto_1fr] [&>*]:min-w-0">
        <Panel title="Eficiência de custo" as="h3">
          <CompositeScoreRing
            score={scores?.project_efficiency_score ?? 100}
            caption="do projeto"
          />
        </Panel>

        <Panel
          title="Top ofensores"
          as="h3"
          subtitle="Piores scores de eficiência — clique numa linha pra ver a decomposição."
        >
          <TopOffendersTable tables={scores?.tables ?? []} />
        </Panel>
      </div>

      <OptionCardGrid>
        <OptionCard
          icon={<Search size={18} />}
          title="Scanner de desperdício"
          description="Candidatas a particionamento e sugestões de tipo de coluna, com estimativa de custo."
          to="/finops/scanner"
        />
        <OptionCard
          icon={<TrendingUp size={18} />}
          title="Budget de custo"
          description="Custo agrupável (tabela / dataset / usuário / dia), queries mais caras e projeção do mês."
          to="/finops/budget"
        />
        <OptionCard
          icon={<Target size={18} />}
          title="Configurar budget"
          description="Cadastrar metas de custo mensais por projeto, dataset ou tabela."
          onClick={() => setConfigOpen(true)}
        />
      </OptionCardGrid>

      <BudgetConfigDialog projectId={projectId} open={configOpen} onOpenChange={setConfigOpen} />
    </div>
  )
}

function BigNumber({
  icon,
  label,
  value,
  alert,
}: {
  icon: ReactNode
  label: string
  value: string
  alert?: boolean
}) {
  return (
    <div
      className={cn(
        'dp6-hoverable rounded-lg border bg-card p-4',
        alert ? 'border-status-error' : 'border-border',
      )}
    >
      <span
        aria-hidden="true"
        className="mb-2.5 inline-flex size-6 items-center justify-center rounded-md border border-primary/25 bg-primary/10 text-primary [&_svg]:size-3.5"
      >
        {icon}
      </span>
      <p className="mb-1 text-label text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="font-bold text-title tabular-nums">{value}</p>
    </div>
  )
}

function TopOffendersTable({ tables }: { tables: TableScore[] }) {
  const [expanded, setExpanded] = useState<string | null>(null)

  if (tables.length === 0) {
    return <p className="text-body text-muted-foreground">Nenhuma tabela avaliada ainda.</p>
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-16">Score</TableHead>
          <TableHead>Tabela</TableHead>
          <TableHead className="text-right">Tamanho</TableHead>
          <TableHead className="text-right">Custo 30d</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {tables.slice(0, 15).map((t) => {
          const key = `${t.dataset_id}.${t.table_id}`
          const isOpen = expanded === key
          return (
            <Fragment key={key}>
              <TableRow className="cursor-pointer" onClick={() => setExpanded(isOpen ? null : key)}>
                <TableCell>
                  <CompositeScoreRing score={t.score} compact />
                </TableCell>
                <TableCell>
                  <span className="inline-flex items-center gap-1.5">
                    <ChevronDown
                      size={13}
                      className={cn('shrink-0 transition-transform', !isOpen && '-rotate-90')}
                    />
                    {key}
                    {t.is_partitioned && (
                      <span className="text-muted-foreground text-xs">particionada</span>
                    )}
                  </span>
                </TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {formatBytes(t.size_bytes)}
                </TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {formatUsd(t.observed_cost_usd_30d)}
                </TableCell>
              </TableRow>
              {isOpen && (
                <TableRow>
                  <TableCell colSpan={4} className="bg-muted/40">
                    <ul className="flex flex-col gap-1.5 py-1">
                      {t.factors.map((f) => (
                        <li key={f.name} className="flex items-center gap-3 text-body">
                          <span
                            aria-hidden="true"
                            className="size-2.5 shrink-0 rounded-full"
                            style={{ background: scoreBand(f.value * 100) }}
                          />
                          <b className="w-32 shrink-0">{f.name}</b>
                          <span className="tabular-nums text-muted-foreground">
                            {Math.round(f.value * 100)}% · peso {f.weight}
                          </span>
                          <span className="min-w-0 flex-1 truncate text-muted-foreground">
                            {f.detail}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </TableCell>
                </TableRow>
              )}
            </Fragment>
          )
        })}
      </TableBody>
    </Table>
  )
}
