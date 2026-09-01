import { HardDrive, PiggyBank } from 'lucide-react'
import { OptionCard, OptionCardGrid } from '@/components/OptionCard'
import { PageHeader } from '@/components/PageHeader'

// Tela de overview do grupo "Cloud Storage" da sidebar — aberta ao clicar
// no nome do grupo (o chevron continua abrindo o drill-down inline).
// Mesmo padrão de Governança.
export function StorageOverviewPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Cloud Storage"
        description="Catálogo de buckets do projeto e scanner de desperdício (idade + configuração de storage class)."
      />
      <OptionCardGrid>
        <OptionCard
          icon={<HardDrive />}
          title="Buckets"
          description="Inventário navegável dos buckets do projeto — tamanho, storage class, região, objetos."
          to="/storage/buckets"
        />
        <OptionCard
          icon={<PiggyBank />}
          title="Scanner de desperdício"
          description="Buckets antigos ou mal configurados (STANDARD parado há meses) com a faixa de economia estimada de mudar de classe."
          to="/storage/waste"
        />
      </OptionCardGrid>
    </div>
  )
}
