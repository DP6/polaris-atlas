import { SLA_FILL_COLOR, SLA_LABELS, SLA_ORDER } from '@/features/freshness/sla'
import { cn } from '@/lib/utils'
import type { FreshnessCounts } from '@/types/freshness'

// Barra horizontal empilhada: proporção das tabelas de um dataset entre as
// 6 faixas de SLA de freshness. Componente compartilhado — os cards do
// Catálogo de Dados e o Freshness usam o MESMO (brief §"Freshness" e
// §"Catálogo de Dados"). Sem query nova: consome `FreshnessCounts`, que já
// vem do cache D-1 do domínio de freshness.
//
// Acessível como `role="img"` + `aria-label`/`title` com a decomposição
// completa (mouse vê o `title` nativo). Um tooltip flutuante por segmento
// entra na versão maior do Freshness, não aqui no mini de card.
export function SlaDistributionBar({
  counts,
  className,
  height = 'h-2',
}: {
  counts: FreshnessCounts
  className?: string
  // Classe de altura Tailwind (`h-2` no card, `h-3`/`h-4` em painel maior).
  height?: string
}) {
  const total = SLA_ORDER.reduce((sum, status) => sum + counts[status], 0)
  const label = summarize(counts, total)

  return (
    <div
      className={cn('flex w-full overflow-hidden rounded-pill bg-muted', height, className)}
      role="img"
      aria-label={label}
      title={label}
    >
      {total > 0 &&
        SLA_ORDER.map((status) => {
          const value = counts[status]
          if (value === 0) return null
          return (
            <div
              key={status}
              style={{ width: `${(value / total) * 100}%` }}
              className={cn('h-full', SLA_FILL_COLOR[status])}
            />
          )
        })}
    </div>
  )
}

function summarize(counts: FreshnessCounts, total: number): string {
  if (total === 0) return 'Sem tabelas monitoradas para freshness'
  const parts = SLA_ORDER.filter((status) => counts[status] > 0).map(
    (status) => `${counts[status]} em "${SLA_LABELS[status]}"`,
  )
  return `Distribuição de SLA: ${parts.join(', ')}`
}
