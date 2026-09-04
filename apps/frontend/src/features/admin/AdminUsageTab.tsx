import { Panel } from '@/components/Panel'
import { AccessRequestAnalyticsSection } from '@/features/admin/AccessRequestAnalyticsSection'
import { FavoritesAnalyticsSection } from '@/features/admin/FavoritesAnalyticsSection'
import { LoginAnalyticsSection } from '@/features/admin/LoginAnalyticsSection'
import { NavigationAnalyticsSection } from '@/features/admin/NavigationAnalyticsSection'
import { PiiScanActivitySection } from '@/features/admin/PiiScanActivitySection'
import { ProfilingActivitySection } from '@/features/admin/ProfilingActivitySection'
import { RetentionFunnelSection } from '@/features/admin/RetentionFunnelSection'
import { UsageHeatmapSection } from '@/features/admin/UsageHeatmapSection'

// Layout de BLOCOS: toda seção fica dentro de um `<Panel>` (as que ainda
// usam `CollapsibleSection` puro por dentro ganham a moldura pelo wrapper).
// O combo de acessos (rico) ocupa a largura toda; funil + heatmap dividem
// uma linha 2-col; as seções pesadas de tabela seguem empilhadas full-width.
export function AdminUsageTab() {
  return (
    <div className="flex flex-col gap-6">
      <LoginAnalyticsSection />

      <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
        <RetentionFunnelSection />
        <UsageHeatmapSection />
      </div>

      <Panel>
        <FavoritesAnalyticsSection />
      </Panel>
      <Panel>
        <ProfilingActivitySection />
      </Panel>
      <Panel>
        <AccessRequestAnalyticsSection />
      </Panel>
      <Panel>
        <NavigationAnalyticsSection />
      </Panel>
      <Panel>
        <PiiScanActivitySection />
      </Panel>
    </div>
  )
}
