import { type ReactNode, useCallback, useState } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'

export interface ChartTooltipState {
  x: number
  y: number
  content: ReactNode
}

interface PointerLike {
  clientX: number
  clientY: number
}

// Tooltip flutuante compartilhado de gráfico/mini-gráfico — segue o cursor,
// some ao sair. Referência de comportamento: `#hoverTip` do protótipo
// visual (não a implementação vanilla — aqui é React + portal).
//
// Uso:
//   const tip = useChartTooltip()
//   <rect onMouseMove={(e) => tip.show(e, <><b>{label}</b><span>{value}</span></>)}
//         onMouseLeave={tip.hide} />
//   ...
//   <ChartTooltip state={tip.state} />   // uma vez, no fim da árvore da tela
export function useChartTooltip() {
  const [state, setState] = useState<ChartTooltipState | null>(null)
  const show = useCallback((e: PointerLike, content: ReactNode) => {
    setState({ x: e.clientX, y: e.clientY, content })
  }, [])
  const move = useCallback((e: PointerLike) => {
    setState((prev) => (prev ? { ...prev, x: e.clientX, y: e.clientY } : prev))
  }, [])
  const hide = useCallback(() => setState(null), [])
  return { state, show, move, hide }
}

// Renderiza o balão. Portal pro <body> pra escapar de qualquer `overflow`
// dos containers de gráfico. `pointer-events-none` pra nunca roubar o
// mousemove do elemento por baixo.
export function ChartTooltip({
  state,
  className,
}: {
  state: ChartTooltipState | null
  className?: string
}) {
  if (!state || typeof document === 'undefined') return null

  const pad = 14
  const flipX = state.x + 260 > window.innerWidth
  const flipY = state.y + 140 > window.innerHeight

  return createPortal(
    <div
      role="tooltip"
      className={cn(
        'pointer-events-none fixed z-50 max-w-60 rounded-lg border border-border bg-popover px-3 py-2 text-label text-popover-foreground shadow-elevation-1',
        className,
      )}
      style={{
        left: state.x + (flipX ? -pad : pad),
        top: state.y + (flipY ? -pad : pad),
        transform: `translate(${flipX ? '-100%' : '0'}, ${flipY ? '-100%' : '0'})`,
      }}
    >
      {state.content}
    </div>,
    document.body,
  )
}
