import { useState } from 'react'
import { ChoiceToggle } from '@/components/ChoiceToggle'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

const DEFAULT_OPTIONS = [30, 60, 90, 365] as const

interface LookbackPickerProps {
  value: number
  onChange: (days: number) => void
  // Presets em pills; qualquer outro valor entra pelo "Outro" + input.
  options?: readonly number[]
  label?: string
  min?: number
  max?: number
}

// Seletor "últimos N dias" — presets em `ChoiceToggle` + pill "Outro" com
// input numérico. Compartilhado por Tabelas órfãs e Budget de custo.
export function LookbackPicker({
  value,
  onChange,
  options = DEFAULT_OPTIONS,
  label = 'Período analisado (dias)',
  min = 1,
  max,
}: LookbackPickerProps) {
  const isPreset = options.includes(value)
  const [showCustom, setShowCustom] = useState(!isPreset)

  return (
    <div>
      <span className="mb-1.5 block text-xs font-medium text-muted-foreground">{label}</span>
      <div className="flex flex-wrap items-center gap-1">
        <ChoiceToggle
          aria-label={label}
          options={options.map((d): { value: number; label: string } => ({
            value: d,
            label: String(d),
          }))}
          value={showCustom ? -1 : value}
          onChange={(days) => {
            onChange(days)
            setShowCustom(false)
          }}
        />
        <button
          type="button"
          aria-pressed={showCustom}
          onClick={() => setShowCustom(true)}
          className={cn(
            'rounded-pill border px-3 py-1 text-xs font-medium transition-colors',
            showCustom
              ? 'border-primary bg-primary/10 text-foreground'
              : 'border-border text-muted-foreground hover:bg-muted',
          )}
        >
          Outro
        </button>
        {showCustom && (
          <Input
            type="number"
            min={min}
            max={max}
            className="h-7 w-20 text-xs"
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
          />
        )}
      </div>
    </div>
  )
}
