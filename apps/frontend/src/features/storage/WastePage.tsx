import { useState } from 'react'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { PageHeader } from '@/components/PageHeader'
import { RefreshButton } from '@/components/RefreshButton'
import { SortableTableHead } from '@/components/SortableTableHead'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { WarningCallout } from '@/components/WarningCallout'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { useWasteCandidates } from '@/features/storage/hooks'
import { useTableFilterSort } from '@/hooks/useTableFilterSort'
import { formatBytes, formatNumber, formatUsd } from '@/lib/format'
import type { WasteCandidate } from '@/types/storage'

const MIN_DAYS_OPTIONS = [30, 60, 90] as const
const CUSTOM_DAYS_OPTION = '__custom__'

// Select de dias com opção de digitar valor livre — os presets continuam
// como atalho, "Outro" revela um Input numérico. Mesmo comportamento nos
// dois pontos de renderização (gate de pré-run e filtro inline pós-run).
function MinDaysPicker({ value, onChange }: { value: number; onChange: (days: number) => void }) {
  const isPreset = (MIN_DAYS_OPTIONS as readonly number[]).includes(value)
  const [showCustom, setShowCustom] = useState(!isPreset)

  return (
    <div className="flex items-center gap-2">
      <Select
        value={showCustom ? CUSTOM_DAYS_OPTION : String(value)}
        onValueChange={(next) => {
          if (!next) return
          if (next === CUSTOM_DAYS_OPTION) {
            setShowCustom(true)
            return
          }
          setShowCustom(false)
          onChange(Number(next))
        }}
      >
        <SelectTrigger className="w-24">
          <SelectValue>{() => (showCustom ? 'Outro' : `${value} dias`)}</SelectValue>
        </SelectTrigger>
        <SelectContent>
          {MIN_DAYS_OPTIONS.map((days) => (
            <SelectItem key={days} value={String(days)}>
              {days} dias
            </SelectItem>
          ))}
          <SelectItem value={CUSTOM_DAYS_OPTION}>Outro</SelectItem>
        </SelectContent>
      </Select>
      {showCustom && (
        <Input
          type="number"
          min={1}
          className="h-8 w-20"
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
        />
      )}
    </div>
  )
}

type SortKey =
  | 'bucket_name'
  | 'eligible_object_count'
  | 'eligible_size_bytes'
  | 'oldest_object_age_days'
  | 'estimated_savings_usd_month_min'
  | 'confidence'

function compare(a: WasteCandidate, b: WasteCandidate, key: SortKey): number {
  if (key === 'bucket_name') {
    return a.bucket_name.localeCompare(b.bucket_name)
  }
  if (key === 'confidence') {
    return a.confidence.localeCompare(b.confidence)
  }
  return a[key] - b[key]
}

function ConfidenceBadge({ candidate }: { candidate: WasteCandidate }) {
  if (candidate.confidence === 'usage_confirmed') {
    return (
      <Badge
        variant="secondary"
        className="border-status-ok/30 bg-status-ok/10 text-status-ok-foreground"
        title={`${candidate.usage_confirmed_object_count} de ${candidate.eligible_object_count} objetos sem leitura registrada nos últimos 90 dias`}
      >
        Sem leitura confirmada
      </Badge>
    )
  }
  return (
    <Badge
      variant="secondary"
      title={
        candidate.usage_confirmed_object_count > 0
          ? `${candidate.usage_confirmed_object_count} de ${candidate.eligible_object_count} objetos sem leitura registrada — os demais foram lidos nos últimos 90 dias`
          : 'Baseado só em idade + ausência de lifecycle rule, sem checagem de leitura'
      }
    >
      Só configuração
    </Badge>
  )
}

export function WastePage() {
  const { projectId } = useProjectContext()
  const [minDaysUnused, setMinDaysUnused] = useState(60)
  const [hasRun, setHasRun] = useState(false)
  const wasteQuery = useWasteCandidates(projectId, minDaysUnused, hasRun)
  const data = wasteQuery.data

  const {
    sortKey,
    sortDir,
    toggleSort,
    visibleRows: visibleCandidates,
  } = useTableFilterSort<WasteCandidate, SortKey>({
    rows: data?.candidates ?? [],
    initialSortKey: 'estimated_savings_usd_month_min',
    compare,
    matches: () => true,
  })

  if (!hasRun) {
    return (
      <div className="flex flex-col gap-4">
        <PageHeader
          title="Scanner de desperdício"
          description={
            'Sinaliza buckets com objetos em storage class STANDARD parados há muito tempo, ' +
            'candidatos a mudar pra uma classe mais barata (Nearline/Coldline/Archive) — baseado ' +
            'em idade do objeto + ausência de lifecycle rule já configurada. Quando o audit log ' +
            'de leitura de objeto (DATA_READ) está habilitado no projeto, a confiança sobe pra ' +
            '"sem leitura confirmada" em vez de só "configuração"; sem ele, a checagem degrada ' +
            'graciosamente pra só idade + config, sem bloquear o resultado.'
          }
        />

        <div className="flex flex-col gap-4 rounded-lg border border-border p-4">
          <div>
            <span className="mb-1.5 block text-xs font-medium text-muted-foreground">
              Objetos STANDARD sem modificação há pelo menos
            </span>
            <MinDaysPicker value={minDaysUnused} onChange={setMinDaysUnused} />
          </div>

          <div>
            <Button onClick={() => setHasRun(true)} disabled={wasteQuery.isFetching}>
              {wasteQuery.isFetching ? 'Executando…' : 'Executar'}
            </Button>
          </div>
        </div>
      </div>
    )
  }

  if (wasteQuery.isLoading) {
    return <p className="text-muted-foreground">Carregando…</p>
  }

  if (wasteQuery.isError) {
    return <ApiErrorNotice error={wasteQuery.error} />
  }

  if (!data) return null

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Scanner de desperdício"
        description={`${data.candidates.length} buckets candidatos a mudança de storage class`}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => setHasRun(false)}>
              Nova busca
            </Button>
            <RefreshButton
              isRefreshing={wasteQuery.isFetching}
              onRefresh={() => wasteQuery.refetch()}
            />
          </>
        }
      />

      {data.usage_check_warning && <WarningCallout>{data.usage_check_warning}</WarningCallout>}

      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">
          Objetos STANDARD sem modificação há pelo menos
        </span>
        <MinDaysPicker value={minDaysUnused} onChange={setMinDaysUnused} />
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <SortableTableHead
              label="Bucket"
              active={sortKey === 'bucket_name'}
              direction={sortDir}
              onClick={() => toggleSort('bucket_name')}
            />
            <SortableTableHead
              label="Objetos elegíveis"
              active={sortKey === 'eligible_object_count'}
              direction={sortDir}
              onClick={() => toggleSort('eligible_object_count')}
              align="right"
            />
            <SortableTableHead
              label="Tamanho"
              active={sortKey === 'eligible_size_bytes'}
              direction={sortDir}
              onClick={() => toggleSort('eligible_size_bytes')}
              align="right"
            />
            <SortableTableHead
              label="Objeto mais antigo"
              active={sortKey === 'oldest_object_age_days'}
              direction={sortDir}
              onClick={() => toggleSort('oldest_object_age_days')}
              align="right"
            />
            <SortableTableHead
              label="Economia estimada/mês"
              active={sortKey === 'estimated_savings_usd_month_min'}
              direction={sortDir}
              onClick={() => toggleSort('estimated_savings_usd_month_min')}
              align="right"
            />
            <SortableTableHead
              label="Confiança"
              active={sortKey === 'confidence'}
              direction={sortDir}
              onClick={() => toggleSort('confidence')}
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleCandidates.map((candidate) => (
            <TableRow key={candidate.bucket_name}>
              <TableCell className="font-medium">{candidate.bucket_name}</TableCell>
              <TableCell className="text-right">
                {formatNumber(candidate.eligible_object_count)}
              </TableCell>
              <TableCell className="text-right">
                {formatBytes(candidate.eligible_size_bytes)}
              </TableCell>
              <TableCell className="text-right">{candidate.oldest_object_age_days} dias</TableCell>
              <TableCell className="text-right" title={data.savings_disclaimer}>
                {formatUsd(candidate.estimated_savings_usd_month_min)} –{' '}
                {formatUsd(candidate.estimated_savings_usd_month_max)}
              </TableCell>
              <TableCell>
                <ConfidenceBadge candidate={candidate} />
              </TableCell>
            </TableRow>
          ))}
          {visibleCandidates.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-muted-foreground">
                Nenhum bucket candidato encontrado com esse threshold.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
