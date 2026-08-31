import { MetricGrid, MetricTile } from '@/components/MetricTile'

interface Kpi {
  label: string
  value: string
  alert?: boolean
}

export function KpiCards({ items }: { items: Kpi[] }) {
  return (
    <MetricGrid>
      {items.map((item) => (
        <MetricTile key={item.label} label={item.label} value={item.value} alert={item.alert} />
      ))}
    </MetricGrid>
  )
}
