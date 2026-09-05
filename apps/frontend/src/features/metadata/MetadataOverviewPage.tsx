import { Search } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
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
import { useMetadataOverview } from '@/features/metadata/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import type { CertificationStatus } from '@/types/metadata'

const CERTIFICATION_LABEL: Record<CertificationStatus, string> = {
  draft: 'Rascunho',
  in_review: 'Em revisão',
  approved: 'Aprovado',
}

const CERTIFICATION_COLOR: Record<CertificationStatus, string> = {
  draft: 'var(--color-muted-foreground)',
  in_review: 'var(--color-status-warn)',
  approved: 'var(--color-status-ok)',
}

function CertificationBadge({ status }: { status: CertificationStatus | null }) {
  if (!status) {
    return (
      <Badge variant="outline" className="text-muted-foreground">
        Não documentada
      </Badge>
    )
  }
  return (
    <Badge
      variant="outline"
      style={{ borderColor: CERTIFICATION_COLOR[status], color: CERTIFICATION_COLOR[status] }}
    >
      {CERTIFICATION_LABEL[status]}
    </Badge>
  )
}

// Visão geral de metadados do projeto — 3º item da seção Governança
// (junto de Freshness e Tabelas sem consumidor). Lista todas as tabelas
// do projeto (via catalog, $0), com status de certificação/dono/tags de
// quem já tem metadado cadastrado — tabela sem metadado aparece como
// "Não documentada", nunca é escondida (ver docs/specs/metadata.md,
// AC-META-007).
export function MetadataOverviewPage() {
  const { projectId } = useProjectContext()
  const [certificationStatus, setCertificationStatus] = useState<string>('all')
  const [q, setQ] = useState('')

  const overviewQuery = useMetadataOverview(projectId, {
    certificationStatus: certificationStatus === 'all' ? undefined : certificationStatus,
    q: q || undefined,
  })

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Metadados"
        description="Descrição, ownership, classificação e certificação por tabela — quais tabelas do projeto já estão documentadas."
      />

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-xs">
          <Search
            size={14}
            className="-translate-y-1/2 absolute top-1/2 left-2.5 text-muted-foreground"
          />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por descrição…"
            className="pl-8"
          />
        </div>
        <Select
          value={certificationStatus}
          onValueChange={(value) => setCertificationStatus(value ?? 'all')}
        >
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Certificação" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas as certificações</SelectItem>
            <SelectItem value="draft">Rascunho</SelectItem>
            <SelectItem value="in_review">Em revisão</SelectItem>
            <SelectItem value="approved">Aprovado</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {overviewQuery.isLoading && <LoadingState />}
      {overviewQuery.isError && <ApiErrorNotice error={overviewQuery.error} />}

      {overviewQuery.data && (
        <>
          <p className="text-muted-foreground text-sm">
            {overviewQuery.data.documented_count} de {overviewQuery.data.total_tables} tabelas
            documentadas
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tabela</TableHead>
                <TableHead>Certificação</TableHead>
                <TableHead>Dono técnico</TableHead>
                <TableHead>Domínio</TableHead>
                <TableHead>Sensibilidade</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {overviewQuery.data.tables.map((t) => (
                <TableRow key={`${t.dataset_id}.${t.table_id}`}>
                  <TableCell>
                    <Link
                      to={`/analyze/${t.dataset_id}/${t.table_id}/metadata`}
                      className="font-medium hover:underline"
                    >
                      {t.dataset_id}.{t.table_id}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <CertificationBadge status={t.certification_status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {t.owner?.technical_owner ?? '—'}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {t.classification?.domain ?? '—'}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {t.classification?.sensitivity ?? '—'}
                  </TableCell>
                </TableRow>
              ))}
              {overviewQuery.data.tables.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    Nenhuma tabela encontrada com esse filtro.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </>
      )}
    </div>
  )
}
