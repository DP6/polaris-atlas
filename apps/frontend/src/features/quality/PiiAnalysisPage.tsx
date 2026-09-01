import { PageHeader } from '@/components/PageHeader'
import { PiiTab } from '@/features/pii/PiiTab'
import { useAnalysisContext } from '@/features/quality/analysisContext'

export function PiiAnalysisPage() {
  const { projectId, datasetId, tableId, isView } = useAnalysisContext()
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: '..', label: `${datasetId}.${tableId}` }}
        title="Fingerprint de PII"
        description="Detecção de coluna com dado pessoal sensível por heurística de nome + amostragem."
      />
      <PiiTab projectId={projectId} datasetId={datasetId} tableId={tableId} isView={isView} />
    </div>
  )
}
