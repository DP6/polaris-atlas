import { Calendar, CalendarDays, UserCircle, Users } from 'lucide-react'
import { useMemo, useState } from 'react'
import { ChoiceToggle } from '@/components/ChoiceToggle'
import { CollapsibleSection } from '@/components/CollapsibleSection'
import { ComboChart } from '@/components/ComboChart'
import { DateField } from '@/components/DateField'
import { PaginationBar } from '@/components/PaginationBar'
import { Panel } from '@/components/Panel'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useLoginAnalytics } from '@/features/admin/hooks'
import { KpiCards } from '@/features/catalog/KpiCards'
import { usePagination } from '@/hooks/usePagination'
import { formatDate } from '@/lib/format'
import type { LoginCountBucket } from '@/types/admin'

const LOOKBACK_DAYS = 90
type Granularity = 'day' | 'month'
type BarMetric = 'accumulated' | 'perPeriod'

function todayDailyKey(): string {
  return new Date().toISOString().slice(0, 10)
}

// Mesmo algoritmo de datetime.isocalendar() do Python (ISO 8601) — precisa
// bater com o formato do backend pra achar o bucket da semana atual.
function isoWeekKey(now: Date): string {
  const date = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()))
  const dayNum = (date.getUTCDay() + 6) % 7
  date.setUTCDate(date.getUTCDate() - dayNum + 3)
  const firstThursday = new Date(Date.UTC(date.getUTCFullYear(), 0, 4))
  const firstDayNum = (firstThursday.getUTCDay() + 6) % 7
  firstThursday.setUTCDate(firstThursday.getUTCDate() - firstDayNum + 3)
  const week = 1 + Math.round((date.getTime() - firstThursday.getTime()) / (7 * 86400000))
  return `${date.getUTCFullYear()}-W${String(week).padStart(2, '0')}`
}

function monthKey(now: Date): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function shortLabel(period: string, granularity: Granularity): string {
  if (granularity === 'month') return period
  const date = new Date(period)
  if (Number.isNaN(date.getTime())) return period
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit' }).format(date)
}

function findBucket(buckets: LoginCountBucket[], period: string): LoginCountBucket | undefined {
  return buckets.find((b) => b.period === period)
}

export function LoginAnalyticsSection() {
  const [granularity, setGranularity] = useState<Granularity>('day')
  const [barMetric, setBarMetric] = useState<BarMetric>('accumulated')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')

  const analyticsQuery = useLoginAnalytics(
    from || to ? { from: from || undefined, to: to || undefined } : { lookbackDays: LOOKBACK_DAYS },
  )

  const recentEvents = analyticsQuery.data?.recent_events ?? []
  const pagination = usePagination({ rowCount: recentEvents.length })
  const pageEvents = recentEvents.slice(pagination.start, pagination.end)

  const chartData = useMemo(() => {
    const buckets =
      granularity === 'month'
        ? (analyticsQuery.data?.monthly ?? [])
        : (analyticsQuery.data?.daily ?? [])
    let running = 0
    return buckets.map((bucket) => {
      running += bucket.login_count
      return {
        label: shortLabel(bucket.period, granularity),
        perPeriod: bucket.login_count,
        accumulated: running,
      }
    })
  }, [analyticsQuery.data, granularity])

  if (analyticsQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando acessos…</p>
  }

  if (analyticsQuery.isError || !analyticsQuery.data) {
    return (
      <p className="text-sm text-status-error-foreground">Erro ao carregar os acessos ao Hub.</p>
    )
  }

  const { daily, weekly, monthly, recent_events } = analyticsQuery.data
  const now = new Date()
  const today = findBucket(daily, todayDailyKey())
  const thisWeek = findBucket(weekly, isoWeekKey(now))
  const thisMonth = findBucket(monthly, monthKey(now))

  const barSeries =
    barMetric === 'accumulated'
      ? {
          key: 'accumulated',
          name: 'Acumulado',
          color: 'color-mix(in oklab, var(--color-primary) 26%, transparent)',
        }
      : {
          key: 'perPeriod',
          name: 'Acessos no período',
          color: 'color-mix(in oklab, var(--color-primary) 26%, transparent)',
        }
  const lineSeries =
    barMetric === 'accumulated'
      ? [{ key: 'perPeriod', name: 'Acessos no período', color: 'var(--color-primary)' }]
      : [{ key: 'accumulated', name: 'Acumulado', color: 'var(--color-primary)' }]

  return (
    <Panel
      title="Acessos ao Hub"
      subtitle="Coluna e linha na mesma janela — troque qual métrica é coluna e qual é linha, a granularidade e o período."
      actions={
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <span className="text-label text-muted-foreground">Coluna</span>
            <ChoiceToggle
              aria-label="Métrica da coluna"
              size="sm"
              options={[
                { value: 'accumulated', label: 'Acumulado' },
                { value: 'perPeriod', label: 'Período' },
              ]}
              value={barMetric}
              onChange={setBarMetric}
            />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-label text-muted-foreground">Granularidade</span>
            <ChoiceToggle
              aria-label="Granularidade"
              size="sm"
              options={[
                { value: 'day', label: 'Dia' },
                { value: 'month', label: 'Mês' },
              ]}
              value={granularity}
              onChange={setGranularity}
            />
          </div>
          <DateField
            id="login-from"
            label="De"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
          <DateField id="login-to" label="Até" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <KpiCards
          items={[
            {
              label: 'Acessos hoje',
              value: String(today?.login_count ?? 0),
              icon: <Users size={14} />,
            },
            {
              label: 'Usuários únicos hoje',
              value: String(today?.unique_users ?? 0),
              icon: <UserCircle size={14} />,
            },
            {
              label: 'Acessos esta semana',
              value: String(thisWeek?.login_count ?? 0),
              icon: <Calendar size={14} />,
            },
            {
              label: 'Acessos este mês',
              value: String(thisMonth?.login_count ?? 0),
              icon: <CalendarDays size={14} />,
            },
          ]}
        />

        <ComboChart
          data={chartData}
          xKey="label"
          bar={barSeries}
          lines={lineSeries}
          height={200}
          valueFormat={(v) => String(Math.round(v))}
        />

        <CollapsibleSection
          title={`Acessos recentes (últimos ${recent_events.length})`}
          variant="subsection"
        >
          <div className="max-h-[420px] overflow-y-auto rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>E-mail</TableHead>
                  <TableHead>Quando</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pageEvents.map((event) => (
                  <TableRow key={`${event.email}-${event.logged_in_at}`}>
                    <TableCell>{event.email}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(event.logged_in_at)}
                    </TableCell>
                  </TableRow>
                ))}
                {recent_events.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={2} className="text-muted-foreground">
                      Nenhum acesso registrado ainda.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
          <PaginationBar
            page={pagination.page}
            pageCount={pagination.pageCount}
            pageSize={pagination.pageSize}
            setPageSize={pagination.setPageSize}
            start={pagination.start}
            end={pagination.end}
            totalCount={recent_events.length}
            onPrevious={pagination.goToPreviousPage}
            onNext={pagination.goToNextPage}
          />
        </CollapsibleSection>
      </div>
    </Panel>
  )
}
