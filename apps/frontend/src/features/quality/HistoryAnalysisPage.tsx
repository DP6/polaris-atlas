import { PageHeader } from '@/components/PageHeader'
import { useAnalysisContext } from '@/features/quality/analysisContext'
import { HistoryTab } from '@/features/quality/HistoryTab'

export function HistoryAnalysisPage() {
  const { projectId, datasetId, tableId } = useAnalysisContext()
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: '..', label: `${datasetId}.${tableId}` }}
        title="Histórico de profiling"
        description="Runs anteriores desta tabela e a evolução da densidade / duplicatas."
      />
      <HistoryTab projectId={projectId} datasetId={datasetId} tableId={tableId} />
    </div>
  )
}
