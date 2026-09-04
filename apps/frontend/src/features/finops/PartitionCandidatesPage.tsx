import { PageHeader } from '@/components/PageHeader'
import { PartitionCandidatesTab } from '@/features/finops/scannerTabs'
import { useProjectContext } from '@/features/projects/ProjectContext'

// Sub-rota `/finops/scanner/particionamento` (rodada 3). O corpo vem de
// `scannerTabs.tsx` (era aba de FinOpsPage).
export function PartitionCandidatesPage() {
  const { projectId } = useProjectContext()
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: '/finops/scanner', label: 'Scanner de desperdício' }}
        title="Candidatas a particionamento"
        description="Tabelas ainda não particionadas, com pelo menos 1 GB, que têm ao menos uma coluna DATE/DATETIME/TIMESTAMP candidata a chave de partição."
      />
      <PartitionCandidatesTab projectId={projectId} />
    </div>
  )
}
