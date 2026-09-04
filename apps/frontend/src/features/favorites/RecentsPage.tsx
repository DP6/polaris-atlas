import { History } from 'lucide-react'
import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { useHistory } from '@/features/history/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import { formatRelativeToNow } from '@/lib/format'

// Tela dedicada das tabelas vistas recentemente (rodada 3) — clicar em
// "Recentes" na sidebar abre esta seção no `<main>`.
export function RecentsPage() {
  const { projectId } = useProjectContext()
  const historyQuery = useHistory()

  const recentTables = (historyQuery.data?.recent_tables ?? []).filter(
    (t) => t.project_id === projectId,
  )

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Recentes"
        description="Tabelas que você abriu recentemente neste projeto, da mais recente pra mais antiga."
      />

      {recentTables.length === 0 ? (
        <EmptyState
          icon={History}
          title="Nada por aqui ainda"
          description="Abra uma tabela pra ela aparecer neste histórico."
        />
      ) : (
        <Panel title="Tabelas recentes" as="h3">
          <ul className="flex flex-col gap-0.5">
            {recentTables.map((view) => (
              <li
                key={`${view.dataset_id}.${view.table_id}.${view.viewed_at}`}
                className="rounded-lg hover:bg-muted"
              >
                <Link
                  to={`/datasets/${view.dataset_id}`}
                  state={{ highlightTable: view.table_id }}
                  className="flex items-center justify-between gap-3 px-3 py-2 text-body text-foreground"
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <History size={12} className="shrink-0 text-muted-foreground" />
                    <span className="truncate" title={`${view.dataset_id}.${view.table_id}`}>
                      {view.dataset_id}.{view.table_id}
                    </span>
                  </span>
                  <span className="shrink-0 text-label text-muted-foreground">
                    {formatRelativeToNow(view.viewed_at)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  )
}
