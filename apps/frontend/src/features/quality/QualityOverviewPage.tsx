import { BarChart2, FolderKanban } from 'lucide-react'
import { OptionCard, OptionCardGrid } from '@/components/OptionCard'
import { PageHeader } from '@/components/PageHeader'

// Overview do grupo "Análises de qualidade" da sidebar (clique no nome).
export function QualityOverviewPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Análises de qualidade"
        description="Escolha uma tabela pra rodar schema, profiling, PII, tipos de coluna, histórico ou mapa de acesso — ou compare runs salvas em pastas."
      />
      <OptionCardGrid>
        <OptionCard
          icon={<BarChart2 />}
          title="Analisar uma tabela"
          description="Lista de tabelas do projeto — escolha uma pra abrir o módulo de qualidade em tela cheia."
          to="/quality/tables"
        />
        <OptionCard
          icon={<FolderKanban />}
          title="Pastas de profiling"
          description="Runs de profiling salvas em pastas, com comparação coluna a coluna entre elas."
          to="/quality/folders"
        />
      </OptionCardGrid>
    </div>
  )
}
