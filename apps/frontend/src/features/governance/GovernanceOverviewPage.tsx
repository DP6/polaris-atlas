import { Clock, Unlink } from 'lucide-react'
import { OptionCard, OptionCardGrid } from '@/components/OptionCard'
import { PageHeader } from '@/components/PageHeader'

// Tela de overview do grupo "Governança" da sidebar — aberta ao clicar no
// nome do grupo (o chevron continua abrindo o drill-down inline). Cards de
// função, estilo Catálogo de Dados.
export function GovernanceOverviewPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Governança"
        description="Freshness com SLA e tabelas sem consumidor conhecido."
        showBrandBars
      />
      <OptionCardGrid>
        <OptionCard
          icon={<Clock />}
          title="Freshness & SLA"
          description="Quanto tempo desde a última atualização de cada tabela, contra o SLA da faixa."
          to="/freshness"
          featured
        />
        <OptionCard
          icon={<Unlink />}
          title="Tabelas sem consumidor"
          description="Tabelas que não aparecem lidas em nenhum job do BigQuery na janela — candidatas a limpeza."
          to="/orphans"
        />
      </OptionCardGrid>
    </div>
  )
}
