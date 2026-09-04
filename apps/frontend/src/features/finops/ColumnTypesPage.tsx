import { PageHeader } from '@/components/PageHeader'
import { ColumnTypesTab } from '@/features/finops/scannerTabs'
import { useProjectContext } from '@/features/projects/ProjectContext'

// Sub-rota `/finops/scanner/tipos-coluna` (rodada 3). O corpo vem de
// `scannerTabs.tsx` (era aba de FinOpsPage).
export function ColumnTypesPage() {
  const { projectId } = useProjectContext()
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: '/finops/scanner', label: 'Scanner de desperdício' }}
        title="Tipos de coluna"
        description="Colunas STRING que caberiam num tipo lógico mais barato. Diferente das outras telas do scanner, este scan amostra dado real via TABLESAMPLE e tem custo de BigQuery — escolha o escopo e estime antes de escanear."
      />
      <ColumnTypesTab projectId={projectId} />
    </div>
  )
}
