import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface ChoiceOption<T> {
  value: T
  label: ReactNode
}

interface ChoiceToggleProps<T> {
  options: ChoiceOption<T>[]
  value: T
  onChange: (value: T) => void
  // "md" (padrão) = px-3 py-1 text-xs; "sm" = pill compacto pra sidebar.
  size?: 'sm' | 'md'
  'aria-label'?: string
  className?: string
}

const SIZE_CLASS = {
  sm: 'px-2 py-0.5 text-[11px]',
  md: 'px-3 py-1 text-xs',
} as const

// Grupo "escolher um" em pills — o padrão `rounded-pill border` com
// primária no ativo, copiado à mão em LookbackPicker, QuantityPicker e no
// gate do BudgetPage. `aria-pressed` + `role="group"` pro leitor de tela.
export function ChoiceToggle<T extends string | number>({
  options,
  value,
  onChange,
  size = 'md',
  className,
  'aria-label': ariaLabel,
}: ChoiceToggleProps<T>) {
  return (
    // biome-ignore lint/a11y/useSemanticElements: role="group" + aria-label é o padrão WAI-ARIA pra um grupo de toggles rotulado; <fieldset> traz reset/legend que não cabem num segmented control
    <div role="group" aria-label={ariaLabel} className={cn('flex flex-wrap gap-1', className)}>
      {options.map((opt) => {
        const active = opt.value === value
        return (
          <button
            key={String(opt.value)}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              'rounded-pill border font-medium transition-colors',
              SIZE_CLASS[size],
              active
                ? 'border-primary bg-primary/10 text-foreground'
                : 'border-border text-muted-foreground hover:bg-muted',
            )}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}
