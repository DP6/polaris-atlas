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

- **Raio de componente — "quase quadrado", `--radius = 5px`** (rodada 3;
  era 10px na rodada 2). Todo **retângulo** (card, painel, tabela, input,
  botão) cai em ~5px; **pill** (`--radius-pill = 9999px`: badge, toggle,
  avatar) continua totalmente redondo. Não re-hardcodar `rounded-[Npx]`.
  - A escala derivada `--radius-sm…--radius-4xl` foi **achatada de
    propósito**: `--radius-xl == --radius-lg == --radius` (5px). Motivo:
    card usa `rounded-xl`, botão/input usam `rounded-lg` — os dois
    precisam bater em 5px. `sm`/`md` ficam 1–3px menores (chip pequeno,
    botão `xs`/`sm` → `sm` = `calc(5px - 3px)` = 2px); `2xl`+ crescem em
    passos fixos (`+4/+10/+16px`) pro dialog e afins.
  - `--radius-control` = `--radius` (mantido como apelido semântico).
- **Elevação:** `--shadow-elevation-1` (popover/menu), `--shadow-elevation-2`
  (dialog). Fora disso, profundidade continua vindo de **borda**. O
  `--shadow-glow` (`0 18px 40px -20px var(--glow)`) foi **aposentado do
  hover** na rodada 3 (o usuário pediu menos glow grande) — hoje só
  `--glow` cru sobrevive em acentos contidos (botão primário
  `.dp6-gradient-primary`, barra ativa da sidebar, aresta de lineage).
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

## Vida — gradiente, glow, glass, movimento

Refresh visual 2026-09 (brief: `docs/specs/frontend-visual-refresh.md`). A
regra antiga "sem gradiente, sem sombra, flat" foi **relaxada** — na medida
do protótipo (`.panel`/`.kpi`/`.btn.primary`), **não** ilimitado. O que
**não** entrou: efeitos de fundo de tela cheia (constelação, aurora/blobs,
grain, scanlines, "sweep", parallax de cursor). Ver
[`ui-ux-rules.md`](ui-ux-rules.md) §Identidade visual pra fronteira.

**Tokens** (em `index.css`):

| Token | O que é |
|---|---|
| `--primary-2` / `--color-primary-2` | Amarelo dp6 mais claro (`#ffca45`). **Só** topo de gradiente (botão primário, barra ativa, preenchimento de gráfico). Nunca texto. |
| `--glow` | `rgba(255,179,2, .30)` no dark / `.22` no claro — o rgba tintado do glow. Rodada 3: só sobrevive em acentos contidos (`.dp6-gradient-primary`, `.dp6-nav-active`, `.dp6-lineage`). |
| `--shadow-glow` | Sombra `0 18px 40px -20px var(--glow)`. **Aposentado na rodada 3** (o hover de card/tile/opt-card não usa mais glow grande) — token permanece definido mas sem consumidor. |
| `--ease-dp6` / `ease-dp6` | `cubic-bezier(.16,1,.3,1)` — curva única dos hovers/entradas do refresh. |

**Utilitárias plain-CSS** (em `index.css`, fora de `@layer`):

| Classe | Uso |
|---|---|
| `.dp6-hoverable` | Hover discreto (rodada 3, sem glow grande): só um contorno fino em `--primary` (`box-shadow: 0 0 0 1px …primary 22%`) + `translateY(-2px)` (só com `prefers-reduced-motion: no-preference`). Em card/painel/linha clicável — **não** no `MetricTile` (big number não é clicável). |
| `.dp6-glass` | Superfície semitransparente + `backdrop-filter: blur`. **Opt-in**, raro (o app é denso e quase não tem o que desfocar atrás); na dúvida `bg-card` sólido. |
| ~~`.dp6-headline-glow`~~ | **Removida na rodada 3.** O `<h1>` do `PageHeader` agora é chapado (o usuário pediu menos gradiente grande em telas). |
| ~~`.dp6-brand-bars`~~ | **Removida na rodada 3** junto com o componente `<BrandBars>` e o prop `showBrandBars` do `PageHeader`. |
| `.dp6-gradient-primary` | Gradiente + inset ring + glow do botão "herói". **Opt-in via `className`** num `<Button variant="default">` específico (a primitiva `ui/button` é read-only, não dá pra override global). |
| `.dp6-nav-active` | Item de nav **ativo** da sidebar: barra de acento `3px` à esquerda com glow (`::before`) + fundo em gradiente `--primary/14 → transparent`. Substitui o bloco amarelo chapado. Par com `rounded-lg` + `text-foreground` + ícone `text-primary` no `NavLink`. Ver `frontend-visual-refresh-plan.md` §1 (Q-001). |
| `.dp6-lineage` (escopo) | Arestas do grafo de lineage: `.react-flow__edge-path` amarelo + `.dp6-edge-hot`/`.dp6-edge-dim` no hover de aresta. O `.animated` do @xyflow anima; reduced-motion congela. |
| `.dp6-opt-card` | Card de escolha (protótipo `.opt-card`): hover lift `translateY(-3px)` (gated em `no-preference`) + `border-color` em `--primary` + `--shadow-elevation-1` (rodada 3: sem glow). `.dp6-opt-card-featured` **removida** — nenhum card usa amarelo de fundo; diferenciação só no hover. Renderizado pelo `<OptionCard>`. |
| `.dp6-nav-item` | Item de nav em **hover**: dica de glow (anel `inset` fino em `--primary`) — mais contido que `.dp6-hoverable` (numa lista vertical densa o glow cheio vira ruído). |

Além das classes, uma **regra global** (não utilitária, mesmo padrão da
regra de foco): `[data-slot="table-body"] [data-slot="table-row"]:hover` →
gradiente amarelo sutil + barra lateral `inset 3px` em `--primary` na
primeira célula. Substitui o `hover:bg-muted` uniforme que o `ui/table` já
aplicava em toda linha. Restrita ao corpo (não pega o cabeçalho).

**Movimento:** teto de transição sobe pra **≤300ms** (era ≤200ms) pros
hovers/entradas. O reset de `prefers-reduced-motion` no fim do `index.css`
continua **absoluto e intocado** — nada de `!important` que fure ele, nada
de animação contínua/decorativa, nada de skeleton.

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
| `MetricTile` / `MetricGrid` | Tile de KPI: valor `text-title` bold, rótulo `text-label uppercase`. `icon` (lucide, num "chip" acima do rótulo — mapeamento por KPI no brief). `alert` → borda `--status-error`. **Sem hover** (rodada 3: big number não é clicável). `MetricGrid` = grid `auto-fill`. | Um número solto no meio de texto |
| `ChartTooltip` + `useChartTooltip` | Tooltip flutuante que segue o cursor, compartilhado por gráfico/mini-gráfico (crosshair de linha, hover de barra). Portal pro `<body>`, `pointer-events-none`. `useChartTooltip()` → `{ state, show, move, hide }`; `<ChartTooltip state={…} />` uma vez por tela. | Tooltip ancorado num elemento fixo (use `ui/tooltip`) |
| `SlaDistributionBar` | **3 barras verticais** (verde/amarelo/vermelho — as 6 faixas de SLA colapsadas em `SLA_SEVERITY`) da distribuição das tabelas de um dataset. As 3 sempre presentes; varia a **altura** (∝ contagem, altura mínima 6% pra faixa com 0). Prop `height` = classe de altura do container (`h-8` em célula de tabela, `h-10`/`h-12` em card/painel). Consome `FreshnessCounts` (sem query nova). `role="img"` + `title` com a decomposição. Cards do Catálogo de Dados + Freshness. Ver `docs/specs/freshness.md`. | Mostrar contagem exata por faixa (isso é tabela, ver `DatasetFreshnessTable`) |
| `Panel` | "Bloco" (protótipo `.panel`): container 5px com `border` + `bg-card` + borda-gradiente (`.dp6-panel`). Props `title`/`subtitle`/`actions`/`as`/`filterRow` (filtros DENTRO do painel)/`hoverable`/`glass`. Corpo não clipa scroll horizontal. Padrão pra toda tabela de domínio que hoje fica solta na página. | Um `<Table>` que já está dentro de outro container com título |
| `ComboChart` | Coluna + linha(s) recharts num `bloco`, eixo Y duplo (coluna esq., linha dir.). Props `bar`/`lines`/`refLine`. Extraído do `<ComposedChart>` de BudgetPage. | Uma série só (use `LineChart`/`BarChart` direto) |
| `OptionCard` + `OptionCardGrid` | Card de escolha: ícone-chip + título + descrição + `meta`. Props `to`/`onClick`/`soon`/`layout` (`"stack"` default \| `"wide"` = ícone à esquerda, card retangular baixo). Todos com a mesma cor de base (`bg-card`) — diferenciação só no hover. `OptionCardGrid` `columns` (2\|3\|4) fixa o máximo por linha; sem ele, auto-fill a partir de 16rem. Telas de overview de grupo + chooser de análise (`columns={4}` + `layout="wide"`). | Lista densa (use `<Table>`) |
| `HBarList` | Lista de barras horizontais + `ChartTooltip` no hover (contagem exata). Item = `{label,value,displayValue,tooltip,variant:'key'|'cat'}`. Gráfico de cardinalidade por coluna da análise de qualidade. | Tabela de dados (use `<Table>`) |
| `CompositeScoreRing` | Anel de score composto (SVG à mão, cap arredondado). `score` central (`--foreground`, nunca `--primary`), `segments` (1–2 anéis + legenda texto+valor), `compact` (34px pra coluna de tabela). | Barra de progresso simples (use `Progress`/`CompletenessBar`) |
| `Funnel` | Funil de retenção em `<polygon>` afunilando; rótulo+valor+% numa coluna ao lado (nunca por dentro). `role="img"` + `aria-label`. | Comparação de categorias não afuniladas (use `BarChart`) |
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
