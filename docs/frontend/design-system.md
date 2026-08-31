# Design system — o contrato com o código

Identidade visual baseada no brand **dp6** (part of the brandtech group).
Referência de produto: **Metabase** — denso, funcional, orientado a dados.
Filosofia: minimalismo com personalidade — menos decoração, mais clareza.

## Regra de sincronização (obrigatória)

> Nenhum valor é documentado aqui sem existir como token em
> `apps/frontend/src/index.css`. Nenhum token entra, sai ou muda de valor
> no `index.css` sem que este arquivo seja atualizado **no mesmo PR**.

O `index.css` é a fonte de verdade dos valores; este doc explica o
propósito de cada grupo e o que **não** fazer com ele.

---

## Tailwind v4 — onde vive cada coisa

Não existe `tailwind.config.js`. Tudo está em `apps/frontend/src/index.css`:

- `@import "tailwindcss"`, `"tw-animate-css"`, `"shadcn/tailwind.css"`.
- `@custom-variant dark (&:is(.dark *))` — o tema é a classe `.dark` em
  `<html>` (ver [`behaviors.md`](behaviors.md) §Tema).
- Bloco **`@theme inline`** — pares `--color-*: var(--*)`, a escala
  `--text-*` (com `--text-*--line-height`), `--radius-*`,
  `--shadow-elevation-*`, `--font-sans`.
- Blocos **`:root`** (tema claro) e **`.dark`** (tema escuro) logo abaixo —
  os valores concretos (`--background`, `--primary`, `--status-*`, …).
- Fora de `@layer`: `:focus-visible` global, `.dp6-divider`, scrollbar
  fina, reset de `prefers-reduced-motion`.

Para adicionar/alterar um token: editar `@theme inline` **e** os blocos
`:root`/`.dark` — nunca um `tailwind.config`.

`components.json`: style `base-nova`, `baseColor: neutral`, `cssVariables:
true`, sem `prefix`, `iconLibrary: lucide`. Aliases: `@/components`,
`@/components/ui`, `@/lib`, `@/lib/utils`, `@/hooks`.

---

## Cores

### Base (shadcn) — invertidas entre `:root` (claro) e `.dark`

`--background` `--foreground` · `--card(-foreground)` · `--popover(-foreground)` ·
`--secondary(-foreground)` · `--muted` `--muted-foreground` · `--accent(-foreground)` ·
`--border` · `--input` · `--ring` · `--destructive` · além do set `--sidebar*`.

- Usar sempre pelo papel (`bg-card`, `text-muted-foreground`, `border-border`),
  nunca o hex.
- `--muted-foreground` foi recalibrado na auditoria de acessibilidade
  (claro `#555b62`, escuro `#8f96a1`) para passar ≥4.5:1 contra
  `--background` **e** `--card` (o `#5b626c` original tinha ~2.74:1 no
  escuro — texto secundário quase ilegível). Não voltar ao valor antigo.

### Acento dp6

`--primary` = **`#FFB302`** (amarelo dp6), `--primary-foreground` =
`#1D1D1B`, idênticos nos dois temas. `--ring` e `--sidebar-primary`
seguem o mesmo amarelo.

- `#FFB302` é cor de **preenchimento** (botão primário, indicador ativo,
  barra, `.dp6-divider`), **nunca de texto** sobre `--background`/`--card`
  — contraste ≈1.7:1 no claro, falha AA. Isso vale para `text-primary` e
  qualquer `text-status-*` sem sufixo `-foreground`.

### Status — dois papéis, não confundir

| Token | Papel | Contraste exigido | Varia por tema? |
|---|---|---|---|
| `--status-{ok,warn,error,info}` | **preenchimento / gráfico** — chip `bg-status-warn/12`, borda `/30`, barra de chart | ≥3:1 (fill) | não |
| `--status-{ok,warn,error,info}-foreground` | **texto / ícone** sobre superfície tintada — classe `text-status-*-foreground` | ≥4.5:1, **nos dois temas** | **sim** |

Valores de fill (ambos os temas): ok `#34D399` · warn `#FFB302` ·
error `#E53E3E` · info `#63B3ED`.
Valores de foreground — claro: ok `#0b7a43` · warn `#8a5700` ·
error `#c1291f` · info `#1a6ba8`; escuro: ok `#34d399` · warn `#ffb302` ·
error `#f87171` · info `#63b3ed`. (Contrastes calculados nos comentários
do `index.css`.)

### Acentos secundários

`--accent-blue` `#1a365d` · `--accent-purple` `#6b46c1` ·
`--accent-green` `#059669` · `--accent-orange` `#f97316` — uso pontual
(ex.: unicidade HLL no modal de profiling: roxo = alta cardinalidade,
laranja = baixa). No máximo **2 cores de destaque por tela** (ver
[`ui-ux-rules.md`](ui-ux-rules.md)).

---

## Tipografia

Fonte **Ubuntu**, carregada via `<link>` em `apps/frontend/index.html`
(`family=Ubuntu:wght@300;400;500;700`) — **não** por `@import` no CSS
(Tailwind v4 descarta `@import` posicionado depois do conteúdo expandido
de `"tailwindcss"`).

Pesos disponíveis: **300, 400, 500, 700**. O peso **600 (`font-semibold`)
não existe no Ubuntu** — usar `font-bold` (700) em título e `font-medium`
(500) onde precisa de peso médio.

Escala **semântica** (tokens em `@theme inline`, cada um com
`--text-*--line-height`, então a classe `text-x` já traz o line-height):

| Token | Tamanho | Uso |
|---|---|---|
| `text-label` | 0.75rem / 12px | rótulo de campo, cabeçalho de tabela, badge, caption |
| `text-body` | 0.875rem / 14px | corpo, célula de tabela, descrição — **mínimo de leitura** |
| `text-subtitle` | 1rem / 16px | `<h3>` de subseção, valor de KPI pequeno |
| `text-title` | 1.25rem / 20px | `<h2>` de seção, valor de `MetricTile` |
| `text-display` | 1.75rem / 28px | `<h1>` de página (via `PageHeader`) |

- Usar essas classes. **Não** usar `text-[11px]`/`text-[13px]` ad-hoc nem a
  escala genérica `text-xs…text-3xl` para hierarquia.
- Corpo nunca abaixo de 14px. `text-label`/12px só para rótulo/caption/badge.
- Bloco de texto corrido (descrição, callout) com `max-w-[65ch]`.

---

## Raio, elevação, espaçamento

- **Raio de componente:** `--radius-control` (botão, input, card, tabela,
  popover) e `--radius-pill` (`9999px`, para badge/toggle). Não
  re-hardcodar `rounded-[Npx]`. Existe também a escala derivada
  `--radius-sm…--radius-4xl` (múltiplos de `--radius` = `0.5rem`).
- **Elevação:** um par sutil só — `--shadow-elevation-1` (popover/menu),
  `--shadow-elevation-2` (dialog). Sem `box-shadow` pesado; a identidade
  dp6 prioriza **borda**.
- **Espaçamento** (escala 4/8/12/16/24/32):

  | Entre o quê | classe |
  |---|---|
  | Seções de página (separação semântica forte) | `gap-8` (32) |
  | Blocos dentro de uma seção | `gap-4` (16) |
  | Elementos relacionados (label+control, ícone+texto) | `gap-2` / `gap-1.5` |
  | Padding de card/callout | `p-4`; célula de tabela `p-2` |

- **Container de conteúdo:** `max-w-[1400px] mx-auto` — já aplicado no
  `apps/frontend/src/app/layout.tsx`, não estica de ponta a ponta em
  monitor largo.

---

## Ícones

`lucide-react`. Outline, `16px` inline / `20px` em botões. Ícone
decorativo com `aria-hidden="true"`; ícone informativo com rótulo
(`<span class="sr-only">` ou texto ao lado).

Mapeamento de domínio: Catálogo `Database` · Freshness `Clock` ·
Profiling `BarChart2` · FinOps `DollarSign` · Qualidade `CheckCircle` ·
Alerta `AlertTriangle` · Projeto GCP `Cloud`.

---

## Catálogo — componentes compartilhados (`apps/frontend/src/components/`)

**Usar estes em vez de recriar o padrão à mão.** Todos nasceram de
duplicação real removida (a auditoria de UI/acessibilidade,
branch `fix/ui-a11y-tokens`, mergeada em `main` via PR #49). Não são
primitivos — compõem primitivos de `ui/`.

| Componente | Quando usar | Quando NÃO usar |
|---|---|---|
| `PageHeader` | Cabeçalho de rota: **um** `<h1>` (`text-display`) + subtítulo + slot `actions` + `back` opcional. Renderizar fora dos ramos de loading/erro. Empilha em `< sm`. | Dentro de uma seção (use `SectionHeading`) |
| `SectionHeading` | `<h2>`/`<h3>` real dentro da página (`text-title`/`text-subtitle`) + slot `actions`. | Como título clicável/colapsável (use `CollapsibleSection`) |
| `CollapsibleSection` | Bloco colapsável cujo título **é** um `<h2>`/`<h3>` real envolvendo o disclosure (padrão WAI-ARIA). `variant="section"|"subsection"`, `defaultOpen`, `actions` (fora do trigger). | Conteúdo que nunca colapsa (use `SectionHeading`) |
| `WarningCallout` | Aviso / degradação (`role="status"`, ícone + texto). `variant="warning"` (heads-up, resultado vazio explicado, cache não gerado) \| `"info"` (neutro, ex.: grafo truncado). | Erro de query (use `ApiErrorNotice`) |
| `ApiErrorNotice` | Erro de query (`role="alert"`): mostra `error.message` real + `error.body.fix` (comando `gcloud` de correção) quando existe. Props `action`, `showFix`. | `<p class="text-status-error">Erro ao carregar…</p>` — nunca |
| `LoadingState` | Carregando: spinner + texto inline (`role="status"`), `label` custom. | Skeleton elaborado — a plataforma não usa (ver `ui-ux-rules.md`) |
| `EmptyState` / `EmptyStateRow` | Estado vazio: ícone + título + descrição/ação. `EmptyStateRow` (com `colSpan`) para dentro de `<TableBody>`. | — |
| `StatusBadge` | Badge de estado: **ícone + rótulo**, nunca só cor (WCAG 1.4.1). `status="ok\|warn\|error\|info\|running\|neutral"`. | Badge sem semântica de estado (use `Badge` de `ui/`) |
| `CacheStalenessBadge` | Indicador "Cache atualizado há Xh" nas telas servidas por cache pré-computado (lineage, órfãs, mapa de acesso). `cacheUpdatedAt = null` → não renderiza (veio ao vivo). | Fora dessas telas |
| `MetricTile` / `MetricGrid` | Tile de KPI: valor `text-title` bold, rótulo `text-label uppercase`. `alert` → borda `--status-error`. `MetricGrid` = grid `auto-fill` (sem breakpoint mágico). | Um número solto no meio de texto |
| `ChoiceToggle` | Grupo "escolher um" em pills (`role="group"` + `aria-pressed`, `aria-label` obrigatório). `size="sm\|md"`. | Mais de ~5 opções, ou multi-seleção (use `Select`/checkboxes) |
| `DateField` | `<input type="date">` com `<Label htmlFor>` associada e altura `h-8` consistente com os filtros. | Input de data sem rótulo visível |
| `SortableTableHead` | `<th>` clicável com seta de ordenação (`active`, `direction`, `align`). Par com `useTableFilterSort`. | Cabeçalho de coluna não-ordenável |
| `PaginationBar` | Anterior/Próxima + "linhas por página" + "X–Y de Z". Some com `totalCount === 0`. Par com `usePagination`. | Listas curtas que nunca paginam |
| `RefreshButton` | Botão-ícone ghost "Atualizar dados" (spin em `isRefreshing`) — normalmente no slot `actions` do `PageHeader`. | — |
| `SqlPreview` | Bloco do SQL gerado por um fluxo de análise: "Ver/Ocultar SQL" + "Copiar SQL", `font-mono`, fundo `bg-background`. | Trecho de código que não é o SQL da query em questão |
| `DatasetScopeGate` | Tela de pré-execução: obriga escolher escopo (1+ datasets, ou "Todos") antes de disparar um scan de projeto inteiro. Props `projectId`, `title`, `description`, `onRun`, `runLabel`, `isRunning`, `extraControls`. | Escopo por tabela (isso é `ColumnTypeScopePicker`, feature-level) |
| `ThemeToggle` | Alternador sol/lua — só no topbar. | Qualquer outro lugar |

Ao criar um componente compartilhado novo: adicionar linha nesta tabela
**no mesmo PR** e apontar a tela canônica em [`references.md`](references.md).

---

## Primitivos shadcn (`apps/frontend/src/components/ui/`)

Hoje presentes: `badge` `button` `card` `checkbox` `collapsible` `command`
`dialog` `input` `input-group` `label` `popover` `progress` `select`
`separator` `skeleton` `sonner` `table` `tabs` `textarea` `tooltip`.

Regras:

- **Adicionar via CLI:** `pnpm dlx shadcn add <nome>` (style `base-nova`,
  ver `components.json`). Nunca copiar/colar à mão.
- **Não editar o arquivo gerado.** O lint do biome está **desligado** para
  `src/components/ui/**` (override em `apps/frontend/biome.json`)
  justamente porque é código de terceiro — tratar como read-only.
- **Customização só via token.** Se a cor/raio/tipo do primitivo está
  errada, o problema é um token no `index.css`, não o `.tsx`. Não forkar o
  primitivo para "ajustar um detalhe" — se for inevitável, é um componente
  novo em `src/components/` que envolve o primitivo (foi assim que
  `WarningCallout`, `StatusBadge` etc. nasceram).
- `skeleton` existe no diretório mas a plataforma **não usa skeleton
  loaders** — o padrão de carregamento é `LoadingState` (ver
  [`ui-ux-rules.md`](ui-ux-rules.md) e [`behaviors.md`](behaviors.md)).
