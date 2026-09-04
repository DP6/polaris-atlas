import { CheckCircle2, Loader2, Search as SearchIcon, XCircle } from 'lucide-react'
import { useState } from 'react'
import { ChoiceToggle } from '@/components/ChoiceToggle'
import { Panel } from '@/components/Panel'
import { SectionHeading } from '@/components/SectionHeading'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useSearchTables } from '@/features/catalog/hooks'
import { SearchAbsentTable } from '@/features/catalog/SearchAbsentTable'
import { SearchMatchesTable } from '@/features/catalog/SearchMatchesTable'
import { useHistory, useRecordSearch } from '@/features/history/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { ApiError } from '@/lib/http-client'
import type { SearchMode } from '@/types/catalog'

const MODE_OPTIONS: { value: SearchMode; label: string }[] = [
  { value: 'exact', label: 'Igual a' },
  { value: 'contains', label: 'Contém' },
  { value: 'not_contains', label: 'Não contém' },
  { value: 'not_exact', label: 'Diferente de' },
]

// Busca global de tabela → em quais datasets do projeto ela existe (ou
// não), com modo igual/contém/não contém/diferente. Componente
// autocontido (state + hooks + resultados) — usado tanto na overview do
// Catálogo de Dados quanto na rota /search.
export function TableSearchPanel() {
  const { projectId } = useProjectContext()
  const [q, setQ] = useState('')
  const [mode, setMode] = useState<SearchMode>('exact')
  const [inputFocused, setInputFocused] = useState(false)
  const searchMutation = useSearchTables()
  const recordSearch = useRecordSearch()
  const historyQuery = useHistory()
  const recentSearches = historyQuery.data?.recent_searches.filter(
    (s) => s.project_id === projectId,
  )
  const showRecentSearches = inputFocused && !q.trim() && Boolean(recentSearches?.length)

  function runSearch(query: string, searchMode: SearchMode) {
    if (!projectId || !query.trim()) return
    const trimmed = query.trim()
    searchMutation.mutate(
      { projectId, q: trimmed, mode: searchMode },
      { onSuccess: () => recordSearch.mutate({ query: trimmed, mode: searchMode, projectId }) },
    )
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    runSearch(q, mode)
  }

  function handleRecentSearchClick(query: string, recentMode: string) {
    setQ(query)
    setMode(recentMode as SearchMode)
    setInputFocused(false)
    runSearch(query, recentMode as SearchMode)
  }

  const errorMessage =
    searchMutation.error instanceof ApiError
      ? searchMutation.error.message
      : searchMutation.error instanceof Error
        ? searchMutation.error.message
        : null

  const result = searchMutation.data
  const hasNoResults = Boolean(
    result && result.datasets_with_match.length === 0 && result.datasets_without_match.length === 0,
  )

  const filterRow = (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
      <div className="relative flex min-w-[240px] flex-1 flex-col gap-1.5">
        <Label htmlFor="table-search-q">Nome da tabela ou partição</Label>
        <Input
          id="table-search-q"
          placeholder="ex: events_20260812, ga4_events, crm"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => setInputFocused(true)}
          onBlur={() => setInputFocused(false)}
          autoComplete="off"
        />
        {showRecentSearches && (
          <div className="absolute top-full left-0 z-10 mt-1 w-full rounded-md border border-border bg-popover p-1 shadow-md">
            <p className="px-2 py-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              Buscas recentes
            </p>
            {recentSearches?.map((search) => (
              <button
                key={`${search.query}.${search.mode}.${search.searched_at}`}
                type="button"
                // preventDefault no mousedown (não no click): sem isso o
                // input perde foco (blur) antes do onClick disparar.
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handleRecentSearchClick(search.query, search.mode)}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
              >
                <SearchIcon size={14} className="shrink-0 text-muted-foreground" />
                <span className="truncate">{search.query}</span>
                <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                  {search.mode}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-1.5">
        <span className="text-label text-muted-foreground">Modo</span>
        <ChoiceToggle
          aria-label="Modo de busca"
          options={MODE_OPTIONS}
          value={mode}
          onChange={setMode}
        />
      </div>

      <Button type="submit" disabled={!q.trim() || searchMutation.isPending}>
        <SearchIcon size={14} />
        Buscar
      </Button>
    </form>
  )

  return (
    <Panel
      title="Buscar tabela no projeto"
      subtitle="Em quais datasets uma tabela existe (ou não), com filtro de modo."
      filterRow={filterRow}
    >
      {searchMutation.isPending && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 size={16} className="animate-spin" />
          Essa consulta pode demorar alguns segundos dependendo do tamanho do projeto…
        </div>
      )}

      {errorMessage && <p className="text-sm text-status-error-foreground">{errorMessage}</p>}

      {result && hasNoResults && (
        <p className="text-sm text-muted-foreground">
          Nenhuma tabela encontrada com esse termo no projeto {result.project_id}.
        </p>
      )}

      {result && !hasNoResults && (
        <div className="flex flex-col gap-6">
          {result.datasets_with_match.length > 0 && (
            <div className="flex flex-col gap-2">
              <SectionHeading as="h3">
                <span className="inline-flex items-center gap-2">
                  <CheckCircle2
                    size={16}
                    className="text-status-ok-foreground"
                    aria-hidden="true"
                  />
                  Encontrado em {result.datasets_with_match.length}{' '}
                  {result.datasets_with_match.length === 1 ? 'dataset' : 'datasets'}
                </span>
              </SectionHeading>
              <SearchMatchesTable matches={result.datasets_with_match} />
            </div>
          )}

          {result.datasets_without_match.length > 0 && (
            <div className="flex flex-col gap-2">
              <SectionHeading as="h3">
                <span className="inline-flex items-center gap-2">
                  <XCircle size={16} className="text-status-error-foreground" aria-hidden="true" />
                  Ausente em {result.datasets_without_match.length}{' '}
                  {result.datasets_without_match.length === 1 ? 'dataset' : 'datasets'}
                </span>
              </SectionHeading>
              <SearchAbsentTable datasets={result.datasets_without_match} />
            </div>
          )}
        </div>
      )}
    </Panel>
  )
}
