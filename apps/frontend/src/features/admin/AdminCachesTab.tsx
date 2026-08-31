import { useQueryClient } from '@tanstack/react-query'
import type { LucideIcon } from 'lucide-react'
import {
  Check,
  ChevronDown,
  ChevronRight,
  ChevronsUpDown,
  Database,
  RotateCw,
  Search,
  SearchX,
  TriangleAlert,
  X,
} from 'lucide-react'
import { Fragment, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { ApiErrorNotice } from '@/components/ApiErrorNotice'
import { DateField } from '@/components/DateField'
import { EmptyState } from '@/components/EmptyState'
import { LoadingState } from '@/components/LoadingState'
import { PaginationBar } from '@/components/PaginationBar'
import { SectionHeading } from '@/components/SectionHeading'
import { SortableTableHead } from '@/components/SortableTableHead'
import { StatusBadge } from '@/components/StatusBadge'
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
import { Label } from '@/components/ui/label'
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

type SortKey = 'when' | 'projects' | 'duration'

function ageHours(iso: string | null): number | null {
  if (!iso) return null
  const d = new Date(iso).getTime()
  if (Number.isNaN(d)) return null
  return (Date.now() - d) / 3_600_000
}

// Verde < 26h (ciclo diário + folga), amarelo 26–50h, vermelho > 50h ou
// nunca gerado. Ícone acompanha a cor (WCAG 1.4.1 — não só cor).
function freshnessMeta(iso: string | null): { cls: string; Icon: LucideIcon } {
  const h = ageHours(iso)
  if (h === null) return { cls: 'text-status-error-foreground', Icon: TriangleAlert }
  if (h <= 26) return { cls: 'text-status-ok-foreground', Icon: Check }
  if (h <= 50) return { cls: 'text-status-warn-foreground', Icon: TriangleAlert }
  return { cls: 'text-status-error-foreground', Icon: TriangleAlert }
}

function runDurationMs(run: EventCacheRun): number {
  if (!run.finished_at) return -1
  const ms = new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()
  return Number.isNaN(ms) || ms < 0 ? -1 : ms
}

function runDuration(run: EventCacheRun): string {
  const ms = runDurationMs(run)
  if (ms < 0) return '—'
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
  if (run.status === 'running') return <StatusBadge status="running">em andamento</StatusBadge>
  const failed = failedProjects(run).length
  if (failed > 0) return <StatusBadge status="warn">{failed} com problema</StatusBadge>
  return <StatusBadge status="ok">concluída</StatusBadge>
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
            id="cache-scope-picker"
            variant="outline"
            size="sm"
            role="combobox"
            aria-label="Projetos a escanear"
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
                  <span className="flex-1 break-words font-mono text-xs">{projectId}</span>
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
    <div className="rounded-lg border border-primary/30 p-4">
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

        <div className="flex flex-col items-end gap-3">
          <div className="flex items-end gap-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cache-scope-picker" className="text-label text-muted-foreground">
                Projetos
              </Label>
              <ProjectScopePicker
                knownProjects={knownProjects}
                selected={selectedProjects}
                onChange={setSelectedProjects}
              />
            </div>
            <Button
              type="button"
              variant="default"
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
            <Label htmlFor="cache-force-full" className="cursor-pointer font-normal">
              forçar completo (re-escaneia a janela inteira)
            </Label>
          </div>
        </div>
      </div>

      {problems.length > 0 && (
        <ul className="mt-3 flex flex-col gap-0.5 text-xs">
          {problems.map((p) => (
            <li key={p.project_id} className="flex items-center gap-2">
              <TriangleAlert
                size={12}
                className="shrink-0 text-status-warn-foreground"
                aria-hidden="true"
              />
              <span className="text-status-warn-foreground">
                {PROJECT_STATUS_LABEL[p.status] ?? p.status}
              </span>
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
      <span
        className={
          project.status === 'ok' ? 'text-status-ok-foreground' : 'text-status-warn-foreground'
        }
      >
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
    return (
      <span className="inline-flex items-center gap-1 text-sm text-status-error-foreground">
        <X size={12} aria-hidden="true" />
        nunca rodou
      </span>
    )
  }
  const { cls, Icon } = freshnessMeta(cache.cached_at)
  return (
    <div className="flex flex-col leading-tight">
      <span className={cn('inline-flex items-center gap-1 text-sm', cls)}>
        <Icon size={12} aria-hidden="true" />
        {formatRelativeToNow(cache.cached_at)}
        {cache.event_count !== null && (
          <span className="ml-1 text-xs text-muted-foreground">({cache.event_count})</span>
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
  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({
    key: 'when',
    dir: 'desc',
  })

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

  const sortedRuns = useMemo(() => {
    const arr = [...filteredRuns]
    arr.sort((a, b) => {
      let cmp: number
      if (sort.key === 'when') cmp = a.started_at.localeCompare(b.started_at)
      else if (sort.key === 'projects') cmp = a.projects.length - b.projects.length
      else cmp = runDurationMs(a) - runDurationMs(b)
      return sort.dir === 'asc' ? cmp : -cmp
    })
    return arr
  }, [filteredRuns, sort])

  const pagination = usePagination({ rowCount: sortedRuns.length, initialPageSize: 10 })
  const pageRuns = sortedRuns.slice(pagination.start, pagination.end)

  function toggleSort(key: SortKey) {
    setSort((s) =>
      s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' },
    )
  }

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
    <div className="mt-4 flex flex-col gap-8">
      <div className="flex flex-col gap-1">
        <SectionHeading as="h2">
          Cache de audit log (lineage, acesso, órfãs, FinOps, Storage)
        </SectionHeading>
        <p className="max-w-[65ch] text-body text-muted-foreground">
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
        <SectionHeading as="h3">Execução atual</SectionHeading>
        {runsQuery.isLoading ? (
          <LoadingState />
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

      <section className="flex flex-col gap-3">
        <SectionHeading as="h3">Histórico de execuções</SectionHeading>

        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cache-status-filter" className="text-label text-muted-foreground">
              Status do projeto
            </Label>
            <Select
              value={statusFilter}
              onValueChange={(v) => setStatusFilter(v ?? STATUS_FILTER_ALL)}
            >
              <SelectTrigger
                id="cache-status-filter"
                aria-label="Status do projeto"
                className="w-44"
                size="sm"
              >
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
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cache-project-filter" className="text-label text-muted-foreground">
              Projeto
            </Label>
            <div className="relative">
              <Search
                size={14}
                className="-translate-y-1/2 absolute top-1/2 left-2.5 text-muted-foreground"
              />
              <Input
                id="cache-project-filter"
                value={projectFilter}
                onChange={(e) => setProjectFilter(e.target.value)}
                placeholder="Filtrar por projeto…"
                className="h-8 w-52 pl-8"
              />
            </div>
          </div>

          <DateField
            label="De"
            id="cache-date-from"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
          <DateField
            label="Até"
            id="cache-date-to"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />

          <div className="flex items-center gap-1.5 pb-1.5 text-sm text-muted-foreground">
            <Checkbox
              id="cache-only-failures"
              checked={onlyFailures}
              onCheckedChange={(v) => setOnlyFailures(v === true)}
            />
            <Label htmlFor="cache-only-failures" className="cursor-pointer font-normal">
              só com falha
            </Label>
          </div>
        </div>

        {runs.length === 0 ? (
          runsQuery.isLoading ? (
            <LoadingState />
          ) : (
            <EmptyState
              icon={Database}
              title="Nenhuma execução registrada ainda."
              description="O primeiro ciclo roda automaticamente às 03:00 UTC — ou dispare um agora pelo botão acima."
            />
          )
        ) : sortedRuns.length === 0 ? (
          <EmptyState
            icon={SearchX}
            title="Nenhuma execução casa com os filtros."
            description="Ajuste o status, o projeto ou o período."
          />
        ) : (
          <>
            <div className="overflow-x-auto rounded-lg border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8" />
                    <SortableTableHead
                      label="Quando"
                      active={sort.key === 'when'}
                      direction={sort.dir}
                      onClick={() => toggleSort('when')}
                    />
                    <TableHead>Status</TableHead>
                    <SortableTableHead
                      label="Projetos"
                      active={sort.key === 'projects'}
                      direction={sort.dir}
                      onClick={() => toggleSort('projects')}
                    />
                    <SortableTableHead
                      label="Duração"
                      active={sort.key === 'duration'}
                      direction={sort.dir}
                      onClick={() => toggleSort('duration')}
                    />
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
              totalCount={sortedRuns.length}
              onPrevious={pagination.goToPreviousPage}
              onNext={pagination.goToNextPage}
            />
          </>
        )}
      </section>

      <section className="flex flex-col gap-3 rounded-lg border border-border bg-muted/30 p-4">
        <SectionHeading as="h3" className="text-muted-foreground">
          Freshness por projeto
        </SectionHeading>
        {projects.length === 0 ? (
          statusQuery.isLoading ? (
            <LoadingState />
          ) : (
            <EmptyState icon={Database} title="Nenhum projeto conhecido ainda." />
          )
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border bg-card">
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
