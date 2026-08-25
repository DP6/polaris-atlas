import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from 'recharts'
import { CollapsibleSection } from '@/components/CollapsibleSection'
import { useDomainUsageRanking } from '@/features/admin/hooks'
import { KpiCards } from '@/features/catalog/KpiCards'

export function DomainUsageRankingSection() {
  const analyticsQuery = useDomainUsageRanking()

  if (analyticsQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando ranking de domínios…</p>
  }

  if (analyticsQuery.isError || !analyticsQuery.data) {
    return <p className="text-sm text-status-error">Erro ao carregar o ranking de domínios.</p>
  }

  const { monthly, total_profiling_runs, total_pii_scans } = analyticsQuery.data

  return (
    <CollapsibleSection title="Ranking de domínios mais usados">
      <p className="text-sm text-muted-foreground">
        Compara volume de profiling rodado com scans de PII, por mês — onde o esforço de manutenção
        compensa mais. Navegação em buckets do Storage ainda não é rastreada, fica de fora deste
        ranking.
      </p>

      <KpiCards
        items={[
          { label: 'Total de profiles rodados', value: String(total_profiling_runs) },
          { label: 'Total de scans de PII', value: String(total_pii_scans) },
        ]}
      />

      <div className="h-56 w-full shrink-0 rounded-lg border border-border bg-card p-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={monthly}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="period" tick={{ fontSize: 11 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={28} />
            <RechartsTooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="profiling_count" name="Profiling" fill="var(--color-primary)" />
            <Bar dataKey="pii_scan_count" name="PII scan" fill="var(--color-accent-purple)" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {monthly.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Nenhum profiling ou scan de PII registrado ainda.
        </p>
      )}
    </CollapsibleSection>
  )
}
