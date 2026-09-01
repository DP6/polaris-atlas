import { Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { EmptyState } from '@/components/EmptyState'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useDatasets, useTables } from '@/features/catalog/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { formatDate, formatNumber } from '@/lib/format'

// Entrada "por função → tabela" pro módulo de análise (a outra é
// Catálogo de Dados → dataset → "Analisar"). Escolhe um dataset, lista as
// tabelas, e cada "Analisar" abre a tela de escolha de tipo de análise.
export function QualityTablesPage() {
  const { projectId } = useProjectContext()
  const navigate = useNavigate()
  const datasetsQuery = useDatasets(projectId)
  const [datasetId, setDatasetId] = useState('')
  const tablesQuery = useTables(projectId, datasetId || undefined)

  if (datasetsQuery.isLoading) return <LoadingState />
  if (datasetsQuery.isError) return <ApiErrorNotice error={datasetsQuery.error} />

  const datasets = datasetsQuery.data?.datasets ?? []

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        back={{ to: '/quality', label: 'Análises de qualidade' }}
        title="Analisar uma tabela"
        description="Escolha um dataset e a tabela; a próxima tela pergunta qual tipo de análise rodar."
      />

      <Panel
        filterRow={
          <Select value={datasetId} onValueChange={(v) => setDatasetId(v ?? '')}>
            <SelectTrigger className="w-64">
              <SelectValue>{(v: string) => v || 'Escolha um dataset…'}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {datasets.map((d) => (
                <SelectItem key={d.dataset_id} value={d.dataset_id}>
                  {d.dataset_id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      >
        {!datasetId ? (
          <EmptyState
            title="Escolha um dataset"
            description="para listar as tabelas disponíveis."
          />
        ) : tablesQuery.isLoading ? (
          <LoadingState />
        ) : tablesQuery.isError ? (
          <ApiErrorNotice error={tablesQuery.error} />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tabela</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead className="text-right">Colunas</TableHead>
                <TableHead>Atualização</TableHead>
                <TableHead className="text-right">Linhas</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {(tablesQuery.data?.tables ?? []).map((t) => (
                <TableRow key={t.table_id}>
                  <TableCell className="font-medium">{t.table_id}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{t.table_type}</Badge>
                  </TableCell>
                  <TableCell className="text-right">{t.column_count}</TableCell>
                  <TableCell>{formatDate(t.last_modified_time)}</TableCell>
                  <TableCell className="text-right">{formatNumber(t.row_count)}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => navigate(`/analyze/${datasetId}/${t.table_id}`)}
                    >
                      <Sparkles size={14} />
                      Analisar
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {(tablesQuery.data?.tables.length ?? 0) === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">
                    Nenhuma tabela nesse dataset.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </Panel>
    </div>
  )
}
