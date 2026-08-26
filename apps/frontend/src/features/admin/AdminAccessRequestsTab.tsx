import { ClipboardCheck } from 'lucide-react'
import { Fragment, useState } from 'react'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { RefreshButton } from '@/components/RefreshButton'
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
import {
  useAccessRequests,
  useApproveAccessRequest,
  useDenyAccessRequest,
} from '@/features/admin/hooks'
import { ProjectChecklistPanel } from '@/features/admin/ProjectChecklistPanel'
import { formatDate } from '@/lib/format'
import type { AccessRequestStatus, AccessRequestType } from '@/types/admin'

const STATUS_FILTER_ALL = 'all'
type StatusFilter = AccessRequestStatus | typeof STATUS_FILTER_ALL

const STATUS_LABELS: Record<AccessRequestStatus, string> = {
  pending: 'Pendente',
  approved: 'Aprovada',
  denied: 'Negada',
}

const STATUS_BADGE_CLASS: Record<AccessRequestStatus, string> = {
  pending: 'border-status-warn/30 bg-status-warn/10 text-status-warn',
  approved: 'border-status-ok/30 bg-status-ok/10 text-status-ok',
  denied: 'border-status-error/30 bg-status-error/10 text-status-error',
}

const REQUEST_TYPE_LABELS: Record<AccessRequestType, string> = {
  access: 'Acesso',
  inclusion: 'Inclusão',
}

export function AdminAccessRequestsTab() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('pending')
  const requestsQuery = useAccessRequests(
    statusFilter === STATUS_FILTER_ALL ? undefined : statusFilter,
  )
  const approveMutation = useApproveAccessRequest()
  const denyMutation = useDenyAccessRequest()
  const [checkingRequestId, setCheckingRequestId] = useState<string | null>(null)

  return (
    <div className="mt-4 flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <Select
          value={statusFilter}
          onValueChange={(value) => setStatusFilter((value as StatusFilter) ?? 'pending')}
        >
          <SelectTrigger className="w-40">
            <SelectValue>
              {(value: StatusFilter) =>
                value === STATUS_FILTER_ALL ? 'Todas' : STATUS_LABELS[value]
              }
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="pending">Pendentes</SelectItem>
            <SelectItem value="approved">Aprovadas</SelectItem>
            <SelectItem value="denied">Negadas</SelectItem>
            <SelectItem value={STATUS_FILTER_ALL}>Todas</SelectItem>
          </SelectContent>
        </Select>
        <div className="ml-auto">
          <RefreshButton
            isRefreshing={requestsQuery.isFetching}
            onRefresh={() => requestsQuery.refetch()}
          />
        </div>
      </div>

      {requestsQuery.isLoading && <p className="text-sm text-muted-foreground">Carregando…</p>}
      {requestsQuery.isError && <ApiErrorNotice error={requestsQuery.error} />}

      {requestsQuery.data && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Usuário</TableHead>
              <TableHead>Projeto</TableHead>
              <TableHead>Tipo</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Solicitado em</TableHead>
              <TableHead>Resolvido</TableHead>
              <TableHead className="text-right">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {requestsQuery.data.requests.map((request) => (
              <Fragment key={request.request_id}>
                <TableRow>
                  <TableCell className="font-medium">{request.email}</TableCell>
                  <TableCell>{request.project_id}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{REQUEST_TYPE_LABELS[request.request_type]}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={STATUS_BADGE_CLASS[request.status]}>
                      {STATUS_LABELS[request.status]}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatDate(request.requested_at)}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {request.resolved_by
                      ? `${formatDate(request.resolved_at as string)} por ${request.resolved_by}`
                      : '—'}
                  </TableCell>
                  <TableCell className="text-right">
                    {request.status === 'pending' && (
                      <div className="flex justify-end gap-1">
                        {request.request_type === 'inclusion' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              setCheckingRequestId((current) =>
                                current === request.request_id ? null : request.request_id,
                              )
                            }
                          >
                            <ClipboardCheck size={14} />
                            Verificar checklist
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={approveMutation.isPending || denyMutation.isPending}
                          onClick={() => approveMutation.mutate(request.request_id)}
                        >
                          Aprovar
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={approveMutation.isPending || denyMutation.isPending}
                          onClick={() => denyMutation.mutate(request.request_id)}
                        >
                          Negar
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
                {checkingRequestId === request.request_id && (
                  <TableRow>
                    <TableCell colSpan={7}>
                      <ProjectChecklistPanel projectId={request.project_id} enabled />
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            ))}
            {requestsQuery.data.requests.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground">
                  Nenhuma solicitação {statusFilter === STATUS_FILTER_ALL ? '' : 'nesse status'}{' '}
                  encontrada.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
