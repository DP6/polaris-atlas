import { ArrowLeft } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'

interface PageHeaderProps {
  title: ReactNode
  description?: ReactNode
  // Ações à direita do título (RefreshButton, "Nova busca", etc.).
  actions?: ReactNode
  // Link "voltar" explícito acima do título — quando o destino tem um pai
  // semântico claro (ex: sub-página de módulo → chooser). Sem isso, o
  // PageHeader ainda renderiza um "Voltar" genérico por histórico.
  back?: { to: string; label: string }
  className?: string
}

const BACK_LINK_CLASS =
  'flex w-fit items-center gap-1.5 text-muted-foreground text-sm hover:text-foreground'

// Cabeçalho de rota — um único <h1> por página. Todo PageHeader tem um
// controle "Voltar" no canto superior esquerdo (rodada 3): `back={{to,label}}`
// quando há um pai semântico; senão um "Voltar" genérico que usa o
// histórico do browser (fallback `/`). Só a home `/` fica sem.
export function PageHeader({ title, description, actions, back, className }: PageHeaderProps) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const isHome = pathname === '/'

  return (
    <div className={cn('-mx-2 flex flex-col gap-2 rounded-xl px-2 py-1.5', className)}>
      {back ? (
        <Link to={back.to} className={BACK_LINK_CLASS}>
          <ArrowLeft size={14} aria-hidden="true" />
          {back.label}
        </Link>
      ) : (
        !isHome && (
          <button
            type="button"
            onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/'))}
            className={BACK_LINK_CLASS}
          >
            <ArrowLeft size={14} aria-hidden="true" />
            Voltar
          </button>
        )
      )}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="font-bold text-display">{title}</h1>
          {description && (
            <p className="mt-1 max-w-[65ch] text-body text-muted-foreground">{description}</p>
          )}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
    </div>
  )
}
