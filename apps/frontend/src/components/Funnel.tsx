import { cn } from '@/lib/utils'

interface FunnelStage {
  label: string
  count: number
}

interface FunnelProps {
  stages: FunnelStage[]
  valueFormat?: (n: number) => string
  className?: string
}

// Cor sólida por estágio — mesma progressão do protótipo: amarelo,
// amarelo, warn, err. Estágios além do 4º repetem o último.
const STAGE_FILL = [
  'var(--color-primary)',
  'var(--color-primary)',
  'var(--color-status-warn)',
  'var(--color-status-error)',
]
// Estágio com 0 ainda aparece como um traço.
const MIN_WIDTH_PCT = 4

// Funil de retenção: barras horizontais CENTRADAS afunilando de cima pra
// baixo (largura ∝ contagem), com o rótulo + valor + % (vs. o estágio
// anterior) acima de cada barra. Sem SVG esticado (a versão antiga
// distorcia os trapézios dentro do container de altura fixa). `role="img"`
// + `aria-label`; `<table>` visualmente-oculto de fallback.
export function Funnel({ stages, valueFormat, className }: FunnelProps) {
  const fmt = valueFormat ?? ((n: number) => String(n))
  const max = Math.max(...stages.map((s) => s.count), 1)
  const summary = stages.map((s) => `${s.label}: ${fmt(s.count)}`).join('; ')

  return (
    <div
      className={cn('flex h-full flex-col justify-center gap-3', className)}
      role="img"
      aria-label={`Funil de retenção — ${summary}`}
    >
      {stages.map((stage, i) => {
        const prev = i === 0 ? null : stages[i - 1].count
        const pct = prev && prev > 0 ? `${((stage.count / prev) * 100).toFixed(0)}%` : null
        const width = Math.max((stage.count / max) * 100, MIN_WIDTH_PCT)
        return (
          <div key={stage.label} className="flex flex-col gap-1" aria-hidden="true">
            <div className="flex items-baseline justify-between gap-3 text-body">
              <span>{stage.label}</span>
              <span className="text-muted-foreground tabular-nums">
                {fmt(stage.count)}
                {pct && <span className="ml-1.5 text-label">· {pct}</span>}
              </span>
            </div>
            <div
              className="mx-auto h-3 rounded-sm transition-[width]"
              style={{
                width: `${width}%`,
                background: STAGE_FILL[Math.min(i, STAGE_FILL.length - 1)],
              }}
            />
          </div>
        )
      })}

      <table className="sr-only">
        <caption>Funil de retenção</caption>
        <thead>
          <tr>
            <th>Estágio</th>
            <th>Usuários</th>
          </tr>
        </thead>
        <tbody>
          {stages.map((stage) => (
            <tr key={stage.label}>
              <td>{stage.label}</td>
              <td>{fmt(stage.count)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
