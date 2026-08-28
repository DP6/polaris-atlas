import { AlertCircle, AlertTriangle, Check, Info, Loader2 } from 'lucide-react'
import type { ComponentProps, ReactNode } from 'react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

type Status = 'ok' | 'warn' | 'error' | 'info' | 'running' | 'neutral'

interface StatusBadgeProps {
  status: Status
  children: ReactNode
  className?: string
}

const MAP: Record<
  Status,
  { variant: ComponentProps<typeof Badge>['variant']; Icon: typeof Check | null; spin?: boolean }
> = {
  ok: { variant: 'success', Icon: Check },
  warn: { variant: 'warning', Icon: AlertTriangle },
  error: { variant: 'error', Icon: AlertCircle },
  info: { variant: 'info', Icon: Info },
  running: { variant: 'info', Icon: Loader2, spin: true },
  neutral: { variant: 'outline', Icon: null },
}

// Badge de estado com ícone + rótulo — nunca comunica o estado só por
// cor (WCAG 1.4.1). Cor de texto via --status-*-foreground (AA nos 2
// temas). Substitui os `<Badge className="... text-status-warn">` à mão.
export function StatusBadge({ status, children, className }: StatusBadgeProps) {
  const { variant, Icon, spin } = MAP[status]

  return (
    <Badge variant={variant} className={cn('gap-1', className)}>
      {Icon && <Icon size={11} className={spin ? 'animate-spin' : undefined} aria-hidden="true" />}
      {children}
    </Badge>
  )
}
