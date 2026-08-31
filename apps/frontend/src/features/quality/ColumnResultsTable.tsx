import { StatusBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { CompletenessBar } from '@/features/quality/CompletenessBar'
import type { ColumnProfile, QualityFlag, ScalarValue } from '@/types/profiling'

function formatScalar(value: ScalarValue): string {
  if (value === null) return '—'
  return String(value)
}

// distinct_pct alto = mais provável ser uma chave/id (alta cardinalidade);
// baixo = mais provável ser categórico (baixa cardinalidade).
const HIGH_CARDINALITY_THRESHOLD = 50

const QUALITY_FLAG_LABELS: Record<QualityFlag, string> = {
  ok: 'OK',
  warning: 'Atenção',
  critical: 'Crítico',
}

// Flag de qualidade como <StatusBadge> (ícone + rótulo) — não comunicar
// estado só por cor (WCAG 1.4.1, ver docs/frontend/accessibility.md).
const QUALITY_FLAG_STATUS: Record<QualityFlag, 'ok' | 'warn' | 'error'> = {
  ok: 'ok',
  warning: 'warn',
  critical: 'error',
}

export function ColumnResultsTable({ columns }: { columns: ColumnProfile[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="text-xs">Coluna</TableHead>
          <TableHead className="text-xs">Tipo</TableHead>
          <TableHead className="text-xs">Completude</TableHead>
          <TableHead className="text-xs">Unicidade (HLL)</TableHead>
          <TableHead className="text-xs">Min</TableHead>
          <TableHead className="text-xs">Max</TableHead>
          <TableHead className="text-xs">Tipo lógico</TableHead>
          <TableHead className="text-xs">Quality flag</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {columns.map((column) => (
          <TableRow key={column.column_name}>
            <TableCell className="text-xs font-medium">{column.column_name}</TableCell>
            <TableCell className="text-xs text-muted-foreground">{column.data_type}</TableCell>
            <TableCell className="text-xs">
              <CompletenessBar value={column.completeness_pct} flag={column.quality_flag} />
            </TableCell>
            <TableCell className="text-xs">
              <span className="font-medium">{column.distinct_pct.toFixed(2)}%</span>
              <span className="ml-1 text-xs text-muted-foreground">({column.distinct_count})</span>
              <Badge variant="outline" className="ml-1.5">
                {column.distinct_pct > HIGH_CARDINALITY_THRESHOLD ? 'chave' : 'categórica'}
              </Badge>
            </TableCell>
            <TableCell
              className="max-w-[110px] truncate text-xs text-muted-foreground"
              title={formatScalar(column.min_value)}
            >
              {formatScalar(column.min_value)}
            </TableCell>
            <TableCell
              className="max-w-[110px] truncate text-xs text-muted-foreground"
              title={formatScalar(column.max_value)}
            >
              {formatScalar(column.max_value)}
            </TableCell>
            <TableCell className="text-xs">
              <Badge variant="outline">{column.inferred_logical_type}</Badge>
            </TableCell>
            <TableCell className="text-xs">
              <StatusBadge status={QUALITY_FLAG_STATUS[column.quality_flag]}>
                {QUALITY_FLAG_LABELS[column.quality_flag]}
              </StatusBadge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
