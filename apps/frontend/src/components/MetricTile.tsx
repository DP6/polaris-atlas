import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface MetricTileProps {
  label: string
  value: ReactNode
  // Realça a borda quando o valor merece atenção (ex: budget estourado,
  // freshness stale).
  alert?: boolean
  className?: string
}

// Tile de métrica único da plataforma — valor em text-title, rótulo em
// text-label uppercase. Substitui o `KpiCards` interno e os tiles à mão
// de BudgetPage/ProfilingDialog (p-3/p-4 e text-lg/xl/2xl divergentes).
export function MetricTile({ label, value, alert, className }: MetricTileProps) {
  return (
    <div
      className={cn(
        'rounded-lg border bg-card p-4',
        alert ? 'border-status-error' : 'border-border',
        className,
      )}
    >
      <p className="mb-1 text-label text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="font-bold text-title">{value}</p>
    </div>
  )
}

interface MetricGridProps {
  children: ReactNode
  className?: string
}

// Grid responsivo de MetricTile — auto-fill (sem breakpoints mágicos):
// preenche a linha e quebra sozinho conforme a largura disponível.
export function MetricGrid({ children, className }: MetricGridProps) {
  return (
    <div
      className={cn(
        'grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(9.5rem,1fr))]',
        className,
      )}
    >
      {children}
    </div>
  )
}
