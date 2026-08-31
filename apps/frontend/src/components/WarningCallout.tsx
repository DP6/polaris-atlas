import { Info, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface WarningCalloutProps {
  children: ReactNode
  // "warning" (padrão) = degradação / heads-up (ex: resultado vazio com
  // explicação, cache não gerado, retenção de audit log). "info" = aviso
  // neutro (ex: grafo de lineage truncado no limite de hops).
  variant?: 'warning' | 'info'
  className?: string
}

const STYLES = {
  warning: {
    box: 'border-status-warn/30 bg-status-warn/12 text-status-warn-foreground',
    Icon: TriangleAlert,
  },
  info: {
    box: 'border-status-info/30 bg-status-info/12 text-status-info-foreground',
    Icon: Info,
  },
} as const

// Substitui as ~10 cópias do `<div className="rounded-lg border
// border-status-warn/30 bg-status-warn/10 p-3 text-sm text-status-warn">`
// espalhadas por lineage/access/finops/storage/pii/orphans. `role="status"`
// para o leitor de tela anunciar; ícone + texto (não depende só de cor);
// texto de status-*-foreground (contraste AA nos 2 temas).
export function WarningCallout({ children, variant = 'warning', className }: WarningCalloutProps) {
  const { box, Icon } = STYLES[variant]

  return (
    <div
      role="status"
      className={cn('flex items-start gap-2 rounded-lg border p-3 text-sm', box, className)}
    >
      <Icon size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
      <div className="max-w-[65ch] leading-relaxed">{children}</div>
    </div>
  )
}
