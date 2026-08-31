import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface LoadingStateProps {
  label?: string
  className?: string
}

// Estado de carregamento padrão da plataforma — spinner + texto, inline
// (canto superior esquerdo, como o conteúdo apareceria). Substitui os
// ~17 `<p className="text-muted-foreground">Carregando…</p>` soltos, cada
// um com um texto/tamanho um pouco diferente. `animate-spin` já respeita
// prefers-reduced-motion pela regra global do index.css.
export function LoadingState({ label = 'Carregando…', className }: LoadingStateProps) {
  return (
    <div
      role="status"
      className={cn('flex items-center gap-2 text-muted-foreground text-sm', className)}
    >
      <Loader2 size={16} className="animate-spin" aria-hidden="true" />
      {label}
    </div>
  )
}
