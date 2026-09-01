import { PageHeader } from '@/components/PageHeader'
import { ColumnTypeSuggestionsTab } from '@/features/finops/ColumnTypeSuggestionsTab'
import { useAnalysisContext } from '@/features/quality/analysisContext'

export function ColumnTypesAnalysisPage() {
  const { projectId, datasetId, tableId, isView } = useAnalysisContext()
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: '..', label: `${datasetId}.${tableId}` }}
        title="Tipos de coluna"
        description="Sugestão de tipo lógico mais barato e candidatos a particionamento."
      />
      <ColumnTypeSuggestionsTab
        projectId={projectId}
        datasetId={datasetId}
        tableId={tableId}
        isView={isView}
      />
    </div>
  )
}
