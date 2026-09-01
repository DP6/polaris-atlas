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

// Cor sólida por estágio — mesma progressão do protótipo (`.fr-fill.s1..s4`):
// amarelo, amarelo, warn, err. Estágios além do 4º repetem o último.
const STAGE_FILL = [
  'var(--color-primary)',
  'var(--color-primary)',
  'var(--color-status-warn)',
  'var(--color-status-error)',
]

// Funil de retenção em TRAPÉZIOS geométricos afunilando, com rótulo +
// valor SEMPRE por fora (coluna ao lado) — nunca centralizado por dentro
// (colide com o valor nos estágios estreitos, ex. 38%). SVG à mão.
export function Funnel({ stages, valueFormat, className }: FunnelProps) {
  const fmt = valueFormat ?? ((n: number) => String(n))
  const max = Math.max(...stages.map((s) => s.count), 1)
  const W = 100
  const rowH = 40
  const gap = 10
  const totalH = stages.length * rowH + Math.max(stages.length - 1, 0) * gap

  const summary = stages.map((s) => `${s.label}: ${fmt(s.count)}`).join('; ')

  return (
    <div
      className={cn('flex items-stretch gap-4', className)}
      role="img"
      aria-label={`Funil de retenção — ${summary}`}
    >
      <svg
        viewBox={`0 0 ${W} ${totalH}`}
        preserveAspectRatio="none"
        className="h-full w-40 shrink-0"
        aria-hidden="true"
      >
        {stages.map((stage, i) => {
          const wTop = ((i === 0 ? stage.count : stages[i - 1].count) / max) * W
          const wBot = (stage.count / max) * W
          const y = i * (rowH + gap)
          const xTop = (W - wTop) / 2
          const xBot = (W - wBot) / 2
          return (
            <polygon
              key={stage.label}
              points={`${xTop},${y} ${xTop + wTop},${y} ${xBot + wBot},${y + rowH} ${xBot},${y + rowH}`}
              fill={STAGE_FILL[Math.min(i, STAGE_FILL.length - 1)]}
              opacity={0.9}
            />
          )
        })}
      </svg>

      <ol className="flex flex-1 flex-col justify-between py-0.5">
        {stages.map((stage, i) => {
          const prev = i === 0 ? null : stages[i - 1].count
          const pct = prev && prev > 0 ? `${((stage.count / prev) * 100).toFixed(0)}%` : null
          return (
            <li
              key={stage.label}
              className="flex items-baseline justify-between gap-3"
              style={{ minHeight: rowH }}
            >
              <span className="text-body">{stage.label}</span>
              <span className="text-body text-muted-foreground tabular-nums">
                {fmt(stage.count)}
                {pct && <span className="ml-1.5 text-label">· {pct}</span>}
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
