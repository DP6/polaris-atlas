import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useDatasets, useTables } from '@/features/catalog/hooks'
import { useBudgets, useRemoveBudget, useUpsertBudget } from '@/features/finops/hooks'
import { formatUsd } from '@/lib/format'
import { ApiError } from '@/lib/http-client'
import type { BudgetEntry, BudgetScope } from '@/types/finops'

interface BudgetConfigDialogProps {
  projectId: string | undefined
  open: boolean
  onOpenChange: (open: boolean) => void
}

function budgetLabel(b: BudgetEntry): string {
  if (b.scope === 'project') return 'Projeto inteiro'
  if (b.scope === 'dataset') return `Dataset ${b.dataset_id}`
  return `Tabela ${b.dataset_id}.${b.table_id}`
}

// Cadastro simples de meta de custo mensal (R2-9): escopo projeto / dataset
// / tabela, valor em USD, sem compartilhamento entre usuários. Lista as
// metas já salvas com remover inline.
export function BudgetConfigDialog({ projectId, open, onOpenChange }: BudgetConfigDialogProps) {
  const [scope, setScope] = useState<BudgetScope>('project')
  const [datasetId, setDatasetId] = useState('')
  const [tableId, setTableId] = useState('')
  const [amount, setAmount] = useState('')

  const budgetsQuery = useBudgets(projectId)
  const datasetsQuery = useDatasets(projectId)
  const tablesQuery = useTables(projectId, scope === 'table' ? datasetId : undefined)
  const upsert = useUpsertBudget(projectId)
  const remove = useRemoveBudget(projectId)

  const amountNumber = Number(amount)
  const canSubmit =
    Number.isFinite(amountNumber) &&
    amountNumber > 0 &&
    (scope === 'project' ||
      (scope === 'dataset' && datasetId) ||
      (scope === 'table' && datasetId && tableId))

  const errorMessage = [upsert.error, remove.error]
    .map((e) => (e instanceof ApiError ? e.message : null))
    .find((m) => m !== null)

  function reset() {
    setScope('project')
    setDatasetId('')
    setTableId('')
    setAmount('')
    upsert.reset()
    remove.reset()
  }

  function handleSubmit() {
    if (!canSubmit) return
    upsert.mutate(
      {
        scope,
        dataset_id: scope === 'project' ? null : datasetId,
        table_id: scope === 'table' ? tableId : null,
        amount_usd: amountNumber,
      },
      { onSuccess: () => setAmount('') },
    )
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset()
        onOpenChange(next)
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Configurar budget</DialogTitle>
          <DialogDescription>
            Meta de custo mensal (só sua — não é compartilhada). A meta de escopo "projeto" vira a
            linha de referência do gráfico de custo.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="budget-scope">Escopo</Label>
            <Select
              value={scope}
              onValueChange={(v) => {
                setScope((v as BudgetScope) ?? 'project')
                setDatasetId('')
                setTableId('')
              }}
            >
              <SelectTrigger id="budget-scope">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="project">Projeto inteiro</SelectItem>
                <SelectItem value="dataset">Dataset</SelectItem>
                <SelectItem value="table">Tabela</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {scope !== 'project' && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="budget-dataset">Dataset</Label>
              <Select
                value={datasetId}
                onValueChange={(v) => {
                  setDatasetId(v ?? '')
                  setTableId('')
                }}
              >
                <SelectTrigger id="budget-dataset">
                  <SelectValue placeholder="Selecione um dataset…" />
                </SelectTrigger>
                <SelectContent>
                  {(datasetsQuery.data?.datasets ?? []).map((d) => (
                    <SelectItem key={d.dataset_id} value={d.dataset_id}>
                      {d.dataset_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {scope === 'table' && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="budget-table">Tabela</Label>
              <Select
                value={tableId}
                onValueChange={(v) => setTableId(v ?? '')}
                disabled={!datasetId}
              >
                <SelectTrigger id="budget-table">
                  <SelectValue placeholder="Selecione uma tabela…" />
                </SelectTrigger>
                <SelectContent>
                  {(tablesQuery.data?.tables ?? []).map((t) => (
                    <SelectItem key={t.table_id} value={t.table_id}>
                      {t.table_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="budget-amount">Valor mensal (US$)</Label>
            <Input
              id="budget-amount"
              type="number"
              min={0}
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="ex: 250"
            />
          </div>

          {errorMessage && <p className="text-sm text-status-error-foreground">{errorMessage}</p>}
        </div>

        {(budgetsQuery.data?.budgets.length ?? 0) > 0 && (
          <div className="flex flex-col gap-1.5 border-border border-t pt-3">
            <p className="text-label text-muted-foreground uppercase tracking-wide">
              Metas cadastradas
            </p>
            <ul className="flex flex-col gap-1">
              {(budgetsQuery.data?.budgets ?? []).map((b) => (
                <li
                  key={`${b.scope}:${b.dataset_id}:${b.table_id}`}
                  className="flex items-center justify-between gap-3 text-body"
                >
                  <span className="min-w-0 truncate">
                    {budgetLabel(b)} — <b className="tabular-nums">{formatUsd(b.amount_usd)}/mês</b>
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Remover meta ${budgetLabel(b)}`}
                    disabled={remove.isPending}
                    onClick={() =>
                      remove.mutate({
                        scope: b.scope,
                        datasetId: b.dataset_id,
                        tableId: b.table_id,
                      })
                    }
                  >
                    <Trash2 size={14} />
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Fechar
          </Button>
          <Button disabled={!canSubmit || upsert.isPending} onClick={handleSubmit}>
            {upsert.isPending ? 'Salvando…' : 'Salvar meta'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
