import { WarningCallout } from '@/components/WarningCallout'

interface DataWindowNoticeProps {
  variant?: 'job' | 'storage'
}

// Resumo fixo da ADR-013 (docs/adr/ADR-013-historico-alem-de-30-dias.md) —
// mesma explicação em toda tela que depende de audit log de job do
// BigQuery (lineage/access/finops: "job") ou de leitura de objeto do GCS
// (storage waste scanner 6.2: "storage"). Texto único aqui em vez de
// copiado em cada Page, mesmo racional do WarningCallout centralizar o
// visual.
const TEXT = {
  job: (
    <>
      O histórico deste projeto cresce a partir do dia em que ele foi integrado ao Atlas. Na
      integração, conseguimos reconstruir até 180 dias anteriores via metadados do BigQuery — além
      disso, dados mais antigos que a integração não são recuperáveis (o Cloud Logging do projeto
      retém audit log por só ~30 dias, e essa configuração está fora do nosso acesso).
    </>
  ),
  storage: (
    <>
      Esta checagem enxerga só os últimos 30 dias de leitura de objeto — diferente de
      lineage/access/finops, não há uma fonte alternativa pra estender essa janela (o Cloud Logging
      do projeto retém Data Access audit log do GCS por só ~30 dias, config fora do nosso acesso).
    </>
  ),
} as const

export function DataWindowNotice({ variant = 'job' }: DataWindowNoticeProps) {
  return <WarningCallout variant="info">{TEXT[variant]}</WarningCallout>
}
