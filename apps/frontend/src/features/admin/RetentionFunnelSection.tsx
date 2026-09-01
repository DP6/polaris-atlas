import { Funnel } from '@/components/Funnel'
import { Panel } from '@/components/Panel'
import { useRetentionFunnel } from '@/features/admin/hooks'

export function RetentionFunnelSection() {
  const funnelQuery = useRetentionFunnel()

  if (funnelQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando funil de retenção…</p>
  }

  if (funnelQuery.isError || !funnelQuery.data) {
    return (
      <p className="text-sm text-status-error-foreground">Erro ao carregar o funil de retenção.</p>
    )
  }

  const d = funnelQuery.data
  const stages = [
    { label: 'Acesso', count: d.users_with_login },
    { label: 'Ação', count: d.users_with_action },
    { label: '+4 Ações', count: d.users_with_5plus_actions },
    { label: '+9 Ações', count: d.users_with_10plus_actions },
  ]

  return (
    <Panel
      title="Funil de retenção"
      subtitle="Últimos 90 dias — login, ≥1 ação (profiling, scan de PII, ver tabela ou busca), ≥5 e ≥10 ações. Leitura aproximada de engajamento; login e ação só precisam estar na mesma janela, não em ordem."
    >
      <div className="h-56">
        <Funnel stages={stages} valueFormat={(n) => `${n} ${n === 1 ? 'usuário' : 'usuários'}`} />
      </div>
    </Panel>
  )
}
