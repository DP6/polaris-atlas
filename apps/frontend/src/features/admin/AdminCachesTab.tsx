import { useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, RotateCw } from 'lucide-react'
import { toast } from 'sonner'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  ADMIN_EVENT_CACHE_STATUS_QUERY_KEY,
  useEventCacheStatus,
  useRefreshEventCache,
} from '@/features/admin/hooks'
import { formatRelativeToNow } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { EventCacheRun, EventCacheRunProject } from '@/types/admin'

const PROJECT_STATUS_LABEL: Record<string, string> = {
  ok: 'ok',
  access_denied: 'sem acesso',
  quota_exceeded: 'cota estourada',
  api_error: 'erro de API',
  unexpected_error: 'erro',
  unknown: '—',
}

function ageHours(iso: string | null): number | null {
  if (!iso) return null
  const d = new Date(iso).getTime()
  if (Number.isNaN(d)) return null
  return (Date.now() - d) / 3_600_000
}

// Verde < 26h (ciclo diário + folga), amarelo 26–50h, vermelho > 50h ou
// nunca gerado.
function freshnessClass(iso: string | null): string {
  const h = ageHours(iso)
  if (h === null) return 'text-status-error'
  if (h <= 26) return 'text-status-ok'
  if (h <= 50) return 'text-status-warn'
  return 'text-status-error'
}

function RunStatusBadge({ run }: { run: EventCacheRun }) {
  if (run.status === 'running') {
    return (
      <Badge className="gap-1.5 border-status-info/30 bg-status-info/10 text-status-info">
        <RotateCw size={11} className="animate-spin" />
        em andamento
      </Badge>
    )
  }
  const failed = run.projects.filter((p) => p.status !== 'ok').length
  if (failed > 0) {
    return (
      <Badge className="gap-1 border-status-warn/30 bg-status-warn/10 text-status-warn">
        <AlertTriangle size={11} />
        {failed} com problema
      </Badge>
    )
  }
  return <Badge className="border-status-ok/30 bg-status-ok/10 text-status-ok">concluída</Badge>
}

function runDuration(run: EventCacheRun): string {
  if (!run.finished_at) return '—'
  const ms = new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()
  if (Number.isNaN(ms) || ms < 0) return '—'
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}min ${s % 60}s`
}

function countByStatus(projects: EventCacheRunProject[]): string {
  const counts = new Map<string, number>()
  for (const p of projects) counts.set(p.status, (counts.get(p.status) ?? 0) + 1)
  return [...counts.entries()]
    .map(([status, n]) => `${n} ${PROJECT_STATUS_LABEL[status] ?? status}`)
    .join(' · ')
}

function RunCard({ run }: { run: EventCacheRun }) {
  const done = run.projects.length
  const problems = run.projects.filter((p) => p.status !== 'ok')

  return (
    <div className="rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <RunStatusBadge run={run} />
          <span className="text-sm text-muted-foreground">
            iniciada {formatRelativeToNow(run.started_at)}
            {run.status !== 'running' && ` · durou ${runDuration(run)}`}
          </span>
        </div>
        <span className="text-xs text-muted-foreground">
          {done}/{run.project_count} projetos
        </span>
      </div>

      {run.projects.length > 0 && (
        <p className="mt-1.5 text-xs text-muted-foreground">{countByStatus(run.projects)}</p>
      )}

      {problems.length > 0 && (
        <ul className="mt-2 flex flex-col gap-0.5 text-xs">
          {problems.map((p) => (
            <li key={p.project_id} className="flex items-center gap-2">
              <span className="text-status-warn">{PROJECT_STATUS_LABEL[p.status] ?? p.status}</span>
              <span className="font-mono text-muted-foreground">{p.project_id}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function AdminCachesTab() {
  const statusQuery = useEventCacheStatus()
  const refreshMutation = useRefreshEventCache()
  const queryClient = useQueryClient()

  const runs = statusQuery.data?.runs ?? []
  const projects = statusQuery.data?.projects ?? []
  const kindLabels = projects[0]?.caches.map((c) => c.label) ?? []
  const isRunning = runs.some((r) => r.status === 'running')

  function refresh() {
    refreshMutation.mutate(undefined, {
      onSuccess: () => {
        toast.success('Atualização disparada — acompanhe o progresso abaixo.')
        // Dá um tempo pro Job criar o doc da execução, depois recarrega.
        setTimeout(
          () => queryClient.invalidateQueries({ queryKey: ADMIN_EVENT_CACHE_STATUS_QUERY_KEY }),
          2_000,
        )
      },
      onError: () => toast.error('Não foi possível disparar a atualização.'),
    })
  }

  return (
    <div className="mt-4 flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium">
            Cache de audit log (lineage, acesso, órfãs, FinOps, Storage)
          </p>
          <p className="text-xs text-muted-foreground">
            Recomputado 1×/dia (D-1, 03:00 UTC) pra todos os projetos conhecidos. Use "Atualizar
            agora" pra forçar; a tela faz polling e mostra cada projeto sendo processado.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={refreshMutation.isPending}
          onClick={refresh}
        >
          <RotateCw
            size={14}
            className={refreshMutation.isPending || isRunning ? 'animate-spin' : undefined}
          />
          {isRunning ? 'Atualizando…' : 'Atualizar agora'}
        </Button>
      </div>

      {statusQuery.isError && <ApiErrorNotice error={statusQuery.error} />}

      <section className="flex flex-col gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Últimas execuções
        </h2>
        {runs.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {statusQuery.isLoading ? 'Carregando…' : 'Nenhuma execução registrada ainda.'}
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {runs.map((run) => (
              <RunCard key={run.run_id} run={run} />
            ))}
          </div>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Freshness por projeto
        </h2>
        {projects.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {statusQuery.isLoading ? 'Carregando…' : 'Nenhum projeto conhecido ainda.'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Projeto</TableHead>
                  {kindLabels.map((label) => (
                    <TableHead key={label}>{label}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {projects.map((project) => (
                  <TableRow key={project.project_id}>
                    <TableCell className="font-mono text-xs">{project.project_id}</TableCell>
                    {project.caches.map((cache) => (
                      <TableCell key={cache.kind} className="whitespace-nowrap">
                        <span className={cn('text-sm', freshnessClass(cache.cached_at))}>
                          {formatRelativeToNow(cache.cached_at)}
                        </span>
                        {cache.event_count !== null && (
                          <span className="ml-1.5 text-xs text-muted-foreground">
                            ({cache.event_count})
                          </span>
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>
    </div>
  )
}
