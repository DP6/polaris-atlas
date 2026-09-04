# Padrões recorrentes

Composições que aparecem em várias telas. Antes de montar uma do zero,
confira se já existe aqui — as peças (`src/components/`, `src/hooks/`) já
estão prontas.

Formato: **para que serve · peças · arquivo canônico pra copiar ·
pegadinhas**.

---

## 1. Cabeçalho de rota

- **Para que serve:** título + subtítulo + ações de uma página inteira.
- **Peças:** `PageHeader` (título/descrição/`actions`/`back`).
- **Voltar (rodada 3):** **todo** `PageHeader` mostra um controle "Voltar"
  no canto superior esquerdo — só a home `/` fica sem. Passe
  `back={{to,label}}` quando a página tem um pai semântico claro (ex:
  sub-página de módulo → chooser); sem o prop, o `PageHeader` renderiza um
  "Voltar" genérico que usa o histórico do browser (`navigate(-1)`,
  fallback `/`). Não montar botão de voltar à mão na página.
- **Canônico:** `features/catalog/CatalogOverviewPage.tsx`,
  `features/freshness/FreshnessPage.tsx`.
- **Pegadinhas:** renderizar o `PageHeader` **fora** dos ramos de
  loading/erro — a página mostra o `<h1>` mesmo enquanto os dados
  carregam; o `LoadingState`/`ApiErrorNotice` entra só no lugar do
  conteúdo. Um `<h1>` por rota.

## 2. Tabela filtrável e ordenável (dados já no cliente)

- **Para que serve:** listar um array já carregado inteiro, com busca por
  texto, ordenação por coluna e paginação client-side.
- **Peças:** `useTableFilterSort` (filtra → ordena) + `SortableTableHead`
  (cabeçalho clicável) + `usePagination` + `PaginationBar` + primitivo
  `ui/table`. Filtros extras (um `<Select>` de tipo/status) ficam como
  `useState` local e entram dentro do `matches` passado ao hook.
- **Canônico:** `features/storage/WastePage.tsx`,
  `features/lineage/OrphansPage.tsx`.
- **Pegadinhas:** `matches`/`compare` quase sempre são closures novas a
  cada render — é intencional (correção > memoização, tabelas pequenas).
  `usePagination` reclampa `page` sozinho quando o total encolhe; ao
  trocar algo alheio a filtro/sort (ex.: modo de agrupamento), chamar
  `resetPage()`. Estado vazio da tabela = `EmptyStateRow` com `colSpan`.

## 3. Linha de KPIs

- **Para que serve:** faixa de métricas-resumo no topo de uma tela.
- **Peças:** `MetricGrid` (grid `auto-fill`) + `MetricTile` (valor
  `text-title`, rótulo `text-label uppercase`; `alert` → borda vermelha).
- **Canônico:** `features/catalog/KpiCards.tsx`,
  `features/finops/BudgetPage.tsx`.
- **Pegadinhas:** valor formatado com `lib/format.ts` (`formatBytes`,
  `formatNumber`, `formatUsd`…), não `toLocaleString` solto. Não voltar a
  `p-3`/`text-lg` à mão — o `MetricTile` fixa o tamanho.

## 4. Fluxo de análise sob demanda

- **Para que serve:** telas que rodam uma query cara só quando o usuário
  pede — padrão **config → (estimar custo) → executar → resultado**.
- **Peças:** um seletor de escopo (`DatasetScopeGate` por dataset, ou
  `features/finops/ColumnTypeScopePicker.tsx` por tabela) → `ChoiceToggle`
  para opções (amostragem, janela…) → botão "Estimar custo" (dry run) →
  botão "Executar" → resultado com `MetricTile` + `SqlPreview` (o SQL
  gerado, com "Copiar SQL") + tabela por linha.
- **Canônico:** `features/quality/ProfilingDialog.tsx`,
  `features/storage/WastePage.tsx`,
  `features/finops/ColumnTypeSuggestionsTab.tsx`.
- **Pegadinhas:** o custo estimado (dry run) vem antes de qualquer query
  real — regra do `CLAUDE.md` (§"Contexto: Backend"). Estado de execução
  usa `StatusBadge status="running"`. Não disparar a query no `onMount`.

## 5. Gate de escopo de projeto/dataset

- **Para que serve:** obrigar a escolher o alvo antes de um scan de
  projeto inteiro.
- **Peças:** `DatasetScopeGate` (1+ datasets ou "Todos"). No nível do
  shell, o "Digite um projeto GCP para começar" fica em
  `app/layout.tsx` (`routeNeedsProject` — só `/admin` dispensa projeto).
- **Canônico:** `features/lineage/OrphansPage.tsx`.
- **Pegadinhas:** granularidade certa: por **dataset** → `DatasetScopeGate`;
  por **tabela** → `ColumnTypeScopePicker`. Não misturar.

## 6. Indicador de "dado veio de cache"

- **Para que serve:** telas servidas por um cache pré-computado (job
  diário D-1): lineage, tabelas órfãs, mapa de acesso.
- **Peças:** `CacheStalenessBadge` (`cacheUpdatedAt`; `null` = veio ao
  vivo, não renderiza) + `formatRelativeToNow` (`lib/format.ts`) +
  `RefreshButton` no slot `actions` do `PageHeader` para forçar refetch.
- **Canônico:** `features/lineage/LineageTab.tsx`,
  `features/lineage/OrphansPage.tsx`.
- **Pegadinhas:** o badge some quando `cacheUpdatedAt` é `null` — não
  envolver em condicional própria.

## 7. Página longa em seções colapsáveis

- **Para que serve:** telas com muitos blocos independentes (o Admin).
- **Peças:** `CollapsibleSection` (`variant="section"` = ex-`<h2>`;
  `"subsection"` = bloco nomeado dentro; `actions` fora do trigger).
- **Canônico:** `features/admin/AdminUsageTab.tsx` e os
  `features/admin/*Section.tsx`.
- **Pegadinhas:** o título **é** o cabeçalho real (`<h2>`/`<h3>`) — não
  aninhar outro `SectionHeading` dentro.

## 8. Dialog / modal

- **Para que serve:** ação focada sem sair da tela (profiling, salvar em
  pasta, solicitar acesso, logout).
- **Peças:** primitivo `ui/dialog` (usa `--shadow-elevation-2`).
- **Canônico:** `features/quality/ProfilingDialog.tsx`,
  `features/admin/RequestAccessDialog.tsx`.
- **Pegadinhas:** o dialog do shadcn já trata foco/Esc/overlay — não
  reimplementar. Conteúdo com estado próprio (form) deve resetar ao
  fechar.
