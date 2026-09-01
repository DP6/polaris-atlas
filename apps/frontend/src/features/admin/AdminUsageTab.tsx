import { AccessRequestAnalyticsSection } from '@/features/admin/AccessRequestAnalyticsSection'
import { FavoritesAnalyticsSection } from '@/features/admin/FavoritesAnalyticsSection'
import { LoginAnalyticsSection } from '@/features/admin/LoginAnalyticsSection'
import { NavigationAnalyticsSection } from '@/features/admin/NavigationAnalyticsSection'
import { PiiScanActivitySection } from '@/features/admin/PiiScanActivitySection'
import { ProfilingActivitySection } from '@/features/admin/ProfilingActivitySection'
import { RetentionFunnelSection } from '@/features/admin/RetentionFunnelSection'
import { UsageHeatmapSection } from '@/features/admin/UsageHeatmapSection'

// Layout de BLOCOS (não mais scroll corrido de CollapsibleSection): o
// combo de acessos (rico) ocupa a largura toda; funil + heatmap dividem
// uma linha 2-col; as seções pesadas de tabela seguem empilhadas full-width.
export function AdminUsageTab() {
  return (
    <div className="flex flex-col gap-6">
      <LoginAnalyticsSection />

      <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
        <RetentionFunnelSection />
        <UsageHeatmapSection />
      </div>

      <FavoritesAnalyticsSection />
      <ProfilingActivitySection />
      <AccessRequestAnalyticsSection />
      <NavigationAnalyticsSection />
      <PiiScanActivitySection />
    </div>
  )
}
