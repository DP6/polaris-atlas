import { Fragment } from 'react'
import type { HeatmapCell } from '@/types/admin'

// weekday: 0=segunda ... 6=domingo (Python datetime.weekday(), mesma
// convenção do backend — ver analytics_schemas.py::HeatmapCell).
const WEEKDAY_LABELS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
const HOURS = Array.from({ length: 24 }, (_, i) => i)

// recharts não tem heatmap nativo — grade CSS simples em vez de forçar
// um gráfico recharts pra um formato que ele não cobre bem. Intensidade
// por opacity sobre --color-primary (mais simples e com suporte de
// browser mais amplo que color-mix()).
function cellStyle(count: number, max: number): React.CSSProperties {
  if (count === 0 || max === 0) return { backgroundColor: 'var(--color-muted)' }
  const intensity = 0.15 + (count / max) * 0.85
  return { backgroundColor: 'var(--color-primary)', opacity: intensity }
}

export function UsageHeatmapGrid({ cells }: { cells: HeatmapCell[] }) {
  const countByKey = new Map<string, number>()
  for (const cell of cells) {
    countByKey.set(`${cell.weekday}-${cell.hour}`, cell.count)
  }
  const max = cells.reduce((acc, c) => Math.max(acc, c.count), 0)

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card p-4">
      <div
        className="inline-grid items-center gap-0.5"
        style={{ gridTemplateColumns: '36px repeat(24, 20px)' }}
      >
        <div />
        {HOURS.map((hour) => (
          <div key={`hour-${hour}`} className="text-center text-[9px] text-muted-foreground">
            {hour % 3 === 0 ? hour : ''}
          </div>
        ))}
        {WEEKDAY_LABELS.map((label, weekday) => (
          <Fragment key={label}>
            <div className="pr-1 text-right text-muted-foreground text-xs">{label}</div>
            {HOURS.map((hour) => {
              const count = countByKey.get(`${weekday}-${hour}`) ?? 0
              return (
                <div
                  key={`${label}-${hour}`}
                  title={`${label} ${hour}h — ${count} evento${count === 1 ? '' : 's'}`}
                  className="aspect-square rounded-sm"
                  style={cellStyle(count, max)}
                />
              )
            })}
          </Fragment>
        ))}
      </div>
    </div>
  )
}
