import { ShieldAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
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
import type { MetadataColumnUpsertRequest, MetadataTableResponse } from '@/types/metadata'

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

  function saveColumn(columnName: string, request: MetadataColumnUpsertRequest, okMsg: string) {
    return upsertColumn
      .mutateAsync({ columnName, request })
      .then(() => toast.success(okMsg))
      .catch(() => toast.error(`Não foi possível salvar "${columnName}"`))
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Coluna</TableHead>
          <TableHead>Tipo (BQ)</TableHead>
          <TableHead>Descrição</TableHead>
          <TableHead>Termo de glossário</TableHead>
          <TableHead>PII</TableHead>
          {canManage && <TableHead className="w-20" />}
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
              pending={upsertColumn.isPending}
              onSaveText={(request) =>
                saveColumn(col.column_name, request, `Coluna "${col.column_name}" salva`)
              }
              onTogglePii={(flag) =>
                saveColumn(
                  col.column_name,
                  { pii_flag: flag },
                  flag
                    ? `"${col.column_name}" marcada como PII`
                    : `"${col.column_name}" marcada como não PII`,
                )
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
  pending,
  onSaveText,
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
  pending: boolean
  onSaveText: (request: MetadataColumnUpsertRequest) => void
  onTogglePii: (flag: boolean) => void
}) {
  const [descriptionDraft, setDescriptionDraft] = useState(description ?? '')
  const [glossaryDraft, setGlossaryDraft] = useState(glossaryTerm ?? '')

  // Re-sincroniza os rascunhos quando o valor salvo muda (após o próprio
  // save, ou uma edição concorrente que o refetch trouxe).
  useEffect(() => {
    setDescriptionDraft(description ?? '')
  }, [description])
  useEffect(() => {
    setGlossaryDraft(glossaryTerm ?? '')
  }, [glossaryTerm])

  const descriptionDirty = descriptionDraft !== (description ?? '')
  const glossaryDirty = glossaryDraft !== (glossaryTerm ?? '')
  const dirty = descriptionDirty || glossaryDirty

  function save() {
    const request: MetadataColumnUpsertRequest = {}
    if (descriptionDirty) request.description = descriptionDraft || null
    if (glossaryDirty) request.glossary_term = glossaryDraft || null
    onSaveText(request)
  }

  return (
    <TableRow>
      <TableCell className="font-medium">{column.column_name}</TableCell>
      <TableCell className="text-muted-foreground">{column.data_type}</TableCell>
      <TableCell>
        {canManage ? (
          <Input
            value={descriptionDraft}
            onChange={(e) => setDescriptionDraft(e.target.value)}
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
            disabled={!canManage || pending}
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
      {canManage && (
        <TableCell>
          <Button
            size="sm"
            variant="outline"
            className="h-8"
            disabled={!dirty || pending}
            onClick={save}
          >
            Salvar
          </Button>
        </TableCell>
      )}
    </TableRow>
  )
}
