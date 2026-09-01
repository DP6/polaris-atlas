import { Database } from 'lucide-react'
import { EmptyState } from '@/components/EmptyState'

export function CatalogOverviewPage() {
  return (
    <div className="flex h-full flex-col">
      {/* A rota índice não tem título visível (é uma tela de "escolha algo"),
          mas precisa de um <h1> pra dar nome à página no leitor de tela. */}
      <h1 className="sr-only">Catálogo de Dados</h1>
      <div className="flex flex-1 items-center justify-center">
        <EmptyState
          icon={Database}
          title="Selecione um dataset na barra lateral"
          description="para ver o catálogo de tabelas e views."
        />
      </div>
    </div>
  )
}
