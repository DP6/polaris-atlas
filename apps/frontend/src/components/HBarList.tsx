import type { ReactNode } from 'react'
import { ChartTooltip, useChartTooltip } from '@/components/ChartTooltip'
import { cn } from '@/lib/utils'

export interface HBarItem {
  label: string
  // Drives bar width (0..`max`).
  value: number
  // Texto à direita.
  displayValue: string
  // Conteúdo do tooltip flutuante no hover.
  tooltip: ReactNode
  // `key` = roxo (cardinalidade alta), `cat` = azul (categórica).
  variant?: 'key' | 'cat'
}

// Lista de barras horizontais + `ChartTooltip` no hover — o "gráfico de
// cardinalidade por coluna" da tela de análise de qualidade (substitui os
// gauges pequenos). Primeiro consumidor real do `ChartTooltip`.
export function HBarList({ items, max }: { items: HBarItem[]; max?: number }) {
  const tip = useChartTooltip()
  const ceiling = max ?? Math.max(...items.map((i) => i.value), 1)

  return (
    <>
      <div className="flex flex-col gap-1.5">
        {items.map((item) => (
          <div key={item.label} className="grid grid-cols-[10rem_1fr_4.5rem] items-center gap-3">
            <span className="truncate text-body" title={item.label}>
              {item.label}
            </span>
            <button
              type="button"
              aria-label={`${item.label}: ${item.displayValue}`}
              onMouseMove={(e) => tip.show(e, item.tooltip)}
              onMouseLeave={tip.hide}
              className="h-5 overflow-hidden rounded-md bg-muted"
            >
              <span
                className={cn(
                  'block h-full rounded-md',
                  item.variant === 'cat' ? 'bg-status-info' : 'bg-accent-purple',
                )}
                style={{ width: `${(item.value / ceiling) * 100}%` }}
              />
            </button>
            <span className="text-right text-label text-muted-foreground tabular-nums">
              {item.displayValue}
            </span>
          </div>
        ))}
      </div>
      <ChartTooltip state={tip.state} />
    </>
  )
}
