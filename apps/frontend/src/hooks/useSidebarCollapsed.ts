import { useCallback, useState } from 'react'

const STORAGE_KEY = 'atlas:sidebar-collapsed'

function readStored(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

// Recolhedor do menu lateral (DatasetSidebar). Expandido é o padrão —
// mesma filosofia de persistência do useTheme: só grava, cai no default
// se localStorage estiver indisponível. Sem script bloqueante em
// index.html (diferente do tema): a sidebar só aparece depois que o
// projeto é resolvido no ProjectContext, então um flash de layout aqui é
// irrelevante.
export function useSidebarCollapsed() {
  const [collapsed, setCollapsedState] = useState<boolean>(readStored)

  const setCollapsed = useCallback((next: boolean) => {
    setCollapsedState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next ? '1' : '0')
    } catch {
      // localStorage indisponível (modo privado, etc.) — não persiste
      // entre sessões, mas continua funcionando na atual.
    }
  }, [])

  const toggle = useCallback(() => setCollapsed(!collapsed), [collapsed, setCollapsed])

  return { collapsed, toggle }
}
