import { Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'
import { FavoriteNickname } from '@/features/favorites/FavoriteNickname'
import { useFavorites, useUpdateFavoriteNickname } from '@/features/favorites/hooks'
import { useProjectContext } from '@/features/projects/ProjectContext'
import type { Favorite } from '@/types/favorites'

// Tela dedicada dos favoritos do projeto (rodada 3) — clicar em "Favoritos"
// na sidebar abre esta seção no `<main>`; o chevron continua abrindo a
// lista inline no menu.
export function FavoritesPage() {
  const { projectId } = useProjectContext()
  const favoritesQuery = useFavorites()
  const updateNickname = useUpdateFavoriteNickname()

  const projectFavorites = (favoritesQuery.data?.favorites ?? []).filter(
    (f) => f.project_id === projectId,
  )
  const tables = projectFavorites.filter((f) => f.table_id !== null)
  const datasets = projectFavorites.filter((f) => f.table_id === null)

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Favoritos"
        description="Datasets e tabelas que você marcou com a estrela neste projeto."
      />

      {projectFavorites.length === 0 ? (
        <EmptyState
          icon={Star}
          title="Nenhum favorito ainda"
          description="Clique na estrela ao lado de um dataset ou tabela para favoritar."
        />
      ) : (
        <div className="flex flex-col gap-4">
          {tables.length > 0 && (
            <Panel title="Tabelas favoritas" as="h3">
              <FavoriteList favorites={tables} projectId={projectId} onRename={updateNickname} />
            </Panel>
          )}
          {datasets.length > 0 && (
            <Panel title="Datasets favoritos" as="h3">
              <FavoriteList favorites={datasets} projectId={projectId} onRename={updateNickname} />
            </Panel>
          )}
        </div>
      )}
    </div>
  )
}

function FavoriteList({
  favorites,
  projectId,
  onRename,
}: {
  favorites: Favorite[]
  projectId: string | undefined
  onRename: ReturnType<typeof useUpdateFavoriteNickname>
}) {
  return (
    <ul className="flex flex-col gap-0.5">
      {favorites.map((favorite) => {
        const label = favorite.table_id
          ? `${favorite.dataset_id}.${favorite.table_id}`
          : favorite.dataset_id
        return (
          <li
            key={`${favorite.dataset_id}.${favorite.table_id ?? ''}`}
            className="group flex flex-col gap-0.5 rounded-lg px-3 py-2 hover:bg-muted"
          >
            <Link
              to={`/datasets/${favorite.dataset_id}`}
              state={favorite.table_id ? { highlightTable: favorite.table_id } : undefined}
              className="flex items-center gap-2 text-body text-foreground"
            >
              <Star size={12} className="shrink-0 fill-primary text-primary" />
              <span className="truncate" title={label}>
                {label}
              </span>
            </Link>
            <FavoriteNickname
              nickname={favorite.nickname}
              onSave={(nickname) =>
                projectId &&
                onRename.mutate({
                  projectId,
                  datasetId: favorite.dataset_id,
                  tableId: favorite.table_id,
                  nickname,
                })
              }
            />
          </li>
        )
      })}
    </ul>
  )
}
