import { PageHeader } from '@/components/PageHeader'
import { TableSearchPanel } from '@/features/catalog/TableSearchPanel'

export function SearchPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Buscar tabelas"
        description="Encontre em quais datasets uma tabela existe (ou não) dentro do projeto selecionado."
      />
      <TableSearchPanel />
    </div>
  )
}
