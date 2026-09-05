import { ShieldAlert } from 'lucide-react'
import { useState } from 'react'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useSuggestedPii, useUpsertColumnMetadata } from '@/features/metadata/hooks'
import type { ColumnDetail } from '@/types/catalog'
import type { MetadataTableResponse } from '@/types/metadata'

interface ColumnMetadataTableProps {
  projectId: string
  datasetId: string
  tableId: string
  bqColumns: ColumnDetail[]
  metadata: MetadataTableResponse
  canManage: boolean
}

// Enumeração de colunas vem do catalog (schema real do BigQuery, já
// carregado pelo AnalysisContext) — não do doc de metadados, que só tem
// as colunas já editadas alguma vez. Uma coluna dropada no BQ some
// daqui automaticamente (o backend também rejeita PUT nela, ver
// AC-META-005).
export function ColumnMetadataTable({
  projectId,
  datasetId,
  tableId,
  bqColumns,
  metadata,
  canManage,
}: ColumnMetadataTableProps) {
  const suggestedPiiQuery = useSuggestedPii(projectId, datasetId, tableId)
  const upsertColumn = useUpsertColumnMetadata(projectId, datasetId, tableId)

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Coluna</TableHead>
          <TableHead>Tipo (BQ)</TableHead>
          <TableHead>Descrição</TableHead>
          <TableHead>Termo de glossário</TableHead>
          <TableHead>PII</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {bqColumns.map((col) => {
          const meta = metadata.columns[col.column_name]
          const suggestion = suggestedPiiQuery.data?.columns.find(
            (c) => c.column_name === col.column_name,
          )
          return (
            <ColumnRow
              key={col.column_name}
              column={col}
              description={meta?.description ?? null}
              glossaryTerm={meta?.glossary_term ?? null}
              piiFlag={meta?.pii?.flag ?? suggestion?.flagged ?? false}
              piiConfirmed={meta?.pii?.source === 'manual'}
              suggestionFlagged={suggestion?.flagged}
              suggestionConfidence={suggestion?.confidence}
              canManage={canManage}
              onSaveDescription={(value) =>
                upsertColumn.mutate({
                  columnName: col.column_name,
                  request: { description: value || null },
                })
              }
              onSaveGlossaryTerm={(value) =>
                upsertColumn.mutate({
                  columnName: col.column_name,
                  request: { glossary_term: value || null },
                })
              }
              onTogglePii={(flag) =>
                upsertColumn.mutate({ columnName: col.column_name, request: { pii_flag: flag } })
              }
            />
          )
        })}
      </TableBody>
    </Table>
  )
}

function ColumnRow({
  column,
  description,
  glossaryTerm,
  piiFlag,
  piiConfirmed,
  suggestionFlagged,
  suggestionConfidence,
  canManage,
  onSaveDescription,
  onSaveGlossaryTerm,
  onTogglePii,
}: {
  column: ColumnDetail
  description: string | null
  glossaryTerm: string | null
  piiFlag: boolean
  piiConfirmed: boolean
  suggestionFlagged: boolean | undefined
  suggestionConfidence: 'high' | 'medium' | null | undefined
  canManage: boolean
  onSaveDescription: (value: string) => void
  onSaveGlossaryTerm: (value: string) => void
  onTogglePii: (flag: boolean) => void
}) {
  const [descriptionDraft, setDescriptionDraft] = useState(description ?? '')
  const [glossaryDraft, setGlossaryDraft] = useState(glossaryTerm ?? '')

  return (
    <TableRow>
      <TableCell className="font-medium">{column.column_name}</TableCell>
      <TableCell className="text-muted-foreground">{column.data_type}</TableCell>
      <TableCell>
        {canManage ? (
          <Input
            value={descriptionDraft}
            onChange={(e) => setDescriptionDraft(e.target.value)}
            onBlur={() => {
              if (descriptionDraft !== (description ?? '')) onSaveDescription(descriptionDraft)
            }}
            placeholder="descrição…"
            className="h-8 text-xs"
          />
        ) : (
          <span className="text-muted-foreground text-xs">{description ?? '—'}</span>
        )}
      </TableCell>
      <TableCell>
        {canManage ? (
          <Input
            value={glossaryDraft}
            onChange={(e) => setGlossaryDraft(e.target.value)}
            onBlur={() => {
              if (glossaryDraft !== (glossaryTerm ?? '')) onSaveGlossaryTerm(glossaryDraft)
            }}
            placeholder="termo…"
            className="h-8 text-xs"
          />
        ) : (
          <span className="text-muted-foreground text-xs">{glossaryTerm ?? '—'}</span>
        )}
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          <Checkbox
            id={`pii-${column.column_name}`}
            checked={piiFlag}
            disabled={!canManage}
            onCheckedChange={(checked) => onTogglePii(checked === true)}
          />
          <label htmlFor={`pii-${column.column_name}`} className="cursor-pointer text-xs">
            {piiFlag ? 'PII' : 'Não PII'}
          </label>
          {suggestionFlagged !== undefined && !piiConfirmed && (
            <Tooltip>
              <TooltipTrigger render={<span className="text-muted-foreground [&_svg]:size-3" />}>
                <ShieldAlert />
              </TooltipTrigger>
              <TooltipContent>
                Sugestão do scanner: {suggestionFlagged ? 'PII' : 'não PII'}
                {suggestionConfidence ? ` (confiança ${suggestionConfidence})` : ''} — ainda não
                confirmado
              </TooltipContent>
            </Tooltip>
          )}
        </div>
      </TableCell>
    </TableRow>
  )
}
