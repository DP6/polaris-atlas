import { createContext, useContext } from 'react'
import type { TableDetail } from '@/types/catalog'

export interface AnalysisContextValue {
  projectId: string
  datasetId: string
  tableId: string
  tableDetail: TableDetail | undefined
  isView: boolean
}

const AnalysisContext = createContext<AnalysisContextValue | null>(null)

export function AnalysisContextProvider(props: {
  value: AnalysisContextValue
  children: React.ReactNode
}) {
  return <AnalysisContext.Provider value={props.value}>{props.children}</AnalysisContext.Provider>
}

// Contexto compartilhado pelas páginas do módulo de análise
// (`/analyze/:datasetId/:tableId/*`) — evita cada página re-derivar
// datasetId/tableId dos params e refazer o `useTableDetail`.
export function useAnalysisContext(): AnalysisContextValue {
  const ctx = useContext(AnalysisContext)
  if (!ctx) {
    throw new Error('useAnalysisContext deve ser usado dentro de <AnalysisLayout>')
  }
  return ctx
}
