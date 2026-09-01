import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'

interface OptionCardProps {
  icon: ReactNode
  title: string
  description: string
  // Vira `<Link>`; se ausente e `onClick` presente, vira `<button>`.
  to?: string
  onClick?: () => void
  // Desabilitado + opacidade reduzida + selo "em breve".
  soon?: boolean
  // Linha de meta no rodapé (badge, contagem…).
  meta?: ReactNode
  // "stack" (default) = ícone acima, card mais alto. "wide" = ícone à
  // esquerda + texto à direita, card retangular baixo (grade de muitos
  // cards, ex: chooser de análise).
  layout?: 'stack' | 'wide'
}

// Card de escolha (protótipo `.opt-card`): ícone-chip + título + descrição
// + meta. Usado nas telas de overview de grupo (Governança, Qualidade,
// FinOps) e no chooser de tipo de análise. Todos os cards têm a mesma cor
// de base (`bg-card`) — diferenciação só no hover (`.dp6-opt-card`).
export function OptionCard({
  icon,
  title,
  description,
  to,
  onClick,
  soon,
  meta,
  layout = 'stack',
}: OptionCardProps) {
  const isWide = layout === 'wide'
  const className = cn(
    'dp6-opt-card rounded-lg border border-border bg-card text-left',
    isWide ? 'flex items-start gap-3 p-4' : 'flex flex-col gap-2.5 p-5',
    soon && 'pointer-events-none opacity-55',
  )

  const body = (
    <>
      <span
        aria-hidden="true"
        className="inline-flex size-9 shrink-0 items-center justify-center rounded-md border border-primary/25 bg-primary/10 text-primary [&_svg]:size-[18px]"
      >
        {icon}
      </span>
      <div className={cn('min-w-0', isWide ? 'flex flex-col gap-1' : 'contents')}>
        <h3 className="font-bold text-subtitle">{title}</h3>
        <p className="text-body text-muted-foreground">{description}</p>
        {(meta || soon) && (
          <div className={cn('flex items-center gap-2 pt-1', !isWide && 'mt-auto')}>
            {soon ? (
              <span className="rounded-pill border border-border px-2 py-0.5 text-label text-muted-foreground">
                em breve
              </span>
            ) : (
              meta
            )}
          </div>
        )}
      </div>
    </>
  )

  if (soon) return <div className={className}>{body}</div>
  if (to)
    return (
      <Link to={to} className={className}>
        {body}
      </Link>
    )
  return (
    <button type="button" onClick={onClick} className={className}>
      {body}
    </button>
  )
}

// `columns` fixa o máximo por linha (`1 → 2 → N`); sem ele, auto-fill a
// partir de 16rem. Use `columns` quando a grade tem muitos cards e cada
// um é `layout="wide"` (ex: chooser de análise, no máx. 4 por linha).
const GRID_COLUMNS: Record<number, string> = {
  2: 'grid-cols-1 sm:grid-cols-2',
  3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
  4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
}

export function OptionCardGrid({
  children,
  columns,
}: {
  children: ReactNode
  columns?: 2 | 3 | 4
}) {
  return (
    <div
      className={cn(
        'grid gap-4',
        columns
          ? GRID_COLUMNS[columns]
          : '[grid-template-columns:repeat(auto-fill,minmax(16rem,1fr))]',
      )}
    >
      {children}
    </div>
  )
}
