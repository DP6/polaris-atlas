import type { LucideIcon } from 'lucide-react'
import { Inbox } from 'lucide-react'
import type { ReactNode } from 'react'
import { TableCell, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: ReactNode
  action?: ReactNode
  className?: string
}

// Estado vazio padrão da plataforma — ícone + título + descrição/ação
// opcionais. Substitui os `<p className="text-sm text-muted-foreground">
// Nenhum … </p>` soltos. Para tabela, usar <EmptyStateRow>.
export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn('flex flex-col items-center justify-center gap-2 py-12 text-center', className)}
    >
      <Icon size={28} className="text-muted-foreground" aria-hidden="true" />
      <p className="font-medium text-sm">{title}</p>
      {description && <p className="max-w-[46ch] text-muted-foreground text-sm">{description}</p>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}

interface EmptyStateRowProps {
  colSpan: number
  children: ReactNode
}

// Mesmo papel, dentro de <TableBody> — mantém a semântica de tabela
// (linha `colSpan` centralizada), padrão já usado nas páginas de resultado.
export function EmptyStateRow({ colSpan, children }: EmptyStateRowProps) {
  return (
    <TableRow className="hover:bg-transparent">
      <TableCell colSpan={colSpan} className="h-24 text-center text-muted-foreground">
        {children}
      </TableCell>
    </TableRow>
  )
}
