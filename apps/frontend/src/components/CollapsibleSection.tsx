import { ChevronDown, ChevronRight } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { cn } from '@/lib/utils'

interface CollapsibleSectionProps {
  title: ReactNode
  // 'section' = tópico de topo da aba (equivalente ao antigo <h2>).
  // 'subsection' = bloco nomeado dentro de um tópico (ex: "Bases mais
  // favoritadas", "Drill-down").
  variant?: 'section' | 'subsection'
  defaultOpen?: boolean
  // Conteúdo à direita do título (ex: toggle de agrupamento) — fica fora
  // do trigger, sempre visível e clicável mesmo com a seção fechada.
  actions?: ReactNode
  children: ReactNode
}

export function CollapsibleSection({
  title,
  variant = 'section',
  defaultOpen = true,
  actions,
  children,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen)
  const isSection = variant === 'section'
  // Cabeçalho real (<h2>/<h3>) envolvendo o botão de disclosure — padrão
  // WAI-ARIA: o leitor de tela navega por cabeçalho e o botão anuncia
  // expandido/recolhido. Antes o trigger era só um <button> estilizado,
  // invisível pra navegação por cabeçalho.
  const Heading = isSection ? 'h2' : 'h3'

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Heading
          className={cn(
            'm-0',
            isSection ? 'font-semibold text-lg' : 'font-medium text-muted-foreground text-sm',
          )}
        >
          <CollapsibleTrigger className="flex items-center gap-1.5 text-left hover:text-foreground">
            {open ? (
              <ChevronDown size={isSection ? 16 : 14} aria-hidden="true" />
            ) : (
              <ChevronRight size={isSection ? 16 : 14} aria-hidden="true" />
            )}
            {title}
          </CollapsibleTrigger>
        </Heading>
        {actions}
      </div>
      <CollapsibleContent className={cn('flex flex-col gap-4', isSection ? 'pt-4' : 'pt-2')}>
        {children}
      </CollapsibleContent>
    </Collapsible>
  )
}
