import { CollapsibleSection } from '@/components/CollapsibleSection'
import { useUsageHeatmap } from '@/features/admin/hooks'
import { UsageHeatmapGrid } from '@/features/admin/UsageHeatmapGrid'

export function UsageHeatmapSection() {
  const heatmapQuery = useUsageHeatmap()

  if (heatmapQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando mapa de calor…</p>
  }

  if (heatmapQuery.isError || !heatmapQuery.data) {
    return <p className="text-sm text-status-error-foreground">Erro ao carregar o mapa de calor.</p>
  }

  const { cells } = heatmapQuery.data
  const hasData = cells.some((c) => c.count > 0)

  return (
    <CollapsibleSection title="Horário de uso">
      <p className="text-sm text-muted-foreground">
        Combina login, profiling, scan de PII, visualização de tabela e busca dos últimos 90 dias
        num mapa de dia da semana × hora — útil pra saber quando dar suporte/manutenção sem
        atrapalhar quem está usando o Hub.
      </p>

      {hasData ? (
        <UsageHeatmapGrid cells={cells} />
      ) : (
        <p className="text-sm text-muted-foreground">
          Nenhuma atividade registrada nos últimos 90 dias.
        </p>
      )}
    </CollapsibleSection>
  )
}
