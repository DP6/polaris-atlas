import { ArrowLeft } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'

interface PageHeaderProps {
  title: ReactNode
  description?: ReactNode
  // Ações à direita do título (RefreshButton, "Nova busca", etc.).
  actions?: ReactNode
  // Link "voltar" acima do título (ex: Administração).
  back?: { to: string; label: string }
  className?: string
}

// Cabeçalho de rota — um único <h1> por página, renderizado FORA dos
// ramos de loading/erro (antes cada rota copiava o bloco à mão, algumas
// com <h1> duplicado entre estados, e a rota índice sem <h1> nenhum).
export function PageHeader({ title, description, actions, back, className }: PageHeaderProps) {
  return (
    <div className={cn('flex flex-col gap-2', className)}>
      {back && (
        <Link
          to={back.to}
          className="flex w-fit items-center gap-1.5 text-muted-foreground text-sm hover:text-foreground"
        >
          <ArrowLeft size={14} aria-hidden="true" />
          {back.label}
        </Link>
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
