import {
  Bar,
  BarChart,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from 'recharts'
import { CollapsibleSection } from '@/components/CollapsibleSection'
import { useRetentionFunnel } from '@/features/admin/hooks'

export function RetentionFunnelSection() {
  const funnelQuery = useRetentionFunnel()

  if (funnelQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando funil de retenção…</p>
  }

  if (funnelQuery.isError || !funnelQuery.data) {
    return <p className="text-sm text-status-error">Erro ao carregar o funil de retenção.</p>
  }

  const { users_with_login, users_with_action, users_with_repeat_action } = funnelQuery.data
  const stages = [
    { label: 'Logaram', count: users_with_login },
    { label: '≥1 ação', count: users_with_action },
    { label: 'Ação repetida', count: users_with_repeat_action },
  ]

  return (
    <CollapsibleSection title="Funil de retenção">
      <p className="text-sm text-muted-foreground">
        Últimos 90 dias — login, pelo menos uma ação (profiling, scan de PII, visualização de tabela
        ou busca) e ação repetida (2 ou mais, qualquer combinação). Login e ação não precisam estar
        em ordem, só na mesma janela — leitura aproximada de engajamento, não um funil estrito.
      </p>

      <div className="h-40 w-full shrink-0 rounded-lg border border-border bg-card p-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={stages} layout="vertical" margin={{ left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} width={100} />
            <RechartsTooltip formatter={(value) => [String(value), 'Usuários']} />
            <Bar dataKey="count" fill="var(--color-primary)" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="flex gap-4 text-muted-foreground text-xs">
        {stages.slice(1).map((stage, index) => {
          const previous = stages[index].count
          const pct = previous > 0 ? `${((stage.count / previous) * 100).toFixed(0)}%` : '—'
          return (
            <span key={stage.label}>
              {stage.label}: {pct} de "{stages[index].label}"
            </span>
          )
        })}
      </div>
    </CollapsibleSection>
  )
}
