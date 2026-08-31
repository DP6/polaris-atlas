import type { ComponentProps } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

interface DateFieldProps extends Omit<ComponentProps<typeof Input>, 'type'> {
  label: string
  id: string
}

// Campo de data com <Label> associada e altura consistente com os demais
// controles de filtro (h-8). Envolve o <input type="date"> nativo — que
// já renderiza no formato local (dd/mm/aaaa em pt-BR) — em vez de deixá-lo
// solto sem rótulo.
export function DateField({ label, id, className, ...props }: DateFieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id} className="text-label text-muted-foreground">
        {label}
      </Label>
      <Input id={id} type="date" className={cn('h-8 w-[9.5rem]', className)} {...props} />
    </div>
  )
}
