import { ChevronRight, File, Folder } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { RefreshButton } from '@/components/RefreshButton'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { useBucketObjects } from '@/features/storage/hooks'
import { formatBytes, formatDate } from '@/lib/format'
import { linkClass } from '@/lib/utils'

// Nome de exibição de um objeto/prefixo relativo ao prefixo atual — GCS
// não tem pastas reais, name/prefixes sempre vêm com o caminho completo
// (mesma convenção do backend, ver domains/storage/schemas.py).
function relativeName(fullName: string, currentPrefix: string): string {
  return fullName.startsWith(currentPrefix) ? fullName.slice(currentPrefix.length) : fullName
}

function breadcrumbSegments(prefix: string): { label: string; prefix: string }[] {
  const parts = prefix.split('/').filter(Boolean)
  return parts.map((label, index) => ({
    label,
    prefix: `${parts.slice(0, index + 1).join('/')}/`,
  }))
}

export function BucketBrowserPage() {
  const { bucketName } = useParams<{ bucketName: string }>()
  const { projectId } = useProjectContext()
  const [searchParams, setSearchParams] = useSearchParams()
  const prefix = searchParams.get('prefix') ?? ''
  // Pilha de page_token visitados neste prefixo — GCS pagina por token
  // encadeado, não por offset, então "página anterior" só existe se a
  // gente já guardou o token de onde veio.
  const [pageTokenStack, setPageTokenStack] = useState<(string | undefined)[]>([undefined])
  // Reseta a pilha de paginação quando o prefixo navegado muda — padrão
  // recomendado pelo React pra "ajustar estado quando uma prop muda"
  // sem useEffect (evita o round-trip extra de um efeito rodando depois
  // do render com o prefixo antigo).
  const [prefixAtLastReset, setPrefixAtLastReset] = useState(prefix)
  if (prefix !== prefixAtLastReset) {
    setPrefixAtLastReset(prefix)
    setPageTokenStack([undefined])
  }

  const currentPageToken = pageTokenStack[pageTokenStack.length - 1]
  const query = useBucketObjects(projectId, bucketName, prefix || undefined, currentPageToken)
  const data = query.data

  function navigateToPrefix(nextPrefix: string) {
    setSearchParams(nextPrefix ? { prefix: nextPrefix } : {})
  }

  if (!bucketName) return null

  if (query.isLoading) {
    return <LoadingState />
  }

  if (query.isError) {
    return <ApiErrorNotice error={query.error} />
  }

  if (!data) return null

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={bucketName}
        actions={
          <RefreshButton isRefreshing={query.isFetching} onRefresh={() => query.refetch()} />
        }
      />

      <nav
        aria-label="Trilha de navegação"
        className="-mt-3 flex flex-wrap items-center gap-1 text-muted-foreground text-sm"
      >
        <Link to="/storage" className={linkClass}>
          Buckets
        </Link>
        <ChevronRight size={12} aria-hidden="true" />
        <button type="button" onClick={() => navigateToPrefix('')} className={linkClass}>
          {bucketName}
        </button>
        {breadcrumbSegments(prefix).map((segment) => (
          <span key={segment.prefix} className="flex items-center gap-1">
            <ChevronRight size={12} aria-hidden="true" />
            <button
              type="button"
              onClick={() => navigateToPrefix(segment.prefix)}
              className={linkClass}
            >
              {segment.label}
            </button>
          </span>
        ))}
      </nav>

      <Panel>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nome</TableHead>
              <TableHead className="text-right">Tamanho</TableHead>
              <TableHead>Storage class</TableHead>
              <TableHead>Modificado em</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.prefixes.map((childPrefix) => (
              <TableRow
                key={childPrefix}
                className="cursor-pointer"
                onClick={() => navigateToPrefix(childPrefix)}
              >
                <TableCell className="font-medium">
                  <span className="flex items-center gap-2">
                    <Folder size={14} className="text-muted-foreground" />
                    {relativeName(childPrefix, prefix)}
                  </span>
                </TableCell>
                <TableCell className="text-right text-muted-foreground">—</TableCell>
                <TableCell className="text-muted-foreground">—</TableCell>
                <TableCell className="text-muted-foreground">—</TableCell>
              </TableRow>
            ))}
            {data.objects.map((object) => (
              <TableRow key={object.name}>
                <TableCell className="font-medium">
                  <span className="flex items-center gap-2">
                    <File size={14} className="text-muted-foreground" />
                    {relativeName(object.name, prefix)}
                  </span>
                </TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {formatBytes(object.size_bytes)}
                </TableCell>
                <TableCell className="text-muted-foreground">{object.storage_class}</TableCell>
                <TableCell className="text-muted-foreground">
                  {formatDate(object.updated)}
                </TableCell>
              </TableRow>
            ))}
            {data.prefixes.length === 0 && data.objects.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground">
                  Nada encontrado neste caminho.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Panel>

      {(pageTokenStack.length > 1 || data.next_page_token) && (
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={pageTokenStack.length <= 1}
            onClick={() => setPageTokenStack((stack) => stack.slice(0, -1))}
          >
            Página anterior
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!data.next_page_token}
            onClick={() =>
              setPageTokenStack((stack) => [...stack, data.next_page_token ?? undefined])
            }
          >
            Próxima página
          </Button>
        </div>
      )}
    </div>
  )
}
