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
}

// Card de escolha (protótipo `.opt-card`): ícone-chip + título + descrição
// + meta. Usado nas telas de overview de grupo (Governança, Qualidade,
// FinOps) e no chooser de tipo de análise. Todos os cards têm a mesma cor
// de base (`bg-card`) — diferenciação só no hover (`.dp6-opt-card`).
export function OptionCard({ icon, title, description, to, onClick, soon, meta }: OptionCardProps) {
  const className = cn(
    'dp6-opt-card flex flex-col gap-2.5 rounded-lg border border-border bg-card p-5 text-left',
    soon && 'pointer-events-none opacity-55',
  )

  const body = (
    <>
      <span
        aria-hidden="true"
        className="inline-flex size-9 items-center justify-center rounded-md border border-primary/25 bg-primary/10 text-primary [&_svg]:size-[18px]"
      >
        {icon}
      </span>
      <h3 className="font-bold text-subtitle">{title}</h3>
      <p className="text-body text-muted-foreground">{description}</p>
      {(meta || soon) && (
        <div className="mt-auto flex items-center gap-2 pt-1">
          {soon ? (
            <span className="rounded-pill border border-border px-2 py-0.5 text-label text-muted-foreground">
              em breve
            </span>
          ) : (
            meta
          )}
        </div>
      )}
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

export function OptionCardGrid({ children }: { children: ReactNode }) {
  return (
    <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(16rem,1fr))]">
      {children}
    </div>
  )
}
