# CHANGELOG — Observability Hub

Histórico de fases, decisões, erros cometidos e pivotagens.
Atualizado ao final de cada fase pelo Claude Code.

---

## Refresh visual do Hub — rodada 3 (ajustes de UI, 2026-09)

Terceira leva de ajustes finos após validação visual do usuário em `dev`. Sem
funcionalidade nova. Plano em `~/.claude/plans/gere-um-plano-altera-es-unified-wilkes.md`
(11 branches R3-*, empilhadas sobre a ponta da rodada 2). Decisões travadas: voltar global
por histórico no `PageHeader`; período do Budget = preset 7/15/30 dias (teto do cache);
scanner de desperdício vira overview de 2 cards → sub-rotas; distribuição de freshness = 3
barras verticais sempre visíveis.

### R3-tokens — `feat/r3-tokens` (só front-end)

- **Raio 10px → 5px:** `--radius` de `0.625rem` → `0.3125rem` em `:root` e `.dark`
  (`index.css`). Escala derivada (`--radius-sm…4xl`) segue via `calc()`.
- **Menos gradiente grande:** `.dp6-headline-glow` (wash amarelo atrás de todo `<h1>`) e
  `.dp6-brand-bars` (+ componente `BrandBars` + prop `showBrandBars` do `PageHeader` + 4
  call sites) **removidos**. `.dp6-hoverable:hover` e `.dp6-opt-card:hover` perderam o
  `--shadow-glow` (agora contorno fino / `--shadow-elevation-1`). Hover de linha de tabela
  de `primary 9%` → `6%`. `--glow` cru só sobrevive em `.dp6-gradient-primary` /
  `.dp6-nav-active` / `.dp6-lineage`.
- **Cards com cor de base única:** `OptionCard` perdeu o prop `featured` + `.dp6-opt-card-featured`
  (fundo amarelo) — removido dos 3 call sites (Governança, AnalysisChooser, QualityOverview).
- **Big number sem hover:** `MetricTile` e o `BigNumber` da FinOps overview perderam
  `.dp6-hoverable` (não são clicáveis).
- Doc-sync: `docs/frontend/design-system.md` (§Raio, §Vida, tabela de componentes),
  `docs/frontend/ui-ux-rules.md` (§Identidade). `pnpm lint` + `pnpm build` verdes.

### R3-back — `feat/r3-back` (só front-end)

- **Voltar padronizado:** `PageHeader` sempre renderiza um controle "Voltar" no
  topo-esquerdo (exceto na home `/`). Com `back={{to,label}}` → `<Link>` semântico
  (comportamento das 11 telas que já tinham); sem o prop → `<button>` genérico que faz
  `navigate(-1)` (fallback `navigate('/')` quando não há histórico). As ~16 telas com
  `PageHeader` sem `back` ganham o voltar automaticamente.
- Doc-sync: `docs/frontend/patterns.md` §Cabeçalho de rota, `ui-ux-rules.md`.

### R3-catalog-volume — `feat/r3-catalog-volume` (só front-end)

- Catálogo de Dados (`/`): 3º big number **"Volume"** (`formatBytes` do
  `Σ dataset.total_size_bytes` — campo já existe em `DatasetSummary`, vem de
  `TABLE_STORAGE` no backend, sem agregação nova). Ícone `HardDrive`.

### R3-freshness — `feat/r3-freshness` (só front-end)

- `SlaDistributionBar` reescrito: **3 barras verticais** (verde/amarelo/
  vermelho — as 6 faixas de SLA colapsadas em `SLA_SEVERITY`) no lugar da
  barra horizontal empilhada. As 3 **sempre presentes**; varia só a altura
  (∝ contagem, altura mínima 6% pra faixa com 0). Prop `height` = classe
  do container. Call sites: `SlaRow` `h-12`, `DatasetFreshnessTable` `h-8`,
  `DatasetOverviewCard` default `h-10`. `TableFreshnessTable` não usa o
  componente — sem mudança.
- Doc-sync: `design-system.md`, `docs/specs/freshness.md`.

### R3-finops-overview — `feat/r3-finops-overview` (só front-end)

- `DatasetSidebar`: NavLink **"Visão geral"** (`Gauge`, `to="/finops" end`) como 1º filho
  do grupo FinOps.
- `FinOpsOverviewPage`: o `OptionCardGrid` (Scanner / Budget / Configurar budget) subiu
  pra logo após o `PageHeader`, antes dos big numbers.

### R3-finops-scanner-cards — `feat/r3-finops-scanner-cards` (só front-end)

- `/finops/scanner` deixou de ser 2 abas e virou **overview de 2 cards** (`ScannerOverviewPage`)
  → sub-rotas `/finops/scanner/particionamento` (`PartitionCandidatesPage`) e
  `/finops/scanner/tipos-coluna` (`ColumnTypesPage`), cada uma com `PageHeader` + voltar.
- `FinOpsPage.tsx` → renomeado `scannerTabs.tsx`; os dois corpos (`PartitionCandidatesTab`,
  `ColumnTypesTab`) agora são `export`, o wrapper `FinOpsPage` + `<Tabs>` foram removidos.
- `router.tsx`: 3 rotas no lugar de 1. Doc-sync: `finops-column-types.md`.

### R3-finops-budget-period — `feat/r3-finops-budget-period` (backend + front-end)

- **Backend:** `GET /finops/{p}/budget` ganhou `lookback_days` (`1`–`31`, default `30`,
  clampado no service). A janela deixou de ser fixa no mês corrente
  (`period_start = now - lookback_days`); `_month_start` removido. A projeção virou
  **run-rate mensal** (`média_da_janela × dias_do_mês`) e `projection.days_elapsed` = a
  janela. `finops-budget.md` → v1.8. `uv run pytest tests/unit` = 825 ok.
- **Frontend:** novo `components/LookbackPicker.tsx` (extraído de `OrphansPage`, agora com
  props `options`/`label`/`max`) — `OrphansPage` refatorado pra usá-lo. `BudgetPage`: gate
  com `LookbackPicker` (presets 7/15/30, teto 31); `useBudget`/`finopsApi.getBudget`
  passam `lookback_days`; copies "mês corrente" → "período" / "Janela analisada".
- `pnpm lint` + `pnpm build` verdes.

### R3-fav-recent — `feat/r3-fav-recent` (só front-end)

- Novas rotas `/favoritos` (`FavoritesPage`) e `/recentes` (`RecentsPage`) — a lista
  completa no `<main>`, reusando `useFavorites`/`useUpdateFavoriteNickname`/`useHistory`,
  `Panel`, `EmptyState`, `FavoriteNickname`.
- `DatasetSidebar`: as `SidebarSection` "Favoritos" e "Recentes" ganharam `to=` (nome →
  página; chevron continua abrindo a lista inline). "Recentes" deixou de ser escondida
  quando vazia (mostra um aviso).
- `pnpm lint` + `pnpm build` verdes.

### R3-quality — `feat/r3-quality` (só front-end)

- `OptionCard` ganhou `layout="wide"` (ícone à esquerda, card retangular baixo);
  `OptionCardGrid` ganhou `columns` (2/3/4 — máximo por linha). `AnalysisChooserPage`
  (`/analyze/:d/:t`): 7 cards agora `layout="wide"` + `columns={4}`.
- `/quality` (clique em "Análises de qualidade" na sidebar) virou **redirect →
  `/quality/folders`** — o card "Analisar uma tabela" saiu do overview; `QualityOverviewPage`
  deletado. `/quality/tables` segue alcançável pelo botão "Analisar" do `AssetsTable`.
- Doc-sync: `design-system.md`, `nav-overview-screens.md`. `pnpm lint` + `pnpm build` verdes.

### R3-storage — `feat/r3-storage` (só front-end)

- Novo `StorageOverviewPage` na rota `/storage` (padrão Governança) — 2 `OptionCard`:
  "Buckets" (`/storage/buckets`) e "Scanner de desperdício" (`/storage/waste`). A lista de
  buckets moveu de `/storage` → `/storage/buckets`.
- `DatasetSidebar`: NavLink "Buckets" agora `to="/storage/buckets"` (o label do grupo cai
  na overview). `BucketBrowserPage` breadcrumb → `/storage/buckets`.
- Doc-sync: `nav-overview-screens.md`. `pnpm lint` + `pnpm build` verdes.

### R3-admin — `feat/r3-admin` (só front-end)

- **Funil de retenção reescrito** (`components/Funnel.tsx`): barras horizontais centradas
  afunilando de cima pra baixo (largura ∝ contagem) + rótulo/valor/% acima de cada barra +
  `<table>` sr-only. A versão R2-5 (`<polygon>` SVG com `preserveAspectRatio="none"`)
  distorcia dentro do `h-56`.
- **Todas as seções da aba "Uso do Hub" viram bloco:** `AdminUsageTab` embrulha
  `FavoritesAnalyticsSection`, `ProfilingActivitySection`, `AccessRequestAnalyticsSection`,
  `NavigationAnalyticsSection`, `PiiScanActivitySection` em `<Panel>` (as que ainda usam
  `CollapsibleSection` por dentro ganham a moldura pelo wrapper).
- **Combobox `Command` no dark:** `CommandItem` ganhou `data-selected:bg-primary/10` +
  `data-[checked=true]:bg-primary/15 font-medium` — o item destacado/escolhido pinta um
  fundo amarelo suave (antes `bg-muted` sumia no dark). Vale pra todo combobox
  (ProjectSelector, pickers do Admin, SaveRunToFolderDialog).
- Doc-sync: `design-system.md`, `docs/specs/admin.md`. `pnpm lint` + `pnpm build` verdes.

## Refresh visual do Hub — rodada 2 (2026-09)

Segunda rodada, sobre as lacunas que a rodada 1 marcou como "especificado,
implementação pendente" (`docs/specs/frontend-visual-refresh-plan.md` §5) +
1 bug. Plano completo em
`~/.claude/plans/gere-um-plano-altera-es-unified-wilkes.md` (fatiado em
~13 branches R2-*, empilhadas sobre a ponta da rodada 1). Decisões
travadas com o usuário: chooser de análise com os 7 módulos ativos em
tela cheia; cabeçalho de grupo da sidebar = chevron abre lista + label
abre overview; escopo de backend completo (budget CRUD, score por tabela,
4º modo de busca, filtro de/até no Admin, `table_type` no lineage); funil
de retenção em trapézios com rótulo por fora.

### R2-1 — `feat/r2-pageheader-brandbars` (só front-end)

- `.dp6-headline-glow` reworkada: elipse suave `at 78% 25%` no lugar do
  wash duro `at 100% 0%` (o usuário leu o antigo como "degradê" colado no
  canto). Continua `background` na box, sem `::before` vazando.
- `.dp6-brand-bars` nova: motivo de 3 barras diagonais `skewX(-18deg)` (1
  preenchida + glow) no canto direito, auto-contido (`overflow:hidden` +
  `mask` + `z-index:-1`). Novo `components/BrandBars.tsx`.
- `PageHeader` ganhou `showBrandBars?: boolean` (opt-in; `relative
  isolate` só quando ligado). `design-system.md` §Vida + tabela de
  componentes + `ui-ux-rules.md` §Identidade atualizados no mesmo PR.

### R2-2 — `feat/r2-panel-component` (só front-end)

- Novo `components/Panel.tsx` — "bloco" da plataforma (protótipo `.panel`):
  container 10px com `border` + `bg-card` + borda-gradiente `.dp6-panel`
  (`::after` mascarado). Props `title`/`subtitle`/`actions`/`as`/`filterRow`
  (filtros DENTRO do painel, não soltos antes da `<Table>`)/`hoverable`/`glass`.
- `.dp6-panel` nova no `index.css`. `AssetsTable` (tabela de tabelas de um
  dataset) é o primeiro adotante — vira `<Panel title="Ativos" subtitle=…
  filterRow=…>`. Roll pras outras ~20 tabelas soltas na R2-3.
- `design-system.md` (linha do componente + `.dp6-panel` implícito em §Vida).

### R2-3 — `feat/r2-panel-rollout` (só front-end)

- `<Panel>` nas tabelas soltas de Storage (`BucketsPage`, `WastePage`,
  `BucketBrowserPage`), Freshness (`DatasetFreshnessTable`,
  `TableFreshnessTable`) e Governança (`OrphansPage`). Filtro vai pro
  slot `filterRow` (dentro do painel). Sem `index.css`.
- Admin (`AdminUsageTab`/seções) fica pra R2-5 e FinOps
  (`FinOpsPage`/`BudgetPage`) pra R2-12 — essas telas são reescritas lá e
  já nascem em `Panel`. `QualityFolderComparisonPage` não entrou: já é
  bloco estruturado (chart em box + tabela sob um `<h3>` real).

### R2-4 — `feat/r2-catalog-table-search` (backend + front-end)

Resolve o bug: na overview do Catálogo só dava pra filtrar dataset por
nome; a busca global de tabela era só um link pra `/search`.

- **Backend (B5):** 4º modo de busca `not_exact` ("diferente a") —
  `SearchMode.NOT_EXACT`, branch `table_name != @q` em
  `repository.search_tables` (mesmo fan-out por região), service pula a
  busca secundária de prefixo pra esse modo. Query só-metadado ($0,
  mesma forma de `exact`/`contains`). `catalog.md` + testes (74 catalog,
  785 unit no total).
- **Front-end:** novo `features/catalog/TableSearchPanel.tsx` autocontido
  (state + `useSearchTables` + `SearchMatchesTable`/`SearchAbsentTable`),
  modo via `ChoiceToggle` de 4 opções, dentro de um `<Panel>`.
  `CatalogOverviewPage` monta o painel (+ mantém o filtro inline de
  dataset, agora rotulado "Navegar por dataset"). `SearchPage` vira só
  `PageHeader` + `<TableSearchPanel>`. `types/catalog.ts` SearchMode +1.
  ASM-CAT-01 resolvida; AC-CAT-OV-06 novo em `catalog.md`.

### R2-5 — `feat/r2-admin-usage-blocks` (backend + front-end)

- Novos `components/ComboChart.tsx` (coluna+linha recharts, eixo Y duplo,
  extraído do ComposedChart de BudgetPage) e `components/Funnel.tsx`
  (trapézios `<polygon>` afunilando, rótulo/valor/% por FORA, `role=img`).
- `LoginAnalyticsSection`: `LineChart` → `ComboChart` + `ChoiceToggle` de
  troca de métrica (coluna = Acumulado/Período) + toggle Dia/Mês (buckets
  daily/monthly) + `DateField` De/Até. Vira `<Panel>`.
- `RetentionFunnelSection`: `BarChart` → `<Funnel>`. Vira `<Panel>`.
- `AdminUsageTab`: `flex-col gap-8` de `CollapsibleSection` → blocos —
  combo full-width, funil+heatmap 2-col, tabelas empilhadas.
- **Backend (B7):** `?from=&to=` no `GET /admin/analytics/logins` — `from`
  vira o `since`, `to` filtra o topo (fim do dia UTC). Sem eles,
  `lookback_days` como antes. `admin.md` + teste. pytest 786 ok.
  ACs AC-ADM-RV-01..04 marcados ✅, ASM-ADM-RV-01 resolvida.

### R2-6 — `feat/r2-nav-overview-screens` (só front-end)

- Carve-out do brief "nível 1 abre overview". Novos `components/OptionCard.tsx`
  (`OptionCard` + `OptionCardGrid`) + `.dp6-opt-card`/`.dp6-opt-card-featured`.
- Páginas `GovernanceOverviewPage` (`/governanca`), `QualityOverviewPage`
  (`/quality`), `QualityTablesPage` (`/quality/tables` — select de dataset
  → tabela → `/analyze/:d/:t`). Rotas no `router.tsx`.
- `DatasetSidebar`: `SidebarSection`/`SidebarServiceGroup` ganharam prop
  `to` — nome vira `NavLink` (Governança→/governanca, FinOps→/finops,
  Análises de qualidade→/quality, Catálogo de Dados→/, Cloud Storage→/storage),
  chevron isola o disclosure.
- `docs/specs/nav-overview-screens.md` novo (AC-NAV-OV-01..03).
  `design-system.md` + `ui-ux-rules.md` no mesmo PR.

## Refresh visual do Hub — fundação de tokens (2026-09)

Primeira fatia do refresh visual (brief:
`docs/specs/frontend-visual-refresh.md`; plano fatiado em 13 PRs:
`docs/specs/frontend-visual-refresh-plan.md`). Decisões de design tomadas
sobre um protótipo (`~/polaris-hub-mockup/`) levadas ao app real — dev
primeiro, prod só com aprovação explícita do usuário.

### O que foi feito (PR `feat/fe-refresh-foundation`)

- **Raio "quase quadrado":** `--radius` 8px → **10px** nos dois temas.
  Escala derivada achatada de propósito — `--radius-xl == --radius-lg ==
  --radius` — pra card (`rounded-xl`) e botão/input (`rounded-lg`) caírem
  os dois em 10px. Pill (`--radius-pill`, badge/toggle/avatar) intocado.
- **Tokens novos** (`index.css`): `--primary-2`/`--color-primary-2`
  (`#ffca45`, topo de gradiente), `--glow` (rgba tintado, por tema),
  `--shadow-glow` (classe `shadow-glow`), `--ease-dp6` (`ease-dp6`).
- **Utilitárias plain-CSS:** `.dp6-hoverable` (glow + contorno fino em
  `--primary` + `translateY(-2px)` gated em `no-preference`),
  `.dp6-glass`, `.dp6-headline-glow`, `.dp6-gradient-primary`.
- **Componentes compartilhados:** `MetricTile` ganhou prop `icon` (chip
  acima do rótulo) + `.dp6-hoverable` embutido; `PageHeader` ganhou o
  glow radial contido atrás do `<h1>`; novo `components/ChartTooltip.tsx`
  (+ `useChartTooltip`) — tooltip flutuante de gráfico via portal.
- **Harness atualizado no mesmo PR** (regra do próprio harness):
  `design-system.md` §Raio + §Vida (nova) + §Catálogo; `ui-ux-rules.md`
  §Identidade visual (relaxada) + §Movimento (teto ≤300ms).

### Decisão de arquitetura

- A regra "flat, sem gradiente/sombra" foi **relaxada, não abolida**: só
  o que o protótipo usa em `.panel`/`.kpi`/`.btn.primary`. Os efeitos de
  fundo de tela cheia do protótipo (constelação, aurora, grain,
  scanlines, sweep, parallax) **não** foram adotados — o princípio
  "ferramenta densa, rapidez > espetáculo" continua. Registrado como
  ASM-006/007 no brief.
- Botão primário com gradiente é **opt-in via `className`
  (`.dp6-gradient-primary`)**, não override global de `ui/button` — a
  primitiva shadcn é read-only (regra do design-system).
- `--radius-xl == --radius-lg` quebra a monotonicidade da escala shadcn
  de propósito; documentado em `design-system.md` §Raio.

### Perguntas em aberto resolvidas por decisão (reconfirmar no review)

Q-001 (item ativo da sidebar), Q-002 (onde vive o score por tabela do
FinOps), Q-003 (fonte do mini-gráfico dos cards de dataset) — respondidas
em `frontend-visual-refresh-plan.md` §1, usuário ausente até o review.
Checagem de backend: `description` de dataset **é** mudança de backend
(`DatasetSummary` não tem o campo) — sliced como PR 7.

### Fatias seguintes (uma branch por PR, empilhadas — plano §4/§5)

- **`feat/fe-refresh-rename-catalogo`** (PR 3): "Catálogo" → "Catálogo de
  Dados" na UI + `docs/site`. Sem mudança de comportamento.
- **`feat/fe-refresh-sidebar`** (PR 4): item ativo da sidebar no novo
  tratamento (Q-001 — `.dp6-nav-active`: barra de acento + gradiente, não
  mais bloco amarelo); hover com dica de glow (`.dp6-nav-item`); ícone
  `Boxes` nos datasets; ícone do serviço em `--primary`; mais respiro
  entre grupos (`space-y-4`, `gap-4`). `index.css` +2 utilitárias →
  `design-system.md` §Vida atualizado no mesmo PR.
- **`feat/fe-refresh-tables`** (PR 5): hover de linha de tabela no novo
  tratamento — regra global em `index.css` (`[data-slot=table-body]
  [data-slot=table-row]:hover` → gradiente amarelo + barra lateral `inset
  3px`), substitui o `hover:bg-muted` uniforme do `ui/table`. Zero
  arquivo de feature tocado. `design-system.md` §Vida + `ui-ux-rules.md`
  §Tabelas no mesmo PR.
- **`feat/catalogo-de-dados-overview`** (PR 6): rota `/` deixa de ser um
  `EmptyState` e vira a tela de overview do domínio — `PageHeader` +
  KPIs (com ícone) + grade de `DatasetOverviewCard` (ícone, contagem,
  tamanho, região, `SlaDistributionBar`) + busca por dataset + link pra
  `/search`. Novo `components/SlaDistributionBar.tsx` (barra empilhada
  compartilhada, consome `FreshnessCounts`, sem query nova — Q-003).
  `KpiCards` ganhou `icon`. ACs novos em `catalog.md` (overview +
  `description` como PR 7) e `freshness.md` (componente compartilhado).
- **`feat/catalog-dataset-description`** (PR 7, **mexe no backend**):
  `DatasetSummary.description: str | None`. "Query 2 — Resumo de datasets"
  ganhou `LEFT JOIN INFORMATION_SCHEMA.SCHEMATA_OPTIONS` (`option_name =
  'description'`) + `SAFE.JSON_VALUE` — uma query por região, metadado
  ($0), dentro do cache de 5min. Frontend: `DatasetOverviewCard` mostra
  a descrição real (`line-clamp-2`), fallback pro texto fixo. Sem role
  IAM nova (mesma permissão de metadado já usada pra SCHEMATA/TABLES).
  ACs AC-CAT-DESC-01/02 em `catalog.md`. `pytest tests/unit` 783 ok.
- **`feat/fe-refresh-freshness`** (PR 8): `SlaRow` (totais de projeto e
  de dataset) ganhou a `SlaDistributionBar` agregada abaixo dos números;
  `DatasetFreshnessTable` ganhou coluna "Distribuição" por linha. As
  colunas de contagem por faixa (ordenáveis) continuam — a barra é
  adicional. Fecha a história de "mesmo componente nos dois lados" com
  o Catálogo de Dados. Cosmético (sem AC novo).
- **`feat/fe-refresh-kpi-icons`** (PR 9): ícone no chip de cada KPI
  (`MetricTile.icon`, mapeamento do brief) — `CatalogDatasetPage`
  (Região/Tabelas/Views/Tamanho/Linhas/Freshness), `BudgetPage`,
  `ProfilingDialog`, `LoginAnalyticsSection`, `AccessRequestAnalyticsSection`.
  As mini-stat rows à mão de `PiiTab`/`FinOpsPage` (readout de dry-run,
  não usam `MetricTile`) ficaram fora — converter é refactor à parte.
- **`feat/fe-refresh-primary-cta`** (PR 10): `.dp6-gradient-primary`
  (gradiente + inset ring + glow) nos CTAs herói dos fluxos
  config→executar→resultado: `DatasetScopeGate` (cobre OrphansPage etc.),
  `ProfilingDialog` "Executar profile", `ColumnTypeSuggestionsTab`
  "Escanear", `FinOpsPage` "Executar". Opt-in via `className` — a
  primitiva `ui/button` continua intocada.
- **`docs/fe-refresh-deferred-specs`** (PR 11, docs): ACs de "refresh
  visual — pendente" nas specs de lineage/quality/finops/storage/admin +
  `frontend-visual-refresh-plan.md` §5 (estado real).
- **`fix/catalog-description-safe`** (PR 12): reverte a leitura de
  `description` da PR 7 — ver "Erros cometidos e aprendizados".

### Erros cometidos e aprendizados

- **PR 7 quebrou `GET /projects/{id}/validate` em `dev` ("Failed to
  fetch" ao selecionar um projeto).** O `LEFT JOIN` com
  `region-{region}.INFORMATION_SCHEMA.SCHEMATA_OPTIONS` +
  `SAFE.JSON_VALUE` era SQL que os testes unitários **não exercitam** (o
  `bigquery.Client` é mockado — `client.query().result()` devolve rows
  fixas), então `pytest` passou com a query inválida. Em runtime, o
  `BadRequest` do BigQuery virou um 500 **não tratado** → como o
  `ServerErrorMiddleware` do Starlette fica por fora do `CORSMiddleware`,
  a resposta de erro saiu **sem `Access-Control-Allow-Origin`** → o
  browser reporta `TypeError: Failed to fetch`, não o 500 real. Reverti
  a query (`get_datasets_summary` volta ao original, `description: None`
  fixo). Aprendizados: (1) query BQ nova **exige** teste de integração
  contra um projeto real antes de subir — mock de client não é
  suficiente pra validar SQL; (2) `INFORMATION_SCHEMA.SCHEMATA_OPTIONS`
  region-qualified e `SAFE.JSON_VALUE` precisam ser confirmados num
  dataset real; (3) sintoma "Failed to fetch" (não o erro real) =
  provável 500 sem CORS por exceção não tratada — olhar o handler de
  exceção antes de assumir rede/cold start.

---

## Harness de front-end (`docs/skills/frontend.md` → `docs/frontend/`)

Toda a orientação de front-end vivia num arquivo só, `docs/skills/frontend.md`
(~305 linhas), acumulando quatro responsabilidades: design system,
catálogo de componentes, regras de UI/UX + acessibilidade, e mockups
ASCII de tela.

### Problema

- **Desatualização**: os mockups ASCII (Topbar, Sidebar, modal de
  profiling) e os snippets CSS (`.btn-primary`, `.card`) predatam a
  implementação shadcn e divergiram; o doc citava a escala tipográfica
  antiga (`--text-xs`) já substituída pela semântica.
- **Cobertura incompleta**: 7 componentes compartilhados
  (`CacheStalenessBadge`, `CollapsibleSection`, `DatasetScopeGate`,
  `PaginationBar`, `RefreshButton`, `SqlPreview`, `ThemeToggle`) fora do
  catálogo.
- **Sem camada de patterns nem de behaviors**: composições recorrentes
  (tabela filtrável, fluxo de análise, gate de escopo) e padrões de
  loading/erro/vazio não documentados.
- **Racional de design difuso**: as decisões da auditoria de
  acessibilidade viviam só neste CHANGELOG e na memória.
- **CLAUDE.md**: front-end referenciado em duas seções com sobreposição;
  árvore de pastas sem listar `docs/skills/`, `docs/specs/`,
  `docs/design-references/`.

### O que foi feito

- **`docs/frontend/`** — harness com 8 arquivos, um por responsabilidade:
  `README.md` (índice + roteiro "tarefa → o que ler"), `design-system.md`
  (espelho de `apps/frontend/src/index.css` + catálogo completo dos ~18
  componentes de `src/components/` + regra dos primitivos shadcn),
  `ui-ux-rules.md` (regras normativas + porquê), `accessibility.md`
  (WCAG 2.1 AA acionável + como verificar), `patterns.md` (8 composições
  recorrentes com arquivo canônico), `behaviors.md` (data fetching,
  estados, feedback, formatação, tema, localStorage), `references.md`
  (telas canônicas internas + `docs/design-references/`), `CHECKLIST.md`
  (entrega, fonte única).
- **`docs/skills/frontend.md`** virou tombstone com tabela de "seção →
  para onde foi". Removido após uma release.
- **CLAUDE.md**: árvore de pastas atualizada; "Convenções — Frontend"
  ganhou ponteiro pro harness + ressalva de que Vitest/RTL é planejado
  (não há setup nem `vitest` no `package.json`); "Contexto: Frontend"
  troca "ler a skill" por "ler `docs/frontend/README.md`", checklist vira
  ponteiro pra `docs/frontend/CHECKLIST.md`.
- Comentários de código com o caminho antigo atualizados
  (`apps/frontend/src/index.css` ×4, `hooks/useTheme.ts`,
  `features/quality/QualityFolderComparisonPage.tsx`).
- `docs/design-references/README.md` ganhou back-link pro harness.

### Decisão de arquitetura

O **código é a fonte de verdade dos valores** (tokens em `index.css`,
componentes em `src/components/`); o harness é a fonte de verdade das
**decisões e do porquê**. `design-system.md` e `index.css` mudam **no
mesmo PR** — a regra de sincronização está no topo do arquivo. Os três
eixos (design system, regras, referências) ficam em arquivos separados
porque têm dono e taxa de mudança diferentes. Nada de token/componente
real foi alterado — o harness documenta o estado atual.

---

## Listas de projeto seguem só o registro do ADM (`hub_projects`)

Bug reportado pelo usuário: `bigquery-public-data` aparecia na tela
Admin → Caches ("Freshness por projeto") e `dp6-ci-polaris` no seletor de
projeto, mesmo sem estarem cadastrados em Admin → Projetos.

### Causa

Três listas de projeto ignoravam o registro `hub_projects`:

- **Job diário** e **`/api/v1/admin/event-cache/status`**: varriam
  `hub_projects` ∪ `event_cache.list_seen_projects()`. A coleção
  `event_cache_seen_projects` era gravada por `record_project_seen()` em
  **qualquer cache miss do request path** — inclusive para projetos só
  *referenciados* na travessia de lineage (`bigquery-public-data.samples…`).
- **`/api/v1/projects`** (seletor): enumerava **todo projeto que a SA de
  runtime alcança** via Cloud Resource Manager (`roles/browser`), com um
  flag `has_access`. O projeto host `dp6-ci-polaris` entrava sempre.

### O que foi feito

- **`hub_projects` é a única fonte.** `_known_projects` (job) e
  `_known_cache_projects` (admin service) retornam só
  `admin_repository.list_projects`. `list_accessible_projects` (catalog)
  passou a listar `hub_projects` ∩ acesso do usuário — sem mais flag
  `has_access` no schema `AccessibleProject`.
- **`record_project_seen` / `list_seen_projects` / a coleção
  `event_cache_seen_projects` removidas** (4 call sites em
  lineage/access/storage/finops). O fluxo de cache miss
  (`EventCacheNotReadyError` → degradar pra vazio com `warning`) não muda.
- **`core/resourcemanager.py` removido** (ficou sem uso);
  `google-cloud-resource-manager` saiu do `pyproject.toml`. `roles/browser`
  da SA de runtime deixou de ser necessária (anotado em
  `docs/onboarding-cliente.md`; revogação IaC fica pra um PR de infra).
- **`scripts/cleanup_unregistered_project_cache.py`** (dry-run por
  padrão): esvazia `event_cache_seen_projects` e apaga metadados órfãos
  de `event_cache_metadata`. Não toca `event_cache_runs` nem os blobs.
- **Frontend**: `ProjectSelector` perdeu o badge "Sem acesso" (todo item
  do dropdown agora é acessível); campo de texto livre continua validando
  qualquer ID.

### Decisão de arquitetura

Wildcard `allowed_projects=["*"]` controla **acesso**, não mais quais
projetos o Hub opera. Um projeto acessível só por wildcard precisa ser
cadastrado em Admin → Projetos pra entrar no ciclo do cache e nos
seletores. Invalida **ASM-003** de `docs/specs/lineage.md` (confirmado
com o usuário 2026-08-31).

---

## Cache de audit log incremental (delta diário por `receiveTimestamp`)

Continuação do trabalho de 429/custo do Cloud Logging. Depois de cache +
retry + tela de acompanhamento, o modelo ainda era **full scan diário**
da janela inteira (30d job / 90d storage), reescrevendo o blob. Num
projeto de volume alto (`observability-hub-dev` ≈ 50 mil eventos/30d) o
full scan diário ainda podia estourar a cota `read_requests` (o usuário
subiu o limite de 60 → 200/min), e o cache de `access` chegou a **nunca
popular** — o run abortava no 429 antes de gravá-lo.

### O que foi feito

- **Modelo incremental no Job** (`jobs/refresh_event_cache.py`). Cada run
  lê só o delta — `receiveTimestamp > min(last_scan_receive_ts dos kinds)`
  (não uma janela fixa de N dias, pra capturar logs ingeridos com
  atraso) — faz `event_cache.merge_dedup` com o blob (dedup por `job_id`,
  o evento novo vence) e evicta os eventos fora da janela rolante: **31
  dias** pros domínios de job (`timestamp < hoje−31d`), **90 dias** pra
  storage. Derruba a leitura diária de ~15 páginas/projeto pra ~1. O
  **full scan** só roda na 1ª execução do projeto, sem `last_scan_receive_ts`
  no metadado, blob sumido (lifecycle do bucket), ou toggle "forçar
  completo".
- **`set_cache_metadata` cresceu**: `window_start`, `last_scan_receive_ts`
  (o anchor do próximo delta), `last_full_scan_at`, `mode`
  (`full`/`incremental`). `first_cached_at`/`last_full_scan_at`
  preservados entre runs.
- **`JobEvent` ganhou `timestamp`** (`endTime or startTime or createTime`)
  — necessário só pra a evicção de janela. `access`/`finops` já tinham;
  os 3 `_parse_entry` passaram a usar o mesmo fallback de 3 campos.
- **Request path parou de escanear ao vivo.** `get_job_events_cached`
  (lookback default), `get_access_events_cached`, `get_scan_events_cached`,
  `get_read_object_keys_cached`: cache miss → `record_project_seen` +
  `EventCacheNotReadyError` (nova exceção). `list_access_events` e
  `list_scan_events` **removidas**; `list_job_events` fica (só
  `/orphans?lookback_days=<custom>`); `list_read_object_keys` virou
  `scan_read_object_events`. Serviços de lineage/access/finops/storage
  capturam `EventCacheNotReadyError` **junto** de `LoggingQuotaExceededError`
  e degradam pra resposta vazia com `warning` "cache ainda não gerado".
  `main.py` mapeia pra 503 só como rede de segurança.
- **Cache de storage virou `dict[(bucket, objeto) → ISO da última
  leitura]`** (era `set` sem data — não dava pra evictar por idade).
  `_deserialize_read_object_keys` devolve `None` pro formato antigo →
  força full scan. O consumidor devolve `set(cache.keys())`.
- **Toggle "forçar completo"** no gatilho de admin:
  `POST /api/v1/admin/event-cache/refresh?force_full=true` →
  `run_v2.RunJobRequest.Overrides` injeta
  `OBSERVABILITY_HUB_CACHE_FORCE_FULL=1` só naquela execução;
  `core/config.py::settings.cache_force_full` (nunca lê `os.environ` fora
  de config).
- **Freshness da aba Caches** ganhou `never_run` ("nunca rodou" vs. uma
  janela), `window_start`, `last_full_scan_at`, `mode`. Retenção de
  execuções subiu 20 → 200.

### Erros cometidos e aprendizados

- `_JOB_KIND_SPECS` guardava **referências de função** capturadas no
  import — o `monkeypatch` dos testes não pegava (o job usava a função
  antiga). Corrigido guardando o módulo + o **nome** e resolvendo via
  `getattr` no uso. Aprendizado: tabela de despacho num módulo
  orquestrador que os testes precisam mockar tem que resolver os
  callables tarde, não no load.
- Stub de parser nos testes do job devolvia as entradas cruas (strings)
  como "eventos" — quebrava no windowing novo (`e.timestamp`). O full
  scan antigo não tocava os eventos, o incremental sim. Stubs de parser
  agora devolvem objetos com `.job_id`/`.timestamp`.

---

## Tela de acompanhamento do cache de audit log (Administração → Caches)

Pedido do usuário: não bastava o botão "Atualizar caches", precisava de
uma tela com feedback granular — qual projeto já foi processado, com que
status, quando cada cache foi gerado.

### O que foi feito

- **Job grava o progresso no Firestore.** `jobs/refresh_event_cache.main()`
  cria um doc em `event_cache_runs` (`start_cache_run`), atualiza
  `projects.{project_id}` conforme cada projeto termina
  (`record_cache_run_project` — status `ok`/`access_denied`/
  `quota_exceeded`/`api_error`/`unexpected_error` + contagens de eventos),
  e marca `done` no fim (`finish_cache_run`, em `try/finally`).
  `_refresh_project` passou a **retornar** `(status, counts)` em vez de só
  logar. Mantém só as ~20 execuções mais recentes (`_prune_cache_runs`).
- **Endpoint** `GET /api/v1/admin/event-cache/status` (`domains/admin/service.py::get_event_cache_status`):
  últimas 5 execuções + freshness por projeto × domínio (lineage / access /
  finops_scan_events / storage_read_keys), tudo do Firestore — **sem
  tocar Cloud Logging nem o Cloud Run Admin API** (não precisa de
  `roles/run.viewer` na SA de runtime). Polling barato.
- **Tela** `AdminCachesTab` (nova aba "Caches" em Administração): cards de
  execução (badge de status, duração, `N ok · M cota estourada · …`,
  lista dos projetos com problema) + tabela de freshness por projeto
  (relativo + contagem, colorido verde/amarelo/vermelho por idade). O
  botão de disparo saiu do header do AdminPage pra dentro desta aba;
  `refetchInterval` cai pra 8s enquanto há execução `running` pra ver os
  projetos "acenderem" um a um.
- Nova coleção Firestore `event_cache_runs` registrada em
  `docs/gcp-components.md` (mesmo named database, sem recurso GCP novo).

---

## Um scan de audit log no job de refresh + 429 degrada pra warning (não 503) em access/lineage/finops

Continuação do fix do 429 do Cloud Logging. Depois de cache + retry + 503,
a tela de **Acesso** ainda dava erro em dev: 503 em vez de "Failed to
fetch", mas ainda quebrada. Causa: o cache de `access` do projeto estava
frio e o request path não conseguia populá-lo (scan ao vivo × cota
saturada).

### Diagnóstico

`observability-hub-dev` como projeto alvo tem volume ALTO de
`jobservice.jobcompleted` (são as próprias queries do Hub — profiling,
PII, catálogo). O job diário `_refresh_project` fazia **3 scans idênticos
de 30 dias** desse filtro (lineage, access, finops), triplicando o
consumo da cota `read_requests`. Num projeto de volume alto isso estoura
os 60/min no meio do primeiro projeto, o `_refresh_project` aborta, e
**nenhum** dos 4 caches é gravado — então "Atualizar caches" também não
resolvia.

### O que foi feito

- **Job faz UM scan, alimenta 3 parsers.**
  `core/logging_client.py::bigquery_job_events_filter(lookback_days)`
  centraliza o filtro compartilhado; cada repo ganhou um `parse_*`
  público (`parse_job_events`/`parse_access_events`/`parse_scan_events`)
  separado do `list_*` (que continua pro request-path fallback). O job
  chama `list_entries_with_retry` uma vez e passa os `LogEntry` crus pros
  3 parsers → ~3× menos leitura de cota no refresh.
- **429 persistente degrada pra warning, não 503**, em access, lineage
  (grafo + órfãs) e finops (partition-candidates + budget) — mesmo
  tratamento que `storage` já dava pro waste scanner 6.2. A tela abre
  vazia com um aviso ("limite de leitura de audit logs... um admin pode
  forçar 'Atualizar caches'") em vez de um erro. Durante a expansão do
  grafo de lineage, um projeto não-raiz com 429 vira soft-fail (não
  expande a partir dele, o resto do grafo continua) — igual ao
  tratamento de `LoggingAccessDeniedError` que já existia lá.
- `LoggingQuotaExceededError` → HTTP 503 (`main.py`) continua como rede
  de segurança pra qualquer caminho que não capture a exceção.
- `tests/unit/jobs/test_refresh_event_cache.py` reescrito pro modelo de
  scan único; testes de degradação nos 3 serviços.

### Erros cometidos e aprendizados

- A ideia de "3 scans idênticos, tradeoff aceito (1×/dia, fora do
  request path)" — registrada no CHANGELOG do fix do cache de finops —
  não sobreviveu ao primeiro projeto de volume real. O tradeoff só valia
  enquanto o volume era baixo; virou a causa direta de o cache nunca
  popular. Unificado agora.

---

## Retry com backoff no scan de audit log (core/logging_client.py::list_entries_with_retry)

Terceira e última parte da frente do 429 do Cloud Logging (depois do
cache de finops e do mapeamento 429 → 503 nos 4 domínios). Os fixes
anteriores tornavam o 429 um 503 limpo; este faz a **maioria** dos 429
nem chegar lá.

### O que foi feito

- Novo `core/logging_client.py::list_entries_with_retry(client, *,
  resource_names, filter_, page_size, project_id)` — materializa a
  paginação de `client.list_entries` numa lista com
  `google.api_core.retry.Retry` (backoff exponencial, `initial=1s`,
  `max=10s`, `timeout=30s`) em `TooManyRequests`/`ResourceExhausted`
  (429) e `ServiceUnavailable` (503). Mapeia `Forbidden` →
  `LoggingAccessDeniedError` e 429 persistente (após o deadline) →
  `LoggingQuotaExceededError`.
- Os 4 call sites (`finops.list_scan_events`, `lineage.list_job_events`,
  `access.list_access_events`, `storage.list_read_object_keys`) passaram
  a usar o helper — some o `try/except Forbidden` copiado em cada um e o
  `except TooManyRequests` naked que os fixes anteriores tinham colocado
  nos `get_*_cached`.
- `jobs/refresh_event_cache.py`: `_refresh_project` e
  `_refresh_storage_read_keys` ganharam `except LoggingQuotaExceededError`
  (agora que `list_*` pode levantá-la em vez de um `GoogleAPICallError`
  cru) — status `quota_exceeded` no log, não derruba os demais projetos.
- `tests/conftest.py`: fixture autouse `_fast_logging_retry` zera
  `_RETRY_TIMEOUT_SECONDS` — nenhum teste unitário exercita backoff real
  (sem isso o suite ia de 3s pra ~110s). `tests/unit/core/test_logging_client.py`
  novo cobre a mecânica do retry com deadline/sleep próprios.

### Descoberta técnica (registrada no fix anterior, confirmada aqui)

O transporte REST do client (`_use_grpc=False`, obrigatório — ver
docstring do módulo) **não aceita `retry=` nativo** e o 429 estoura no
meio da paginação (`_get_next_page_response`). Por isso o retry envolve o
scan inteiro: um 429 na página 8 re-executa da página 1. Aceitável — é
raro, tem backoff, e fora do request path (o job diário) o custo não
importa. `ResourceExhausted` é subclasse de `TooManyRequests` no
`google-api-core` instalado (2.34), então um predicado só cobre as duas
formas do 429.

### Erros cometidos e aprendizados

- Primeira rodada de testes rodou o backoff de verdade (deadline de 30s ×
  ~4 testes de cota) e o suite foi de 3s pra 110s. Corrigido com a
  fixture autouse no conftest zerando o deadline — a lição é que
  qualquer retry com sleep real precisa de um kill-switch de teste
  global, não patch caso a caso.

---

## FinOps passa a ler audit log via cache pré-computado (fix do 429 → "Failed to fetch")

Usuário reportou `google.api_core.exceptions.TooManyRequests: 429` nos
logs (`logging.googleapis.com/read_requests`, cota
`ReadRequestsPerMinutePerProject` = 60/min, default), correlacionado com
"Failed to fetch" recorrentes no app. Stack apontava
`finops/repository.py::list_scan_events` via
`GET /api/v1/finops/{project}/partition-candidates`.

### Diagnóstico

`finops` foi o único domínio que leu Cloud Logging que **não** tinha sido
migrado pro cache diário quando `lineage`/`access` (e depois `storage`,
commit `bb54830`) foram. `scan_partition_candidates` e `get_budget`
chamavam `list_scan_events` **direto no request path** — scan síncrono de
30 dias de `jobservice.jobcompleted` a cada request. Com `page_size=1000`,
cada scan vira N chamadas paginadas de `entries.list`; um projeto ativo
+ o refetch do TanStack Query estoura 60/min num uso normal de tela (12
ocorrências em 7 dias). O `429` não era capturado (só `Forbidden` era) →
500 não tratado → "Failed to fetch". Cota é global por projeto e dev+prod
compartilham o balde (topologia single-project), o que amplifica.

### O que foi feito (fix 1 de 2 — este é o cache; o retro com backoff vem depois)

- `domains/finops/repository.py` ganhou o mesmo quarteto de
  `domains/access`: `serialize/deserialize_scan_events`,
  `read/write_scan_events_cache`, `get_scan_events_cached`, sobre o
  `core/event_cache.py` compartilhado (GCS + Firestore), namespace
  `_CACHE_KIND = "finops_scan_events"`. **Nenhum recurso Terraform novo** —
  reaproveita bucket/Firestore/Job já existentes.
- `jobs/refresh_event_cache.py` (o mesmo Job diário D-1) agora também
  varre `list_scan_events` pra cada projeto conhecido, no `try` principal
  (não isolado como storage): finops lê a mesma fonte que lineage
  (`jobservice.jobcompleted`), então se `list_job_events` passou, este
  passa. `ScanEvent` carrega `timestamp` por evento, então **um cache de
  30 dias serve os dois consumidores** — `partition-candidates` (janela
  fixa) e `budget` (recorte month-to-date por filtro no service).
- `domains/finops/service.py` / `api/v1/finops.py`: os 2 endpoints
  passaram a receber `storage_client` + `firestore_client` via `Depends`
  e ler `get_scan_events_cached` em vez de escanear ao vivo.
- `PartitionCandidatesResponse` / `BudgetResponse` ganharam
  `cache_updated_at: datetime | None` (mesmo campo que `LineageGraphResponse`
  já expõe; aditivo/opcional).
- **Stopgap de 429 introduzido junto** (o fix 2 generaliza com retry): nova
  `core/exceptions.py::LoggingQuotaExceededError` + handler em `main.py`
  → HTTP **503 + `Retry-After: 60`**. Aplicado no fallback ao vivo dos
  **quatro** domínios que leem Cloud Logging, não só finops — durante a
  validação em dev, `Acesso` deu "Failed to fetch" pelo mesmo motivo
  (cache frio + cota saturada + `TooManyRequests` não capturado, só
  `Forbidden` era). `get_scan_events_cached`/`get_access_events_cached`/
  `get_job_events_cached` mapeiam `TooManyRequests` → 503;
  `get_read_object_keys_cached` também, mas `storage/service.py` degrada
  pra warning "config_based" (checagem 6.2 é best-effort, não deve
  derrubar `waste-candidates` inteiro).
- `docs/specs/finops-waste-scanner.md` bump v1.3 (mecanismo + AC-001 a
  AC-008 + Suposições), `finops-budget.md` bump v1.3 (cross-ref);
  `lineage.md`/`access.md`/`storage.md` ganharam a linha de "429 → 503"
  em Casos de borda.

### Não fez parte desta mudança (fica pro fix 2)

`core/logging_client.py::list_entries_with_retry` — retry com backoff
(`google.api_core.retry.Retry` envolvendo a paginação inteira, já que o
transporte REST `_use_grpc=False` não aceita `retry=` nativo) aplicado
aos 4 call sites de `list_entries` (finops, lineage, access, storage),
substituindo o `except TooManyRequests` naked do finops. Ordem invertida
a pedido do usuário: fix 1 (cache) mata o bug visível já; fix 2 (retry)
suaviza o 429 residual de cache miss / do Job.

### Erros cometidos e aprendizados

- Nenhuma quebra nova nesta mudança. Aprendizado do diagnóstico: a cota
  `read_requests` conta **páginas** de `entries.list`, não "scans" — o
  `page_size=1000` que parecia otimização de latência era multiplicador
  de consumo de cota. O cache elimina isso do request path; o retry do
  fix 2 cobre o resíduo.

---

## Cache TTL em 3 endpoints sem cache de Catalog/Freshness

Continuação da mesma investigação de custo de Cloud Run (ver item
seguinte). Achados #2 a #4, mais leves que o de storage (loop
sequencial por região sem paralelizar / drill-down sem TTL nenhum, não
scan de Cloud Logging) — resolvidos com o mesmo padrão de TTL de 5min
já usado por `get_partition_stats`/`get_table_cached`, sem job nem
cache compartilhado novo.

### O que foi feito
- `domains/catalog/repository.py::get_datasets_summary` — loop
  sequencial por região virou `ThreadPoolExecutor` (mesma técnica de
  `search_tables`) + cache TTL 5min por `(project_id, regions)`.
  Chamada por 3 endpoints (`validate_project`, `list_datasets`,
  `search(mode=not_contains)`), inclusive a tela de entrada do produto.
- `domains/freshness/repository.py::get_freshness_summary_by_dataset` —
  mesmo tratamento (paralelização + TTL 5min).
- `domains/catalog/repository.py::get_table_partitions` — não tinha
  cache nenhum (diferente da função irmã `get_partition_stats`, já
  cacheada); ganhou o mesmo TTL 5min por `(table_ref, partition_field)`.
- `docs/specs/catalog.md` bump pra v1.7, `docs/specs/freshness.md` pra
  v1.3, documentando os TTLs novos.

---

## Waste scanner do Storage passa a usar o cache pré-computado de audit log

Usuário investigou custo de Cloud Run com o Claude Code (cobrança de
CPU-segundos por request) e pediu pra levantar quais domínios ainda
faziam trabalho síncrono caro dentro do request-response cycle,
seguindo o mesmo racional que já resolveu esse problema em
lineage/access (ver "Cache pré-computado de audit log" acima).
Achado mais grave: `GET /api/v1/storage/{project}/waste-candidates`
(checagem 6.2, "objeto sem leitura recente") chamava
`list_read_object_keys` **direto no request path** — scan síncrono de
90 dias de audit log do GCS a cada chamada, estruturalmente idêntico ao
bug que lineage/access já tinham.

### O que foi feito
- `domains/storage/repository.py` ganhou o mesmo trio já usado por
  `domains/access`: `write_read_object_keys_cache`/
  `read_read_object_keys_cache`/`get_read_object_keys_cached`, sobre o
  mesmo `core/event_cache.py` compartilhado (GCS + Firestore) — nenhum
  recurso Terraform novo, reaproveita bucket/Firestore já existentes.
- `jobs/refresh_event_cache.py` (o mesmo Job diário D-1) agora também
  varre `list_read_object_keys` pra cada projeto conhecido, numa função
  isolada (`_refresh_storage_read_keys`) com seu próprio try/except —
  Data Access audit logs do GCS podem não estar habilitados no projeto
  (ainda o caso em prod), e isso não pode derrubar o refresh de
  lineage/access do mesmo projeto.
- `domains/storage/service.py`/`api/v1/storage.py`: endpoint passou a
  receber `firestore_client` via `Depends` e ler do cache em vez de
  escanear ao vivo.
- `docs/specs/storage.md` bump pra v1.3 (seção 6.2 documenta o
  mecanismo, seção 11 nova com Critérios de aceite AC-009 a AC-015).

### Não fez parte desta mudança
Outros 3 endpoints sem cache identificados na mesma investigação
(`catalog.get_datasets_summary`, `freshness.get_freshness_summary_by_dataset`,
`catalog.get_table_partitions`) — mais leves (loop sequencial por
região sem paralelizar / falta de TTL curto, não scan de Cloud Logging)
e resolvidos um de cada vez em sessões seguintes, não com o padrão
pesado de Job+cache.

---

## Cloud Run com CPU sempre alocada de novo — recorrência do diagnóstico anterior, agora fixado no Terraform

Usuário reportou custo de Cloud Run de ~R$5/dia com uso quase só de
teste — muito acima do esperado pra volume de tráfego tão baixo.

### Diagnóstico
Billing Report (agrupado por SKU) mostrou o SKU **"Services CPU
(Instance-based billing) in us-central1"** dominando o mês (R$17,75 de
R$20,38 total), com **169.551 segundos de CPU** (~47h) — muito mais do
que cliques manuais explicariam. "Instance-based billing" é o nome do
SKU quando `cpu_idle=false` ("CPU sempre alocada", cobra o tempo de
vida inteiro da instância, não só o processamento de requisição) — a
alternativa normal pra uma API HTTP é `cpu_idle=true` ("CPU só durante
requisição"). `terraform plan` contra o state real confirmou:
`cpu_idle: false -> true` nos 4 serviços (backend/frontend × dev/prod).

Isso é uma **recorrência** de um diagnóstico já feito antes (ver seção
"CI/CD: gate de aprovação manual antes de deploy de app em prod", achado
de custo do Cloud Run) — na época, a mesma configuração foi encontrada
ligada, revertida **manualmente via `gcloud`** (nunca chegou a ir pro
Terraform, que não declarava `resources.cpu_idle` de jeito nenhum) e
sem registro de como foi religada. Sem estar no IaC, o fix anterior não
era durável — por isso recorreu.

### O que foi feito
`infra/terraform/modules/cloud-run/main.tf`: `resources.cpu_idle = true`
declarado explicitamente (nunca existia no módulo antes). Efeito: agora
todo `terraform apply` (automático em dev a cada push, automático em
prod a cada merge em `main`) reafirma esse valor — uma mudança manual
fora do fluxo do projeto não sobrevive ao próximo apply. Confirmado via
`terraform plan` real (dev e prod): `Plan: 0 to add, 3 to change, 0 to
destroy` nos dois — só update in-place, sem destroy/replace.

### Avaliação de risco (antes de aplicar)
- Nenhum dos 4 serviços usa `BackgroundTasks`/thread solta/streaming
  (confirmado por grep) — nada depende de CPU disponível depois da
  resposta HTTP ser enviada, então `cpu_idle=true` é seguro pro
  comportamento atual.
- Cloud Run Job (`backend-{env}-refresh-cache`) não é afetado — Jobs
  não têm conceito de "idle", sempre rodam com CPU cheia até terminar.
- `terraform-apply-prod.yml` roda automático no merge (sem gate manual,
  decisão já registrada) — a mudança em prod acontece assim que este PR
  for mergeado em `main`, sem aprovação extra.
- Causa raiz de como isso foi ligado da primeira (e agora segunda) vez
  continua desconhecida — declarar no Terraform corrige a recorrência
  via IaC, mas não identifica quem/o que ligou manualmente.

### Erros cometidos e aprendizados
- O fix anterior (seção "CI/CD: gate de aprovação manual...", mais
  abaixo neste arquivo) só corrigiu o sintoma ao vivo (`gcloud run
  services update` manual), sem trazer a configuração pro Terraform —
  por isso não durou. Aprendizado
  aplicável a qualquer diagnóstico de config incorreta encontrada ao
  vivo num recurso gerenciado por Terraform: o fix "de verdade" é
  sempre no código (IaC), nunca só no recurso — senão o próximo apply
  (ou uma mudança manual futura) desfaz silenciosamente.

---

## Apagar projeto, checklist de onboarding e solicitação de inclusão de projeto

Três ajustes pedidos no admin/seletor de projeto: (1) quando o usuário
digita manualmente um `project_id` que falha na validação por falta de
onboarding (não só falta de ACL, que já tinha CTA), agora dá pra pedir
que o projeto seja incluído no Hub; (2) `Admin → Por projeto` ganhou um
botão de apagar (só tinha registrar); (3) um checklist best-effort
confirma BigQuery/Logging/Storage antes de registrar um projeto ou
aprovar um pedido de inclusão.

### O que foi feito
- **Apagar projeto**: `DELETE /api/v1/admin/projects/{project_id}`
  (`domains/admin/repository.py::delete_project`, mirror de
  `delete_group`) — remove só o doc `hub_projects`, sem cascade pra
  grants explícitos de usuários/grupos. Botão novo em `AdminProjectsTab.tsx`,
  sem confirmação modal (mesmo padrão do botão de revogar acesso já
  existente).
- **Checklist de onboarding (best-effort)**: novo
  `domains/admin/checklist_service.py` — 4 itens (`bigquery` reaproveita
  `discover_regions`, já usado por `validate_project`; `logging`/`storage`
  ganham probes novos e pequenos; `audit_logs` é sempre `not_checked`,
  não dá pra verificar sem uma role nova que não faz parte do onboarding
  hoje). `GET /api/v1/admin/projects/{project_id}/checklist` + componente
  `ProjectChecklistPanel.tsx` reaproveitado em dois lugares: no fluxo de
  registrar projeto e nas linhas de pedido de inclusão em "Solicitações".
- **Solicitação de inclusão de projeto**: `access_requests` ganhou
  `request_type: "access" | "inclusion"` (default `"access"`, cobre docs
  antigos). Aprovar um pedido `"inclusion"` chama `upsert_project` antes
  de `grant_project_to_user` — registra o projeto e libera o solicitante
  num clique só, assumindo que o admin já fez o onboarding real no GCP.
  `ProjectSelector.tsx`: `access_denied`/`project_not_found` ganham a
  mesma CTA "Solicitar inclusão no Hub" (usuário comum não distingue os
  dois casos — admin investiga qual é qual ao revisar).
- `docs/specs/admin.md` bump pra v1.9, primeira vez com seções Critérios
  de aceite/Suposições/Perguntas em aberto.

### Decisões tomadas com o usuário (perguntadas antes de implementar)
- `access_denied` e `project_not_found` compartilham a mesma CTA de
  inclusão, em vez de diferenciar (usuário não consegue distinguir os
  dois na prática).
- Aprovar uma inclusão registra + libera tudo junto, não em dois passos
  manuais separados.
- Checklist é best-effort (probing real, sem exigir role nova de
  `resourcemanager.projects.getIamPolicy`) em vez de introspecção exata
  de IAM policy — troca precisão por não exigir mudança de escopo em
  todo cliente já onboardado.

---

## Cache pré-computado de audit log — resolve "Failed to fetch" em Lineage/Acesso/Órfãs

Usuário relatou "failed to fetch" recorrente nas telas de Lineage, Mapa
de Acesso e Tabelas sem consumidor. Diagnóstico: `list_job_events`/
`list_access_events` escaneavam todo o audit log do Cloud Logging (até
30 dias, sem limite de resultados) **a cada requisição**, sem cache —
em projetos com volume real, isso estourava o timeout do Cloud Run
(300s, sem override até agora) ou a memória do container, e o Cloud Run
derruba a conexão TCP nesses casos em vez de devolver um erro HTTP
normal, o que o browser reporta como `TypeError: Failed to fetch` sem
nenhuma informação útil. Usuário pediu pra combinar 4 propostas
discutidas (cache entre requisições, pré-computação via job periódico,
timeout maior, mais memória) num plano único.

### O que foi feito
- **Cache compartilhado (GCS + Firestore)**: novo `core/event_cache.py`
  — payload de eventos serializado vai pro GCS (Firestore tem limite de
  1MiB/doc, facilmente ultrapassado em 30 dias de audit log de um
  projeto com uso real), metadado pequeno (`cached_at`) vai pro
  Firestore. `domains/lineage/repository.py` e `domains/access/repository.py`
  ganham `get_job_events_cached`/`get_access_events_cached` — tentam o
  cache primeiro, caem no scan ao vivo em cache miss e gravam o
  resultado (auto-cura).
- **Job diário (D-1, 03:00 UTC)**: novo pacote `jobs/refresh_event_cache.py`,
  rodando como Cloud Run Job (`infra/terraform/modules/cloud-run-job`,
  novo módulo) disparado por Cloud Scheduler — varre a união de
  `hub_projects` (registro admin) com projetos "vistos" via cache miss
  no request path (cobre acesso só-wildcard, que nunca ganha doc em
  `hub_projects`). Roda com a **mesma SA de runtime** do Cloud Run
  Service correspondente (nunca uma nova), pra não reabrir onboarding
  manual de IAM cross-project de nenhum cliente já liberado.
- **Gatilho manual de admin**: `POST /api/v1/admin/event-cache/refresh`
  + botão "Atualizar cache agora" em Admin → Por projeto — dispara a
  mesma execução completa do Job sob demanda via Cloud Run Admin API
  (`core/run_client.py`). Cloud Run Jobs sempre exigem
  `roles/run.invoker` (diferente do Service), então a SA de runtime do
  backend só precisou desse IAM binding — sem segredo/token customizado.
- **Timeout e memória do Cloud Run Service**: novo `timeout_seconds` no
  módulo `cloud-run` (default 300, preserva os demais serviços);
  `backend-{dev,prod}` sobem pra 600s/1Gi como rede de segurança do
  fallback síncrono em cache miss.
- Frontend: `cache_updated_at` nas 3 responses + badge "Cache atualizado
  há Xh" (`CacheStalenessBadge.tsx`) em Lineage, Órfãs e Mapa de Acesso.
- `docs/specs/lineage.md` bump pra v2.3 (primeira vez com seções
  Critérios de aceite/Suposições/Perguntas em aberto); `docs/specs/access.md`
  pra v1.1, referenciando o mecanismo compartilhado em vez de duplicá-lo.
- Bootstrap (`infra/terraform/bootstrap/modules/wif-bootstrap`) ganhou
  `cloudscheduler.googleapis.com` em `required_apis` e
  `roles/storage.admin`/`roles/cloudscheduler.admin` nas roles do
  deployer — **exige um `terraform apply` manual em
  `infra/terraform/bootstrap` antes do próximo apply de
  `environments/{dev,prod}`**, já que essas roles/APIs não existiam
  antes desta mudança.

### Mudanças de arquitetura
- Decisão explícita (revisitada com o usuário durante a sessão):
  descartada a alternativa de um Cloud Logging Sink no projeto-alvo
  exportando pra BigQuery — violaria "o Hub nunca instala nada no
  projeto alvo" (ADR-006) e trocaria a fonte de dados "custo $0"
  documentada por queries BigQuery faturáveis. O cache faz o trabalho
  inteiro dentro do projeto do próprio Hub, sem tocar em nenhum
  projeto-alvo.
- Cadência do job mudou de "a cada 15 min" (proposta inicial) para 1x/dia
  D-1 — decisão do usuário, priorizando custo de execução sobre
  frescor do dado; compensado pelo gatilho manual de admin pra quando
  alguém precisar de um refresh imediato.

### Erros cometidos e aprendizados
- Primeira execução manual do Job em dev **derrubou o processo inteiro**
  (`Container called exit(1)`) na primeira entrada de `hub_projects`/
  "vistos" apontando pra um projeto inexistente (`inter-mta`, cliente
  descontinuado) — `list_job_events` levantou `google.api_core.exceptions.NotFound`
  (404), não `LoggingAccessDeniedError` (403), e `_refresh_project` só
  tratava o segundo caso. Cloud Logging devolve 404 (não 403) quando a
  SA do Hub não tem **nenhum** binding de IAM no projeto — caso
  diferente de "tem algum acesso mas falta a role certa" (que já era
  coberto). Corrigido capturando também `GoogleAPICallError` (cobre
  `NotFound` e qualquer outro erro de API do Google) e, como rede de
  segurança final, `Exception` genérica — nenhuma entrada obsoleta em
  `hub_projects`/"vistos" pode voltar a derrubar o refresh dos demais
  projetos. Adicionado teste de regressão rodando `main()` de ponta a
  ponta com um projeto inexistente no meio da lista
  (`test_main_processes_all_projects_even_when_one_does_not_exist`).
- Segundo bug real, mais sério: usuário testou Lineage logo depois do
  deploy e levou o **mesmo "Failed to fetch"** que esta mudança inteira
  existe pra resolver — dessa vez em segundos, não minutos, e pra
  qualquer projeto (inclusive `observability-hub-dev`, já consultado
  com sucesso antes). Causa: `google_storage_bucket.event_cache` foi
  criado, mas **nenhum IAM binding concedeu acesso a ele pra SA de
  runtime do backend** — toda leitura/escrita do cache batia
  `403 Forbidden`, e `event_cache.read_cache_bytes` só tratava
  `NotFound` (cache miss legítimo), não `Forbidden`. A exceção não
  tratada virava 500 sem headers de CORS (por isso `net::ERR_FAILED`
  no browser, não um 500 "normal"). Pior: o Job de refresh **mascarou
  esse mesmo bug** — a rede de segurança genérica adicionada no bug
  anterior (`except GoogleAPICallError`/`except Exception`) capturou o
  `Forbidden` de cada escrita e logou como aviso, então a execução do
  Job aparecia como "Succeeded" no Console mesmo sem gravar nada de
  verdade no cache. Corrigido em duas frentes: (1)
  `google_storage_bucket_iam_member` concedendo `roles/storage.objectAdmin`
  pra SA de runtime, nos dois ambientes (infra, causa raiz); (2)
  `get_job_events_cached`/`get_access_events_cached` passaram a
  capturar **qualquer** exceção ao ler/gravar o cache (não só
  `NotFound`) e cair pro scan ao vivo — o cache nunca mais pode
  transformar uma resposta que funcionaria em uma que quebra.
  Aprendizado: ao adicionar um recurso de storage novo num
  Terraform module, sempre conferir explicitamente se a SA que vai
  *usá-lo em runtime* tem IAM sobre ele — criar o bucket não concede
  acesso a ninguém por padrão, e um `except` genérico numa rede de
  segurança de nível superior (o Job) pode esconder um bug de nível
  inferior (a causa raiz) em vez de só conter danos, então esse tipo de
  cobertura ampla não substitui monitorar o *conteúdo* dos logs, só a
  ausência de crash.

---

## Ajustes na aba "Uso do Hub" — remoção do ranking + funil em 4 estágios

Dois ajustes pedidos pelo usuário depois de revisar a v1.7 em produção:
o ranking de domínios só comparava 2 de 8 domínios do produto (o gap já
estava documentado no CHANGELOG anterior e na spec), e o usuário decidiu
remover a seção em vez de completar a instrumentação dos domínios
faltantes. O funil de retenção ganhou 2 estágios novos.

### O que foi feito
- Removido por completo o ranking de domínios mais usados (endpoint,
  service, schemas, hook, tipo e componente React) — comparava só
  profiling vs. PII scan (catalog/lineage/freshness/finops/storage sem
  tracking de uso, `access_requests` não integrado). Decisão do usuário:
  "exclua essa seção por enquanto, não faz sentido ter ela".
- Funil de retenção expandido de 3 para 4 estágios: acesso → ação
  (≥1) → +4 ações (≥5 total) → +9 ações (≥10 total). Nomes de campo no
  schema usam o limiar literal (`users_with_5plus_actions`/
  `users_with_10plus_actions`) em vez da fraseação relativa do usuário —
  essa fica só no rótulo do frontend.
- `docs/specs/admin.md` bump pra v1.8.

### Mudanças de arquitetura
- Nenhuma — mesma mecânica de agregação em Python sobre os sinais já
  rastreados; a remoção do ranking não afeta `analytics_repository.py`
  (suas funções continuam usadas por outras 3 leituras: atividade de
  profiling, atividade de PII scan e o heatmap de horário).

---

## Visualizações do brainstorm (Uso do Hub + telas existentes, 2 PRs)

Continuação da série de ajustes de UX — usuário pediu pra implementar o
brainstorm de gráficos antes de voltar pra documentação de telas. A
pesquisa mostrou que o admin "Uso do Hub" já tinha 6 seções (3 com
gráfico recharts) e que profiling/PII scan já eram rastreados — só
faltava virar gráfico. Recalibrado com o usuário: "buckets navegados"
(sem tracking hoje) e sparkline de Freshness (exigiria o primeiro job
agendado da história do app) ficaram fora desta rodada.

### O que foi feito
- **PR A** (3 gráficos triviais, zero mudança de backend): segunda
  linha de duplicatas% no histórico de profiling; custo acumulado vs.
  projeção no Budget quando agrupado por Dia; `BarChart` agrupado no
  diff coluna a coluna das pastas de comparação de profiling.
- **PR B** (3 seções novas em "Uso do Hub", backend + frontend):
  - Ranking de domínios mais usados (profiling vs. PII scan, por mês) —
    reaproveita as mesmas leituras que já alimentam
    `/analytics/profiling`/`/analytics/pii-scans`, zero gravação nova.
  - Mapa de calor de horário de uso (dia da semana × hora) — combina
    login + profiling + PII scan + table view + busca; sem heatmap
    nativo no recharts, grade CSS customizada
    (`UsageHeatmapGrid.tsx`) em vez de forçar um gráfico que a lib não
    cobre.
  - Funil de retenção (login → ≥1 ação → ação repetida) — "ação" não
    precisa vir depois do login temporalmente, só na mesma janela de
    90 dias (evita lógica frágil de ordenação pra um funil que só
    precisa ser uma leitura aproximada de engajamento).
  - `docs/specs/admin.md` bump pra v1.7.

### Mudanças de arquitetura
- Nenhuma — as 3 seções novas reaproveitam 100% das leituras Firestore
  já existentes (`list_all_profiling_runs`, `list_all_pii_scans`,
  `list_login_events`, `list_all_table_views`, `list_all_searches`),
  só agregação nova em Python.

---

## UX: 12 ajustes identificados durante a documentação de telas (6 PRs)

Usuário começou a tirar prints pra montar a documentação de telas do
Hub e, no processo, listou 12 problemas/ajustes de UX espalhados pelo
app. Cada item foi esclarecido via pergunta direta antes de implementar
(navegação, redundância entre features, filtros pouco flexíveis,
consistência de padrão entre telas parecidas, tema claro). Entregue em
6 PRs pequenos, empilhados numa cadeia de branches (só a última branch
da série vira PR pra `main` — decisão do usuário pra testar tudo junto
em dev antes de qualquer coisa ir pra prod, em vez de 6 aprovações de
deploy separadas).

### O que foi feito
- **Tema claro menos branco chapado**: `--background`/`--card`/
  `--popover`/`--sidebar` do tema claro viram off-white leve
  (`#FAFAF8`/`#F0EFEC`), mudança sutil pedida explicitamente.
- **Descrições nas abas do modal de Profiling**: Análise de qualidade,
  Lineage, Acesso e Tipos de coluna ganham um parágrafo curto
  explicando a funcionalidade.
- **Sidebar**: "Datasets disponíveis"→"Catálogo"; seção "Profiling"
  renomeada "Análises de DQ" e movida pra logo acima de "Recentes";
  "Favoritos" sempre visível (com estado vazio) mesmo sem nenhum
  favorito ainda; seletor de quantidade (5/10/20/Todos) em Favoritos e
  Recentes.
- **Seletor de dia com texto livre**: "Período analisado" (Tabelas sem
  consumidor) e "sem modificação há pelo menos" (Storage/Scanner de
  desperdício) ganham opção "Outro" além dos atalhos — backend trocou
  `IntEnum` restrito por `int` livre (`Query(ge=1)`) nos três lugares
  que tinham essa trava (`lookback_days` em lineage, `min_days_unused`
  em storage).
- **Freshness — filtro por múltiplas faixas + mínimo de tabelas**: a
  tabela de datasets troca o filtro de faixa única por seleção múltipla
  de faixas de SLA + campo de mínimo — um dataset só aparece se a soma
  das contagens dele nas faixas selecionadas atingir o mínimo. 100%
  client-side, sem mudança de backend.
- **Consolidação FinOps** (o PR maior dos 6):
  - "Tabelas sem uso" (FinOps) removida — era essencialmente a mesma
    pergunta que "Tabelas sem consumidor" (Governança/lineage) já
    respondia, só em lugar diferente do app. A única capacidade
    exclusiva (custo de storage estimado) foi levada pra
    `OrphanTable`, não perdida — `estimate_bigquery_storage_cost_usd`
    extraída de `domains/finops/service.py` pra `core/pricing.py`
    (cálculo puro, sem estado de domínio, agora reaproveitado por
    `finops` e `lineage`).
  - "Candidatas a particionamento" ganhou escopo por tabela (não só
    por dataset inteiro) — mesmo `ColumnTypeScopePicker` já usado em
    "Tipos de coluna", dataset expansível → tabela individual.
  - Os dois seletores de escopo (particionamento, tipos de coluna)
    ficaram colapsáveis (`Collapsible`), economizando espaço na tela
    depois da primeira seleção.
  - "Tipos de coluna" do FinOps trocou o badge compacto (tipo atual só
    no hover) por uma tabela com "Tipo atual"/"Tipo sugerido" em
    colunas visíveis — mesmo padrão que a aba equivalente dentro do
    modal de Profiling já usava.

### Erros cometidos e aprendizados
- `pnpm exec tsc --noEmit` (sem `-b`) deu falso-negativo — não acusou
  um `Cannot find name` real (componente removido de um import mas
  ainda usado no JSX) que `pnpm build` (`tsc -b && vite build`) pegou
  na hora. O projeto usa TypeScript composite/project references
  (`tsconfig.json` com `references`), e `tsc --noEmit` solto não
  reavalia esse grafo do mesmo jeito que `tsc -b`. A partir daqui,
  `pnpm build` é o check autoritativo neste repo, não `tsc --noEmit`
  isolado — usar o `--noEmit` só como feedback rápido intermediário,
  sempre confirmando com `pnpm build` antes de considerar um PR pronto.

### Mudanças de arquitetura
- Primeiro caso de fluxo git "branches empilhadas, PR só na última"
  nesta sessão — cada PR pequeno pode ser revisado/testado
  isoladamente em dev (push em qualquer branch já dispara deploy de
  dev), mas só um merge/aprovação de prod cobre a série inteira.

---

## Docs: specs faltantes (auth/favorites/history) + práticas de rastreabilidade no CLAUDE.md

Pedido do usuário, motivado por uma comparação com o framework
spec-driven do onp-spec-driven (github.com/onovoprogramador/onp-spec-driven):
avaliamos o que valia adotar sem migrar pro motor mecânico completo deles.

### O que foi feito
- `docs/specs/auth.md`, `docs/specs/favorites.md`, `docs/specs/history.md`
  (novos) — os 3 domínios de plataforma que já estavam implementados sem
  spec (gap real, não um domínio faltando implementação). Escritas
  retroativamente, documentando o comportamento atual (endpoints, regras,
  casos de borda) — não um plano futuro.
- `CLAUDE.md` — formalizadas práticas novas na seção "Contexto: Spec e
  documentação": critérios de aceite numerados (`AC-xxx`) em tabela
  apontando o teste que prova (sem precisar de motor mecânico — só a
  disciplina de nomear e referenciar), só quando a mudança toca
  comportamento de domínio documentado numa spec; seções `## Suposições`
  (`ASM-xxx`) e `## Perguntas em aberto` (`Q-xxx`) persistidas na spec,
  em vez de decisões esclarecidas por pergunta direta ficarem só no
  histórico do chat; regra de que "Erros cometidos e aprendizados" no
  CHANGELOG só recebe entrada amarrada a uma falha real, não opinião
  solta.
- `CLAUDE.md` — nova seção "Colaboração" (perguntar mais/presumir menos,
  sugerir funcionalidades quando fizer sentido) e regras novas em "Git e
  Claude Code": nunca fazer deploy (push/merge/aprovação de gate de prod)
  sem confirmação explícita a cada vez, com resumo breve dos commits; PRs
  não levam mais o rodapé "Generated with Claude Code" (commits mantêm o
  trailer `Co-Authored-By: Claude`).
- As 3 specs novas já nascem no formato com AC-xxx, mapeando pra nomes
  reais de teste já existentes em `tests/unit/{auth,favorites,history}/`
  — sem retrofit de tags nos arquivos de teste em si (os domínios são
  estáveis, não estão sendo modificados agora).

### Mudanças de arquitetura
- Nenhuma mudança de código — só documentação e convenção de processo.

---

## Profiling v1.4: pastas de comparação de runs

Parte 2/2 do pedido do usuário sobre histórico de profiling — parte 1 foi
a entrada anterior, "Profiling v1.3: parâmetros registrados no
histórico". Aqui: curar runs
específicos em pastas nomeadas (ex: "unicidade exata e 1 ano de consulta"
vs. "amostragem total") e comparar os resultados salvos numa tela
dedicada, em vez de depender só do histórico corrido de até 30 runs por
tabela.

### O que foi feito
- Backend: novo domínio de pastas dentro de `domains/quality/` —
  `folder_repository.py` (Firestore: `profiling_folders/{folder_id}` +
  subcoleção `entries`), schemas novos (`ProfilingFolder`,
  `ProfilingFolderEntry`, `FolderVisibility`, requests/responses), e 7
  endpoints em `router_folders` (`/api/v1/quality/folders...`, sem
  `project_id` no path — pastas juntam runs de tabelas/projetos
  diferentes por decisão do usuário). Cada entry grava um snapshot
  completo do run (não uma referência ao histórico, que trima a 30 por
  tabela). Regra de acesso em 2 níveis: quem só *vê* (visibilidade
  `shared_all`/`shared_emails`/dono/admin) vs. quem *gerencia* (só dono
  ou admin do Hub — edita, apaga, adiciona/remove entries).
- Frontend: `SaveRunToFolderDialog.tsx` (botão "Salvar em pasta" em
  `ProfilingDialog.tsx`, some assim que um run termina),
  `QualityFoldersPage.tsx` (lista de pastas visíveis) e
  `QualityFolderComparisonPage.tsx` (detalhe da pasta — cards por entry
  com parâmetros/métricas, edição de nome/compartilhamento pra quem
  gerencia, e uma tabela de diff coluna a coluna automática quando ≥2
  entries são da mesma tabela, destacando diferenças de completude acima
  de 10pp). Nova subseção própria "Profiling" na sidebar (dentro do
  grupo BigQuery, ao lado de Governança/FinOps), item único "Pastas de
  profiling".
- `docs/specs/profiling.md` bump pra v1.4, nova seção "Pastas de
  comparação de profiling" documentando modelo de dados, regra de
  acesso, os 7 endpoints e a lógica de comparação coluna a coluna.

### Mudanças de arquitetura
- Primeiro caso no Hub de uma pasta poder juntar dados de projetos GCP
  diferentes no mesmo agrupamento lógico — decisão explícita do usuário
  ("qualquer tabela") em vez de prender a pasta a uma tabela/projeto só.
- Primeiro router de `quality` que não depende de `project_id` no path
  (mesmo padrão já usado por `GET /api/v1/projects`) — `router` (existente,
  histórico) e `router_folders` (novo) coexistem no mesmo módulo
  `api/v1/quality.py`, registrados separadamente em `main.py`.

---

## Profiling v1.3: parâmetros registrados no histórico

Parte 1/2 de um pedido do usuário sobre histórico de profiling — parte 2
é o domínio de pastas de comparação (feature nova, PR separado).

### O que foi feito
`ProfilingHistoryRun` (histórico de até 30 runs por tabela, Firestore)
ganhou `parameters` (amostragem, método de unicidade, coluna/janela de
data) — antes só `overall_density`/`estimated_duplicate_pct`/`columns`
eram salvos, sem registrar QUAIS filtros geraram aquele resultado.
`None` em runs salvos antes desta versão (docs antigos do Firestore não
têm o campo — `service.get_quality_history` usa `.get()`, não indexação
direta). `HistoryTab.tsx` mostra os parâmetros na linha expandida de
cada run.

### Mudanças de arquitetura
- Nenhuma — `parameters` já existia como conceito em `ProfilingRequest`/
  `ProfilingRunResponse.parameters` (resposta do run ao vivo), só não
  era persistido no histórico.

---

## Frontend: modo claro (light/dark toggle)

Pedido do usuário — `docs/skills/frontend.md` já previa isso como
"opcional, futuro" desde a v1 da skill, com a regra exata de como
inverter as cores (só `--color-bg-*`/`--color-text-*`, mantendo
`#FFB302` e as cores de status/accent-* idênticas nos dois temas).

### O que foi feito
- `src/index.css`: as variáveis de cor que viviam em `:root, .dark`
  (mesmos valores nos dois seletores, ou seja, sem efeito real de tema)
  foram separadas — `:root` ganhou valores light novos (fundo branco,
  superfícies cinza-claro neutras, texto escuro), `.dark` manteve
  exatamente os valores de antes.
- `hooks/useTheme.ts` (novo) — estado do tema, persistido em
  `localStorage` (`observability-hub:theme`), alterna a classe `.dark`
  em `<html>`. Dark é o padrão: só "light" é persistido, ausência de
  valor salvo sempre cai em dark.
- `components/ThemeToggle.tsx` (novo) — botão no Topbar (ícone
  sol/lua), mesmo padrão visual dos outros botões de ícone com Tooltip
  já existentes ali.
- `index.html` — troquei `<html class="dark">` fixo por um script
  bloqueante inline que aplica a classe antes do primeiro paint (lendo
  a mesma chave do `localStorage`), evitando flash do tema errado
  enquanto o React ainda não montou.

### Erros cometidos e aprendizados
- Primeira versão dos comentários novos em `index.css` usava a notação
  `--color-bg-*/--color-text-*` (com barra colada no asterisco) — a
  sequência `*/` fechou o comentário CSS no meio da frase, quebrando o
  parser (confirmado pelo `biome check`, ~95 erros de parse em cascata
  a partir daquele ponto). Corrigido trocando a barra por "e" — mesmo
  cuidado vale pra qualquer comentário CSS que mencione múltiplos
  padrões `--algo-*` separados por `/`.

### Mudanças de arquitetura
- Nenhuma — CSS variables + classe `.dark` já era o mecanismo usado
  (via Tailwind v4 `@custom-variant dark`), só não tinha um segundo
  valor real nem um jeito de alternar. `docs/skills/frontend.md`
  atualizada de "não implementar no MVP" pra documentar o que existe.

---

## Freshness (filtro granular na visão de datasets) + FinOps Budget v1.2 (group_by=dataset)

Dois pedidos pontuais do usuário, entregues juntos por serem pequenos e
independentes.

### O que foi feito
- `DatasetFreshnessTable.tsx` (visão `/freshness`, lista de datasets)
  ganhou o mesmo tratamento que `TableFreshnessTable.tsx` já tinha
  recebido numa sessão anterior: filtro de 3 buckets agregados
  (Ok/Alerta/Obsoleta) trocado pelas 6 faixas granulares de SLA, e cada
  uma das 6 colunas de contagem por faixa virou ordenável (clicar em
  "12h a 24h" ordena pela contagem daquela faixa específica), além da
  ordenação por "Pior status" que já existia.
- `BudgetGroupBy` ganhou `dataset` como opção nova, ao lado de
  table/user/day/month/year — a v1.1 desta spec tinha **removido** um
  "custo por dataset" fixo em favor do `group_by` genérico; a v1.2 traz
  `dataset` de volta como uma opção dentro do mesmo mecanismo (pedido do
  usuário — granularidade de tabela é demais pra uma visão "quanto cada
  área/dataset custa"). Fan-out dedup a nível de dataset: duas tabelas
  do mesmo dataset tocadas pela mesma query contam uma vez, não duas.

### Mudanças de arquitetura
- Nenhuma — `dataset` reaproveita a mesma função `_group_keys` e o
  mesmo mecanismo `group_by` já existente, só mais um branch.

---

## Storage v1.2: navegar dentro de um bucket

Parte 6/7 (último item de feature nova) do plano combinado desta sessão
— o único dos 11 itens que é capacidade nova de verdade, não
reordenação/gate de UI existente.

### O que foi feito
Novo endpoint `GET /api/v1/storage/{project}/{bucket_name}/objects`
(`domains/storage/repository.py::browse_bucket_objects`) pagina objetos
de um bucket sob demanda — diferente de `list_bucket_objects_cached`
(lista TUDO de uma vez, usado só pra agregação/scanner), aqui é uma
página por vez via `client.list_blobs(..., delimiter="/", page_token=,
max_results=100)`. `delimiter="/"` simula navegação por "pasta" (GCS não
tem pastas reais) — `iterator.prefixes` vira a lista de subpastas do
prefixo atual.

Frontend: nova rota `storage/:bucketName` (`BucketBrowserPage.tsx`),
breadcrumb clicável, paginação por pilha de `page_token` (GCS pagina por
token encadeado, não por offset — "página anterior" só existe porque a
pilha guarda os tokens já visitados). Link novo em cada linha de
`BucketsPage.tsx` pra entrar no bucket. Nenhuma IAM nova —
`roles/storage.objectViewer` já cobria `storage.objects.list`/`.get`.

### Erros cometidos e aprendizados
- Primeira versão do reset de paginação ao trocar de prefixo usava
  `useEffect` — o linter (biome, regra de exhaustive-deps) reclamou
  corretamente que o efeito não *lê* `prefix`, só reage à mudança dele,
  então a dependência "não é necessária" do ponto de vista da regra.
  Troquei pelo padrão que o próprio React recomenda pra "ajustar estado
  quando uma prop muda" sem `useEffect` (comparar com um estado
  "valor na última vez" durante o render, resetar inline se mudou) — mais
  simples e sem o round-trip extra de um efeito rodando depois do render.

### Mudanças de arquitetura
- Nenhuma — mesmo client (`core/storage_client.py`), mesmo domínio
  (`domains/storage`), só uma função de repository nova.

---

## FinOps Budget + Storage waste scanner: tela de pré-execução

Parte 5/7 do plano combinado desta sessão. Diferente do PR anterior
(que precisou de mudança de backend), este é só reordenação de
frontend — os dois endpoints já suportavam os parâmetros necessários
(`group_by`/`limit` no budget; `min_days_unused` no waste scanner de
storage), só não havia gate nenhum antes de disparar a query.

### O que foi feito
- `BudgetPage.tsx`: ao entrar na tela, mostra descrição do que o budget
  faz + os controles de agrupamento (tabela/usuário/dia/mês/ano, já
  existiam, só apareciam depois do resultado) e um seletor de limite de
  itens (5/10/20/50, não existia na UI antes, endpoint já suportava) +
  botão "Executar". `useBudget` ganhou um parâmetro `enabled`.
- `WastePage.tsx` (storage): mesmo padrão — descrição da regra (idade +
  lifecycle rule, com nota sobre a checagem opcional via audit log) +
  seletor de threshold (30/60/90 dias, já existia) + botão "Executar".
  `useWasteCandidates` ganhou o mesmo parâmetro `enabled`.
- As duas telas ganharam um botão "Nova busca" pra voltar à tela de
  pré-execução sem perder o resultado anterior visível até clicar.

### Mudanças de arquitetura
- Nenhuma — sem `DatasetScopeGate` aqui (nem budget nem o waste scanner
  de storage têm granularidade de dataset), gate construído inline em
  cada página, mesmo padrão visual do componente compartilhado.

---

## Lineage v2.1 + FinOps waste-scanner v1.1: gate de escopo por dataset

Pedido do usuário: 11 ajustes de UX/backend coletados de uso real,
entregues em 7 PRs sequenciais (plano em modo de planejamento). Esta
entrada cobre o maior PR do lote — 3 telas que escaneavam o projeto
inteiro sem gate nem explicação da regra: tabelas sem consumidor
(lineage), candidatas a particionamento e tabelas sem uso (finops).

### O que foi feito
Generalizado o padrão já existente em `ColumnTypeScopePicker.tsx` (que
exige escolher tabelas antes de rodar column-type-suggestions) num
componente novo `components/DatasetScopeGate.tsx` — granularidade de
dataset (não tabela), com descrição da regra da tela + botão
"Executar". As 3 telas passaram a exigir esse gate antes de disparar a
query real; nenhuma delas tinha antes.

Backend: `GET /orphans` ganhou `datasets` (repetido) + `lookback_days`
(`LookbackDays` IntEnum: 30/60/90/365, era fixo em 30). `GET
/unused-tables` e `GET /partition-candidates` ganharam `datasets`. Os
três continuam funcionando sem o parâmetro (scan de projeto inteiro,
capacidade preservada pra scripts/testes) — só o frontend passou a
sempre mandar um escopo explícito. `list_all_table_refs` (duplicada em
`lineage` e `finops`, domínios isolados por convenção do projeto)
ganhou filtro `WHERE table_schema IN UNNEST(@datasets)` nas duas cópias.

Também: coluna "Tipo atual" na tabela de sugestões de tipo de coluna
(profiling) — o campo `current_type` já vinha no payload, só não era
renderizado.

### Erros cometidos e aprendizados
- Testes existentes de `list_all_table_refs` (lineage e finops) mockavam
  `client.query` com uma função que só aceitava `sql` — quebraram ao
  `query()` passar a sempre receber `job_config` (mesmo que `None`).
  Ajustado pra aceitar o kwarg opcional nos dois arquivos de teste.

### Mudanças de arquitetura
- Nenhuma — `DatasetScopeGate` é um componente novo em `components/`
  (compartilhado entre domínios, diferente de `ColumnTypeScopePicker`
  que é local a `features/finops/`), mas segue o mesmo racional já
  estabelecido, não introduz um padrão novo.

---

## Catalog v1.6: seletor de projeto lista os projetos que a SA alcança

Pedido do usuário logo após reportar (e eu confirmar via logs) que a
integração com o Workspace da v1.5/v1.6 do Admin está retornando 403 —
achado registrado em backlog pelo usuário, não resolvido nesta entrada
(ver seção anterior no histórico da sessão, não neste CHANGELOG: a causa
é a conta impersonada não ter privilégio de admin no Workspace). Trocando
de prioridade, o pedido novo: "no seletor de projetos, sejam listados
todos os projetos que a SA tem acesso e com flags pro usuario de quais
deles ele tem ou não acesso como user".

### O que foi feito
Até aqui o seletor de projeto (`ProjectSelector.tsx`) era só um campo de
texto livre — o usuário digitava o `project_id` de cabeça e clicava
"Validar" pra descobrir se tinha acesso. Não existia nenhuma descoberta
automática de quais projetos GCP a service account de runtime alcança —
só validação de UM projeto por vez, sob demanda.

Novo endpoint `GET /api/v1/projects` (`core/resourcemanager.py::list_reachable_projects`,
Cloud Resource Manager `search_projects`) lista os projetos que a SA
enxerga — requer `roles/browser` da SA no projeto alvo, role nova,
**opcional** (não bloqueia nenhum domínio de observabilidade existente,
só não aparece no seletor sem ela). Cada projeto retornado já vem com
`has_access` calculado pra o usuário atual (reaproveita
`admin_service.has_project_access`, mesma checagem de
`require_project_access`). O frontend ganhou um `Select` com esses
projetos (mostrando "Sem acesso" nos que o usuário não pode entrar ainda)
ao lado do campo de texto livre, que continua funcionando como fallback
— importante porque a lista da SA só cresce conforme mais projetos
ganham `roles/browser` no onboarding, e nem todo projeto onboardado até
hoje tem essa role ainda.

Granted `roles/browser` pras duas SAs de runtime (`backend-dev-run`,
`backend-prod-run`) no próprio `dp6-ci-polaris` nesta sessão, já que é o
único projeto-alvo registrado até agora (topologia single-project) —
registrado em `docs/onboarding-cliente.md`.

### Erros cometidos e aprendizados
- Antes de implementar, investiguei se a Resource Manager API listaria os
  projetos que a SA alcança só com as roles do checklist atual
  (`bigquery.*`, `logging.*`, `storage.*`) — nenhuma delas implica
  `resourcemanager.projects.get`, então `search_projects` teria retornado
  sempre vazio sem uma role nova. Evitou implementar uma feature que
  pareceria funcionar em teste unitário (mockado) mas nunca retornaria
  nada em produção.
- `GET /api/v1/projects` não pode usar `require_project_access` (a
  dependency de router original) porque essa dependency exige
  `project_id` como path param — o endpoint novo é project-agnostic.
  Resolvido movendo `require_project_access` de dependency de router pra
  dependency só da rota `/validate`, e usando `get_current_user` (menos
  restritivo) no nível do router.

### Mudanças de arquitetura
- Nenhuma — nova role opcional (`roles/browser`) e um client novo isolado
  (`core/resourcemanager.py`), mesmo padrão dos outros clients GCP em
  `core/`.

---

## Admin v1.6: descoberta automática de grupos no "Criar grupo"

Direto depois da v1.5 (grupos vinculados ao Workspace), feedback do
usuário sobre a própria v1.5: "a guia grupos no adm não está retornando
os grupos existentes no workspace" — esperava a aba listar os grupos do
Workspace sozinha (autocomplete/seleção), não continuar exigindo digitar
o e-mail exato de um grupo real pra ativar o lado automático.

### O que foi feito
Novo endpoint `GET /api/v1/admin/workspace-groups`
(`workspace_directory.list_domain_groups`) lista todos os grupos do
domínio via Admin SDK Directory API (`groups?domain=...`, paginado,
mesmo cache de 5min e mesmo fail-closed de `get_group_members` — lista
vazia em qualquer erro, nunca propaga exceção). O diálogo "Criar grupo"
em `AdminGroupsTab.tsx` trocou o campo de texto livre por um `Select`
populado com esses grupos (já filtrando os que já viraram `hub_group`),
com uma opção "Nome livre" que volta pro campo de texto antigo pra quem
quer um grupo só com `manual_members`, sem vínculo a nenhum grupo real.

### Erros cometidos e aprendizados
- `ruff` sinalizou `lambda: []` num teste novo sugerindo o builtin
  `list` no lugar — trivial, mas serve de lembrete de rodar `ruff check`
  antes de considerar a parte de backend pronta, mesmo em testes.
- `Select.onValueChange` do shadcn/ui aceita `string | null` (o `null`
  vem de deselect), incompatível direto com `useState<string>` — mesmo
  padrão já usado em `ProfilingDialog.tsx` (`value ?? fallback`), só não
  copiado de primeira.

### Mudanças de arquitetura
- Nenhuma — mesmo módulo isolado `core/workspace_directory.py` da v1.5,
  só ganhou uma função de leitura a mais.

---

## Admin v1.5: grupos vinculados a grupos reais do Google Workspace

Direto depois da v1.4 (grupos de acesso), pedido do usuário pra não
precisar cadastrar membro manualmente — vincular aos grupos que já
existem no Workspace.

### O que foi feito
Modelo híbrido: cada grupo (`hub_groups`) passa a ter dois eixos de
membro que se somam — `manual_members` (cadastro direto na Hub, como
antes) e `workspace_members` (membros reais de um grupo do Google
Workspace, lidos ao vivo via Admin SDK Directory API, nunca persistidos
em Firestore). Novo módulo `core/workspace_directory.py` faz domain-wide
delegation **sem chave de service account** — a SA de runtime assina o
próprio JWT de delegação via IAM Credentials API (`signBlob`), não
precisa de chave baixada. Cache de 5min por grupo (mesmo padrão do scan
de PII) — a leitura roda no caminho de `has_project_access`, chamado em
quase todo endpoint.

`has_project_access` ganhou uma reescrita: como membros do Workspace não
ficam no Firestore, não dá pra fazer uma query `array_contains`
direcionada como antes (`groups_with_member`, removida) — agora escaneia
os grupos (coleção pequena) e só consulta o Workspace pros grupos que já
liberam o `project_id` em questão (evita chamada externa desnecessária).

### Erros cometidos e aprendizados
- Minha primeira versão de `get_group_members` tinha a construção das
  credenciais **fora** do `try/except` — uma falha ali (ex: domain-wide
  delegation ainda não configurada) propagava a exceção em vez de
  retornar lista vazia, quebrando o próprio princípio de fail-closed que
  o módulo documenta. Pego pelo teste
  `test_get_group_members_returns_empty_and_does_not_raise_on_credentials_error`
  antes de subir — o teste existia especificamente pra validar esse
  comportamento, e falhou corretamente.
- Pesquisei a técnica de "domain-wide delegation sem chave" antes de
  implementar (webfetch de fontes técnicas + inspeção do código-fonte de
  `google.auth.iam.Signer` e `google.oauth2.service_account.Credentials`
  na própria lib instalada) em vez de confiar de memória — resumos de
  blog encontrados na busca tinham detalhes desatualizados/imprecisos
  (endpoint OAuth legado, formato de payload divergente); a fonte de
  verdade acabou sendo o código-fonte real da lib já instalada no
  projeto.
- Concessão de IAM a nível de recurso (SA sobre si mesma) precisou de
  uma role de projeto adicional (`roles/iam.serviceAccountAdmin`) que o
  grupo `gcp-ci-polaris@dp6.com.br` não tinha — `resourcemanager.
  projectIamAdmin` não cobre IAM policy de recursos individuais como
  service accounts. Depois da propagação (~21min, mais lenta que o
  usual), `gcloud iam service-accounts add-iam-policy-binding` continuou
  falhando com "getIamPolicy denied" mesmo com `get-iam-policy` direto
  já funcionando — contornado fazendo `get-iam-policy` + editar o JSON +
  `set-iam-policy` explícito, que funcionou de primeira. Causa exata do
  `add-iam-policy-binding` (comando de conveniência) falhar nesse caso
  específico não totalmente esclarecida — mas o contorno (get/edit/set
  manual) é confiável e documentado aqui pra próxima vez que algo
  parecido acontecer.

### Mudanças de arquitetura
- Nenhuma mudança de arquitetura geral — extensão do domínio `admin`
  (ADR-009). A técnica de domain-wide delegation sem chave é nova no
  projeto, mas isolada em `core/workspace_directory.py`, sem acoplar
  nenhum outro domínio a ela.

---

## Admin v1.4: grupos de acesso + fix de bug no roteamento de `/admin`

### O que foi feito
- **Bug corrigido**: `/admin` só abria depois de um `project_id`
  validado no seletor do Topbar — `AppLayout` gateava o `<Outlet />`
  inteiro atrás de `projectId`, incluindo rotas (como admin) que não
  dependem de projeto nenhum. Agora só as rotas de dado de projeto
  exigem `projectId`; `/admin` funciona mesmo sem nenhum acesso
  liberado ainda (importante justamente pro caso de bootstrap, antes de
  qualquer projeto GCP estar liberado).
- **Grupos (`hub_groups`)**: terceiro eixo de controle de acesso, ao
  lado de `hub_users.allowed_projects` (individual) e
  `hub_projects.is_public` (público) — um grupo tem membros (e-mails) e
  projetos liberados; cada membro herda o acesso do grupo, além do que
  já tiver individualmente. Nova aba "Grupos" em `/admin` (CRUD
  completo); aba "Por usuário" ganhou uma coluna mostrando de quais
  grupos cada usuário faz parte. Ver `docs/specs/admin.md` v1.4 pra
  detalhes completos (schema, endpoints, casos de borda).

### Erros cometidos e aprendizados
- Nenhum nesta mudança — spec lida antes de implementar (v1.3 já
  registrava "Grupos/times" como fora do escopo, virou o ponto de
  partida do desenho da v1.4).

### Mudanças de arquitetura
- Nenhuma — extensão do mesmo domínio `admin` (ADR-009), sem novo
  serviço nem mudança de padrão de acesso a dado.

---

## CI/CD: gate de aprovação manual antes de deploy de app em prod

Direto em `main`, fora de qualquer sprint — pedido do usuário depois de
investigar um custo de Cloud Run maior que o normal (ver item abaixo).

### O que foi feito
`backend-deploy-prod.yml`/`frontend-deploy-prod.yml` ganharam
`environment: production` no job de deploy — GitHub segura o job em
"Waiting" até alguém aprovar manualmente (Settings → Environments →
`production`, "Required reviewers"), em vez de publicar sozinho a cada
push em `main`. `terraform-apply-prod.yml` continua automático, de
propósito: mudança de infra já passa por `terraform plan` revisado
antes do merge, diferente do deploy de app, que sobe uma imagem nova
sem revisão nenhuma no meio. `dev` não muda — continua 100% automático.

### Nota sobre a primeira aplicação (corrida de tempo)
No dia em que o gate foi configurado, o `backend-deploy-prod.yml` do
push seguinte ficou corretamente em "Waiting", mas o
`frontend-deploy-prod.yml` do mesmo push **não** — já estava
`in_progress` quando a regra de proteção do environment foi salva.
Deploy único, sem gate, não repetido depois — não é um problema na
configuração, é só o tipo de corrida que só acontece na primeira vez
que a regra é criada.

### Diagnóstico de custo do Cloud Run (achado no caminho, não relacionado ao domínio storage)
Investigando por que um dia teve custo bem maior que os outros: os 4
serviços Cloud Run (dev/prod × backend/frontend) estavam com
`run.googleapis.com/cpu-throttling: false` ("CPU sempre alocada" —
cobra pelo tempo de vida da instância inteira, não só durante o
processamento da requisição). Confirmado que não vinha do Terraform
(`resources.cpu_idle` não é declarado no módulo `cloud-run`) nem do
workflow de deploy (nenhum dos 4 passa essa flag) — foi mudado
manualmente fora do fluxo do projeto, sem registro de quando ou por
quê. Revertido pro padrão (CPU só durante request) nos 4 serviços,
confirmado com `gcloud run services describe` + health check 200 nos
4 depois do rollout. `min_instance_count = 0` (scale-to-zero) confirmado
intacto nos 4 — nunca foi a causa.

Volume de requisições do dia em questão (dev 1163, prod 37) bateu com
um dia de implementação intensa (a própria sprint do domínio storage) —
não foi um vazamento de tráfego, foi o multiplicador de custo do CPU
sempre alocado em cima de um dia de uso real e alto.

---

## Auditoria completa de documentação de acesso e hospedagem

Pedido explícito do usuário: revisão de ponta a ponta de toda a
documentação que será entregue a terceiros (para liberar acesso a
projetos-alvo) e usada pelo próprio usuário (para hospedar o Hub do
zero em outra conta/repositório GitHub). Achados e correções:

- `docs/playbooks/liberar-projeto-para-o-hub.md` e
  `docs/manual-liberacao-acesso-cliente.md` **não mencionavam o domínio
  `storage` de forma alguma** (escritos antes da Fase 5) — nenhuma das
  duas roles de storage, nenhuma API, nenhum audit log. Atualizados com
  a seção completa (API, as 2 roles sempre juntas, audit log opcional
  com aviso de volume, checklist, troubleshooting).
- `docs/onboarding-cliente.md`: introdução citava só 4 dos 8 domínios;
  tabela de roles não creditava `pii`/`access`/`finops` como
  consumidores das roles já listadas; justificativa de "`billing.viewer`
  não necessário" ainda dizia "FinOps não implementado" (implementado
  há dias). Todos corrigidos.
- **Achado crítico nos dois playbooks de hospedagem**
  (`hospedar-hub-em-novo-projeto.md`, `manual-implementacao-cliente.md`):
  a escolha de nome dos dois projetos GCP nunca foi documentada como
  **obrigatória** terminar em `-dev`/`-prod` — só aparecia como exemplo
  sugerido. `core/secrets.py::_is_prod()` decide qual par de secrets
  OAuth ler checando literalmente `project_id.endswith("-prod")`; um
  nome fora desse padrão faz login de prod ler secrets de dev
  silenciosamente, sem erro. Adicionado como aviso obrigatório, item de
  checklist e linha de troubleshooting nos dois documentos.
- Os dois playbooks de hospedagem também ganharam o passo de configurar
  o `environment: production` do GitHub (ver seção de CI/CD acima) — sem
  isso, replicar o repositório copia os workflows já gateados, mas sem
  a regra de proteção configurada o gate simplesmente não existe.

Nenhuma mudança de código nesta sessão — só documentação.

---

## Fase 5 — Storage (Cloud Storage): domínio novo, 4 itens (concluída, validada em dev)

Branch `feat/storage-mvp`, a partir de `main` pós-PR #24. Primeira
expansão do Hub pra além do BigQuery (spec `docs/specs/storage.md`,
motivação registrada lá: Storage → Scheduler → Workflows é a ordem de
prioridade planejada). Quatro itens, cada um validado em dev pelo usuário
antes do próximo começar, nenhum PR pra `main` ainda.

### 1. Catálogo de buckets
`GET /api/v1/storage/{project}/buckets` — nome, storage class, região,
tamanho total + contagem de objetos (via listagem cacheada 5min, mesmo
padrão de `core/bigquery.py::get_table_cached`), `has_lifecycle_rule`,
`time_created`/`updated` (metadado nativo do `Bucket`, de graça na mesma
chamada). Novo `core/storage_client.py`, novo grupo `SidebarServiceGroup`
"Cloud Storage" na sidebar (irmão de "BigQuery").

**Bug real encontrado em dev**: `roles/storage.objectViewer` (única role
que a v1 da spec previa) não cobre `storage.buckets.list`/`storage.
buckets.get` — só `storage.objects.*`. `list_buckets()` (a primeira
chamada do domínio) precisa também de `roles/storage.bucketViewer`
(role dedicada, só leitura de metadado de bucket). Confirmado com
`gcloud iam roles describe`, corrigido no handler de 403 e no checklist
de `docs/onboarding-cliente.md` (as duas roles, sempre juntas).

### 2. Freshness — implementada, validada, depois substituída
V1: endpoint dedicado (`GET .../buckets/{bucket}/freshness`), botão "Ver
freshness" sob demanda no frontend, `last_modified` = `max(customTime ou
updated)` entre os **objetos** do bucket. Validada em dev e então
**descartada por decisão do usuário**, substituída por `time_created`/
`updated` do próprio `Bucket` (item 1) como colunas direto na tabela —
mais barato (zero chamada extra), mas semanticamente diferente:
`Bucket.updated` reflete mudança de config (lifecycle, storage class),
não gravação de objeto. Trade-off registrado explicitamente na spec
(seção 5) — código da v1 removido por completo, não deixado como dead
code.

### 3. Scanner de desperdício — duas checagens independentes
`GET /api/v1/storage/{project}/waste-candidates?min_days_unused=30|60|90`
(`IntEnum`, mesma correção de `Literal`→422 já feita no FinOps):
- **6.1 (config-based)**: bucket sem lifecycle rule + objetos `STANDARD`
  mais antigos que o threshold. Sempre disponível, só metadado.
- **6.2 (usage-based, pedido numa segunda rodada depois de habilitar
  Data Access audit log `DATA_READ` do GCS em dev)**: objeto elegível por
  6.1 sem nenhuma leitura (`storage.objects.get`) nos audit logs em 90
  dias ganha `confidence: "usage_confirmed"`. Payload do audit log de GCS
  é o proto padrão `google.cloud.audit.AuditLog` — **diferente** do
  formato legado que lineage/access usam pra job do BigQuery, parser novo
  em `domains/storage/repository.py::list_read_object_keys`, mesmo client
  de Cloud Logging (roles já cross-granted). Degradação graciosa
  obrigatória: `Forbidden` ou resultado vazio pro projeto inteiro (audit
  log pode estar desabilitado) nunca falha a requisição — cai pra
  `config_based` em todos os candidatos, com `usage_check_warning`
  explicando o motivo.

Faixa de economia (nunca valor único) reflete migração pra `NEARLINE`
(mínimo) ou `COLDLINE` (máximo) sobre bytes reais armazenados —
`ARCHIVE` fica de fora de propósito (retrieval caro + duração mínima de
365 dias).

**Gap pré-existente encontrado, corrigido junto** (não era novo deste
item): `list_bucket_objects_cached` não capturava `Forbidden` — um
projeto com `bucketViewer` mas sem `objectViewer` estourava 500 cru em
vez do 403 limpo do domínio. `repository.py` ganhou `project_id` nos
parâmetros de listagem de objetos pra poder relançar
`StorageAccessDeniedError`.

### 4. Extensão do lineage — bucket como nó do grafo
`load` (GCS→BQ) vira aresta bucket→tabela; `extract` (BQ→GCS) vira aresta
tabela→bucket. Payloads reais capturados ao vivo em dev (gravação real de
objeto + `gcloud logging read`) usados como fixture de teste, não
inventados. `JobEvent` ganhou `source_buckets`/`destination_buckets`;
`NodeRef` (service.py) generaliza `TableRefTuple` (3-tupla) +
`BucketRef` (1-tupla) — discriminável só pelo tamanho da tupla.

**Decisão de desenho tomada com o usuário**: bucket é sempre nó **folha**
— entra no grafo quando descoberto pelos eventos já buscados do lado
tabela, mas a travessia BFS nunca expande a partir dele. Diferente de
tabela, bucket não tem "projeto dono" confiável via API pra saber em qual
audit log procurar quem mais o referencia (nome do bucket não garante o
projeto GCP dono, e jobs que o tocam podem rodar em qualquer projeto
observado pelo Hub). `LineageNode` ganhou `type`/`bucket_name`;
`project_id`/`dataset_id`/`table_id` viraram opcionais. Frontend:
`bucketNode` novo em `LineageGraph.tsx` (ícone `HardDrive`, cor
`status-ok`).

**Gap encontrado, deliberadamente não corrigido** (fora do escopo deste
item — é do domínio `lineage` inteiro, não específico de bucket): nenhum
parser de audit log do projeto (lineage, access, finops) filtra
`jobStatus.state != "DONE"` — um job que falhou mas tem `destinationTable`/
`sourceUris` no config já criaria uma aresta hoje. Registrado como
backlog do domínio lineage na spec.

### Falha de processo encontrada e corrigida durante esta sessão
Commits de fechamento do SESSIONLOG/CHANGELOG de uma sessão anterior
(reconstrução completa depois de 4 dias sem atualização, ver seção
"Documentação para cliente" abaixo) tinham ficado presos na branch
`feature/admin-usage-analytics` — nunca foram mergeados em `main` via PR,
só pusheados pra o remoto da própria branch. Quando `feat/storage-mvp`
foi criada a partir de `main` atualizada, herdou a versão **velha** do
SESSIONLOG (de 2026-08-14). Descoberto e corrigido nesta sessão com um
merge explícito de `feature/admin-usage-analytics` em `feat/storage-mvp`
antes do fechamento de documentação — sem isso, a reconstrução de 4 dias
de trabalho teria se perdido uma segunda vez.

### Status final
- Backend: 597 testes unitários (0 no início do domínio storage), 100%
  passando, `ruff check`/`ruff format` limpos.
- Frontend: `biome check`, `tsc -b`, `vite build` limpos.
- Validado em dev pelo usuário — os 4 itens, incluindo o grafo de lineage
  com bucket real (`RAW.crm_leads_staging` ⟷ buckets `landing`/
  `processed`, jobs LOAD/EXTRACT reais).
- Infraestrutura de prod promovida antes do merge (IAM, buckets, mocks,
  audit config — checklist em `docs/onboarding-cliente.md`) e deploy
  automático confirmado verde depois (`gh run list`).
- **PR #25 mergeado em `main`, deployado em prod.**

---

## Documentação para cliente — playbooks operacionais e manuais (PRs #22, #23, #24)

Branch `feature/admin-usage-analytics`, três commits **docs-only** (não
tocam `apps/`, sem deploy disparado — confirmado via `gh run list`).
Fecha o ciclo iniciado por `docs/onboarding-cliente.md` (checklist
técnico) com material de execução e material voltado a cliente final,
todos referenciando o mesmo checklist e os ADRs 006/009 como fonte de
verdade técnica.

### O que foi feito

**Dois playbooks internos** (`docs/playbooks/`, público: time do Hub):
1. `liberar-projeto-para-o-hub.md` (216 linhas) — roteiro de "já tenho um
   projeto GCP com dados, o que preciso fazer pra o Hub ler esse
   projeto". Explicitamente não é fonte de verdade — aponta pra
   `docs/onboarding-cliente.md` pra isso, e pede que quem executar volte
   lá pra registrar a concessão. Deixa claro que a liberação de
   infraestrutura GCP é só metade do caminho — a segunda camada (ACL do
   Hub, ADR-009) é liberada depois, dentro do próprio `/admin`.
2. `hospedar-hub-em-novo-projeto.md` (449 linhas) — roteiro de "quero
   rodar minha própria cópia do Hub em projetos GCP diferentes dos
   originais, do zero". Bootstrap único por par de ambientes (dev/prod);
   depois de concluído, o dia a dia vira só `git push`. Cobre o
   inventário completo de infraestrutura que o Hub precisa pra existir
   (2 Cloud Run, Artifact Registry compartilhado, SAs de runtime,
   Firestore, Secret Manager, WIF, bucket GCS de state).

**Dois manuais voltados a cliente final** (linguagem sem jargão interno):
3. `docs/manual-implementacao-cliente.md` (361 linhas) — implementação de
   uma instância própria do Hub no GCP do cliente, hospedagem/
   administração sob controle dele. Seção "Segurança e escopo" explícita:
   tudo dentro dos projetos do próprio cliente, sem credencial de longa
   duração (WIF), permissões mínimas, reversível, nada trafega pra fora
   do ambiente GCP dele. Público: responsável técnico com papel *Owner*.
4. `docs/manual-liberacao-acesso-cliente.md` (197 linhas) — contraparte de
   `liberar-projeto-para-o-hub.md`, em linguagem de cliente: como
   autorizar o Hub (já hospedado) a ler um projeto GCP existente. Mesma
   seção "o que faz/não faz": só leitura, nada instalado no projeto do
   cliente, acesso escopado e revogável, cliente confirma cada permissão
   antes de conceder. Público: *Owner*/*IAM Admin*. Tempo estimado
   10–15min (vs. meio dia do manual de implementação).

### Decisões desta sessão

**Decisão 1 — Quatro documentos, não dois, por causa da audiência**
- Playbook interno (linguagem do time do Hub, assume contexto do
  CLAUDE.md/ADRs) e manual de cliente (linguagem sem jargão, assume
  Owner de um GCP que nunca ouviu falar do Hub) são públicos diferentes
  o bastante pra não caber no mesmo texto — cada par (liberar acesso /
  hospedar o Hub) ganhou uma versão de cada.

### Status até o momento
- Docs-only, sem impacto em testes/build/deploy.
- Nenhum projeto de cliente real usou os manuais ainda — primeira
  validação de uso real fica pra quando isso acontecer.

---

## Admin — refactor de colunas/filtros e UX de listas longas (commits `568622a`, `301fc59`)

Branch `feature/admin-usage-analytics`. Depois da v1.3 (seis seções de
analytics simultâneas na aba "Uso do Hub"), dois ajustes de qualidade
antes de fechar a frente de Admin.

### O que foi feito
1. **Padronização de colunas/filtros (`568622a`)**: as seis seções tinham
   crescido cada uma com sua própria tabela ad-hoc (nomes de coluna
   diferentes pra projeto/dataset/tabela, filtros inconsistentes entre
   seções). Refatorado pra um padrão único de colunas e filtros
   compartilhado entre todas.
2. **Tópicos recolhíveis + paginação (`301fc59`)**: as seis seções
   (Acessos, Favoritos, Profiling, Solicitações, Navegação, Scans de
   PII) e seus sub-blocos nomeados (ex: "Bases mais favoritadas",
   "Drill-down") passaram a usar `CollapsibleSection` — abrem por
   padrão, mas podem ser recolhidas. Toda lista tabular ganhou paginação
   client-side de verdade via `usePagination`/`PaginationBar`
   (10/20/50/100 linhas por página) dentro de um container com scroll
   vertical, em vez de despejar a lista inteira na tela.

### Status até o momento
- Backend: sem mudança de API — refactor e paginação são só frontend.
- Frontend: `biome check`, `tsc --noEmit`, `vite build` limpos.
- Validação visual fica a cargo do usuário após deploy em dev.

---

## Admin v1.3: solicitações de acesso, navegação agregada, atividade de scans de PII

Branch `feature/admin-usage-analytics` (mesma do Admin v1.2, ainda sem
push/PR). Usuário pediu um brainstorm de que outros serviços/
funcionalidades já existentes valeria mapear no painel "Uso do Hub" —
escolheu, em ordem de custo/valor, os 3 desta rodada; deixou expansão
pra serviços GCP fora do BigQuery registrada como backlog
(`SESSIONLOG.md`, item 14), adiada por decisão explícita.

### O que foi feito

Mais 3 seções na aba "Uso do Hub":

1. **Solicitações de acesso** — zero gravação nova. `access_requests`
   (já existia desde a v1.1) já tinha tudo; nova leitura agrega por mês
   (`{period, total, approved, denied, pending}`), lista os 10 projetos
   mais pedidos e calcula taxa de aprovação (`null` se nada foi
   resolvido ainda, não `0%`). Gráfico de barras empilhado por status.
2. **Navegação agregada** — zero gravação nova. `domains/history` já
   persistia `history_table_views`/`history_searches` por usuário; nova
   leitura via `collection_group` agrega entre todos (mesmo padrão de
   favoritos). "Tabelas mais vistas" (gráfico de barras horizontal) +
   "buscas mais frequentes" (tabela). Ressalva explícita na UI: cada
   usuário só guarda os 20 itens mais recentes, é uma métrica de uso
   recente, não histórico completo.
3. **Atividade de scans de PII** — gravação nova, mesmo padrão do
   profiling. `domains/pii` não persistia nada até aqui (só cache em
   memória, TTL 5min, sem usuário). Novo `history_repository.py` grava
   em `pii_scan_history/{doc}/scans` a cada execução real (não em cache
   hit). Tabela de atividade idêntica à de profiling.

### Decisões desta sessão

**Decisão 1 — Nome de subcoleção `scans`, não `runs`, pro histórico de PII**
- Achado durante a investigação, não pedido pelo usuário: profiling já
  usa `collection_group("runs")` pra agregação global. Se PII também
  usasse `runs` como nome de subcoleção, a mesma query passaria a
  devolver os dois históricos misturados — `collection_group` ignora o
  caminho do documento-pai, só olha o nome da subcoleção. Confirmado
  por grep antes de implementar que nenhum domínio usava `scans`.

**Decisão 2 — Histórico de PII só grava em execução real, não em cache hit**
- `run_pii_scan` tem cache em memória (TTL 300s) que devolve o mesmo
  resultado sem recomputar. Gravar histórico incondicionalmente faria
  um cache hit parecer uma execução nova (mesmo `executed_at`/
  `executed_by` de uma ação que não aconteceu de fato). A gravação fica
  só no branch de cache miss.

**Decisão 3 — Listas achatadas com agregação client-side, mesmo padrão da v1.2**
- Solicitações de acesso é a exceção (agregação já pronta no backend,
  porque o volume é pequeno e as métricas — mês/status/projeto — são
  fixas); navegação segue o padrão de favoritos (lista achatada, front
  agrega do jeito que precisar) porque "top tabelas"/"top buscas" são
  cálculos simples e mantém o backend sem opinião sobre quantos itens
  mostrar.

### Status até o momento
- Backend: 556 testes unitários, 100% passando, `ruff check`/`ruff
  format --check` sem erros.
- Frontend: `tsc --noEmit` limpo, `pnpm lint` (biome) sem erros,
  `pnpm build` concluído (bundle: 1.311 kB / gzip 389 kB — backlog de
  code-splitting, item 12 do `SESSIONLOG.md`, cresce a cada rodada).
- Validação visual (gráficos novos, números batendo) fica a cargo do
  usuário após deploy em dev.

---

## Admin v1.2: painel de uso/gestão — acessos ao Hub, favoritos entre usuários, atividade de profiling

Branch `feature/admin-usage-analytics`. Brainstorm do usuário: quer
visão gerencial de uso do Hub em `/admin` — acessos por dia/semana/mês,
quem acessou e quando, bases mais favoritadas, favoritos por usuário (e
o inverso), histórico de quais tabelas tiveram profile executado.

### O que foi feito

Nova aba "Uso do Hub" em `/admin`, com três seções:

1. **Acessos ao Hub** — login era 100% stateless até aqui (JWT em
   cookie, nenhum registro em lugar nenhum). Nova coleção Firestore
   `login_events/{auto_id}` (email + `logged_in_at`), gravada
   best-effort em `POST /auth/callback` (falha na gravação nunca
   derruba o login). KPIs (hoje/semana/mês + usuários únicos), gráfico
   de tendência diária, tabela de acessos recentes.
2. **Favoritos entre usuários** — `domains/favorites` só tinha visão
   por usuário (`users/{email}/favorites/`); nova leitura via
   `collection_group("favorites")` agrega todo mundo. "Bases mais
   favoritadas" (top 10) + drill-down bidirecional (usuário → itens
   favoritados, base → usuários que favoritaram), pedido explícito do
   usuário ("nos dois sentidos").
3. **Atividade de profiling** — `domains/quality/history_repository.py`
   já gravava `executed_by`/`executed_at` por tabela; ganhou também
   `project_id`/`dataset_id`/`table_id` dentro de cada run (antes só
   existiam implícitos no ID do documento-pai, sem como parsear de volta
   com segurança) pra permitir uma leitura global via
   `collection_group("runs")`.

### Decisões desta sessão

**Decisão 1 — Login events em Firestore, não Cloud Logging**
- Perguntado e confirmado com o usuário. Cloud Logging já mordeu o
  projeto duas vezes (`roles/logging.privateLogViewer` — falha
  silenciosa sem essa role, ver `docs/onboarding-cliente.md`); Firestore
  é consistente com o resto do app (favorites/history/admin) e muito
  mais simples de agregar por dia/semana/mês.

**Decisão 2 — Drill-down bidirecional de favoritos, não só contagem**
- Perguntado e confirmado com o usuário ("nos dois sentidos"). Resolvido
  com um único endpoint retornando a lista achatada de favoritos (com
  `owner_email` derivado do path do Firestore) — o front-end agrupa dos
  dois lados a partir do mesmo payload, sem precisar de dois endpoints
  nem agregação server-side.

**Decisão 3 — `unique_users` além de `login_count` por bucket**
- Não pedido explicitamente, mas adicionado como boa prática de mercado
  (padrão DAU/WAU/MAU) — mesma passada em Python que agrupa por
  dia/semana/mês já computa isso sem custo extra de leitura no Firestore.

**Decisão 4 — Agregações via `collection_group` sem `order_by` combinado**
- Mesma disciplina já estabelecida em `domains/admin/repository.py::
  list_access_requests`: evita depender de índice composto/de
  collection-group manual no Firestore (que falharia silenciosamente em
  produção sem esse índice existir) — ordenação e agrupamento sempre em
  Python.

### Status até o momento
- Backend: 545 testes unitários, 100% passando, `ruff check`/
  `ruff format --check` sem erros.
- Frontend: `tsc --noEmit` limpo, `pnpm lint` (biome) sem erros,
  `pnpm build` concluído.
- Validação visual (gráficos, drill-down, KPIs) fica a cargo do usuário
  após deploy em dev — sem ferramenta de browser neste ambiente.

---

## 4 ajustes de UX: busca no menu, contraste, voltar no admin, favoritos por dataset/apelido

Branch `feat/sprint-3.2`. Usuário validou a reorganização da sidebar por
serviço e o admin em uso real e voltou com 4 pedidos, em ordem de
prioridade declarada.

### O que foi feito

1. **"Buscar tabelas" dentro de "Datasets disponíveis"** — era um link
   solto acima das seções da sidebar; movido pra dentro da seção, como
   primeiro item.
2. **Contraste de `--muted-foreground` corrigido** — `#5b626c` sobre
   `#1d1d1b` media ~2.74:1 (WCAG AA exige ≥4.5:1 pra texto normal),
   calculado via fórmula de luminância relativa (sRGB → linear →
   contraste), não só "parecia ruim". Trocado por `#8f96a1` (mesma
   família azul-acinzentada, 5.66:1 contra `--background`, 4.82:1
   contra `--card`, fundo real da sidebar). Atualizado em `index.css`
   **e** em `docs/skills/frontend.md` juntos — a skill é a fonte de
   verdade documentada da paleta dp6 e precisa ficar sincronizada.
3. **Botão de voltar no `/admin`** — primeira tela do app com esse
   padrão; link discreto (`ArrowLeft` + "Voltar") pra `/`.
4. **Favoritos com dois níveis (tabela/dataset) + apelido** — reescrita
   do domínio `favorites`: `FavoriteTable` virou `Favorite`
   (`table_id: str | None`, `None` = favorito do dataset inteiro) e
   ganhou `nickname: str | None`. Nova rota
   `DELETE /favorites/{project_id}/{dataset_id}` (nível dataset,
   coexiste com a de nível tabela por diferença de segmentos de path).
   Estrela de favoritar dataset adicionada em duas navegações novas: a
   lista "Datasets disponíveis" da sidebar e o cabeçalho de
   `CatalogDatasetPage.tsx`. Seção "Favoritos" da sidebar dividida em
   "Tabelas favoritas" / "Datasets favoritos". Apelido editável inline
   (lápis no hover → input, sem dialog) via `FavoriteNickname.tsx`.

### Decisões desta sessão

**Decisão 1 — `added_at` e `nickname` preservados em upsert repetido**
- Mesmo racional já usado em `domains/admin/repository.py::upsert_user`
  pra `created_at`: sem preservar `added_at`, editar só o apelido de um
  favorito existente reordenaria a lista (ordenada por `added_at`
  desc) — efeito colateral indesejado de uma ação que devia ser só
  renomear. `nickname` ganhou semântica de três estados na chamada de
  `add_favorite`, não dois: `None` = não mexe no apelido já salvo
  (o toggle de favoritar/desfavoritar nunca passa `nickname`, e não
  pode apagar um apelido existente sem querer); `""` = remove o
  apelido de propósito; qualquer outra string = define o apelido.

**Decisão 2 — Contraste corrigido com medição, não só percepção**
- Perguntado e confirmado com o usuário: atualizar `index.css` e
  `docs/skills/frontend.md` juntos. O valor novo foi calculado (não
  escolhido a olho) pra garantir ≥4.5:1 contra os fundos reais onde o
  token aparece.

**Decisão 3 — Apelido editado inline, sem dialog**
- Perguntado e confirmado com o usuário: lápis aparece no hover do
  item (`group-hover`), clique troca o texto por um `Input` autofocado
  ali mesmo — consistente com a preferência por menos fricção nessa
  interação específica (diferente do padrão de dialog já usado em
  `AdminUsersTab.tsx`, mantido lá por ser uma edição com mais campos).

### Status até o momento
- Backend: 534 testes unitários, 100% passando, `ruff check`/`ruff
  format --check` sem erros.
- Frontend: `tsc --noEmit` limpo, `pnpm lint` (biome) sem erros,
  `pnpm build` concluído.
- Validação visual (legibilidade do contraste, favoritos de dataset,
  apelido inline, botão voltar) fica a cargo do usuário após o deploy
  — sem ferramenta de browser neste ambiente.

---

## Admin v1.1: projetos públicos, visão por projeto, solicitação de acesso, mensagens de erro

Branch `feat/finops-budget`. Extensão do ACL v1.0 (ADR-009) — usuário
testou em produção e voltou com três pedidos.

### O que foi feito

1. **Mensagens de erro visíveis** — `ProjectSelector.tsx` mostrava "sem
   acesso" só como um ícone com tooltip no hover. Trocado por um painel
   flutuante (`ApiErrorNotice`, mesmo componente usado no resto do app,
   que ganhou uma prop `action` opcional) com o texto completo e, quando
   o erro é `project_not_authorized`, um botão "Solicitar acesso".
2. **Visão por projeto + projeto público** — nova coleção Firestore
   `hub_projects/{project_id}` (`is_public`), eixo independente do
   `allowed_projects` de cada usuário — libera geral, inclusive quem
   ainda não tem cadastro no Hub. Nova aba "Por projeto" em `/admin`
   (visão inversa da aba "Por usuário": escolhe um projeto, vê/gerencia
   quem tem acesso), via `array_contains_any` no Firestore.
3. **Solicitação de acesso self-service** — `POST /api/v1/access-requests`
   (fora de `/admin`, qualquer usuário autenticado pede pra si mesmo),
   nova aba "Solicitações" em `/admin` com aprovar/negar, badge de
   contagem no ícone de admin do Topbar (`refetchInterval` de 60s, sem
   WebSocket).

### Decisões desta sessão

**Decisão 1 — Badge discreto no Topbar, não banner intrusivo**
- Perguntado e confirmado com o usuário: aviso de pendências como
  contador no ícone de admin já existente, não uma faixa que aparece
  toda vez que um admin abre qualquer página.

**Decisão 2 — `hub_projects` como conceito novo, não widening do wildcard**
- Perguntado e confirmado: "liberado a todos" é uma coleção própria por
  projeto, checada antes do usuário em `has_project_access` — cobre
  "usuários futuros" de verdade (a checagem roda no momento do acesso,
  não fica gravada na lista de cada usuário no momento da liberação).

**Decisão 3 — Filtro de índice composto do Firestore evitado por design**
- `list_access_requests`/`has_pending_request` foram desenhadas pra usar
  no máximo um campo de igualdade no `.where()` — Firestore exige índice
  composto manual pra combinar múltiplos filtros/order_by em campos
  diferentes, e isso falharia silenciosamente em produção sem esse
  índice existir. Ordenação e filtros extras rodam em Python sobre o
  resultado (coleções pequenas o bastante pra isso não pesar).

**Decisão 4 — Revogar acesso explícito não desliga `is_public`**
- Eixos deliberadamente independentes: `DELETE .../projects/{id}/users/{email}`
  só mexe na lista do usuário. Se o projeto está público, ele continua
  acessível por esse caminho — documentado explicitamente pra não virar
  confusão futura ("removi o acesso mas a pessoa ainda entra").

### Status até o momento
- Backend: 522 testes unitários, 100% passando, `ruff check`/`ruff
  format` limpos
- Frontend: `biome check`, `tsc --noEmit`, `vite build` limpos
- Validação end-to-end (badge de pendentes, aprovar/negar, projeto
  público liberando usuário sem cadastro) fica a cargo do usuário depois
  do deploy — sem ferramenta de browser neste ambiente

---

## Controle de acesso por usuário × projeto + tela de admin (novo, ADR-009)

Branch `feat/finops-budget`. Fora do roadmap de observabilidade
(`docs/prd.md`) — mudança de plataforma/segurança, motivada pelo usuário
ao perceber que o Hub, ao ser vinculado a múltiplos projetos-cliente,
não tinha nenhuma barreira impedindo um usuário autenticado de digitar
o `project_id` de um cliente que não é o dele e ver os dados.

### O que foi feito

Segunda camada de autorização em cima do login (Google OAuth) existente:
- Novo domínio `domains/admin/` (Firestore, coleção `hub_users/{email}`)
  com `is_admin`/`allowed_projects` (aceita wildcard `"*"`).
- `core/auth.py::require_project_access` substitui `get_current_user`
  como gate de router em todo endpoint com `project_id` no path
  (catalog, freshness, profiling, quality, lineage, pii, access,
  finops, projects — 9 routers, uma linha cada) — nega antes de
  qualquer chamada real ao BigQuery/Cloud Logging, mesmo que a SA de
  runtime tenha IAM no projeto.
- `core/auth.py::require_admin` gateia a tela `/admin` nova
  (`features/admin/AdminPage.tsx`) — CRUD de usuários administrados,
  sem senha nova, sem Cloud Run novo, reaproveitando 100% da sessão
  OAuth já existente. Link condicional no Topbar (`ShieldCheck`), só
  visível pra quem `is_admin`.
- `scripts/seed_admin.py` novo — bootstrap do primeiro admin (problema
  de ovo-e-galinha: `hub_users` vazio bloqueia `/admin` pra todo mundo,
  ninguém consegue criar o primeiro registro pela UI).
- Spec completa em `docs/specs/admin.md`, decisão arquitetural em
  `docs/adr/ADR-009-acl-usuario-projeto.md` (complementa ADR-006, não
  substitui).

### Decisões desta sessão

**Decisão 1 — Firestore, não Secret Manager, pro ACL**
- A SA de runtime já lê/escreve Firestore hoje (favoritos, histórico) —
  zero IAM novo. Secret Manager é versionado/imutável por natureza,
  inadequado pra CRUD via UI; e o `@lru_cache` sem TTL de
  `get_oauth_allowlist` (Secret Manager) já causou staleness real nesta
  mesma sessão. Leitura de ACL é sempre fresca, sem cache, de propósito.

**Decisão 2 — Login (OAUTH_ALLOWLIST) continua como está, mas sem dar
acesso implícito a projeto**
- Perguntado explicitamente ao usuário se o allow-por-domínio do login
  deveria ser removido (exigindo cadastro individual de todo mundo,
  inclusive time interno) ou mantido só pra login, sem acesso a projeto
  por padrão. Escolhida a segunda opção — menos risco de lockout no dia
  do deploy, mesmo nível de segurança de projeto (quem só passa pelo
  domínio ainda precisa de liberação explícita de um admin pra ver
  qualquer `project_id`).

**Decisão 3 — Wildcard `"*"` em vez de lista exaustiva pra acesso total**
- Perguntado e confirmado com o usuário — admins/líderes que precisam
  ver todos os projetos-cliente usam `"*"` em vez de listar cada um.
  Menos auditável que lista exaustiva, mas muito mais fácil de manter;
  aceito conscientemente.

**Decisão 4 — `is_admin` só populado em `GET /auth/me`, nunca em
`get_current_user`**
- `get_current_user` roda em todo request autenticado — não ganha I/O
  novo (uma leitura Firestore a mais em toda chamada de
  catalog/freshness/etc. seria desperdício). Consequência: `is_admin`
  só é confiável quando `UserInfo` vem de `/auth/me`; `require_admin`
  nunca confia nesse campo, sempre faz checagem fresca própria.

**Decisão 5 — Bloqueio de remover o último admin**
- `upsert_user`/`delete_user` recusam (`LastAdminLockoutError`, 400)
  remover `is_admin` do último administrador restante — sem isso, um
  erro de operação zeraria os admins e ninguém mais conseguiria abrir
  `/admin` pra reverter.

### Investigação técnica relevante

Antes de trocar a dependency de 9 routers, confirmado lendo o código
instalado do FastAPI (`0.141.1`) que uma dependency declarada a nível
de `APIRouter(dependencies=[Depends(fn)])` resolve path params (ex:
`project_id`) da mesma forma que uma dependency de endpoint — o `path`
usado na resolução é o da rota real (prefixo + path), não um path
genérico do router. Isso permitiu trocar `get_current_user` por
`require_project_access` com uma linha por router, sem tocar em nenhum
endpoint individual.

### Status até o momento
- Backend: 492 testes unitários, 100% passando, `ruff check`/`ruff
  format` limpos
- Frontend: `biome check`, `tsc --noEmit`, `vite build` limpos
- Validação end-to-end (login real, `/admin` funcionando, 403 num
  projeto sem ACL) depende do bootstrap do primeiro admin em dev —
  fica a cargo do usuário depois do deploy (sem ferramenta de browser
  neste ambiente)

---

## Reorganização de navegação: hierarquia por serviço observável

Branch `feat/finops-budget`. Não é uma fase nova — mudança estrutural na
sidebar pedida pelo usuário, preparando o Hub pra observar outros
serviços GCP além de BigQuery no futuro (hoje é o único).

### O que foi feito

`DatasetSidebar.tsx` reestruturada em dois níveis: um nó de topo por
serviço observável (`SidebarServiceGroup` — ícone + label + chevron,
visualmente mais forte que as subseções) contendo tudo que já existia
(Buscar tabelas, Governança, FinOps, Datasets disponíveis, Favoritos,
Recentes) como `SidebarSection`s dentro dele. "Governança" e "FinOps"
eram headers estáticos (`<p>`), viraram seções recolhíveis de verdade —
única mudança de comportamento em cima do que já existia, além do
aninhamento.

**Estado inicial:** o grupo "BigQuery" abre por padrão (é o único
serviço hoje — começar fechado deixaria a sidebar vazia no primeiro
acesso); todas as subseções de dentro começam **recolhidas**, sem
exceção (inclusive Datasets disponíveis, que antes abria por padrão) —
decisão explícita do usuário, confirmada via pergunta direta sobre o
estado do nó de topo antes de implementar.

Próximo serviço observável (quando existir) vira um `SidebarServiceGroup`
irmão do de BigQuery, mesmo componente reaproveitado.

### Status
- Frontend: `biome check`, `tsc --noEmit`, `vite build` limpos
- Sem mudança de backend/API — só reorganização de UI
- Validação visual em browser não feita nesta sessão (sem ferramenta de
  browser disponível no ambiente) — pendente de validação do usuário

---

## Fase 4 — FinOps: sugestão de tipo de coluna (concluída, 1ª parte da 3ª frente)

Branch `feat/finops-budget` (mesma branch da 2ª frente, budget — ainda sem
PR pra `main`). Primeira metade de "otimizações sugeridas"
(`docs/prd.md`, 4.3) — a segunda metade (clustering) foi deliberadamente
deferida, ver "Decisão 1" abaixo.

### O que foi feito

Terceira aba em `/finops` ("Tipos de coluna"): detecta colunas `STRING`
cujos valores amostrados são compatíveis com um tipo mais estreito
(`INT64`, `FLOAT64`, `BOOL`, `DATE`, `DATETIME`, `TIMESTAMP`), com
estimativa de economia de storage mensal. Novo par de endpoints —
`POST /finops/{project}/column-type-suggestions/estimate` (dry-run
gratuito) e `.../run` (execução real) — projeto inteiro, não por tabela.

### Decisões desta sessão

**Decisão 1 — Onde a feature mora: nova aba no scanner de desperdício
(projeto inteiro), não no modal de profiling**
- Diferente do scanner de desperdício e do budget (100% metadado/audit
  log, custo $0), esta feature precisa amostrar dado real via
  `TABLESAMPLE` — mesmo custo real que `pii`/`quality` já têm. Perguntado
  explicitamente ao usuário se a feature deveria viver como aba nova no
  scanner de desperdício (visão de projeto inteiro) ou como aba nova no
  modal de profiling (por tabela, mesmo lugar de PII) — escolhido o
  scanner de desperdício. Consequência: fluxo em duas etapas (dry-run
  "Estimar custo" antes de "Escanear", nunca automático ao abrir a tela)
  pra nunca cobrar do usuário sem ele decidir antes olhando pro número.

**Decisão 2 — Nunca sugerir sem economia real, nem com confiança parcial**
- Só vira sugestão se (a) 100% dos valores não-nulos **amostrados**
  batem no tipo candidato (não um limiar configurável tipo "a maioria" —
  aplicar um tipo mais estreito numa coluna que não converte 100%
  quebraria dado real) e (b) a troca de fato economiza bytes
  (`avg_current_bytes > bytes fixos do tipo sugerido` — uma `STRING`
  curta como `"1"` já ocupa menos espaço que um `INT64` de 8 bytes fixos,
  então sugerir a troca nesse caso pioraria o storage). Mesma disciplina
  de "nunca superestimar economia" já aplicada ao scanner de
  particionamento (Fase 4, 1ª frente).

**Decisão 3 — Clustering deferido, não faz parte desta v1**
- Diferente de tipo de coluna (comparação de bytes é objetiva e
  determinística), sugerir clustering exigiria inferir quais colunas
  aparecem com mais frequência em `WHERE`/`GROUP BY`/`JOIN` — só
  disponível via texto livre de query nos audit logs, sem um parser de
  SQL de verdade isso vira heurística de regex frágil. Documentado como
  "fora do escopo" em `docs/specs/finops-column-types.md`, não
  esquecido — merece spec e conversa própria sobre nível de confiança
  aceitável antes de implementar.

**Decisão 4 — Orçamento de tempo por lote, não por tabela**
- `/run` escaneia todas as tabelas elegíveis do projeto em paralelo
  (`ThreadPoolExecutor`, `max_workers=4` — mais conservador que os
  `max_workers=8` de operações gratuitas do domínio, porque aqui cada
  query tem custo real). Orçamento total de 120s pro lote inteiro; se
  esgotar no meio, retorna as tabelas já escaneadas com um `warning` de
  resultado parcial em vez de lançar erro — parcial ainda tem valor aqui
  (lista de oportunidades), diferente de um scan de tabela única em
  `pii`/`quality`, onde parcial não faz sentido.

### Correções pós-validação em dev (mesma branch, v1.1 da spec)

Usuário validou a v1.0 em dev e voltou com dois pedidos, ambos
implementados na mesma sessão:

**1 — Escopo de execução (obrigatório pra produção)**
- Rodar em todas as tabelas de um projeto real é inviável — a v1.0
  fazia isso por padrão. `ColumnTypeScanRequest` ganhou `tables:
  list[str] | None` (`"dataset_id.table_id"`); com escopo explícito,
  `_resolve_eligible_tables` **pula** `repository.list_all_table_refs`
  inteiramente (não enumera o projeto todo só pra filtrar depois).
  Frontend: novo `ColumnTypeScopePicker` (checkbox por dataset — marca
  todas as tabelas dele — que expande em checkboxes por tabela pra
  refinar), com `useDatasets`/`useTables` do catálogo reaproveitados
  (nenhum endpoint novo pra listar datasets/tabelas). Botões
  "Estimar custo"/"Escanear" desabilitados até haver seleção — decisão
  deliberada de não default pra "projeto inteiro" nunca aparecer como
  opção fácil na UI, mesmo a API aceitando `tables=None` por
  flexibilidade/testes.
- Novo componente `components/ui/checkbox.tsx`, adicionado via
  `npx shadcn add checkbox` (primeira vez que esse primitive é usado no
  Hub).

**2 — Também disponível por tabela, dentro do modal de profiling**
- Nova aba "Tipos de coluna" em `ProfilingDialog.tsx`, ao lado de
  Schema/Análise/Histórico/Lineage/PII/Acesso — mesmo padrão de
  `PiiTab.tsx`, mas chamando os mesmos endpoints de projeto com escopo
  implícito de uma tabela só (`tables: ["{dataset}.{tabela}"]`). Sem
  seletor aqui — não faz sentido escolher escopo quando o modal já é
  sobre uma tabela específica.
- Extraído `ColumnTypeSuggestionBadges` (badges de sugestão) como
  componente compartilhado entre a aba de projeto e a aba do modal, pra
  não duplicar a lógica de exibição.

### Status até o momento
- Backend: 468 testes unitários, 100% passando, `ruff check`/`ruff
  format` limpos
- Frontend: `biome check`, `tsc --noEmit`, `vite build` limpos
- Ainda não validado em dev nesta rodada (v1.1) — v1.0 já tinha sido
  validada
- Falta: sugestão de clustering (deferida, ver Decisão 3) — depois disso
  a Fase 4 fecha

---

## Fase 4 — FinOps: budget de custo (em andamento, 2ª de 3 frentes)

Branch `feat/finops-budget`, criada a partir de `feat/finops-waste-scanner`
(PR #19 do scanner de desperdício ainda não mergeado — mesma decisão de
não bloquear a próxima frente esperando review, já usada entre
sprint-3.2 e o scanner).

### O que foi feito

Quatro visões de custo do mês corrente em `GET /api/v1/finops/{project}/budget`,
todas derivadas dos **mesmos audit logs** que o scanner de desperdício já
lê — nenhuma integração nova, nenhuma role de IAM nova:
- **Custo por dataset**: soma `totalBilledBytes` de todo job que
  referenciou uma tabela daquele dataset no mês.
- **Top N queries mais caras**: job_id, quem rodou, tabelas tocadas,
  texto da query (truncado em 2000 caracteres), ordenadas por custo.
- **Top N gastadores**: humano vs. service account, custo total,
  contagem de jobs.
- **Projeção do mês**: custo até agora ÷ dias corridos do mês × dias no
  mês.

Nova página `/finops/budget`, com stat cards de projeção + três tabelas
(reaproveitando `useTableFilterSort`, mesmo hook do scanner de
desperdício). Sidebar ganhou uma segunda entrada no grupo FinOps.

### Erros e decisões desta sessão

**Decisão 1 — Descartada a ideia de usar BigQuery Billing Export**
- Cogitado inicialmente (e chegou a ser mencionado errado numa resposta
  pro usuário) que essa frente precisaria de uma fonte de dados nova
  (Cloud Billing Export ou API). Corrigido antes de implementar: Billing
  Export só quebra custo por **projeto + SKU**, nunca por dataset —
  não resolveria a pergunta que esta feature responde, mesmo se
  configurado. A granularidade certa só existe nos audit logs de job
  (mesma fonte já integrada), então nada precisou ser configurado a
  mais no projeto do cliente.
- Reforça a mesma premissa já embutida em `domains/quality` e no
  scanner de desperdício: a estimativa é on-demand (bytes escaneados ×
  preço/TiB) — não reflete gasto real em projetos com preço flat-rate/
  Editions. Documentado explicitamente em `docs/specs/finops-budget.md`
  por ser o lugar onde um número errado mais provavelmente vira decisão
  financeira.

**Decisão 2 — SA do próprio Hub CONTA aqui, diferente do mapa de acesso**
- `domains/access` exclui a SA de runtime do Hub porque ali a pergunta é
  "quem consome essa tabela de fora" (inspecionar pelo Hub não é
  consumo externo real). Budget pergunta outra coisa — "quanto está
  sendo gasto de verdade" — e profiling/PII rodados pela UI custam
  dinheiro real, então devem contar. Nenhuma exclusão aplicada aqui,
  documentado o contraste explicitamente pra não parecer inconsistência
  acidental entre os dois domínios.

**Decisão 3 — `ScanEvent` estendido em vez de mais um parser duplicado**
- `job_id`/`principal_email`/`query_text` foram adicionados ao mesmo
  `ScanEvent` que o scanner de desperdício já usa (com default vazio,
  no fim da dataclass, pra não quebrar as chamadas existentes) em vez
  de criar uma quarta cópia quase idêntica do parsing de audit log —
  as duas funcionalidades do domínio finops compartilham o mesmo
  repository.py.

### Correções e melhorias pós-review (mesma branch, v1.1 da spec)

Ticket do usuário reportando dois bugs e duas melhorias na tela de
budget. Ver `docs/specs/finops-budget.md` (v1.1) para o detalhe completo.

**Bug real encontrado durante a investigação — regiões fantasma**
- O ticket original descrevia a causa como "busca custo em todas as
  regiões do `BQ_REGIONS` via `INFORMATION_SCHEMA.JOBS`" — verificado
  via grep que isso é **factualmente incorreto**: `get_budget()` nunca
  iterou regiões nem leu `INFORMATION_SCHEMA.JOBS`, só Cloud Logging.
  Perguntado ao usuário se o sintoma ($0.07 fantasma) era real ou
  hipotético antes de implementar o fix descrito — confirmado real.
- Causa raiz investigada com `gcloud logging read` (5000 eventos reais
  de agosto/2026 em `observability-hub-dev`) + replay da lógica de
  agregação: `discover_regions()`/`list_all_table_refs()`/
  `get_date_like_columns()` (usadas por catalog/freshness/finops para
  descoberta de metadados a custo ~zero) rodam
  `` `project.region-X.INFORMATION_SCHEMA.*` `` — o audit log dessas
  queries tem `datasetId="region-US"` e `tableId="INFORMATION_SCHEMA.*"`,
  contado como se fosse um dataset real. **4989 de 5000 jobs amostrados
  (99,8%) eram esse ruído.**
- Fix: `repository._parse_table_ref()` descarta `table_id` que comece
  com `INFORMATION_SCHEMA.` na origem (beneficia todas as funções do
  domínio); `get_budget()` pula o evento inteiro quando não sobra
  nenhuma tabela real do projeto após o filtro.

**Bug 2 — sobreposição visual em "queries mais caras"**
- Texto da query inline na célula colidia visualmente com a coluna de
  tabelas. Fix: texto oculto por padrão, toggle "Ver query"/"Ocultar
  query" por linha expande um bloco `SqlPreview` (componente já
  compartilhado com o preview de SQL do profiling) abaixo da linha.

**Melhoria 1 — agrupamento configurável**
- `by_dataset`/`top_spenders` (visões fixas da v1.0) substituídos por
  `groups: CostGroup[]` + `group_by: table|user|day|month|year`. O
  ticket original descrevia isso via `GROUP BY` em SQL sobre
  `INFORMATION_SCHEMA.JOBS` — reimplementado sobre a arquitetura real
  do domínio (Cloud Logging, sem query BQ nova, sem custo/IAM
  adicional): `service._group_keys()` deriva a chave a partir do
  `ScanEvent` já em memória.

**Melhoria 2 — layout em duas abas**
- `BudgetPage.tsx` reescrita: seções empilhadas → `Tabs` do shadcn/ui
  ("Custo por agrupamento" com pill buttons de `group_by` + total no
  rodapé via `TableFooter`; "Queries mais caras" com o toggle do Bug 2).

### Status até o momento
- Backend: 431 testes unitários, 100% passando, `ruff check`/`ruff
  format` limpos
- Frontend: `biome check`, `tsc --noEmit`, `vite build` limpos
- Commitado na branch `feat/finops-budget`, push e PR **não** feitos —
  aguardando validação manual em dev e aprovação do usuário
- Falta a 3ª frente de FinOps (otimizações sugeridas) e a lacuna da v1
  do PII (adiada, não esquecida)

---

## Fase 4 — FinOps: scanner de desperdício (concluída, PR #19)

Branch `feat/finops-waste-scanner`, criada a partir de `feat/sprint-3.2`
(PR #18 da Sprint 3.2 ainda não mergeado em `main` no momento desta
sessão — decisão consciente do usuário pra não bloquear o início da
Fase 4 esperando review). Primeira das três frentes do roadmap de
FinOps (`docs/prd.md`): scanner de desperdício. Budget/custo por
dataset e otimizações sugeridas ficam pra sessões futuras — a lacuna da
v1 do PII (detecção de nome de pessoa, classificação de sensibilidade
por tabela) foi explicitamente adiada, não faz parte deste trabalho.

### O que foi feito

**Novo domínio `domains/finops`** — duas checagens independentes:

1. **Tabelas sem uso** (`GET /finops/{project}/unused-tables?min_days_unused=30|60|90`):
   tabelas sem leitura conhecida nos audit logs, com custo de storage
   evitável estimado via `size_bytes × preço/GB` (BigQuery já rebaixa
   pra tarifa long-term sozinho depois de 90 dias sem modificação — a
   estimativa usa a tarifa certa conforme `last_modified_time`, não uma
   única tarifa fixa).
2. **Candidatas a particionamento** (`GET /finops/{project}/partition-candidates`):
   tabelas grandes (≥1GB), sem partição, com coluna
   `DATE`/`DATETIME`/`TIMESTAMP` candidata. Estimativa de economia
   **ancorada em custo real observado** (`jobStatistics.totalBilledBytes`
   dos audit logs, campo que nenhum outro domínio lia ainda) em vez de
   uma suposição do zero — só aparece quando há custo real na janela de
   30 dias, sempre como faixa (30%–70% de redução), nunca um número
   único, com disclaimer explícito. Ver "Decisão 1" abaixo — foi uma
   escolha de design discutida em detalhe com o usuário antes de
   implementar, pra não gerar frustração com uma economia superestimada.

Nova página de frontend `/finops` (fora do modal de profiling, diferente
de PII/lineage/access — é uma visão de projeto inteiro, não de uma
tabela só, mesmo padrão de `/orphans`), duas abas (Tabelas sem uso /
Candidatas a particionamento), link novo no sidebar.

### Erros e decisões desta sessão

**Decisão 1 — Estimativa de economia de particionamento: nunca fabricar
um número de aparência precisa sobre suposição não verificada**
- Pedido inicial era "estimativa heurística aproximada". Discutido com o
  usuário até chegar num desenho que ancora a base em dado real (custo
  de scan já observado nos audit logs, não uma frequência de query
  assumida) e só extrapola daí — e mesmo assim como faixa, não um valor
  único, com o disclaimer sempre visível. Justificativa do usuário:
  "sem superestimar a economia para não gerar frustração" — um número
  de decisão financeira errado é pior que não mostrar número nenhum.
- Limitação assumida e documentada: se a query faz `JOIN` com outra
  tabela grande, o custo mostrado é da query inteira, não isolado só
  daquela tabela — sem tentativa de dividir a proporção, dado que não
  está disponível no audit log.

**Decisão 2 — Reaproveitar `core/bigquery.py::get_tables_metadata` em
vez de duplicar mais uma vez**
- Diferente de lineage/pii/access (que duplicam parsing de audit log
  entre si, por serem domínios distintos), a enumeração de tabelas com
  tamanho/partição/`last_modified_time` já vive em `core/bigquery.py`
  (`get_table_cached`/`get_tables_metadata`, usado por catalog e
  freshness) — reaproveitada direto aqui, sem duplicar, porque é
  infraestrutura compartilhada (`core/`), não código de outro domínio.
  A regra de "domínios não importam um do outro" nunca foi sobre
  proibir reaproveitar `core/`.
- `domains/finops/repository.py` ainda duplica o parsing de audit log
  em si (terceira vez, depois de lineage e access) — o que muda é o
  campo novo extraído (`jobStatistics.totalBilledBytes`) e que não
  precisa de `destination_table`/`principal_email`, só leitura.

### Status até o momento
- Backend: 411 testes unitários, 100% passando, `ruff check`/`ruff
  format` limpos
- Frontend: `biome check`, `tsc -b`, `vite build` limpos
- Validado em dev pelo usuário — incluindo dois bugs pegos e corrigidos
  ao vivo depois do deploy: `min_days_unused` como `Literal[int,...]`
  causando 422 (trocado por `IntEnum`) e retry do TanStack Query
  insuficiente pra sobreviver ao cold start do Cloud Run em dev
  (`minScale=0`, decisão consciente do usuário de não mudar).
- Aproveitado o momento pra reorganizar o sidebar em grupos e adicionar
  filtro/ordenação reutilizável (`hooks/useTableFilterSort`) nas tabelas
  de "Tabelas sem consumidor" e do próprio scanner.
- **PR #19 aberto** (`feat/finops-waste-scanner` → `main`, diff limpo
  contra `main` já com a Sprint 3.2 mergeada).
- Faltam a 3ª frente de FinOps (otimizações sugeridas) e a lacuna da v1
  do PII (adiada, não esquecida)

---

## Sprint 3.2 — Qualidade, Discovery e melhorias de UX em tabelas (concluída)

Branch `feat/sprint-3.2`, a partir de `main` pós-PR #17. Sete itens
planejados; sete implementados e testados nesta sessão (o item de score
de qualidade foi implementado, validado e depois removido por completo a
pedido do usuário — por isso a numeração abaixo chega a 6 novas
features, não 7).

### O que foi feito
1. **Filtros e ordenação client-side**: busca por nome + filtro por tipo/
   status SLA + colunas ordenáveis, sem mudança de backend, em
   `AssetsTable` (catálogo), `TableFreshnessTable` (tabelas de um
   dataset) e `DatasetFreshnessTable` (datasets de um projeto, adicionado
   depois a pedido do usuário). Componente `SortableTableHead`
   compartilhado, promovido de um componente que só existia na busca.
2. **Score de qualidade por tabela — implementado e revertido**: média
   ponderada de completude/freshness/duplicatas/documentação (0-100),
   persistida em Firestore por profiling, badge na tabela de ativos.
   Validado em dev e então removido por completo por decisão do usuário.
3. **Histórico de qualidade**: cada profiling grava um snapshot em
   Firestore (máximo 30 runs por tabela); aba "Histórico" no modal com
   gráfico de linha (`recharts`), tabela de runs expansível por coluna e
   alerta de degradação (>10pp de queda de densidade vs. run anterior).
4. **Lineage e tabelas órfãs**: novo domínio a partir de audit logs de
   BigQuery (Cloud Logging) — upstream/downstream de uma tabela e lista
   de órfãs (sem consumidor conhecido). Limitação de visibilidade tratada
   com honestidade: resultado vazio vem com aviso explicando que pode ser
   falta de atividade OU audit logs desabilitados (indistinguível via
   API), em vez de afirmar uma certeza que a implementação não tem.
   **Evoluído na mesma sessão para v2** (spec `docs/specs/lineage.md`):
   upstream/downstream deixou de ser 1 hop direto e virou cadeia
   transitiva completa (ex: `daily_summary` ← `ga4_sessions` ←
   `ga4_events`), representada como grafo dirigido (BFS bidirecional em
   `domains/lineage/service.py`, `max_hops` configurável, padrão 8),
   atravessando projetos GCP quando necessário (nó vira "acesso negado"
   em vez de derrubar a requisição se a SA não tiver Logging no projeto
   não-raiz). Frontend passou de duas listas planas para um diagrama
   (`LineageGraph.tsx`, `@xyflow/react` + `dagre` para layout), sempre
   com o prefixo `project.dataset.table`. Validado em dev pelo usuário
   após o deploy — cadeia completa (`ga4_events → ga4_sessions →
   daily_summary`) confirmada contra audit logs reais.
5. **Fingerprinting de PII**: novo domínio `domains/pii`, nova aba "PII"
   no mesmo modal de profiling (`ProfilingDialog.tsx`). Duas camadas:
   heurística de nome de coluna (grátis, `INFORMATION_SCHEMA.COLUMNS`) +
   amostragem real via `TABLESAMPLE SYSTEM` com `REGEXP_CONTAINS`/
   `COUNTIF` por coluna (email, CPF, CNPJ, telefone BR, CEP, cartão de
   crédito — conjunto BR completo, a pedido do usuário). Coluna só é
   sinalizada pela amostra se ≥ `match_threshold_pct` (padrão 5%) dos
   valores não-nulos amostrados baterem no regex, não "qualquer match" —
   reduz falso positivo de coincidência isolada. Mesmo padrão de
   `/estimate`+`/run` (dry-run antes de executar) e cache de 5min do
   domínio `quality`, reaproveitados ao máximo. Matching roda inteiramente
   em SQL dentro do BigQuery — a API nunca recebe nem loga um valor de
   coluna real, só contagens agregadas. Validado em dev pelo usuário.
6. **Mapa de acesso**: novo domínio `domains/access`, nova aba "Acesso"
   no mesmo modal de profiling. Reaproveita a mesma fonte de dados do
   lineage (audit logs de jobs BigQuery via Cloud Logging), sob um
   ângulo diferente — "quem tocou nessa tabela" em vez de "de onde vem/
   pra onde vai o dado". Agrega por `principal_email`: último acesso,
   contagem, tipo (leitura/escrita) e se é usuário humano ou service
   account (heurística: email termina em `gserviceaccount.com`).
   Diferente do lineage, uma auto-referência (ex: MERGE lendo e
   escrevendo a própria tabela) **conta** como acesso real, em vez de
   ser excluída — ali representaria um ciclo sem sentido, aqui é
   exatamente o tipo de evento que o mapa de acesso quer mostrar.
   Endpoint único (`GET /{project}/{dataset}/{table}`, sem custo de BQ,
   só Cloud Logging), sem fluxo estimar→rodar como PII/profiling — só
   carrega ao abrir a aba, como o Lineage. Fecha os 7 de 7 itens
   planejados da sprint.

### Erros e decisões desta sessão

**Decisão 1 — Score de qualidade removido depois de validado**
- O usuário pediu a remoção completa (backend + frontend) do score de
  qualidade depois de já ter validado a feature em dev, sem registrar o
  motivo. Revertido preservando `core/sla.py` (extração de SLA
  compartilhada entre freshness e quality), que é uma refatoração válida
  independente do score — não fazia sentido desfazer só porque a feature
  que motivou a extração saiu.

**Decisão 2 — Lineage implementado mesmo com Data Access audit logs
desabilitados**
- Pré-requisito técnico da fonte de dados (audit logs de BigQuery via
  Cloud Logging) não está habilitado em nenhum ambiente. Decisão
  consciente do usuário: implementar a feature mesmo assim (ela funciona
  corretamente assim que os logs forem habilitados) em vez de bloquear a
  sprint esperando uma mudança de infraestrutura que não é código.
- Limite técnico registrado explicitamente: a API não consegue
  distinguir "sem atividade no período" de "audit logs desabilitados" —
  os dois casos retornam o mesmo resultado vazio. Resolvido com um campo
  de aviso explícito na resposta em vez de fingir certeza.
- O schema do payload dos audit logs (`BigQueryAuditMetadata`/
  `jobChange`) foi implementado a partir da documentação oficial do
  Google, sem poder validar contra um log real — vale revisitar assim
  que os audit logs forem habilitados e o primeiro job aparecer.

**Decisão 3 — Lineage v1→v2 sem endpoint novo, breaking change direto**
- A extensão pra cadeia transitiva trocou `LineageResponse` (upstream/
  downstream flat) por `LineageGraphResponse` (nodes/edges) na mesma
  rota, em vez de versionar a API. Único consumidor da v1 era
  `LineageTab.tsx` — sem clientes externos, sem convenção de
  versionamento de API em nenhum outro domínio do repo, então manter
  compatibilidade retroativa seria custo sem benefício real.
- Bug encontrado e corrigido no meio do caminho: a v1 comparava
  `(dataset_id, table_id)` descartando `project_id`, então uma tabela
  `outro-projeto.RAW.foo` podia colidir por engano com `RAW.foo` do
  projeto consultado. A travessia v2 casa sempre pela tripla completa.

**Decisão 4 — PII diverge do guard de view de quality: pula a query
paga inteiramente, não só o TABLESAMPLE**
- `quality` (profiling), quando a tabela é VIEW/MATERIALIZED VIEW, só
  omite a cláusula `TABLESAMPLE` e roda a query principal sem amostragem
  — aceitável porque profiling é a funcionalidade central do domínio.
  PII é uma checagem complementar; rodar sem amostragem escanearia a
  view inteira (que pode envolver uma query subjacente pesada) sem o
  usuário ter visto uma estimativa de custo antes. Decisão: pular a
  query de amostragem por completo pra view, mantendo só a heurística de
  nome (grátis) — mesmo padrão de dry-run/estimate de quality, mas com
  esse guard adicional.
- Limitação assumida conscientemente e documentada em
  `docs/specs/pii.md`: os padrões regex (CPF, CNPJ, telefone, cartão)
  validam só formato, sem dígito verificador nem algoritmo de Luhn — e
  não cobrem a variante sem formatação (dígitos crus), que teria alto
  risco de falso positivo contra qualquer sequência numérica do tamanho
  certo.

**Decisão 5 — Mapa de acesso: limitação de visibilidade cross-project
discutida e documentada antes de implementar**
- Durante a conversa sobre o que conta como "acesso" (motivada por uma
  pergunta do usuário sobre um job Glue extraindo do BQ pra S3), ficou
  claro que `list_access_events`/`list_job_events` só enxergam jobs que
  **rodaram no projeto da tabela** — um job rodando em outro projeto que
  lê a tabela via referência cross-project não aparece, porque o audit
  log dele vive no projeto onde ele rodou. Mesma classe de limitação já
  documentada em lineage/órfãs, agora também explícita em
  `docs/specs/access.md`, "Fonte de dados" e "Casos de borda" — em vez
  de descobrir isso depois, via um usuário confuso com um número de
  acessos menor que o esperado.
- Decisão de design: diferente de `get_orphans` (que só conta leitura)
  e do lineage (que exclui auto-referência), o mapa de acesso conta
  leitura **e** escrita, e **não** exclui auto-referência — são
  perguntas diferentes ("quem consome" vs. "de onde vem" vs. "quem
  tocou"), cada domínio com a semântica que faz sentido pra ele mesmo
  reaproveitando a mesma fonte de dados.

### Mudanças de arquitetura
- `core/sla.py`: classificação de SLA extraída de `domains/freshness`
  para `core/`, compartilhada com `domains/quality` (mesmo racional do
  `resolve_dataset_region()` na Fase 2B).
- `core/logging_client.py`: client compartilhado do Cloud Logging, mesmo
  padrão de `core/bigquery.py::get_client()` (singleton via `lru_cache`).
- `LoggingAccessDeniedError` (`core/exceptions.py`) + handler em
  `main.py`: mesmo padrão de `ProjectAccessDeniedError` — falta de IAM
  vira 403 com o comando `gcloud` de correção pronto na resposta.
- `@xyflow/react` + `dagre` (frontend): primeira lib de grafo/diagrama do
  projeto (antes só `recharts`, gráficos, não DAG), adicionada
  especificamente pro diagrama de lineage transitivo — nó custom
  (`LineageGraph.tsx`) reaproveita o padrão visual de bloqueado+tooltip
  já estabelecido nos botões de `AssetsTable.tsx` (item 1 desta sprint)
  pra representar tabelas em projeto sem acesso de Logging.
- `components/SqlPreview.tsx`: promovido de `features/quality/` pro
  nível compartilhado — componente já era genérico (`{sql, defaultOpen}`,
  sem lógica de domínio) e passou a ser usado por `quality` e `pii`, mesmo
  racional do `SortableTableHead` promovido no item 1.
- `domains/pii/`: `repository.py` duplica (não importa)
  `get_table_columns`/`is_view`/`dry_run` de `domains/quality/
  repository.py` — mesma decisão de isolamento de domínio já tomada em
  `domains/lineage/repository.py` (CLAUDE.md proíbe um domínio importar
  de outro).
- `domains/access/`: mesma decisão de duplicação, desta vez sobre
  `domains/lineage/repository.py` — `AccessEvent` é quase idêntico a
  `JobEvent` de lineage, mas carrega também `timestamp`
  (`jobStatistics.endTime`), campo que lineage não lê porque não
  precisa de "quando", só de "de onde/pra onde".

### Status até o momento
- Backend: 367 testes unitários, 100% passando, `ruff check`/`ruff
  format` limpos
- Frontend: `biome check`, `tsc -b`, `vite build` limpos (bundle
  ~1.19 MB / gzip 364 kB)
- Validado em dev (`observability-hub-dev`) pelo usuário: filtros/
  ordenação, histórico de qualidade, lineage v2 (cadeia transitiva
  confirmada contra audit logs reais) e PII. Mapa de acesso ainda não
  validado visualmente no momento deste registro.
- **7 de 7 itens concluídos — sprint fechada.** PR pra `main` ainda não
  aberto.

---

## Sprint 3.1 — Auth (Google OAuth) + UX pessoal (concluída, PR #17)

Reconstruída a partir da descrição do PR #17 — o SESSIONLOG não foi
atualizado durante aquela sessão (falha de processo corrigida a partir
desta sprint).

### O que foi feito
1. **Autenticação real**: senha hardcoded do frontend (dívida técnica
   registrada no backlog da Sprint 2) substituída por Google OAuth 2.0 —
   `domains/auth/` no backend (login, callback, sessão via JWT em cookie
   httpOnly de 12h, allowlist por domínio/email no Secret Manager);
   `RequireAuth` no frontend. Todos os routers de dados passaram a exigir
   sessão válida no backend, não só proteção de rota no frontend.
2. **Modal de profiling**: dois bugs de UI corrigidos (colapso de schema
   em dois níveis, scroll horizontal vazando dos controles) e refatorado
   para Tabs (Schema / Análise de qualidade).
3. **Favoritos**: domínio novo, Firestore por usuário, estrela na tabela
   de ativos com toggle otimista.
4. **Histórico de navegação**: domínio novo, duas subcoleções por usuário
   (visualizações de tabela / buscas), seção "Recentes" na sidebar.

### Erros e aprendizados
- Cookie de logout não limpava de fato a sessão (`delete_cookie` do
  Starlette precisa dos mesmos atributos do cookie original pra
  funcionar) — corrigido em fix separado, pós-validação.

### Status final
- 269 testes backend, `ruff`/`biome`/`tsc`/`vite build` limpos
- Validado em dev pelo usuário (login/logout, allowlist, favoritos,
  histórico, modal de profiling)

---

## Sprint 2.2 e 2.3 — Metadados de partição, refresh, busca reversa e UX (concluída)

Sete funcionalidades sobre o MVP de catálogo/freshness (Fase 2 backend +
Sprint 2 frontend, ambas já concluídas), todas na branch
`feature/partition-metadata`, testadas em dev e validadas pelo usuário
antes de qualquer PR para `main`.

### O que foi feito — Sprint 2.2

1. **Metadados de partição na tabela de ativos**: `partition_type`
   (`"event_date (DAY)"`), `min_partition`, `max_partition`,
   `partition_count` em `TableSummary`, buscados em paralelo só para
   tabelas particionadas.
2. **Botão "Ver partições"**: novo endpoint
   `GET .../tables/{table_id}/partitions`, modal com a lista completa de
   partições distintas + contagem de linhas.
3. **Botão de refresh**: `RefreshButton` compartilhado (`RotateCcw`,
   `animate-spin`), páginas de catálogo e freshness, refetch das queries
   TanStack Query da view atual sem navegar nem limpar o projeto
   selecionado.
4. **Busca reversa tabela → datasets**: novo endpoint
   `GET /catalog/{project_id}/search?q=&mode=exact|contains`, agrupando
   `datasets_with_match`/`datasets_without_match` (este último via
   detecção de prefixo/série, não lista todo dataset do projeto).

### O que foi feito — Sprint 2.3

5. Sidebar de datasets sem os indicadores de status SLA (bolinha
   colorida) — só nome + contagem de tabelas/views.
6. Projeto selecionado persistido em `localStorage`, restaurado e
   revalidado automaticamente no carregamento da página; limpa o storage
   e volta pro campo vazio se a revalidação falhar.
7. Terceiro mode de busca, `not_contains` — inverte a lógica (datasets
   onde nenhuma tabela contém o termo) reaproveitando `mode=contains` +
   o universo completo de datasets do projeto. Resultado da busca
   reescrito como tabelas ordenáveis/filtráveis client-side (`Dataset`,
   `Tabela`, `Atualizado em`, `Linhas`) — `row_count` precisou entrar no
   backend (`DatasetWithMatch`), reaproveitando a mesma chamada
   `client.get_table()` já feita para `last_modified_time`.

### Erros cometidos e aprendizados

**Erro 1 — Reversão completa da estratégia de partições logo na primeira
implementação**
- O que aconteceu: a primeira versão de `get_partition_stats()` seguiu a
  instrução original (usar `INFORMATION_SCHEMA.PARTITIONS`, metadado
  gratuito, com fallback N/D para datasets multi-região). Tecnicamente
  correta, mas **inútil na prática**: todos os datasets de dev e prod
  estão em `US`, então o resultado era N/D sempre. Um PR (#14) chegou a
  ser aberto com essa versão e foi fechado pelo usuário sem merge.
- Correção: reimplementada do zero como uma query real (`MIN`/`MAX`/
  `COUNT(DISTINCT)` direto na coluna de partição), com custo real de
  bytes escaneados em vez de metadado gratuito — mitigado com cache TTL
  de 5min por tabela.
- Aprendizado: "tecnicamente correto pela spec" não é o mesmo que "útil
  no ambiente real" — quando 100% dos dados de teste caem no caso
  degradado de uma spec (aqui, multi-região → N/D), vale checar contra o
  ambiente real antes de considerar a implementação pronta, não só
  contra a spec escrita. `INFORMATION_SCHEMA.PARTITIONS` continua sendo
  uma opção válida em datasets de região específica — só não serve como
  única fonte quando todo o ambiente observado é multi-região.

**Erro 2 — "Linhas" pedida numa tabela sem mudar backend**
- O que aconteceu: a spec da Sprint 2.3 pedia uma coluna "Linhas"
  ordenável no resultado da busca, mas também dizia explicitamente "sem
  mudança de backend" — e o endpoint de busca nunca retornou
  `row_count`. Contradição real, não resolvida com suposição.
- Correção: perguntado ao usuário antes de implementar; decidido
  adicionar `row_count` ao backend mesmo assim, reaproveitando a chamada
  `client.get_table()` que já buscava `last_modified_time` (sem query BQ
  extra).
- Aprendizado: quando uma instrução pede um dado que a fonte não tem E
  proíbe a única forma de obtê-lo, é um bloqueio real — vale perguntar
  em vez de escolher silenciosamente um dos dois lados.

### Mudanças de arquitetura
- Nenhuma mudança estrutural — todas as adições seguem os padrões já
  estabelecidos na Fase 2 (paralelismo com `ThreadPoolExecutor`, cache
  TTL em memória por processo, `service.py` orquestra e `repository.py`
  constrói SQL).

### Status final
- 219 testes unitários backend, 100% passando ✅
- `ruff check`/`ruff format`, `biome check`, `tsc -b`, `vite build`
  limpos em cada commit ✅
- Validado com `curl` contra `observability-hub-dev` (dados reais,
  incluindo o cenário GA4 completo de `not_contains`/prefixo) e pelo
  usuário na interface real, em cada uma das 7 funcionalidades ✅
- Renderização visual no browser **não verificada por este assistente**
  em nenhum momento — Chromium headless não roda neste sandbox (mesma
  limitação de sessões anteriores); toda validação visual foi feita
  pelo usuário diretamente em dev

---

## Fase 2 — Backend MVP (concluída)

### O que foi feito
- Domínio Catálogo (Fase 2A): 4 endpoints, `discover_regions()` para descoberta
  automática de região, modelo de acesso cross-project
- Domínio Freshness (Fase 2B): 2 endpoints, classificação de SLA por janelas
  fixas (12h/24h/48h/7d/1m)
- Domínio Profiling/quality (Fase 2C): 3 endpoints, `sql_builder.py` com
  geração dinâmica de SQL por coluna, dry run de custo, amostragem via
  `TABLESAMPLE SYSTEM`, drill-down de distribuição de nulos ao longo do tempo
- 155 testes unitários passando (100%), com mocks — nenhum toca o BigQuery real
- Validado com `curl` contra `observability-hub-dev` ao final de cada uma das
  três sub-fases, antes de cada commit

### Erros cometidos e aprendizados

**Erro 1 — `INFORMATION_SCHEMA.TABLE_PARTITIONS` não existe em multi-região**
- O que aconteceu: a query de tabelas do catálogo fazia `JOIN` com
  `TABLE_PARTITIONS` para obter `partition_column`; deu `404 NotFound` em
  datasets na multi-região `US`.
- Correção: `TABLE_PARTITIONS` nem tem um campo com o *nome* da coluna de
  particionamento (só `partition_id`, o valor da partição) — e não existe em
  `US`/`EU` de qualquer forma. `partition_column` passou a vir de
  `INFORMATION_SCHEMA.COLUMNS.is_partitioning_column`, que funciona em
  qualquer região e já estava sendo consultada para `clustering_columns`.
- Aprendizado: não confiar em nomes de campo documentados ou sugeridos sem
  validar contra o schema real (`SELECT * LIMIT 1` ou introspecção do
  `result().schema`).

**Erro 2 — `last_modified_time` incorreto, repetido em duas specs**
- O que aconteceu: a spec do catálogo referenciava
  `TABLES.last_modified_time` (não existe) e, na correção seguinte,
  `TABLE_STORAGE.last_modified_time` (também não existe). O mesmo erro
  apareceu de novo na spec de freshness, que também usa `TABLE_STORAGE`.
- Correção: `TABLES` não tem nenhum campo de "última alteração" nesta versão
  do BigQuery; o campo real em `TABLE_STORAGE` é `storage_last_modified_time`.
- Aprendizado: todo campo de `INFORMATION_SCHEMA` citado numa spec precisa
  ser confirmado contra o schema real do projeto antes de implementar — esse
  erro específico se repetiu em 3 ocasiões diferentes ao longo da Fase 2.

**Erro 3 — `description` não existe em `INFORMATION_SCHEMA.COLUMNS`**
- O que aconteceu: o endpoint de detalhe de tabela buscava `description`
  direto de `COLUMNS`; `400 Unrecognized name: description`.
- Correção: `description` vem de `INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`,
  com `JOIN` em `field_path = column_name` para não duplicar linhas em
  colunas `STRUCT`/`RECORD` aninhadas.
- Aprendizado: mesmo aprendizado do Erro 2.

**Erro 4 — `TABLE_STORAGE` sem dados para as tabelas de `observability-hub-dev`**
- O que aconteceu: freshness e profiling dependem de `TABLE_STORAGE` para
  `last_modified_time`/`total_rows`/`size_bytes`; a view retornou 0 linhas
  para as tabelas do projeto dev durante toda a Fase 2.
- Investigação: `TABLE_STORAGE` exige a opção de projeto
  `enable_info_schema_storage` habilitada por região (via `ALTER PROJECT`) —
  mas essa opção já estava `true` em `observability-hub-dev` (confirmado
  consultando `INFORMATION_SCHEMA.PROJECT_OPTIONS`), então não era o
  bloqueio. O motivo real é o lag de propagação que a documentação do Google
  descreve como "cerca de 1 dia" após habilitar a opção ou após mudanças na
  tabela até os dados de storage aparecerem.
- Correção: todo campo que depende de `TABLE_STORAGE`
  (`last_modified_time`, `size_bytes`, `row_count`, `hours_since_update`,
  `sla_status`) foi tipado como opcional (`| None`) em vez de obrigatório.
- Aprendizado: qualquer domínio que dependa de `TABLE_STORAGE` precisa
  tolerar ausência de dado para tabelas recém-criadas ou recém-modificadas —
  não é bug do nosso código, é o comportamento documentado do BigQuery.

### Mudanças de arquitetura
- `resolve_dataset_region()` movido de `domains/catalog/repository.py` para
  `core/bigquery.py` durante a Fase 2B — passou a ser compartilhado entre
  catalog e freshness (e, na prática, também usado por quality na Fase 2C).
  `catalog/repository.py` reexporta o nome para não quebrar chamadas
  existentes de `service.py` e dos testes. Justificativa: `core/exceptions.py`
  já antecipava essa necessidade desde a Fase 2A ("catalog hoje; freshness e
  profiling depois").

### Status final
- Catálogo: 4 endpoints ✅ | Freshness: 2 endpoints ✅ | Profiling: 3 endpoints ✅
- 155 testes unitários, 100% passando ✅
- `ruff check` + `ruff format` limpos em todas as três sub-fases ✅
- Validado com `curl` contra `observability-hub-dev` (dados reais, incluindo
  multi-região `US`, tabelas particionadas/clusterizadas e profiling
  completo em `RAW.crm_leads`) ✅

---

## Fase 1 — Infraestrutura base (concluída)

### O que foi feito
- Bootstrap do Terraform aplicado manualmente em dev e prod
  - Bucket GCS de remote state por ambiente
  - Workload Identity Federation (GitHub Actions → GCP sem service account keys)
  - Service accounts de deploy com permissões mínimas
- GitHub Actions configurados (5 workflows)
  - `terraform-plan.yml` — roda em todo PR que toca infra/
  - `terraform-apply-dev.yml` — push em qualquer branch exceto main
  - `terraform-apply-prod.yml` — push/merge em main
  - `backend-deploy-dev.yml` — build + push + deploy Cloud Run dev
  - `backend-deploy-prod.yml` — build + push + deploy Cloud Run prod
- Módulo Terraform `cloud-run` criado e aplicado em dev e prod
  - Artifact Registry repository
  - Service account de runtime dedicada (backend-run)
  - Cloud Run com health check em /health e lifecycle.ignore_changes na imagem
- Backend skeleton deployado em dev e prod
  - FastAPI com GET /health → {"status": "ok"}
  - Dockerfile multi-stage, usuário não-root, uv como gerenciador de pacotes

### Erros cometidos e aprendizados

**Erro 1 — Permissão faltando no bootstrap**
- O que aconteceu: `gh-deploy-prod` não tinha `roles/iam.serviceAccountAdmin`,
  apenas `roles/iam.serviceAccountUser`. O Terraform Apply falhou ao tentar
  criar a service account `backend-run` no primeiro deploy.
- Correção: adicionado `roles/iam.serviceAccountAdmin` no módulo wif-bootstrap
  e reaplicado o bootstrap manualmente em dev e prod.
- Aprendizado: ao definir permissões de deploy no bootstrap, sempre listar todos
  os tipos de recursos que o Terraform vai criar (SAs, buckets, Cloud Run, etc.)
  e garantir as roles correspondentes.

**Erro 2 — Corrida entre workflows (race condition)**
- O que aconteceu: `backend-deploy-prod.yml` e `terraform-apply-prod.yml`
  dispararam em paralelo no mesmo push. O deploy rodou antes do Terraform criar
  a infraestrutura, gerando drift — Cloud Run criado fora do state com SA default
  do Compute Engine em vez da `backend-run`.
- Correção: adicionado `needs: [wait-for-terraform]` no `backend-deploy-prod.yml`
  para garantir que o Terraform Apply conclua antes do deploy.
- Aprendizado: em monorepos onde um push pode tocar infra/ e apps/ juntos,
  sempre definir ordem explícita entre workflows de infra e de deploy.

**Erro 3 — Drift em prod após race condition**
- O que aconteceu: o Cloud Run criado com drift precisou ser apagado e recriado
  pelo Terraform. O `terraform apply` em environments/prod foi rodado manualmente
  para reconciliar o state.
- Correção: `gcloud run services delete` seguido de `terraform apply` local com
  credenciais de admin.
- Aprendizado: em ambientes sem tráfego real, apagar e recriar é mais seguro
  que `terraform import`. Com tráfego real, sempre preferir import.

### Mudanças de arquitetura
- Nenhuma mudança em relação ao planejado.

### Status final
- dev: Cloud Run ✅ | Artifact Registry ✅ | GET /health HTTP 200 ✅
- prod: Cloud Run ✅ | Artifact Registry ✅ | GET /health HTTP 200 ✅

---

## Fase 0 — Estrutura e documentação (concluída)

### O que foi feito
- Monorepo criado e pushado para GitHub
- Estrutura de pastas definida (apps/backend, apps/frontend, infra/terraform,
  docs/adr, scripts)
- CLAUDE.md criado com convenções completas do projeto
- .gitignore cobrindo Python/uv, Node/pnpm, Terraform, Docker e segredos
- PRD v1.0 criado com funcionalidades, MVP, métricas de sucesso e roadmap
- ADRs 001-005 criados documentando decisões de arquitetura:
  - ADR-001: Monorepo
  - ADR-002: GCP como cloud provider
  - ADR-003: Terraform com diretórios por ambiente
  - ADR-004: Workload Identity Federation
  - ADR-005: Stack minimalista (FastAPI + React + Cloud Run)

### Erros cometidos e aprendizados
- Nenhum erro técnico nesta fase.
- Aprendizado de processo: definir arquitetura e funcionalidades ANTES de abrir
  o Claude Code evita retrabalho. O CLAUDE.md com contexto completo é o
  investimento mais importante do projeto.

### Mudanças de arquitetura
- Nenhuma.

---

## Próximas fases

| Fase | Descrição | Status |
|---|---|---|
| Fase 1.5 | Dados mock no BigQuery (GA4 público) | ✅ Concluída |
| Fase 2 | MVP: Catálogo + Freshness + Profiling (backend) | ✅ Concluída |
| Fase 2D | Frontend MVP | ✅ Concluída |
| Sprint 2.2 | Metadados de partição, "Ver partições", refresh, busca reversa | ✅ Concluída |
| Sprint 2.3 | 4 melhorias de UX (sidebar, localStorage, not_contains, tabela ordenável) | ✅ Concluída |
| Sprint 3.1 | Auth (Google OAuth), favoritos, histórico, fixes no modal de profiling | ✅ Concluída |
| Sprint 3.2 | Filtros/ordenação, histórico de qualidade, lineage e órfãos, PII, mapa de acesso | ✅ Concluída (7 de 7 itens) |
| Fase 4 | FinOps completo (scanner de desperdício, budget de custo, sugestão de tipo de coluna) | ✅ Concluída (3 de 3 frentes — clustering deferido, ver ADR/spec) |
| — | Admin ACL v1.0–v1.3 (controle de acesso usuário×projeto, projetos públicos, solicitação de acesso, painel "Uso do Hub") | ✅ Concluída |
| — | Documentação para cliente (2 playbooks operacionais + 2 manuais voltados a cliente final) | ✅ Concluída |
| Fase 5 | Storage (Cloud Storage): catálogo, scanner de desperdício (config + uso real), extensão do lineage | ✅ Concluída — validada em dev, mergeada em `main` e deployada em prod (PR #25) |


### R2-7 — `feat/r2-analysis-routes` (só front-end)

- **`ProfilingDialog.tsx` deletado.** O fluxo de análise virou a subárvore
  `/analyze/:datasetId/:tableId/*`: `AnalysisLayout` (provê contexto +
  `<Outlet/>`), `AnalysisChooserPage` (7 cards `OptionCard`, todos ativos),
  e 6 páginas de módulo liftando cada corpo de aba (`SchemaTable`,
  `PiiTab`, `ColumnTypeSuggestionsTab`, `HistoryTab`, `AccessTab`; Lineage
  → `/lineage/:d/:t` da R2-8).
- `QualityAnalysisPanel` extraído da antiga aba "Análise de qualidade" +
  novos `components/HBarList.tsx` (cardinalidade em barra horizontal +
  `ChartTooltip` — 1º consumidor real dele) e `components/CompositeScoreRing.tsx`
  (anel de score, SVG à mão). `QualityAnalysisPage` monta os dois +
  `ColumnResultsTable`.
- `AssetsTable` "Analisar" → `navigate('/analyze/:d/:t', { state:{ from } })`.
- `docs/specs/quality.md` novo (AC-QUAL-RV-01..04). `profiling.md` §pendente
  marcada feita. `design-system.md` (HBarList, CompositeScoreRing).

### R2-8 — `feat/r2-lineage-fullscreen` (backend + front-end)

- `LineagePage` (`/lineage/:datasetId/:tableId`) — lifta o grafo pra tela
  cheia. `LineageTab.tsx` deletado (órfão pós-R2-7).
- `LineageGraph`: arestas `animated` (@xyflow) recoloridas amarelo + glow
  via `.dp6-lineage` no index.css; `onEdgeMouseEnter` destaca a aresta +
  os 2 nós ligados, atenua o resto; `nodesep`/`ranksep` maiores, altura 540.
- 3 `<Panel>`: Impacto de mudança de schema (tabelas a jusante + views que
  quebrariam), Fontes, Consumidores. Indicador cache + "profundidade
  limitada a N hops".
- **Backend (B6):** `LineageNode.table_type` — best-effort de
  `INFORMATION_SCHEMA.TABLES` (só-metadado, $0) só pros nós do projeto
  raiz, engolindo exceção. **"Jobs agendados" fica "—"** (exige integrar
  Scheduled Queries / Data Transfer — fora desta rodada). pytest 786 ok.
- `lineage.md` §pendente marcada feita. design-system.md.

### R2-9 — `feat/r2-finops-budget-crud` (backend)

- **Novo domínio `domains/budget`** (Firestore, espelha `domains/favorites`):
  meta de custo mensal **por usuário**, coleção `users/{email}/budgets/{doc_id}`.
  `doc_id` determinístico por escopo — `project` = `{project_id}`, `dataset`
  = `{project_id}__{dataset_id}`, `table` = `+__{table_id}`. `created_at` /
  `created_by` preservados em upsert repetido (reeditar valor não reordena
  nem reatribui autoria).
- **API (em `api/v1/finops.py`, mesmo prefixo + `require_project_access`):**
  `GET /finops/{p}/budgets` (lista do usuário, filtro por projeto in-memory),
  `PUT /finops/{p}/budgets` (upsert; validação escopo×campos no
  `BudgetUpsertRequest` — 422 se `dataset` sem `dataset_id`, `table` sem
  `table_id`, `amount_usd <= 0`), `DELETE /finops/{p}/budgets?scope=&dataset_id=&table_id=`
  (204, idempotente). Os três somam `Depends(get_current_user)` ao
  dependency de router.
- **B2:** `BudgetResponse.budget_target_usd` — `GET /finops/{p}/budget`
  agora lê o budget de `scope=project` do usuário logado (`get_budget`
  ganhou `user_email`; endpoint passa `user.email`). `null` quando não
  cadastrado → o `ComboChart` do FinOps não desenha a linha de referência.
- **Sem BigQuery** (B1/B2 são 100% Firestore — nenhum dry-run a reportar).
- Testes: `tests/unit/budget/{test_repository,test_service}.py` novos +
  2 casos de `budget_target_usd` em `tests/unit/finops/test_service.py`.
  `uv run pytest tests/unit` = 803 ok, `ruff check` limpo.
- `docs/specs/finops-budget.md` → v1.5 (CRUD documentado, AC-FIN-RV-04
  marcado implementado, ASM-FIN-RV-02 confirmada: store por usuário).
- **Incidente de deploy (não-código):** o push do R2-9 falhou 3× no CI
  antes de passar — 1ª por `502 Bad Gateway` no `docker push` pro
  Artifact Registry, 2ª/3ª por startup probe do Cloud Run na mesma janela
  de degradação do GCP (`us-central1`, ~15:22–15:30 UTC). Código
  verificado local (pytest 803 + `uvicorn observability_hub.main:app`
  sobe limpo com o entrypoint exato do container); 4ª tentativa (mesmo
  digest, zero mudança) passou. `backend-dev` nunca ficou fora do ar — o
  Cloud Run só troca tráfego pra revisão `Ready`.

### R2-10 — `feat/r2-finops-cost-series` (backend)

- **`GET /finops/{project_id}/cost-series`** (`domains/finops`, AC-FIN-RV-02):
  série temporal contígua de custo **query + storage** por dia/mês pro
  gráfico combo da visão geral. Params: `granularity` (day/month),
  `cost_type` (all/query/storage), `lookback_days` (1–31, clampado),
  `datasets`, `tables`.
- **Custo de query:** do mesmo cache de audit log de `get_budget`
  (`get_scan_events_cached`, 31 dias) — **nenhum scan novo**. Cada evento
  conta uma vez por período (sem fan-out — evita inflar o total); com
  filtro, o evento entra se qualquer tabela real casar.
- **Custo de storage:** `SUM(COALESCE(total_logical_usage_bytes,
  total_physical_usage_bytes,0))` por `usage_date` de
  `INFORMATION_SCHEMA.TABLE_STORAGE_USAGE_TIMELINE_BY_PROJECT` (fan-out
  por região, agregado no SQL). Custo do dia = `GB × tarifa active /
  dias_do_mês`. `repository.get_storage_cost_timeline` → `None` se
  **nenhuma** região respondeu → `storage_available=false` +
  `query_cost_usd` intacto + `warning`; **nunca 500** (lição do incidente
  da rodada 1). Região que falha sozinha é ignorada.
- **Dry-run:** a query toca só `INFORMATION_SCHEMA.*` (view de metadado,
  BQ não cobra — mesma base $0 de `list_all_table_refs` /
  `get_date_like_columns`). **Sem credencial de GCP no ambiente local pra
  rodar `dry_run` antes** — confirmar em dev pós-deploy (ASM-002 da
  spec); a degradação `storage_available=false` protege se a view cobrar.
- Testes: `tests/unit/finops/test_service.py` (+8, `get_cost_series`),
  `test_repository.py` (+5, `get_storage_cost_timeline`). `uv run pytest
  tests/unit` = 815 ok, `ruff check`/`format` limpos.
- `docs/specs/finops-budget.md` → v1.6.
- **Deploy:** mesma flakiness de startup probe do R2-9 — 4 falhas de
  `Creating Revision...failed` antes de passar no 5º rerun (mesmo digest).
  Código verificado local: `uvicorn observability_hub.main:app` sobe e
  `GET /health` responde **200 em 0.33s**, `/openapi.json` 200. Não é o
  código — é cold-start do Cloud Run perdendo a janela de 40s do probe
  (`failure_threshold=8×5s`, já aumentado uma vez no módulo). Fix de
  verdade = subir o threshold no Terraform (branch de infra à parte).

### R2-11 — `feat/r2-finops-table-score` (backend)

- **`GET /finops/{project_id}/table-scores`** (`domains/finops`,
  AC-FIN-RV-03 / AC-WASTE-RV-01): score de eficiência de custo 0–100 por
  tabela (maior = melhor) + `project_efficiency_score` (média dos scores
  ponderada por `size_bytes`). Params `datasets`, `limit` (1–500).
- **Fórmula PROVISÓRIA** (`_table_efficiency_score`, pura, testada
  direto) — 3 fatores, pesos somando 1.0, expostos em `factors[]` pro
  drill-down recalibrar sem quebrar contrato:
  `partitioning` 0.45 (`1 − economia_particionamento / custo_scan_30d`,
  reaproveita `scan_partition_candidates`), `utilization` 0.30 (`0` se
  ≥100 GB nunca consultada em 30d), `scan_efficiency` 0.25
  (`1/(1+(bytes_30d/size)/10)`). **Sem sinais cross-domain** (drift de
  schema / órfã ficam de fora — domínios isolados, CLAUDE.md). Fórmula
  vai pro review (Q-002 na spec).
- **Nenhuma query BQ nova** — `list_all_table_refs` + `get_tables_metadata`
  (REST cacheado) + cache de audit log + `scan_partition_candidates`. Sem
  `dry_run` a reportar.
- Testes: `tests/unit/finops/test_service.py` (+6: 3
  `_table_efficiency_score`, 3 `compute_table_scores`). `uv run pytest
  tests/unit` = 821 ok, `ruff check`/`format` limpos.
- `docs/specs/finops-budget.md` → v1.7 (fórmula + Q-002 aberta),
  `finops-waste-scanner.md` AC-WASTE-RV-01.

### R2-12 — `feat/r2-finops-overview` (só front-end, consome R2-9/10/11)

- **`FinOpsOverviewPage` na rota `/finops`** (goal 4); o scanner de 2 abas
  virou `/finops/scanner` (`router.tsx` + NavLink "Scanner de desperdício"
  da sidebar; `FinOpsPage` ganhou `back` pra `/finops`).
- Big numbers: Gasto no mês / Meta mensal / Projeção do mês (alerta se
  passar da meta) / Tabelas de baixo score (< 50). `ComboChart` (barra por
  período + linha acumulada + `refLine` de meta) com `ChoiceToggle` de
  granularidade (dia/mês) e tipo de custo (tudo/query/storage) →
  `useCostSeries`. Aviso quando `storage_available=false`.
- `CompositeScoreRing` "Eficiência de custo" (`project_efficiency_score`)
  + `Panel` "Top ofensores": tabela ordenada pior-primeiro, anel compacto
  na coluna Score, linha expansível mostrando a decomposição em
  `factors[]` (nome · % · peso · detalhe).
- `OptionCardGrid`: Scanner de desperdício, Budget de custo, Configurar
  budget (→ `BudgetConfigDialog` novo — escopo projeto/dataset/tabela,
  valor mensal, lista das metas com remover inline; usa
  `useBudgets`/`useUpsertBudget`/`useRemoveBudget`).
- `lib/api/finops.ts` + `types/finops.ts` + `features/finops/hooks.ts`:
  `getCostSeries`, `getTableScores`, `listBudgets`/`upsertBudget`/
  `removeBudget` + tipos; `BudgetResponse` ganhou `budget_target_usd` e
  `cache_updated_at`.
- Sem `index.css` nem componente compartilhado novo (só feature files +
  2 helpers locais) → sem sync de design-system. `pnpm lint` + `pnpm
  build` verdes. `vite build` mantém o aviso pré-existente de chunk > 500
  kB (xyflow/recharts no bundle principal) — R2-7b (lazy) fica como
  follow-up opcional, não regressão desta branch.

### R2-11.5 — `fix/finops-score-and-storage-timeline` (backend + front-end)

Ajustes de validação visual do usuário na visão geral de FinOps:

- **`scan_efficiency` ignora tabelas < 1 GB** (`_SCORE_SCAN_MIN_SIZE_BYTES`
  = `_MIN_TABLE_SIZE_BYTES_FOR_PARTITION_CANDIDATE`) — re-scan de tabela
  pequena custa centavos, não é sinal de desperdício; o fator fica neutro
  (1.0) com detalhe "Tabela pequena (< 1 GB)".
- **Tooltip da fórmula do score** na página `/finops` (`ScoreExplainer` no
  `actions` do painel "Eficiência de custo") — os 3 fatores, pesos, e que
  o score do projeto é média ponderada por tamanho.
- **Storage line em dev caía em `storage_available=false`.** O motivo real
  (agora propagado no `warning` — `get_*` retorna `(valor, motivo)` e o
  service repassa a 1ª linha do erro do BigQuery) foi
  `400 Unrecognized name: total_logical_usage_bytes`: o schema de coluna
  da família `TABLE_STORAGE_USAGE_TIMELINE_*` não bate com a doc.
  **Trocado pra `INFORMATION_SCHEMA.TABLE_STORAGE`** (snapshot atual,
  coluna estável `total_logical_bytes`) → linha **plana** no nível de
  storage de hoje (numa janela ≤ 31d o volume quase não varia). Região em
  minúscula (`region-us`). `get_storage_cost_timeline` +
  `StorageTimelineDay` removidos; `get_current_storage_bytes` novo.
  Permissão não era o problema — sem role nova no onboarding. ASM-002
  resolvida.
- `uv run pytest tests/unit` = 823 ok; `pnpm lint`/`build` verdes.
- `docs/specs/finops-budget.md` (score §, storage §, ASM-002).