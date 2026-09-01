import type { ReactNode } from 'react'
import { MetricGrid, MetricTile } from '@/components/MetricTile'

interface Kpi {
  label: string
  value: string
  // Ícone lucide opcional — repassado ao MetricTile (chip acima do rótulo).
  icon?: ReactNode
  alert?: boolean
}

export function KpiCards({ items }: { items: Kpi[] }) {
  return (
    <MetricGrid>
      {items.map((item) => (
        <MetricTile
          key={item.label}
          label={item.label}
          value={item.value}
          icon={item.icon}
          alert={item.alert}
        />
      ))}
    </MetricGrid>
  )
}
