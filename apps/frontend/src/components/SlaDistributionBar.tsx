import { SLA_ORDER, SLA_SEVERITY } from '@/features/freshness/sla'
import { cn } from '@/lib/utils'
import type { FreshnessCounts, SLAStatus } from '@/types/freshness'

// Distribuição de freshness em 3 BARRAS VERTICAIS (verde / amarelo /
// vermelho) — as 3 sempre presentes, o que varia é a ALTURA de cada uma
// (∝ contagem). As 6 faixas de SLA são colapsadas nas 3 severidades via
// `SLA_SEVERITY`. Componente compartilhado: cards do Catálogo de Dados e
// o Freshness usam o mesmo (sem query nova — consome `FreshnessCounts`,
// que vem do cache D-1 do domínio de freshness).
//
// Acessível como `role="img"` + `aria-label`/`title` com a decomposição.

type Severity = 'ok' | 'warn' | 'error'

const SEVERITY_ORDER: Severity[] = ['ok', 'warn', 'error']
const SEVERITY_FILL: Record<Severity, string> = {
  ok: 'bg-status-ok',
  warn: 'bg-status-warn',
  error: 'bg-status-error',
}
const SEVERITY_LABEL: Record<Severity, string> = {
  ok: 'no prazo',
  warn: 'atrasadas',
  error: 'muito atrasadas',
}
// Faixa com 0 ainda aparece como um traço — nunca some.
const MIN_HEIGHT_PCT = 6

function bySeverity(counts: FreshnessCounts): Record<Severity, number> {
  const acc: Record<Severity, number> = { ok: 0, warn: 0, error: 0 }
  for (const status of SLA_ORDER as SLAStatus[]) {
    acc[SLA_SEVERITY[status]] += counts[status]
  }
  return acc
}

export function SlaDistributionBar({
  counts,
  className,
  height = 'h-10',
}: {
  counts: FreshnessCounts
  className?: string
  // Classe de altura Tailwind do container (`h-8` em célula de tabela,
  // `h-10`/`h-12` em card/painel).
  height?: string
}) {
  const grouped = bySeverity(counts)
  const total = SEVERITY_ORDER.reduce((sum, s) => sum + grouped[s], 0)
  const max = Math.max(...SEVERITY_ORDER.map((s) => grouped[s]), 1)
  const label =
    total === 0
      ? 'Sem tabelas monitoradas para freshness'
      : `Distribuição de freshness: ${SEVERITY_ORDER.map((s) => `${grouped[s]} ${SEVERITY_LABEL[s]}`).join(', ')}`

  return (
    <div
      className={cn('flex w-full items-end gap-1', height, className)}
      role="img"
      aria-label={label}
      title={label}
    >
      {SEVERITY_ORDER.map((severity) => {
        const value = grouped[severity]
        const pct = Math.max((value / max) * 100, MIN_HEIGHT_PCT)
        return (
          <div
            key={severity}
            className={cn('flex-1 rounded-sm', SEVERITY_FILL[severity])}
            style={{ height: `${pct}%` }}
          />
        )
      })}
    </div>
  )
}
