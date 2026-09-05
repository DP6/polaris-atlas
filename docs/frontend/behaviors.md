# Comportamento — referências

Como a interface **se comporta**: buscar dados, mostrar estado, dar
feedback, formatar, lembrar preferência. É referência de padrão, não
regra rígida — mas divergir sem motivo gera inconsistência entre telas.

---

## Data fetching

- **TanStack Query, sempre.** Nenhuma chamada `fetch` direta dentro de um
  componente de página (Guardrail do `CLAUDE.md`).
- **Camadas:**
  - `lib/http-client.ts` — `httpClient.get/post/put/delete`, `credentials:
    'include'` (cookie de sessão cross-site), lança `ApiError` com
    `.status` e `.body` (`{ message, fix? }`).
  - `lib/api/<domínio>.ts` — funções que chamam o `httpClient` e tipam a
    resposta (tipos em `types/<domínio>.ts`).
  - `features/<domínio>/hooks.ts` — os `useQuery`/`useMutation` do
    domínio. Componentes de página consomem **só** esses hooks.
- **Defaults** (`app/query-client.ts`): `staleTime: 30s`; retry só em erro
  de rede ou 5xx (4xx não readianta), backoff exponencial até 8s;
  **mutations também têm retry** (mesma política) por causa do cold start
  do backend em dev.

## Estados de tela

| Estado | Componente | Observação |
|---|---|---|
| Carregando | `LoadingState` | spinner + texto inline, `role="status"`. Sem skeleton. |
| Erro | `ApiErrorNotice` | `role="alert"`; mostra `error.message` real + `error.body.fix` (comando `gcloud` de remediação) quando existe; prop `action` para um botão extra, `showFix={false}` para esconder o `fix`. Nunca `<p class="text-status-error">Erro…</p>`. |
| Vazio | `EmptyState` / `EmptyStateRow` | `EmptyStateRow` (com `colSpan`) dentro de `<TableBody>`. |
| Degradação / heads-up | `WarningCallout` | `role="status"`, `variant="warning"|"info"`. Ex.: resultado vazio com explicação, cache ainda não gerado, grafo truncado. |

O `PageHeader` fica **fora** desses ramos — o `<h1>` aparece mesmo
durante loading/erro; só o conteúdo troca.

## Feedback de ação

- **Toasts:** `sonner` (`components/ui/sonner.tsx`, montado uma vez).
  Confirmar sucesso de mutation curta (favoritou, salvou em pasta), erro
  de ação disparada por botão.
- **Estado "rodando":** `StatusBadge status="running"` (ícone que gira).

## Optimistic update

Padrão em `features/favorites/` — o toggle de favorito atualiza o cache do
React Query na hora e reverte no `onError`. Usar só onde a ação é
idempotente e a latência incomoda (favoritar, nickname). Não para
operações com efeito colateral relevante.

## Paginação

`usePagination` — client-side sobre lista já carregada inteira.
`initialPageSize = 20`; `PAGE_SIZE_OPTIONS = [10, 20, 50, 100]`. `page` é
reclampado sozinho quando o total encolhe. UI via `PaginationBar` (some
com `totalCount === 0`).

## Formatação (`lib/format.ts`)

Sempre por essas funções, nunca `toLocaleString`/`toFixed` solto:

| Função | Regra |
|---|---|
| `formatBytes` | base **1000** (`KB`/`MB`/…), 2 casas; `null → "—"` |
| `formatNumber` | `Intl.NumberFormat('pt-BR')`; `null → "—"` |
| `formatDate` | `pt-BR`, `dd/mm/aaaa hh:mm`; inválido/`null → "—"` |
| `formatPercent` | `n.toFixed(digits)%`, `digits = 1` default |
| `formatUsd` | `US$ `, **6 casas** se `< 0.01` (custo subcentavo de tabela órfã), senão 2 |
| `formatRelativeToNow` | "agora mesmo" / "há N min" / "há Nh" / "há N dias" — usado pelo `CacheStalenessBadge` |

Idioma da UI é **pt-BR**.

## Tema

- `useTheme` (`hooks/useTheme.ts`) — alterna a classe `.dark` em `<html>`.
- **Dark é o padrão.** Só persiste `"light"` em `localStorage`
  (`atlas:theme`); ausência de valor ou `localStorage`
  indisponível → dark.
- Um **script bloqueante em `index.html`** aplica a classe `.dark` antes
  do primeiro paint (evita flash do tema errado); o hook só sincroniza o
  estado do React com o DOM.
- Alternador: `ThemeToggle`, só no topbar.
- Os tokens de status têm variantes `-foreground` **por tema** para
  passar AA nos dois — ver [`design-system.md`](design-system.md).

## Preferências locais (`localStorage`)

Convenção: chave prefixada `atlas:`, toda leitura/escrita em
`try/catch` (modo privado quebra `localStorage`), sempre com um default
sensato.

| Hook / módulo | Chave | Default se ausente |
|---|---|---|
| `useTheme` | `atlas:theme` | `dark` |
| `useSidebarCollapsed` | `atlas:sidebar-collapsed` | expandida (`false`) — persiste; sem script bloqueante (a sidebar só aparece depois do projeto resolvido) |
| `useLastProject` | `atlas:last-project-id` | vazio — só pré-preenche o seletor de projeto |

## Sidebar — dois níveis, não confundir

- **Sidebar inteira** (mostrar/esconder): `useSidebarCollapsed`,
  persistida, default **expandida**. Botão no `Topbar`.
- **Grupos dentro da `DatasetSidebar`** (Catálogo, Governança, FinOps…):
  começam **recolhidos** e o estado **não** é persistido — decisão de
  produto confirmada (2026-08-30), "sidebar menos carregada no primeiro
  acesso". Não inverter sem reconfirmar.

## Contrato de dados de cada tela

Endpoints, parâmetros e response schema não estão aqui — estão na spec do
domínio: `docs/specs/<domínio>.md`.
