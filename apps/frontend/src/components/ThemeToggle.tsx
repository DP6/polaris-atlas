import { Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useTheme } from '@/hooks/useTheme'

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  const isDark = theme === 'dark'

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            className="text-muted-foreground"
            onClick={toggleTheme}
            aria-label={isDark ? 'Mudar para tema claro' : 'Mudar para tema escuro'}
          />
        }
      >
        {isDark ? <Sun size={16} /> : <Moon size={16} />}
      </TooltipTrigger>
      <TooltipContent>{isDark ? 'Tema claro' : 'Tema escuro'}</TooltipContent>
    </Tooltip>
  )
}
