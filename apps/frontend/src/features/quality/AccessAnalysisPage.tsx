import { PageHeader } from '@/components/PageHeader'
import { AccessTab } from '@/features/access/AccessTab'
import { useAnalysisContext } from '@/features/quality/analysisContext'

export function AccessAnalysisPage() {
  const { projectId, datasetId, tableId } = useAnalysisContext()
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: '..', label: `${datasetId}.${tableId}` }}
        title="Mapa de acesso"
        description="Quem acessou esta tabela e quando — audit log de data access, últimos 30 dias."
      />
      <AccessTab projectId={projectId} datasetId={datasetId} tableId={tableId} />
    </div>
  )
}
