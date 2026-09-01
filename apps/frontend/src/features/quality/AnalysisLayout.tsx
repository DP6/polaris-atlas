import { Outlet, useParams } from 'react-router-dom'
import { LoadingState } from '@/components/LoadingState'
import { useTableDetail } from '@/features/catalog/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { AnalysisContextProvider } from '@/features/quality/analysisContext'

const VIEW_TYPES = new Set(['VIEW', 'MATERIALIZED_VIEW'])

// Element da rota `/analyze/:datasetId/:tableId` — só provê o contexto
// (projectId/datasetId/tableId + tableDetail + isView) e renderiza o
// <Outlet/>. Cada página filha traz seu próprio <PageHeader> com `back`.
export function AnalysisLayout() {
  const { projectId } = useProjectContext()
  const { datasetId, tableId } = useParams<{ datasetId: string; tableId: string }>()
  const tableDetailQuery = useTableDetail(projectId, datasetId, tableId)

  if (!projectId || !datasetId || !tableId) return <LoadingState />

  const isView = Boolean(tableDetailQuery.data && VIEW_TYPES.has(tableDetailQuery.data.table_type))

  return (
    <AnalysisContextProvider
      value={{
        projectId,
        datasetId,
        tableId,
        tableDetail: tableDetailQuery.data,
        isView,
      }}
    >
      <Outlet />
    </AnalysisContextProvider>
  )
}
