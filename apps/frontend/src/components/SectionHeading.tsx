import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface SectionHeadingProps {
  children: ReactNode
  // "h2" (padrão) = seção de topo dentro de uma página; "h3" = subseção.
  as?: 'h2' | 'h3'
  // Conteúdo à direita do título (filtros, toggles).
  actions?: ReactNode
  className?: string
}

// Cabeçalho de seção — <h2>/<h3> real, com peso e tamanho visíveis
// (text-title/text-subtitle da escala tipográfica). Substitui os
// `<h2 className="text-xs uppercase text-muted-foreground">` e os
// `<div>`/`<p className="text-sm font-semibold">` usados como título.
export function SectionHeading({ children, as = 'h2', actions, className }: SectionHeadingProps) {
  const Tag = as

  return (
    <div className={cn('flex flex-wrap items-center justify-between gap-2', className)}>
      <Tag
        className={cn('m-0', as === 'h2' ? 'font-bold text-title' : 'font-medium text-subtitle')}
      >
        {children}
      </Tag>
      {actions}
    </div>
  )
}
