import { Columns, Rows3 } from 'lucide-react'
import { OptionCard, OptionCardGrid } from '@/components/OptionCard'
import { PageHeader } from '@/components/PageHeader'

// Overview do "Scanner de desperdício" — 2 cards → sub-rotas (rodada 3;
// antes eram abas de `FinOpsPage`). Mesmo padrão de Governança/Qualidade.
export function ScannerOverviewPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: '/finops', label: 'Visão geral de FinOps' }}
        title="FinOps — Scanner de desperdício"
        description={
          'Candidatas a particionamento e sugestões de tipo de coluna, com estimativa de custo. ' +
          'Tabelas sem uso ficou só em Governança > "Tabelas sem consumidor", pra não duplicar a ' +
          'mesma informação em dois lugares.'
        }
      />
      <OptionCardGrid>
        <OptionCard
          icon={<Rows3 />}
          title="Candidatas a particionamento"
          description="Tabelas ≥ 1 GB ainda não particionadas, com coluna de data candidata a chave de partição — com a economia estimada pelo custo real de scan dos últimos 30 dias."
          to="/finops/scanner/particionamento"
        />
        <OptionCard
          icon={<Columns />}
          title="Tipos de coluna"
          description="Colunas STRING que caberiam num tipo lógico mais barato (INT64, DATE…). Este scan amostra dado real via TABLESAMPLE — estime o custo antes de rodar."
          to="/finops/scanner/tipos-coluna"
        />
      </OptionCardGrid>
    </div>
  )
}
