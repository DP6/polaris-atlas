import type { ReactNode } from 'react'
import { SectionHeading } from '@/components/SectionHeading'
import { cn } from '@/lib/utils'

interface PanelProps {
  title?: ReactNode
  subtitle?: ReactNode
  // À direita do título (filtros globais, toggles, RefreshButton…).
  actions?: ReactNode
  // Nível do heading do título — "h2" (seção de página) ou "h3" (subseção).
  as?: 'h2' | 'h3'
  // Linha de filtro renderizada DENTRO do painel, entre o header e o corpo
  // (no protótipo os filtros ficam dentro do `.panel`, não soltos antes).
  filterRow?: ReactNode
  // `.dp6-hoverable` — só quando o painel inteiro é clicável (é um link).
  hoverable?: boolean
  // `.dp6-glass` — opt-in raro (app denso, quase nada pra desfocar atrás).
  glass?: boolean
  className?: string
  bodyClassName?: string
  children: ReactNode
}

// "Bloco" da plataforma (protótipo `.panel`): container arredondado 10px
// com `border` + `bg-card` + borda-gradiente sutil (`.dp6-panel::after`).
// Título via `SectionHeading`, subtítulo abaixo, filtros dentro. O corpo
// NÃO clipa o scroll horizontal — o `<Table>` mantém seu `overflow-x-auto`.
export function Panel({
  title,
  subtitle,
  actions,
  as = 'h2',
  filterRow,
  hoverable,
  glass,
  className,
  bodyClassName,
  children,
}: PanelProps) {
  const hasHeader = Boolean(title || actions)

  return (
    <div
      className={cn(
        'dp6-panel rounded-lg border border-border bg-card p-4',
        hoverable && 'dp6-hoverable',
        glass && 'dp6-glass',
        className,
      )}
    >
      {hasHeader && (
        <SectionHeading as={as} actions={actions} className={subtitle ? 'mb-1' : 'mb-3'}>
          {title}
        </SectionHeading>
      )}
      {subtitle && <p className="mb-3 max-w-[65ch] text-body text-muted-foreground">{subtitle}</p>}
      {filterRow && <div className="mb-3">{filterRow}</div>}
      <div className={bodyClassName}>{children}</div>
    </div>
  )
}
