import { ChevronDown, DollarSign, Gauge, Info, Search, Target, TrendingUp } from 'lucide-react'
import { Fragment, type ReactNode, useMemo, useState } from 'react'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { CacheStalenessBadge } from '@/components/CacheStalenessBadge'
import { ChoiceToggle } from '@/components/ChoiceToggle'
import { ComboChart } from '@/components/ComboChart'
import { CompositeScoreRing } from '@/components/CompositeScoreRing'
import { DateField } from '@/components/DateField'
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
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
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

// Filtro de data do gráfico (rodada 3, AC-FIN-RV-02) — dois atalhos
// nomeados + os dois DateField ("De"/"Até") pra um intervalo customizado
// qualquer. from/to vazios = "Tudo": o back-end cai no lookback_days
// default (mesmo comportamento de antes do filtro existir).
// 'custom' nunca é clicável (não entra em DATE_PRESET_OPTIONS) — só marca
// "nenhum atalho ativo" quando o usuário digita um intervalo à mão.
type DatePreset = 'month' | 'all' | 'custom'
const DATE_PRESET_OPTIONS: { value: DatePreset; label: string }[] = [
  { value: 'month', label: 'Mês atual' },
  { value: 'all', label: 'Tudo' },
]
// Mínimo de dias pra o teto de budget (meta MENSAL) fazer sentido como
// comparação — evita desenhar a linha contra um intervalo curto/estranho
// onde "dentro do orçamento" enganaria (ver refLine mais abaixo).
const MIN_RANGE_DAYS_FOR_BUDGET_REF_LINE = 20

function toDateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function todayKey(): string {
  return toDateKey(new Date())
}

function currentMonthStartKey(): string {
  const now = new Date()
  return toDateKey(new Date(now.getFullYear(), now.getMonth(), 1))
}

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
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const datePreset: DatePreset =
    dateFrom === currentMonthStartKey() && dateTo === todayKey()
      ? 'month'
      : !dateFrom && !dateTo
        ? 'all'
        : 'custom' // intervalo customizado — nenhum atalho fica marcado
  function applyDatePreset(preset: DatePreset) {
    if (preset === 'month') {
      setDateFrom(currentMonthStartKey())
      setDateTo(todayKey())
    } else if (preset === 'all') {
      setDateFrom('')
      setDateTo('')
    }
  }
  const dateRange =
    dateFrom || dateTo ? { from: dateFrom || undefined, to: dateTo || undefined } : undefined

  const budgetQuery = useBudget(projectId, 'table', 10, 30, true, dateRange)
  const seriesQuery = useCostSeries(projectId, {
    granularity,
    costType,
    from: dateRange?.from,
    to: dateRange?.to,
  })
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

  // O teto de budget é uma meta MENSAL — comparar contra um intervalo
  // curto (ex: 5 dias) enganaria ("dentro do orçamento" cedo demais).
  // "Mês atual" e "Tudo" (~31 dias) sempre passam; um intervalo
  // customizado curto esconde a linha sozinho.
  const rangeDays = budget
    ? Math.round(
        (new Date(budget.period_end).getTime() - new Date(budget.period_start).getTime()) /
          86_400_000,
      ) + 1
    : 0
  const showBudgetRefLine = rangeDays >= MIN_RANGE_DAYS_FOR_BUDGET_REF_LINE

  const refreshing = budgetQuery.isFetching || seriesQuery.isFetching || scoresQuery.isFetching

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
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
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <span className="text-label text-muted-foreground">Granularidade</span>
              <ChoiceToggle
                aria-label="Granularidade"
                options={GRANULARITY_OPTIONS}
                value={granularity}
                onChange={setGranularity}
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-label text-muted-foreground">Tipo de custo</span>
              <ChoiceToggle
                aria-label="Tipo de custo"
                options={COST_TYPE_OPTIONS}
                value={costType}
                onChange={setCostType}
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-label text-muted-foreground">Período</span>
              <ChoiceToggle
                aria-label="Atalhos de período"
                options={DATE_PRESET_OPTIONS}
                value={datePreset}
                onChange={applyDatePreset}
              />
            </div>
            <DateField
              id="finops-date-from"
              label="De"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
            <DateField
              id="finops-date-to"
              label="Até"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
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
                showBudgetRefLine && budget?.budget_target_usd != null
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
        <Panel title="Eficiência de custo" as="h3" actions={<ScoreExplainer />}>
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

      <BudgetConfigDialog projectId={projectId} open={configOpen} onOpenChange={setConfigOpen} />
    </div>
  )
}

// Tooltip com a fórmula completa do score — o mesmo cálculo que alimenta
// o anel do projeto e a coluna "Score" da tabela de Top ofensores.
function ScoreExplainer() {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <button
            type="button"
            aria-label="Como o score de eficiência é calculado"
            className="text-muted-foreground hover:text-foreground [&_svg]:size-4"
          />
        }
      >
        <Info />
      </TooltipTrigger>
      <TooltipContent className="max-w-sm flex-col items-start gap-1.5 whitespace-normal text-left leading-relaxed">
        <p className="font-semibold">Score de eficiência de custo (0–100, maior = melhor)</p>
        <p>Média de 3 fatores, cada um com seu peso:</p>
        <ul className="flex list-disc flex-col gap-1 pl-4">
          <li>
            <b>Particionamento (45%)</b> — quanto do custo de scan dos últimos 30 dias dá pra
            economizar particionando a tabela. 100 se já é particionada ou não tem coluna de data
            candidata.
          </li>
          <li>
            <b>Utilização (30%)</b> — 100 se foi consultada nos últimos 30 dias; se nunca foi, cai
            com o tamanho (storage pago sem uso) e zera a partir de 100 GB.
          </li>
          <li>
            <b>Eficiência de scan (25%)</b> — penaliza re-scan da tabela inteira (sem
            filtro/pruning/cache): escanear 10× o próprio tamanho em 30d dá meia nota. Tabelas
            menores que 1 GB não entram nessa conta.
          </li>
        </ul>
        <p>
          O score do projeto é a média dos scores das tabelas <b>ponderada por tamanho</b> (as
          grandes pesam mais).
        </p>
        <p className="text-background/70">Fórmula provisória — em calibração.</p>
      </TooltipContent>
    </Tooltip>
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
        'rounded-lg border bg-card p-4',
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
