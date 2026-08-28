import { useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronRight,
  ChevronsUpDown,
  RotateCw,
} from 'lucide-react'
import { Fragment, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { PaginationBar } from '@/components/PaginationBar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
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
  ADMIN_EVENT_CACHE_RUNS_QUERY_KEY,
  ADMIN_EVENT_CACHE_STATUS_QUERY_KEY,
  useEventCacheRuns,
  useEventCacheStatus,
  useRefreshEventCache,
} from '@/features/admin/hooks'
import { usePagination } from '@/hooks/usePagination'
import { formatRelativeToNow } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { EventCacheKindStatus, EventCacheRun, EventCacheRunProject } from '@/types/admin'

const PROJECT_STATUS_LABEL: Record<string, string> = {
  ok: 'ok',
  access_denied: 'sem acesso',
  quota_exceeded: 'cota estourada',
  api_error: 'erro de API',
  unexpected_error: 'erro',
  unknown: '—',
}

const STATUS_FILTER_ALL = 'all'
// Filtra por status POR PROJETO (um run casa se algum projeto tem esse
// status) — o status do run em si é só running/done, pouco útil de filtrar.
const STATUS_FILTER_OPTIONS = [
  'ok',
  'access_denied',
  'quota_exceeded',
  'api_error',
  'unexpected_error',
] as const

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

function runDuration(run: EventCacheRun): string {
  if (!run.finished_at) return '—'
  const ms = new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()
  if (Number.isNaN(ms) || ms < 0) return '—'
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}min ${s % 60}s`
}

function failedProjects(run: EventCacheRun): EventCacheRunProject[] {
  return run.projects.filter((p) => p.status !== 'ok')
}

function countByStatus(projects: EventCacheRunProject[]): string {
  const counts = new Map<string, number>()
  for (const p of projects) counts.set(p.status, (counts.get(p.status) ?? 0) + 1)
  return [...counts.entries()]
    .map(([status, n]) => `${n} ${PROJECT_STATUS_LABEL[status] ?? status}`)
    .join(' · ')
}

// full em qualquer projeto do run domina o rótulo (a decisão full/incremental
// é por projeto, mas o usuário quer saber "esse ciclo foi pesado?").
function runMode(run: EventCacheRun): string | null {
  const modes = new Set(run.projects.map((p) => p.mode).filter((m): m is string => m !== null))
  if (modes.size === 0) return null
  if (modes.has('full')) return modes.size === 1 ? 'full' : 'full (parcial)'
  return 'incremental'
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
  const failed = failedProjects(run).length
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

function ProjectScopePicker({
  knownProjects,
  selected,
  onChange,
}: {
  knownProjects: string[]
  selected: string[]
  onChange: (next: string[]) => void
}) {
  const [open, setOpen] = useState(false)
  const label =
    selected.length === 0
      ? 'Todos os projetos'
      : selected.length === 1
        ? selected[0]
        : `${selected.length} projetos`

  function toggle(projectId: string) {
    onChange(
      selected.includes(projectId)
        ? selected.filter((p) => p !== projectId)
        : [...selected, projectId],
    )
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button
            variant="outline"
            size="sm"
            role="combobox"
            aria-expanded={open}
            disabled={knownProjects.length === 0}
            className="w-56 justify-between font-normal"
          />
        }
      >
        <span className="truncate text-left text-xs">{label}</span>
        <ChevronsUpDown className="size-3.5 shrink-0 opacity-50" />
      </PopoverTrigger>
      <PopoverContent className="w-[min(22rem,calc(100vw-2rem))] max-w-none p-0" align="end">
        <Command>
          <CommandInput placeholder="Filtrar projeto…" />
          <CommandList>
            <CommandEmpty>Nenhum projeto.</CommandEmpty>
            {selected.length > 0 && (
              <CommandGroup>
                <CommandItem value="__clear__" onSelect={() => onChange([])}>
                  <span className="text-muted-foreground">Limpar seleção (rodar todos)</span>
                </CommandItem>
              </CommandGroup>
            )}
            <CommandGroup>
              {knownProjects.map((projectId) => (
                <CommandItem key={projectId} value={projectId} onSelect={() => toggle(projectId)}>
                  <Check
                    className={cn(
                      'size-4 shrink-0',
                      selected.includes(projectId) ? 'opacity-100' : 'opacity-0',
                    )}
                  />
                  <span className="flex-1 break-all font-mono text-xs">{projectId}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

function SummaryCard({
  run,
  onRefresh,
  forceFull,
  setForceFull,
  refreshing,
  knownProjects,
  selectedProjects,
  setSelectedProjects,
}: {
  run: EventCacheRun | undefined
  onRefresh: () => void
  forceFull: boolean
  setForceFull: (v: boolean) => void
  refreshing: boolean
  knownProjects: string[]
  selectedProjects: string[]
  setSelectedProjects: (next: string[]) => void
}) {
  const done = run?.projects.length ?? 0
  const problems = run ? failedProjects(run) : []
  const mode = run ? runMode(run) : null

  return (
    <div className="rounded-md border border-border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          {run ? (
            <>
              <div className="flex items-center gap-2">
                <RunStatusBadge run={run} />
                <span className="text-sm text-muted-foreground">
                  {run.status === 'running' ? 'iniciada' : 'concluída'}{' '}
                  {formatRelativeToNow(run.status === 'running' ? run.started_at : run.finished_at)}
                  {run.status !== 'running' && ` · durou ${runDuration(run)}`}
                  {mode && ` · ${mode}`}
                </span>
              </div>
              <span className="text-xs text-muted-foreground">
                {done}/{run.project_count} projetos
                {run.projects.length > 0 && ` — ${countByStatus(run.projects)}`}
              </span>
            </>
          ) : (
            <span className="text-sm text-muted-foreground">
              Nenhuma execução registrada ainda.
            </span>
          )}
        </div>

        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-2">
            <ProjectScopePicker
              knownProjects={knownProjects}
              selected={selectedProjects}
              onChange={setSelectedProjects}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={refreshing}
              onClick={onRefresh}
            >
              <RotateCw
                size={14}
                className={refreshing || run?.status === 'running' ? 'animate-spin' : undefined}
              />
              {run?.status === 'running' ? 'Atualizando…' : 'Atualizar agora'}
            </Button>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Checkbox
              id="cache-force-full"
              checked={forceFull}
              onCheckedChange={(v) => setForceFull(v === true)}
            />
            <label htmlFor="cache-force-full" className="cursor-pointer">
              forçar completo (re-escaneia a janela inteira)
            </label>
          </div>
        </div>
      </div>

      {problems.length > 0 && (
        <ul className="mt-3 flex flex-col gap-0.5 text-xs">
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

function ProjectDetailRow({ project }: { project: EventCacheRunProject }) {
  const counts = [
    ['job', project.job_events],
    ['access', project.access_events],
    ['scan', project.scan_events],
    ['storage', project.storage_read_object_keys],
  ] as const
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs">
      <span className="font-mono">{project.project_id}</span>
      <span className={project.status === 'ok' ? 'text-status-ok' : 'text-status-warn'}>
        {PROJECT_STATUS_LABEL[project.status] ?? project.status}
      </span>
      {project.mode && <span className="text-muted-foreground">{project.mode}</span>}
      {project.raw_entries !== null && (
        <span className="text-muted-foreground">Δ {project.raw_entries}</span>
      )}
      <span className="text-muted-foreground">
        {counts
          .filter(([, n]) => n !== null)
          .map(([label, n]) => `${label} ${n}`)
          .join(' · ')}
      </span>
    </div>
  )
}

function KindFreshness({ cache }: { cache: EventCacheKindStatus }) {
  if (cache.never_run) {
    return <span className="text-sm text-status-error">nunca rodou</span>
  }
  return (
    <div className="flex flex-col leading-tight">
      <span className={cn('text-sm', freshnessClass(cache.cached_at))}>
        {formatRelativeToNow(cache.cached_at)}
        {cache.event_count !== null && (
          <span className="ml-1.5 text-xs text-muted-foreground">({cache.event_count})</span>
        )}
      </span>
      <span className="text-[11px] text-muted-foreground">
        {cache.mode ?? '—'}
        {cache.window_start && ` · janela desde ${formatRelativeToNow(cache.window_start)}`}
      </span>
    </div>
  )
}

export function AdminCachesTab() {
  const statusQuery = useEventCacheStatus()
  const runsQuery = useEventCacheRuns()
  const refreshMutation = useRefreshEventCache()
  const queryClient = useQueryClient()

  const [forceFull, setForceFull] = useState(false)
  const [selectedProjects, setSelectedProjects] = useState<string[]>([])
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const [statusFilter, setStatusFilter] = useState<string>(STATUS_FILTER_ALL)
  const [projectFilter, setProjectFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [onlyFailures, setOnlyFailures] = useState(false)

  const runs = runsQuery.data?.runs ?? []
  const projects = statusQuery.data?.projects ?? []
  const knownProjects = projects.map((p) => p.project_id)
  const kindLabels = projects[0]?.caches.map((c) => c.label) ?? []
  const currentRun = runs.find((r) => r.status === 'running') ?? runs[0]

  const filteredRuns = useMemo(() => {
    const term = projectFilter.trim().toLowerCase()
    return runs.filter((run) => {
      if (statusFilter !== STATUS_FILTER_ALL) {
        if (!run.projects.some((p) => p.status === statusFilter)) return false
      }
      if (onlyFailures && failedProjects(run).length === 0) return false
      if (term && !run.projects.some((p) => p.project_id.toLowerCase().includes(term))) return false
      const day = run.started_at.slice(0, 10) // ISO -> YYYY-MM-DD
      if (dateFrom && day < dateFrom) return false
      if (dateTo && day > dateTo) return false
      return true
    })
  }, [runs, statusFilter, onlyFailures, projectFilter, dateFrom, dateTo])

  const pagination = usePagination({ rowCount: filteredRuns.length, initialPageSize: 10 })
  const pageRuns = filteredRuns.slice(pagination.start, pagination.end)

  function refresh() {
    refreshMutation.mutate(
      { forceFull, projects: selectedProjects },
      {
        onSuccess: () => {
          const scope =
            selectedProjects.length === 0
              ? 'todos os projetos'
              : `${selectedProjects.length} projeto${selectedProjects.length > 1 ? 's' : ''}`
          toast.success(
            `Atualização ${forceFull ? 'completa ' : ''}disparada para ${scope} — acompanhe o progresso abaixo.`,
          )
          setTimeout(() => {
            queryClient.invalidateQueries({ queryKey: ADMIN_EVENT_CACHE_RUNS_QUERY_KEY })
            queryClient.invalidateQueries({ queryKey: ADMIN_EVENT_CACHE_STATUS_QUERY_KEY })
          }, 2_000)
        },
        onError: () => toast.error('Não foi possível disparar a atualização.'),
      },
    )
  }

  function toggleExpand(runId: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(runId)) next.delete(runId)
      else next.add(runId)
      return next
    })
  }

  return (
    <div className="mt-4 flex flex-col gap-6">
      <div>
        <p className="text-sm font-medium">
          Cache de audit log (lineage, acesso, órfãs, FinOps, Storage)
        </p>
        <p className="text-xs text-muted-foreground">
          Recomputado 1×/dia (D-1, 03:00 UTC) de forma incremental — cada ciclo lê só o delta e
          desliza a janela. No disparo manual dá pra escolher projetos (padrão: todos) e marcar
          "forçar completo" (re-escaneia a janela inteira). A tela faz polling e mostra cada projeto
          sendo processado.
        </p>
      </div>

      {(statusQuery.isError || runsQuery.isError) && (
        <ApiErrorNotice error={statusQuery.error ?? runsQuery.error} />
      )}

      <section className="flex flex-col gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Execução atual
        </h2>
        {runsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Carregando…</p>
        ) : (
          <SummaryCard
            run={currentRun}
            onRefresh={refresh}
            forceFull={forceFull}
            setForceFull={setForceFull}
            refreshing={refreshMutation.isPending}
            knownProjects={knownProjects}
            selectedProjects={selectedProjects}
            setSelectedProjects={setSelectedProjects}
          />
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Histórico de execuções
        </h2>

        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={statusFilter}
            onValueChange={(v) => setStatusFilter(v ?? STATUS_FILTER_ALL)}
          >
            <SelectTrigger className="w-44" size="sm">
              <SelectValue>
                {(v: string) =>
                  v === STATUS_FILTER_ALL
                    ? 'Qualquer status'
                    : `Com "${PROJECT_STATUS_LABEL[v] ?? v}"`
                }
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={STATUS_FILTER_ALL}>Qualquer status</SelectItem>
              {STATUS_FILTER_OPTIONS.map((s) => (
                <SelectItem key={s} value={s}>
                  Com "{PROJECT_STATUS_LABEL[s]}"
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Input
            value={projectFilter}
            onChange={(e) => setProjectFilter(e.target.value)}
            placeholder="Filtrar por projeto…"
            className="h-8 w-48"
          />

          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <label htmlFor="cache-date-from">de</label>
            <Input
              id="cache-date-from"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="h-8 w-36"
            />
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <label htmlFor="cache-date-to">até</label>
            <Input
              id="cache-date-to"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="h-8 w-36"
            />
          </div>

          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Checkbox
              id="cache-only-failures"
              checked={onlyFailures}
              onCheckedChange={(v) => setOnlyFailures(v === true)}
            />
            <label htmlFor="cache-only-failures" className="cursor-pointer">
              só com falha
            </label>
          </div>
        </div>

        {runs.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {runsQuery.isLoading ? 'Carregando…' : 'Nenhuma execução registrada ainda.'}
          </p>
        ) : filteredRuns.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhuma execução casa com os filtros.</p>
        ) : (
          <>
            <div className="overflow-x-auto rounded-lg border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8" />
                    <TableHead>Quando</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Projetos</TableHead>
                    <TableHead>Duração</TableHead>
                    <TableHead>Modo</TableHead>
                    <TableHead>Detalhe</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pageRuns.map((run) => {
                    const isOpen = expanded.has(run.run_id)
                    return (
                      <Fragment key={run.run_id}>
                        <TableRow
                          className="cursor-pointer"
                          onClick={() => toggleExpand(run.run_id)}
                        >
                          <TableCell className="text-muted-foreground">
                            {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          </TableCell>
                          <TableCell className="whitespace-nowrap">
                            {formatRelativeToNow(run.started_at)}
                          </TableCell>
                          <TableCell>
                            <RunStatusBadge run={run} />
                          </TableCell>
                          <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                            {run.projects.length}/{run.project_count}
                          </TableCell>
                          <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                            {runDuration(run)}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {runMode(run) ?? '—'}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {run.projects.length > 0 ? countByStatus(run.projects) : '—'}
                          </TableCell>
                        </TableRow>
                        {isOpen && (
                          <TableRow className="bg-muted/30 hover:bg-muted/30">
                            <TableCell />
                            <TableCell colSpan={6} className="whitespace-normal">
                              <div className="flex flex-col gap-1 py-1">
                                {run.projects.length === 0 ? (
                                  <span className="text-xs text-muted-foreground">
                                    Nenhum projeto processado ainda.
                                  </span>
                                ) : (
                                  run.projects.map((p) => (
                                    <ProjectDetailRow key={p.project_id} project={p} />
                                  ))
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                        )}
                      </Fragment>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
            <PaginationBar
              page={pagination.page}
              pageCount={pagination.pageCount}
              pageSize={pagination.pageSize}
              setPageSize={pagination.setPageSize}
              start={pagination.start}
              end={pagination.end}
              totalCount={filteredRuns.length}
              onPrevious={pagination.goToPreviousPage}
              onNext={pagination.goToNextPage}
            />
          </>
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
                      <TableCell key={cache.kind} className="whitespace-nowrap align-top">
                        <KindFreshness cache={cache} />
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
