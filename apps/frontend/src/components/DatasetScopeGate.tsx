import type { ReactNode } from 'react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { useDatasets } from '@/features/catalog/hooks'

interface DatasetScopeGateProps {
  projectId: string | undefined
  title: string
  description: ReactNode
  extraControls?: ReactNode
  runLabel?: string
  isRunning?: boolean
  onRun: (datasets: string[]) => void
}

// Tela de pré-execução compartilhada por telas que escaneiam o projeto
// inteiro (tabelas sem consumidor, candidatas a particionamento, tabelas
// sem uso) — obriga escolher o escopo (1+ datasets, ou "Todos") antes de
// disparar a query real, mesmo racional do ColumnTypeScopePicker (que é
// por tabela, não por dataset — aqui a granularidade certa é dataset).
export function DatasetScopeGate({
  projectId,
  title,
  description,
  extraControls,
  runLabel = 'Executar',
  isRunning = false,
  onRun,
}: DatasetScopeGateProps) {
  const datasetsQuery = useDatasets(projectId)
  const datasets = datasetsQuery.data?.datasets ?? []
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const allSelected = datasets.length > 0 && selected.size === datasets.length

  function toggleDataset(datasetId: string) {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(datasetId)) {
        next.delete(datasetId)
      } else {
        next.add(datasetId)
      }
      return next
    })
  }

  function toggleAll() {
    setSelected(allSelected ? new Set() : new Set(datasets.map((d) => d.dataset_id)))
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold">{title}</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{description}</p>
      </div>

      <div className="flex flex-col gap-4 rounded-lg border border-border p-4">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <Checkbox
              checked={allSelected}
              disabled={datasetsQuery.isLoading || datasets.length === 0}
              onCheckedChange={toggleAll}
            />
            <button
              type="button"
              onClick={toggleAll}
              disabled={datasets.length === 0}
              className="text-sm font-medium hover:text-primary"
            >
              Todos os datasets
            </button>
          </div>

          {datasetsQuery.isLoading && (
            <p className="text-sm text-muted-foreground">Carregando datasets…</p>
          )}
          {!datasetsQuery.isLoading && datasets.length === 0 && (
            <p className="text-sm text-muted-foreground">Nenhum dataset encontrado.</p>
          )}
          <div className="grid max-h-64 grid-cols-2 gap-1.5 overflow-y-auto sm:grid-cols-3">
            {datasets.map((dataset) => (
              <div key={dataset.dataset_id} className="flex items-center gap-2">
                <Checkbox
                  checked={selected.has(dataset.dataset_id)}
                  onCheckedChange={() => toggleDataset(dataset.dataset_id)}
                />
                <button
                  type="button"
                  onClick={() => toggleDataset(dataset.dataset_id)}
                  className="truncate text-sm hover:text-primary"
                >
                  {dataset.dataset_id}
                </button>
              </div>
            ))}
          </div>
        </div>

        {extraControls}

        <div>
          <Button onClick={() => onRun([...selected])} disabled={selected.size === 0 || isRunning}>
            {isRunning ? 'Executando…' : runLabel}
          </Button>
          {selected.size === 0 && (
            <p className="mt-1.5 text-xs text-muted-foreground">
              Escolha ao menos um dataset (ou "Todos os datasets") antes de executar.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
