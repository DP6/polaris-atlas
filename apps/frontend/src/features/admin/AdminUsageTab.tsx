import { AccessRequestAnalyticsSection } from '@/features/admin/AccessRequestAnalyticsSection'
import { FavoritesAnalyticsSection } from '@/features/admin/FavoritesAnalyticsSection'
import { LoginAnalyticsSection } from '@/features/admin/LoginAnalyticsSection'
import { NavigationAnalyticsSection } from '@/features/admin/NavigationAnalyticsSection'
import { PiiScanActivitySection } from '@/features/admin/PiiScanActivitySection'
import { ProfilingActivitySection } from '@/features/admin/ProfilingActivitySection'
import { RetentionFunnelSection } from '@/features/admin/RetentionFunnelSection'
import { UsageHeatmapSection } from '@/features/admin/UsageHeatmapSection'

export function AdminUsageTab() {
  return (
    <div className="flex flex-col gap-8">
      <LoginAnalyticsSection />
      <RetentionFunnelSection />
      <UsageHeatmapSection />
      <FavoritesAnalyticsSection />
      <ProfilingActivitySection />
      <AccessRequestAnalyticsSection />
      <NavigationAnalyticsSection />
      <PiiScanActivitySection />
    </div>
  )
}
