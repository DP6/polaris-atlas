import { PageHeader } from '@/components/PageHeader'
import { useAnalysisContext } from '@/features/quality/analysisContext'
import { QualityAnalysisPanel } from '@/features/quality/QualityAnalysisPanel'

export function QualityAnalysisPage() {
  const { datasetId, tableId } = useAnalysisContext()
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: '..', label: `${datasetId}.${tableId}` }}
        title="Análise de qualidade"
        description="Completude, unicidade (HLL) e duplicatas coluna a coluna, com estimativa de custo antes de executar."
      />
      <QualityAnalysisPanel />
    </div>
  )
}
