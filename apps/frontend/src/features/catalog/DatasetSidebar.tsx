import {
  Boxes,
  ChevronDown,
  Clock,
  Container,
  Database,
  DollarSign,
  FolderKanban,
  Gauge,
  HardDrive,
  History,
  PiggyBank,
  Search,
  Star,
  Timer,
  Unlink,
  Workflow,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { ChoiceToggle } from '@/components/ChoiceToggle'
import { Badge } from '@/components/ui/badge'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Input } from '@/components/ui/input'
import { useDatasets } from '@/features/catalog/hooks'
import { FavoriteNickname } from '@/features/favorites/FavoriteNickname'
import {
  isFavoriteDataset,
  useFavorites,
  useToggleFavorite,
  useUpdateFavoriteNickname,
} from '@/features/favorites/hooks'
import { useHistory } from '@/features/history/hooks'
import { cn } from '@/lib/utils'
import type { Favorite } from '@/types/favorites'

const QUANTITY_OPTIONS = [5, 10, 20] as const
const QUANTITY_ALL = 'all'
type QuantityLimit = (typeof QUANTITY_OPTIONS)[number] | typeof QUANTITY_ALL

interface DatasetSidebarProps {
  projectId: string
}

// Item de nav: ativo = barra de acento à esquerda + fundo em gradiente +
// ícone em primary (Q-001 do refresh visual, utilitárias `.dp6-nav-*` em
// index.css). Não mais o bloco amarelo chapado.
const NAV_LINK_CLASS = ({ isActive }: { isActive: boolean }) =>
  cn(
    'dp6-nav-item flex items-center gap-2 rounded-lg px-3 py-2 text-sm',
    isActive
      ? 'dp6-nav-active font-medium text-foreground [&_svg]:text-primary'
      : 'text-foreground hover:bg-muted',
  )

const SECTION_LABEL_CLASS =
  'px-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase'

// Só mostra "· views" quando há tabelas e views ao mesmo tempo — dataset só
// de views (ou só de tabelas) mostra um único número, sem "0 tabelas"/"0
// views" ao lado.
function formatAssetCounts(totalTables: number, totalViews: number): string {
  const tablesLabel = `${totalTables} ${totalTables === 1 ? 'tabela' : 'tabelas'}`
  const viewsLabel = `${totalViews} ${totalViews === 1 ? 'view' : 'views'}`
  if (totalTables > 0 && totalViews > 0) return `${tablesLabel} · ${viewsLabel}`
  if (totalTables === 0 && totalViews > 0) return viewsLabel
  return tablesLabel
}

// Nó de topo de um serviço observável (hoje só BigQuery — o Hub existe pra
// expandir pra outros serviços GCP no futuro, cada um vira um
// SidebarServiceGroup irmão deste). Visualmente mais forte que
// SidebarSection (ícone, texto não-muted, sem uppercase) pra marcar a
// hierarquia: serviço > seção > item.
function SidebarServiceGroup({
  icon,
  label,
  to,
  open,
  onOpenChange,
  children,
}: {
  icon: ReactNode
  label: string
  // Quando presente, o nome/ícone vira um NavLink pra tela de overview do
  // serviço; o chevron continua sendo só o disclosure do drill-down.
  to?: string
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
}) {
  const rowClass =
    'dp6-nav-item mb-2 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-bold text-foreground hover:bg-muted'
  return (
    <Collapsible open={open} onOpenChange={onOpenChange}>
      {to ? (
        <div className={cn(rowClass, 'p-0')}>
          <NavLink
            to={to}
            end
            className={({ isActive }) =>
              cn(
                'flex flex-1 items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-muted',
                isActive && 'dp6-nav-active text-foreground',
              )
            }
          >
            <span className="text-primary">{icon}</span>
            <span className="flex-1 text-left">{label}</span>
          </NavLink>
          <CollapsibleTrigger
            aria-label={open ? `Recolher ${label}` : `Expandir ${label}`}
            className="flex size-7 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-muted"
          >
            <ChevronDown size={14} className={cn('transition-transform', !open && '-rotate-90')} />
          </CollapsibleTrigger>
        </div>
      ) : (
        <CollapsibleTrigger className={rowClass}>
          <span className="text-primary">{icon}</span>
          <span className="flex-1 text-left">{label}</span>
          <ChevronDown size={14} className={cn('transition-transform', !open && '-rotate-90')} />
        </CollapsibleTrigger>
      )}
      <CollapsibleContent className="flex flex-col gap-4 border-border border-l pl-2">
        {children}
      </CollapsibleContent>
    </Collapsible>
  )
}

// Serviço ainda não implementado (Workflows, Scheduler, Cloud Run) — mesma
// posição visual de SidebarServiceGroup, mas sem Collapsible (nada pra
// expandir) e sem interação: opacity/cursor reaproveitados do padrão já
// usado em AssetsTable.tsx/LineageGraph.tsx pra linha/nó desabilitado.
function SidebarServiceGroupPlaceholder({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <div className="mb-2 flex cursor-not-allowed items-center gap-2 rounded-lg px-2 py-1.5 text-muted-foreground text-sm opacity-50">
      {icon}
      <span className="flex-1 text-left font-bold">{label}</span>
      <Badge variant="outline" className="text-[10px]">
        Em breve
      </Badge>
    </div>
  )
}

// Seletor "quantos mostrar" pra Favoritos/Recentes — mesmo estilo pill
// de LookbackPicker (lineage/OrphansPage.tsx). Estado local por seção,
// não persiste entre sessões (decisão simples de propósito).
function QuantityPicker({
  value,
  onChange,
}: {
  value: QuantityLimit
  onChange: (next: QuantityLimit) => void
}) {
  return (
    <ChoiceToggle
      aria-label="Quantos itens mostrar"
      size="sm"
      className="mb-2 px-3"
      options={[
        ...QUANTITY_OPTIONS.map((n): { value: QuantityLimit; label: string } => ({
          value: n,
          label: String(n),
        })),
        { value: QUANTITY_ALL, label: 'Todos' },
      ]}
      value={value}
      onChange={onChange}
    />
  )
}

// Subseção dentro de um serviço (Governança, FinOps, Catálogo de Dados,
// Favoritos, Análises de qualidade, Recentes) — todas recolhidas por padrão
// (`open` vem de fora, sempre iniciado em `false` no componente pai).
function SidebarSection({
  label,
  to,
  open,
  onOpenChange,
  children,
}: {
  label: string
  // Quando presente, o nome vira um NavLink pra tela de overview do grupo;
  // o chevron continua sendo só o disclosure do drill-down (decisão do
  // usuário — refresh visual rodada 2).
  to?: string
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
}) {
  return (
    <Collapsible open={open} onOpenChange={onOpenChange}>
      {to ? (
        <div className="mb-2 flex items-center gap-1">
          <NavLink
            to={to}
            end
            className={({ isActive }) =>
              cn(
                SECTION_LABEL_CLASS,
                'dp6-nav-item flex flex-1 rounded-lg py-1',
                isActive && 'dp6-nav-active text-foreground',
              )
            }
          >
            {label}
          </NavLink>
          <CollapsibleTrigger
            aria-label={open ? `Recolher ${label}` : `Expandir ${label}`}
            className="flex size-6 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-muted"
          >
            <ChevronDown size={14} className={cn('transition-transform', !open && '-rotate-90')} />
          </CollapsibleTrigger>
        </div>
      ) : (
        <CollapsibleTrigger
          className={cn(SECTION_LABEL_CLASS, 'mb-2 flex w-full items-center justify-between')}
        >
          {label}
          <ChevronDown size={14} className={cn('transition-transform', !open && '-rotate-90')} />
        </CollapsibleTrigger>
      )}
      <CollapsibleContent>{children}</CollapsibleContent>
    </Collapsible>
  )
}

export function DatasetSidebar({ projectId }: DatasetSidebarProps) {
  const datasetsQuery = useDatasets(projectId)
  const favoritesQuery = useFavorites()
  const toggleFavorite = useToggleFavorite()
  const updateNickname = useUpdateFavoriteNickname()
  const projectFavorites = favoritesQuery.data?.favorites.filter((f) => f.project_id === projectId)
  const tableFavorites = projectFavorites?.filter(
    (f): f is Favorite & { table_id: string } => f.table_id !== null,
  )
  const datasetFavorites = projectFavorites?.filter((f) => f.table_id === null)
  const historyQuery = useHistory()
  const recentTablesAll = historyQuery.data?.recent_tables.filter((t) => t.project_id === projectId)

  // Os dois serviços começam recolhidos por padrão — sidebar menos
  // carregada no primeiro acesso, cada um expande sob demanda. Tudo que
  // abre DENTRO de um serviço também começa recolhido, sem exceção.
  const [bigQueryOpen, setBigQueryOpen] = useState(false)
  const [cloudStorageOpen, setCloudStorageOpen] = useState(false)
  const [governanceOpen, setGovernanceOpen] = useState(false)
  const [dqAnalysesOpen, setDqAnalysesOpen] = useState(false)
  const [finopsOpen, setFinopsOpen] = useState(false)
  const [catalogOpen, setCatalogOpen] = useState(false)
  const [favoritesOpen, setFavoritesOpen] = useState(false)
  const [recentOpen, setRecentOpen] = useState(false)
  const [datasetFilter, setDatasetFilter] = useState('')
  const [favoritesLimit, setFavoritesLimit] = useState<QuantityLimit>(5)
  const [recentLimit, setRecentLimit] = useState<QuantityLimit>(5)

  const visibleTableFavorites =
    favoritesLimit === QUANTITY_ALL ? tableFavorites : tableFavorites?.slice(0, favoritesLimit)
  const visibleDatasetFavorites =
    favoritesLimit === QUANTITY_ALL ? datasetFavorites : datasetFavorites?.slice(0, favoritesLimit)
  const recentTables =
    recentLimit === QUANTITY_ALL ? recentTablesAll : recentTablesAll?.slice(0, recentLimit)
  const visibleDatasets = datasetsQuery.data?.datasets.filter((dataset) =>
    dataset.dataset_id.toLowerCase().includes(datasetFilter.toLowerCase()),
  )

  return (
    <aside className="w-60 shrink-0 space-y-4 overflow-y-auto border-r border-border bg-card p-4">
      <SidebarServiceGroup
        icon={<Database size={16} />}
        label="BigQuery"
        open={bigQueryOpen}
        onOpenChange={setBigQueryOpen}
      >
        <SidebarSection
          label="Governança"
          to="/governanca"
          open={governanceOpen}
          onOpenChange={setGovernanceOpen}
        >
          <nav className="flex flex-col gap-0.5">
            <NavLink to="/freshness" className={NAV_LINK_CLASS}>
              <Clock size={16} />
              Freshness
            </NavLink>
            <NavLink to="/orphans" className={NAV_LINK_CLASS}>
              <Unlink size={16} />
              Tabelas sem consumidor
            </NavLink>
          </nav>
        </SidebarSection>

        <SidebarSection label="FinOps" to="/finops" open={finopsOpen} onOpenChange={setFinopsOpen}>
          <nav className="flex flex-col gap-0.5">
            <NavLink to="/finops" end className={NAV_LINK_CLASS}>
              <Gauge size={16} />
              Visão geral
            </NavLink>
            <NavLink to="/finops/scanner" className={NAV_LINK_CLASS}>
              <PiggyBank size={16} />
              Scanner de desperdício
            </NavLink>
            <NavLink to="/finops/budget" className={NAV_LINK_CLASS}>
              <DollarSign size={16} />
              Budget de custo
            </NavLink>
          </nav>
        </SidebarSection>

        <SidebarSection
          label="Catálogo de Dados"
          to="/"
          open={catalogOpen}
          onOpenChange={setCatalogOpen}
        >
          <NavLink to="/search" className={NAV_LINK_CLASS}>
            <Search size={16} />
            Buscar tabelas
          </NavLink>

          {datasetsQuery.isLoading && (
            <p className="px-3 text-sm text-muted-foreground">Carregando…</p>
          )}

          {datasetsQuery.isError && (
            <p className="px-3 text-sm text-status-error-foreground">Erro ao carregar datasets.</p>
          )}

          {datasetsQuery.data && datasetsQuery.data.datasets.length > 0 && (
            <div className="relative mb-2 px-3">
              <Search
                size={13}
                className="-translate-y-1/2 absolute top-1/2 left-5.5 text-muted-foreground"
              />
              <Input
                value={datasetFilter}
                onChange={(e) => setDatasetFilter(e.target.value)}
                placeholder="Filtrar datasets…"
                className="h-8 pl-7 text-sm"
              />
            </div>
          )}

          <nav className="flex flex-col gap-0.5">
            {visibleDatasets?.map((dataset) => {
              const isDatasetFavorite = isFavoriteDataset(
                favoritesQuery.data,
                projectId,
                dataset.dataset_id,
              )
              return (
                <div key={dataset.dataset_id} className="flex items-center gap-1">
                  <NavLink
                    to={`/datasets/${dataset.dataset_id}`}
                    className={({ isActive }) =>
                      cn(
                        'dp6-nav-item flex min-w-0 flex-1 items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm',
                        isActive
                          ? 'dp6-nav-active font-medium text-foreground'
                          : 'text-foreground hover:bg-muted',
                      )
                    }
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <Boxes size={14} className="shrink-0 opacity-70" aria-hidden="true" />
                      <span className="truncate" title={dataset.dataset_id}>
                        {dataset.dataset_id}
                      </span>
                    </span>
                    <span className="shrink-0 text-xs opacity-70">
                      [{formatAssetCounts(dataset.total_tables, dataset.total_views)}]
                    </span>
                  </NavLink>
                  <button
                    type="button"
                    onClick={() =>
                      toggleFavorite.mutate({
                        projectId,
                        datasetId: dataset.dataset_id,
                        tableId: null,
                        isFavorite: isDatasetFavorite,
                      })
                    }
                    aria-label={
                      isDatasetFavorite ? 'Remover dataset dos favoritos' : 'Favoritar dataset'
                    }
                    className="inline-flex size-6 shrink-0 items-center justify-center text-muted-foreground hover:text-foreground"
                  >
                    <Star
                      size={13}
                      className={isDatasetFavorite ? 'fill-primary text-primary' : undefined}
                    />
                  </button>
                </div>
              )
            })}
            {visibleDatasets && visibleDatasets.length === 0 && (
              <p className="px-3 text-sm text-muted-foreground">Nenhum dataset encontrado.</p>
            )}
          </nav>
        </SidebarSection>

        <SidebarSection label="Favoritos" open={favoritesOpen} onOpenChange={setFavoritesOpen}>
          <div className="flex flex-col gap-3">
            {projectFavorites && projectFavorites.length > 0 ? (
              <QuantityPicker value={favoritesLimit} onChange={setFavoritesLimit} />
            ) : (
              <p className="px-3 text-sm text-muted-foreground">
                Nenhum favorito ainda — clique na estrela ao lado de um dataset ou tabela para
                favoritar.
              </p>
            )}

            {visibleTableFavorites && visibleTableFavorites.length > 0 && (
              <div>
                <p className="px-3 text-[11px] font-semibold tracking-wide text-muted-foreground/70 uppercase">
                  Tabelas favoritas
                </p>
                <nav className="flex flex-col gap-0.5">
                  {visibleTableFavorites.map((favorite) => (
                    <div
                      key={`${favorite.dataset_id}.${favorite.table_id}`}
                      className="dp6-nav-item group flex flex-col gap-0.5 rounded-lg px-3 py-2 hover:bg-muted"
                    >
                      <Link
                        to={`/datasets/${favorite.dataset_id}`}
                        state={{ highlightTable: favorite.table_id }}
                        className="flex items-center gap-2 text-sm text-foreground"
                      >
                        <Star size={12} className="shrink-0 fill-primary text-primary" />
                        <span
                          className="truncate"
                          title={`${favorite.dataset_id}.${favorite.table_id}`}
                        >
                          {favorite.dataset_id}.{favorite.table_id}
                        </span>
                      </Link>
                      <FavoriteNickname
                        nickname={favorite.nickname}
                        onSave={(nickname) =>
                          updateNickname.mutate({
                            projectId,
                            datasetId: favorite.dataset_id,
                            tableId: favorite.table_id,
                            nickname,
                          })
                        }
                      />
                    </div>
                  ))}
                </nav>
              </div>
            )}

            {visibleDatasetFavorites && visibleDatasetFavorites.length > 0 && (
              <div>
                <p className="px-3 text-[11px] font-semibold tracking-wide text-muted-foreground/70 uppercase">
                  Datasets favoritos
                </p>
                <nav className="flex flex-col gap-0.5">
                  {visibleDatasetFavorites.map((favorite) => (
                    <div
                      key={favorite.dataset_id}
                      className="dp6-nav-item group flex flex-col gap-0.5 rounded-lg px-3 py-2 hover:bg-muted"
                    >
                      <Link
                        to={`/datasets/${favorite.dataset_id}`}
                        className="flex items-center gap-2 text-sm text-foreground"
                      >
                        <Star size={12} className="shrink-0 fill-primary text-primary" />
                        <span className="truncate" title={favorite.dataset_id}>
                          {favorite.dataset_id}
                        </span>
                      </Link>
                      <FavoriteNickname
                        nickname={favorite.nickname}
                        onSave={(nickname) =>
                          updateNickname.mutate({
                            projectId,
                            datasetId: favorite.dataset_id,
                            tableId: null,
                            nickname,
                          })
                        }
                      />
                    </div>
                  ))}
                </nav>
              </div>
            )}
          </div>
        </SidebarSection>

        <SidebarSection
          label="Análises de qualidade"
          to="/quality"
          open={dqAnalysesOpen}
          onOpenChange={setDqAnalysesOpen}
        >
          <nav className="flex flex-col gap-0.5">
            <NavLink to="/quality/folders" className={NAV_LINK_CLASS}>
              <FolderKanban size={16} />
              Pastas de profiling
            </NavLink>
          </nav>
        </SidebarSection>

        {recentTables && recentTables.length > 0 && (
          <SidebarSection label="Recentes" open={recentOpen} onOpenChange={setRecentOpen}>
            <QuantityPicker value={recentLimit} onChange={setRecentLimit} />
            <nav className="flex flex-col gap-0.5">
              {recentTables.map((view) => (
                <Link
                  key={`${view.dataset_id}.${view.table_id}.${view.viewed_at}`}
                  to={`/datasets/${view.dataset_id}`}
                  state={{ highlightTable: view.table_id }}
                  className="dp6-nav-item flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-foreground hover:bg-muted"
                >
                  <History size={12} className="shrink-0 text-muted-foreground" />
                  <span className="truncate" title={`${view.dataset_id}.${view.table_id}`}>
                    {view.dataset_id}.{view.table_id}
                  </span>
                </Link>
              ))}
            </nav>
          </SidebarSection>
        )}
      </SidebarServiceGroup>

      <SidebarServiceGroup
        icon={<HardDrive size={16} />}
        label="Cloud Storage"
        to="/storage"
        open={cloudStorageOpen}
        onOpenChange={setCloudStorageOpen}
      >
        <nav className="flex flex-col gap-0.5">
          <NavLink to="/storage" end className={NAV_LINK_CLASS}>
            <HardDrive size={16} />
            Buckets
          </NavLink>
          <NavLink to="/storage/waste" className={NAV_LINK_CLASS}>
            <PiggyBank size={16} />
            Scanner de desperdício
          </NavLink>
        </nav>
      </SidebarServiceGroup>

      <SidebarServiceGroupPlaceholder icon={<Workflow size={16} />} label="Workflows" />
      <SidebarServiceGroupPlaceholder icon={<Timer size={16} />} label="Scheduler" />
      <SidebarServiceGroupPlaceholder icon={<Container size={16} />} label="Cloud Run" />
    </aside>
  )
}
