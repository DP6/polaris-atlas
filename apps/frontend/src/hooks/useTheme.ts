import { useCallback, useState } from 'react'

const STORAGE_KEY = 'observability-hub:theme'

export type Theme = 'dark' | 'light'

function readStoredTheme(): Theme {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle('dark', theme === 'dark')
}

// Dark é o padrão do produto (docs/skills/frontend.md) — só persiste
// "light" no localStorage; ausência de valor salvo (ou localStorage
// indisponível) sempre cai em dark. O script bloqueante em index.html
// já aplicou a classe .dark antes do primeiro paint, usando a mesma
// leitura — este hook só sincroniza o estado do React com o DOM.
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(readStoredTheme)

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next)
    applyTheme(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // localStorage indisponível (modo privado, etc.) — o tema escolhido
      // não persiste entre sessões, mas continua funcionando na atual.
    }
  }, [])

  const toggleTheme = useCallback(() => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }, [theme, setTheme])

  return { theme, setTheme, toggleTheme }
}
