import { Copy, Gauge, Percent, Table2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { CompositeScoreRing } from '@/components/CompositeScoreRing'
import { HBarList } from '@/components/HBarList'
import { MetricGrid, MetricTile } from '@/components/MetricTile'
import { Panel } from '@/components/Panel'
import { SqlPreview } from '@/components/SqlPreview'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAnalysisContext } from '@/features/quality/analysisContext'
import { ColumnResultsTable } from '@/features/quality/ColumnResultsTable'
import { useEstimateProfiling, useRunProfiling } from '@/features/quality/hooks'
import { SaveRunToFolderDialog } from '@/features/quality/SaveRunToFolderDialog'
import { formatNumber, formatPercent } from '@/lib/format'
import { ApiError } from '@/lib/http-client'
import type { UniquenessMethod } from '@/types/profiling'

const NO_DATE_COLUMN = '__none__'
const DATE_TYPES = new Set(['DATE', 'DATETIME', 'TIMESTAMP'])
const HIGH_CARDINALITY_PCT = 50

const UNIQUENESS_METHOD_LABELS: Record<UniquenessMethod, string> = {
  approx: 'Aproximado (HLL)',
  exact: 'Exato',
}

// O fluxo config → estimar custo → executar → resultado da antiga aba
// "Análise de qualidade" do ProfilingDialog, agora numa página própria.
export function QualityAnalysisPanel() {
  const { projectId, datasetId, tableId, tableDetail, isView } = useAnalysisContext()

  const [samplePercent, setSamplePercent] = useState(100)
  const [uniquenessMethod, setUniquenessMethod] = useState<UniquenessMethod>('approx')
  const [dateColumn, setDateColumn] = useState(NO_DATE_COLUMN)
  const [dateWindowDays, setDateWindowDays] = useState(30)
  const [saveToFolderOpen, setSaveToFolderOpen] = useState(false)

  const estimateMutation = useEstimateProfiling()
  const runMutation = useRunProfiling()

  // biome-ignore lint/correctness/useExhaustiveDependencies: tableId é só gatilho; .reset muda de referência a cada render
  useEffect(() => {
    setSamplePercent(100)
    setUniquenessMethod('approx')
    setDateColumn(NO_DATE_COLUMN)
    setDateWindowDays(30)
    estimateMutation.reset()
    runMutation.reset()
  }, [tableId])

  const partitionColumn = tableDetail?.partition_column ?? null
  const dateColumns =
    tableDetail?.columns.filter((c) => DATE_TYPES.has(c.data_type.toUpperCase())) ?? []
  const orderedDateColumns =
    partitionColumn && dateColumns.some((c) => c.column_name === partitionColumn)
      ? [
          ...dateColumns.filter((c) => c.column_name === partitionColumn),
          ...dateColumns.filter((c) => c.column_name !== partitionColumn),
        ]
      : dateColumns

  function buildRequest() {
    const hasDateFilter = dateColumn !== NO_DATE_COLUMN
    return {
      projectId,
      datasetId,
      tableId,
      sample_percent: samplePercent,
      uniqueness_method: uniquenessMethod,
      date_column: hasDateFilter ? dateColumn : null,
      date_window_days: hasDateFilter ? dateWindowDays : null,
    }
  }

  const activeError = estimateMutation.error ?? runMutation.error
  const errorMessage =
    activeError instanceof ApiError
      ? activeError.message
      : activeError instanceof Error
        ? activeError.message
        : null
  const sql = runMutation.data?.sql ?? estimateMutation.data?.sql
  const result = runMutation.data

  const configRow = (
    <div className="flex flex-wrap items-end gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="sample-percent">Amostragem (%)</Label>
        <Input
          id="sample-percent"
          type="number"
          min={1}
          max={100}
          className="w-24"
          value={samplePercent}
          onChange={(e) => setSamplePercent(Number(e.target.value))}
          disabled={isView}
        />
        {isView && (
          <p className="text-xs text-status-warn-foreground">
            Amostragem não disponível para views
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1.5">
        <Label>Método unicidade</Label>
        <Select
          value={uniquenessMethod}
          onValueChange={(value) => setUniquenessMethod(value as UniquenessMethod)}
        >
          <SelectTrigger className="w-40">
            <SelectValue>
              {(value: UniquenessMethod) => UNIQUENESS_METHOD_LABELS[value]}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="approx">Aproximado (HLL)</SelectItem>
            <SelectItem value="exact">Exato</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label>Coluna de data</Label>
        <Select
          value={dateColumn}
          onValueChange={(value) => setDateColumn(value ?? NO_DATE_COLUMN)}
        >
          <SelectTrigger className="w-44">
            <SelectValue>
              {(value: string) => (value === NO_DATE_COLUMN ? 'Nenhuma' : value)}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NO_DATE_COLUMN}>Nenhuma</SelectItem>
            {orderedDateColumns.map((column) => (
              <SelectItem key={column.column_name} value={column.column_name}>
                {column.column_name}
                {column.column_name === partitionColumn ? ' (recomendada)' : ''}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {dateColumn !== NO_DATE_COLUMN && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="date-window">Janela (dias)</Label>
          <Input
            id="date-window"
            type="number"
            min={1}
            className="w-24"
            value={dateWindowDays}
            onChange={(e) => setDateWindowDays(Number(e.target.value))}
          />
        </div>
      )}

      <div className="ml-auto flex gap-2">
        <Button
          variant="outline"
          disabled={estimateMutation.isPending}
          onClick={() => estimateMutation.mutate(buildRequest())}
        >
          {estimateMutation.isPending ? 'Estimando…' : 'Estimar custo'}
        </Button>
        <Button
          className="dp6-gradient-primary"
          disabled={runMutation.isPending}
          onClick={() => runMutation.mutate(buildRequest())}
        >
          {runMutation.isPending ? 'Executando…' : 'Executar profile'}
        </Button>
      </div>
    </div>
  )

  return (
    <>
      <Panel
        title="Análise de qualidade"
        subtitle="Amostra a tabela coluna a coluna (completude, unicidade, duplicatas). Estime o custo antes de rodar — o resultado fica no histórico e pode ir pra uma pasta de comparação."
        filterRow={configRow}
      >
        {errorMessage && <p className="text-sm text-status-error-foreground">{errorMessage}</p>}

        {estimateMutation.data && !result && (
          <div className="flex gap-6 rounded-lg border border-border bg-card p-4 text-sm">
            <div>
              <p className="text-xs text-muted-foreground uppercase">Bytes estimados</p>
              <p className="font-bold text-lg">{estimateMutation.data.estimated_bytes_human}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase">Custo estimado</p>
              <p className="font-bold text-lg">
                US$ {estimateMutation.data.estimated_cost_usd.toFixed(8)}
              </p>
            </div>
          </div>
        )}

        {result && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-end">
              <Button variant="outline" size="sm" onClick={() => setSaveToFolderOpen(true)}>
                Salvar em pasta
              </Button>
            </div>

            <MetricGrid>
              <MetricTile
                label="Amostradas"
                value={formatNumber(result.table_summary.total_sampled_rows)}
                icon={<Percent size={14} />}
              />
              <MetricTile
                label="Total da tabela"
                value={formatNumber(result.table_summary.total_table_rows)}
                icon={<Table2 size={14} />}
              />
              <MetricTile
                label="Duplicatas est."
                value={formatPercent(result.table_summary.estimated_duplicate_pct)}
                icon={<Copy size={14} />}
              />
              <MetricTile
                label="Densidade geral"
                value={formatPercent(result.table_summary.overall_density)}
                icon={<Gauge size={14} />}
              />
            </MetricGrid>

            {result.excluded_columns.length > 0 && (
              <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                Colunas excluídas do profiling:
                {result.excluded_columns.map((excluded) => (
                  <Badge key={excluded.column_name} variant="outline" title={excluded.reason}>
                    {excluded.column_name}
                  </Badge>
                ))}
              </p>
            )}

            <ColumnResultsTable columns={result.columns} />

            {sql && <SqlPreview key="run" sql={sql} defaultOpen={false} />}
          </div>
        )}

        {!result && sql && <SqlPreview key="estimate" sql={sql} defaultOpen />}
      </Panel>

      {result && (
        <>
          <Panel
            title="Quality Score"
            subtitle="Composto — completude média, densidade geral e cobertura de tipo lógico."
          >
            <QualityScore
              overallDensity={result.table_summary.overall_density}
              completeness={
                result.columns.length
                  ? result.columns.reduce((s, c) => s + c.completeness_pct, 0) /
                    result.columns.length
                  : 0
              }
              typeCoverage={
                result.columns.length
                  ? (result.columns.filter((c) => Boolean(c.inferred_logical_type)).length /
                      result.columns.length) *
                    100
                  : 0
              }
            />
          </Panel>

          <Panel
            title="Cardinalidade por coluna"
            subtitle="Aproximação de valores distintos por coluna — passe o mouse pra ver a contagem exata."
          >
            <HBarList
              items={result.columns.map((c) => ({
                label: c.column_name,
                value: c.distinct_pct,
                displayValue: `${c.distinct_pct.toFixed(1)}%`,
                variant:
                  c.distinct_pct > HIGH_CARDINALITY_PCT ? ('key' as const) : ('cat' as const),
                tooltip: (
                  <>
                    <b>{c.column_name}</b>
                    <span className="text-muted-foreground">
                      {formatNumber(c.distinct_count)} distintos · {c.distinct_pct.toFixed(2)}%
                    </span>
                  </>
                ),
              }))}
              max={100}
            />
          </Panel>

          <SaveRunToFolderDialog
            open={saveToFolderOpen}
            onOpenChange={setSaveToFolderOpen}
            run={result}
          />
        </>
      )}
    </>
  )
}

function QualityScore({
  overallDensity,
  completeness,
  typeCoverage,
}: {
  overallDensity: number
  completeness: number
  typeCoverage: number
}) {
  const score = Math.round((overallDensity + completeness + typeCoverage) / 3)
  return (
    <CompositeScoreRing
      score={score}
      caption="score geral"
      segments={[
        {
          label: 'Completude média',
          value: Math.round(completeness),
          color: 'var(--color-status-ok)',
        },
        {
          label: 'Densidade geral',
          value: Math.round(overallDensity),
          color: 'var(--color-primary)',
        },
        {
          label: 'Colunas mapeadas',
          value: Math.round(typeCoverage),
          color: 'var(--color-status-info)',
        },
      ]}
    />
  )
}
