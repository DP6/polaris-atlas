import {
  BarChart2,
  Columns,
  GitBranch,
  History,
  ShieldAlert,
  Table2,
  Waypoints,
} from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { OptionCard, OptionCardGrid } from '@/components/OptionCard'
import { PageHeader } from '@/components/PageHeader'
import { useAnalysisContext } from '@/features/quality/analysisContext'

// Index de `/analyze/:datasetId/:tableId` — a "tela de escolha de tipo de
// análise" (protótipo). 7 cards, todos ativos (decisão do usuário).
export function AnalysisChooserPage() {
  const { datasetId, tableId } = useAnalysisContext()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? `/datasets/${datasetId}`
  const base = `/analyze/${datasetId}/${tableId}`

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: from, label: 'Voltar' }}
        title={`${datasetId}.${tableId}`}
        description="Módulo de qualidade — o que você quer ver ou rodar nesta tabela?"
        showBrandBars
      />
      <OptionCardGrid>
        <OptionCard
          icon={<Columns />}
          title="Schema"
          description="Nome, tipo e nullability de cada coluna."
          to={`${base}/schema`}
        />
        <OptionCard
          icon={<BarChart2 />}
          title="Análise de qualidade"
          description="Completude, unicidade (HLL) e duplicatas coluna a coluna, com estimativa de custo."
          to={`${base}/quality`}
          featured
        />
        <OptionCard
          icon={<ShieldAlert />}
          title="Fingerprint de PII"
          description="Detecção de coluna com dado pessoal sensível por heurística de nome + amostragem."
          to={`${base}/pii`}
        />
        <OptionCard
          icon={<Table2 />}
          title="Tipos de coluna"
          description="Sugestão de tipo lógico mais barato e candidatos a particionamento."
          to={`${base}/column-types`}
        />
        <OptionCard
          icon={<History />}
          title="Histórico"
          description="Runs de profiling anteriores desta tabela e a evolução da densidade."
          to={`${base}/history`}
        />
        <OptionCard
          icon={<Waypoints />}
          title="Mapa de acesso"
          description="Quem acessou esta tabela e quando (audit log de data access)."
          to={`${base}/access`}
        />
        <OptionCard
          icon={<GitBranch />}
          title="Lineage"
          description="De onde os dados desta tabela vêm e para onde vão — grafo em tela cheia."
          to={`/lineage/${datasetId}/${tableId}`}
        />
      </OptionCardGrid>
    </div>
  )
}
