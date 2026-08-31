import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { CacheStalenessBadge } from '@/components/CacheStalenessBadge'
import { LoadingState } from '@/components/LoadingState'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { WarningCallout } from '@/components/WarningCallout'
import { useTableAccess } from '@/features/access/hooks'
import { formatDate, formatNumber } from '@/lib/format'
import type { AccessType } from '@/types/access'

interface AccessTabProps {
  projectId: string
  datasetId: string
  tableId: string | null
}

const ACCESS_TYPE_LABELS: Record<AccessType, string> = {
  read: 'Leitura',
  write: 'Escrita',
}

export function AccessTab({ projectId, datasetId, tableId }: AccessTabProps) {
  const accessQuery = useTableAccess(projectId, datasetId, tableId ?? undefined)

  if (accessQuery.isLoading) {
    return <LoadingState />
  }

  if (accessQuery.isError) {
    return <ApiErrorNotice error={accessQuery.error} />
  }

  const data = accessQuery.data
  if (!data) return null

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Mostra quem leu ou escreveu nesta tabela recentemente, via audit logs — útil para confirmar
        se ela ainda tem consumidor antes de arquivar, apagar ou mudar o schema.
      </p>

      {data.warning && <WarningCallout>{data.warning}</WarningCallout>}

      {data.users.length === 0 && !data.warning ? (
        <p className="text-sm text-muted-foreground">
          Nenhum acesso encontrado nos últimos {data.lookback_days} dias.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">Usuário</TableHead>
              <TableHead className="text-xs">Último acesso</TableHead>
              <TableHead className="text-xs">Tipo</TableHead>
              <TableHead className="text-xs text-right">Acessos</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.users.map((user) => (
              <TableRow key={user.principal_email}>
                <TableCell className="text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{user.principal_email}</span>
                    <Badge variant={user.is_service_account ? 'outline' : 'default'}>
                      {user.is_service_account ? 'Service account' : 'Humano'}
                    </Badge>
                  </div>
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {formatDate(user.last_accessed_at)}
                </TableCell>
                <TableCell className="text-xs">
                  <div className="flex flex-wrap gap-1">
                    {user.access_types.map((type) => (
                      <Badge key={type} variant="outline">
                        {ACCESS_TYPE_LABELS[type]}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell className="text-xs text-right">
                  {formatNumber(user.access_count)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <div className="flex items-center gap-2">
        <p className="text-xs text-muted-foreground">
          Baseado em audit logs dos últimos {data.lookback_days} dias.
        </p>
        <CacheStalenessBadge cacheUpdatedAt={data.cache_updated_at} />
      </div>
    </div>
  )
}
