import { cn } from '@/lib/utils'

export interface ScoreSegment {
  label: string
  value: number
  color: string
}

interface CompositeScoreRingProps {
  // Número central 0–100.
  score: number
  // Rótulo abaixo do número (não no modo `compact`).
  caption?: string
  // 1–2 anéis concêntricos + legenda. Ausente → um anel só, cor por faixa.
  segments?: ScoreSegment[]
  size?: number
  // 34px, sem legenda, número compacto — pra coluna "Score" de tabela.
  compact?: boolean
  className?: string
}

function bandColor(score: number): string {
  if (score >= 80) return 'var(--color-status-ok)'
  if (score >= 50) return 'var(--color-status-warn)'
  return 'var(--color-status-error)'
}

// Anel de score composto (protótipo `.hero-ring`) — SVG à mão, cap
// arredondado. Número central em `--foreground` (nunca `--primary` — falha
// AA no claro). Toda linha de legenda com texto + valor (WCAG 1.4.1).
export function CompositeScoreRing({
  score,
  caption,
  segments,
  size = 168,
  compact,
  className,
}: CompositeScoreRingProps) {
  const dim = compact ? 34 : size
  const stroke = compact ? 4 : 10
  const outerR = (dim - stroke) / 2
  const rings = segments?.length
    ? segments
    : [{ label: 'Score', value: score, color: bandColor(score) }]

  const ring = (
    <div className="relative shrink-0" style={{ width: dim, height: dim }}>
      <svg viewBox={`0 0 ${dim} ${dim}`} className="-rotate-90 h-full w-full" aria-hidden="true">
        {rings.map((seg, i) => {
          const r = outerR - i * (stroke + 3)
          const circ = 2 * Math.PI * r
          const clamped = Math.min(Math.max(seg.value, 0), 100)
          return (
            <g key={seg.label}>
              <circle
                cx={dim / 2}
                cy={dim / 2}
                r={r}
                fill="none"
                stroke="var(--color-border)"
                strokeWidth={stroke}
              />
              <circle
                cx={dim / 2}
                cy={dim / 2}
                r={r}
                fill="none"
                stroke={seg.color}
                strokeWidth={stroke}
                strokeLinecap="round"
                strokeDasharray={circ}
                strokeDashoffset={circ * (1 - clamped / 100)}
              />
            </g>
          )
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <b
          className={cn(
            'font-bold text-foreground tabular-nums',
            compact ? 'text-label' : 'text-display',
          )}
        >
          {Math.round(score)}
        </b>
        {!compact && caption && (
          <span className="text-label text-muted-foreground uppercase tracking-wide">
            {caption}
          </span>
        )}
      </div>
    </div>
  )

  if (compact || !segments?.length) return <div className={className}>{ring}</div>

  return (
    <div className={cn('flex flex-wrap items-center gap-7', className)}>
      {ring}
      <ul className="flex min-w-[13rem] flex-1 flex-col gap-2.5">
        {segments.map((seg) => (
          <li key={seg.label} className="flex items-center gap-2.5 text-body">
            <span
              aria-hidden="true"
              className="size-2.5 shrink-0 rounded-full"
              style={{ background: seg.color }}
            />
            {seg.label}
            <b className="ml-auto tabular-nums">{seg.value}%</b>
          </li>
        ))}
      </ul>
    </div>
  )
}
