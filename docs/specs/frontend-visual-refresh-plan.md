# Plano de execução — Refresh visual do Hub

> Companion de [`frontend-visual-refresh.md`](frontend-visual-refresh.md) (o
> brief). O brief traz as **decisões de design**; este arquivo traz o
> **fatiamento em PRs**, as **respostas às perguntas em aberto** (Q-001/002/003)
> e o resultado da checagem de backend que o brief exigia antes de virar plano.
>
> Regra de deploy inalterada (CLAUDE.md): nada em `prod`, nenhum merge em
> `main` sem aprovação explícita do usuário a cada vez. Este plano cobre até
> "implementado e validado em `dev`". As branches são **empilhadas** (cada
> uma parte da anterior); a ordem de review/merge é a ordem da tabela abaixo.

---

## 1. Respostas às perguntas em aberto

O usuário não participa desta rodada até o review final. As perguntas foram
resolvidas por decisão documentada (instrução explícita da sessão: "não
espere confirmação, descreva a decisão e siga"). Cada uma vira uma linha em
`## Perguntas em aberto` do brief com status `respondida` + nota "decidido na
sessão de execução, reconfirmar no review".

### Q-001 — Sidebar: "contorno mais moderno, completo" no item ativo

**Decisão.** O item de nav ativo deixa de ser o bloco amarelo chapado
(`bg-primary text-primary-foreground` atual) e passa a:

1. Barra de acento à esquerda, `3px`, `--primary`, com glow suave
   (`box-shadow: 0 0 12px var(--dp6-glow)`), colada na borda do item.
2. Fundo em gradiente horizontal sutil: `color-mix(--primary 14%, transparent)`
   → `transparent` a ~70%.
3. Forma toda arredondada em `10px` (raio de retângulo novo — ver §3).
4. Texto em `--foreground` (não mais `--primary-foreground` sobre amarelo).
5. Ícone do item em `--primary` quando ativo.

Espelha `.nav a.active` + `.nav a.active::before` do protótipo. Contraste do
texto ativo passa a ser texto normal sobre fundo tintado leve — validar
≥4.5:1 nos dois temas (o gradiente a 14% mantém o fundo praticamente igual
ao `--card`/`--sidebar`, então o texto `--foreground` passa folgado).

**Reconfirmar no review:** se "completo" queria dizer *borda 1px em volta do
item inteiro* (outline) além da barra lateral. O plano assume que **não** —
barra + gradiente + raio já dão o efeito "cartão" sem poluir a lista com N
outlines competindo. Fácil de adicionar (`border` + `--primary/25`) se o
usuário pedir.

### Q-002 — FinOps: onde aparece o "score geral por tabela"

**Decisão.** Sem tela nova. O score por tabela aparece em **dois lugares**:

1. Coluna nova **"Score"** (ordenável) nas tabelas por-tabela do FinOps —
   scanner de desperdício e "Top ofensores" — renderizada como um anel
   compacto + número (`0–100`), cor por faixa (`--status-ok/warn/error`).
2. Bloco expandido ao abrir a linha da tabela (drill-down já existente nos
   fluxos de análise): o mesmo score em anel grande + a decomposição
   (o gráfico próprio que o brief pede).

Racional: o score é derivado de custo/uso **daquela tabela**, então vive ao
lado desses números; evita criar rota e item de menu novos; reaproveita o
padrão de "linha de tabela expansível" que já existe.

**Reconfirmar no review** — é uma decisão de produto (posição de uma métrica
nova). Documentada como `ASM` na spec de FinOps com status `aberta`.

### Q-003 — Catálogo de Dados: fonte do mini-gráfico dos cards de dataset

**Decisão.** O mini-gráfico de cada card de dataset = **distribuição das
tabelas daquele dataset por faixa de SLA de freshness** — exatamente o
componente que o brief já manda reaproveitar do painel "Distribuição por
dataset" do Freshness. **Não exige query nova**: é o mesmo dado de freshness
já calculado por dataset (`domains/freshness`), servido no cache D-1.

O "mini-gráfico no big number" (sparkline de *total de datasets* / *total de
tabelas* ao longo do tempo) fica **fora de escopo desta rodada**: exige série
histórica que o `INFORMATION_SCHEMA` não expõe barato (não há snapshots ao
longo do tempo sem o store de schema-drift). O big number continua número
puro, sem sparkline, até o domínio de schema-drift existir. Registrado como
`ASM` na spec de Catálogo.

---

## 2. Checagem de backend exigida pelo brief

> "Confirmado se `description` de dataset já vem de algum endpoint existente
> ou é mudança de backend."

**Resultado: é mudança de backend.** `DatasetSummary`
(`apps/backend/src/observability_hub/domains/catalog/schemas.py`) **não tem**
campo `description`. O endpoint de listagem de datasets (`GET
/api/v1/catalog/.../datasets`) não expõe a `description` do dataset do
BigQuery. Existe `description` só em nível de **tabela** e **coluna**
(`TableDetail.description`, `ColumnDetail.description`).

Consequência: mostrar a descrição do dataset nos cards do Catálogo de Dados
exige tocar `domains/catalog/` (repository + service + schema) **e** um AC
novo em `docs/specs/catalog.md` — não é só front-end (regra do CLAUDE.md,
"Contexto: Backend"). Sliced como branch própria (PR 7), depois da fundação
visual, para não travar o refresh. `INFORMATION_SCHEMA.SCHEMATA` /
`SCHEMATA_OPTIONS` do BigQuery expõe `schema_name` + opção
`description` — custo desprezível (mesma varredura de metadados já feita);
confirmar o `dry run` na implementação.

---

## 3. Convenções de design — resumo do que muda (detalhe no brief §"MUDAM")

| # | Muda | Onde no código |
|---|---|---|
| Raio | Retângulo (card/painel/tabela/input/botão) → **10px**. Pill continua `9999px`. | `index.css`: `--radius: 0.625rem`; achatar a escala derivada pra `xl == lg == --radius` (cards usam `rounded-xl`, botões `rounded-lg` — os dois precisam cair em 10px). |
| Flat → com vida | Gradiente sutil, glow amarelo, glass leve, animação "na medida do protótipo" passam a ser aceitos. **Não** adotado: constelação/aurora/grain/scanline/sweep/parallax de tela cheia do protótipo (fora do princípio "ferramenta densa, rapidez > espetáculo", que o brief não derruba). | `index.css` tokens novos `--dp6-glow`, `--dp6-primary-2`, `--dp6-gradient-*`, `--dp6-shadow-glow`; utilitárias `.dp6-hoverable`, `.dp6-glass`. |
| Hover glow | Card, linha de tabela, item de menu: glow/sombra amarela, não só borda. | utilitária `.dp6-hoverable` + tratamento no padrão de tabela. |
| Motion | Teto de transição sobe de `≤200ms` pra `≤300ms` (protótipo usa .25–.28s). `prefers-reduced-motion` continua absoluto (reset global intocado). | `ui-ux-rules.md` §Movimento. |
| Ícone em KPI | Todo `MetricTile` ganha slot de ícone; mapeamento do brief. | `MetricTile` (prop `icon`). |
| Glow no cabeçalho | `PageHeader` ganha glow radial amarelo atrás do `<h1>`. | `PageHeader`. |
| Tooltip flutuante | Componente compartilhado que segue o cursor, pra gráfico/mini-gráfico. | novo `components/ChartTooltip.tsx` (+ hook). |

`docs/frontend/design-system.md` e `docs/frontend/ui-ux-rules.md` são
atualizados **no mesmo PR** da primeira mudança de token (PR 2), por regra do
próprio harness. `docs/skills/frontend.md` já é só um redirecionador (o
branch do harness migrou o conteúdo) — não precisa mexer.

---

## 4. Fatiamento em PRs (branches empilhadas, base `main`)

Cada branch parte da anterior. Push em qualquer branch ≠ `main` dispara
deploy em `dev` automaticamente — é o mecanismo de validação. Como as
branches são empilhadas, o deploy em `dev` a qualquer momento reflete a
**ponta** da pilha.

| PR | Branch | Escopo | Toca backend? | Spec com AC novo |
|----|--------|--------|:---:|---|
| 1 | `docs/frontend-refresh-plan` | Harness (`docs/frontend/**`) + referências visuais + brief + **este plano**. Base de tudo. | não | — |
| 2 | `feat/fe-refresh-foundation` | Tokens (`index.css`: raio 10px, glow/gradiente/glass, motion). `MetricTile` (ícone + hover lift/glow). `PageHeader` (glow). `components/ChartTooltip.tsx` novo. Utilitárias `.dp6-hoverable`/`.dp6-glass`. **Atualiza `design-system.md` + `ui-ux-rules.md` + `CHANGELOG.md`.** | não | — (mudança de token/harness, sem domínio) |
| 3 | `feat/fe-refresh-rename-catalogo` | "Catálogo" → **"Catálogo de Dados"** em toda a UI (label de seção da sidebar, títulos, breadcrumbs) + `docs/site/**` onde citar o nome. Mecânico. | não | — (renomeação, sem comportamento) |
| 4 | `feat/fe-refresh-sidebar` | Sidebar: item ativo (Q-001), ícone alinhado ao nome, espaçamento entre grupos + divisor em gradiente, hover glow. | não | — (visual; `ui-ux-rules.md` §Sidebar ajustada) |
| 5 | `feat/fe-refresh-tables` | Tratamento visual compartilhado de tabela: hover em gradiente + barra lateral amarela (glow). Aplicado via o padrão `SortableTableHead`/`ui-table` + utilitária, sem forkar a primitiva. | não | — (visual) |
| 6 | `feat/catalogo-de-dados-overview` | Constrói a **tela de overview** do Catálogo de Dados na rota índice `/` (hoje é só um `EmptyState` "selecione um dataset"). Grade de cards de dataset: ícone, qtd de tabelas, **mini-gráfico de distribuição de SLA** (Q-003), busca cruzada dataset+tabela. Extrai o gráfico "Distribuição por dataset" do Freshness pra `components/SlaDistributionBar.tsx` (reaproveitado dos dois lados). | não | `docs/specs/catalog.md` (overview + card), `docs/specs/freshness.md` (componente extraído) |
| 7 | `feat/catalog-dataset-description` | **Backend**: `DatasetSummary.description` de `INFORMATION_SCHEMA.SCHEMATA_OPTIONS`. **Frontend**: descrição no card (fallback "Sem descrição cadastrada no BigQuery"). | **sim** | `docs/specs/catalog.md` (AC: endpoint expõe `description` de dataset) |
| 8 | `feat/fe-refresh-freshness` | Painel "Distribuição por dataset" no visual novo (usa o componente extraído no PR 6). | não | `docs/specs/freshness.md` se o comportamento mudar |
| 9 | `feat/fe-refresh-lineage` | Arestas animadas ("vivas"), layout maior, hover nas arestas (não só nós), painéis: impacto a montante (com contagem), fontes, consumidores, indicador "cache há X · profundidade Y hops". | não | `docs/specs/lineage.md` (painéis + indicador de profundidade) |
| 10 | `feat/fe-refresh-quality` | "Análises de qualidade" sai do dialog pequeno → submódulo em tela cheia. Lista de tabelas no padrão visual novo. Botão "Analisar" (aqui e no Catálogo) → tela de escolha de tipo de análise (cards: Schema, Qualidade, PII, Tipos de coluna, Histórico, Acesso). Tela "Análise de qualidade" em tela cheia com cardinalidade em **barra horizontal + tooltip** (substitui os gauges). | não | `docs/specs/quality.md` + `docs/specs/profiling.md` (fluxo tela cheia, tela de escolha, barra horizontal) |
| 11 | `feat/fe-refresh-finops` | Custo acumulado+diário (combo bar+linha) filtrável (dataset/tabela/mês-dia/tipo de custo). Top ofensores com tendência. **Dois scores** distintos: (1) eficiência de custo geral (anel composto, já prototipado); (2) score por tabela (Q-002). Cadastro de budget por dataset e por tabela — **só cadastro simples, sem compartilhamento** (travado no brief). | talvez (filtros/score podem exigir agregação nova) | `docs/specs/finops-*.md` (filtros, dois scores, granularidade de budget) |
| 12 | `feat/fe-refresh-storage` | Cards de bucket com mini-gráfico, lifecycle tag, storage class, tamanho, objetos, região. Scanner de desperdício: tabela agrupada por recomendação + mini-gráfico por linha. | não | `docs/specs/storage.md` se comportamento mudar |
| 13 | `feat/fe-refresh-admin` | "Acessos": combo linha+coluna (diário × acumulado) com **controle de troca** de qual métrica é linha/coluna (decisão do usuário final, não fixa). Granularidade dia/mês + **filtro de período (de/até)** novo. Funil de retenção em **trapézios de verdade** com **rótulos FORA do trapézio** (nota técnica do brief — rótulo dentro colide em estágios estreitos). | talvez (filtro de/até pode exigir parâmetro novo no endpoint de analytics) | `docs/specs/admin.md` (filtro de período, controle de troca do combo, funil) |

### Fora do fatiamento (carve-out, spec + branch próprios, NÃO neste refresh)

- **IA de navegação "todo item de nível 1 abre tela de opções/overview".** O
  brief trata isso como convenção já validada no protótipo, mas o app real
  tem uma sidebar em árvore colapsável onde cada dataset é item próprio
  linkando direto pra `/datasets/:id`, com favoritos/filtro/histórico
  embutidos nessa árvore. Trocar isso por "nível 1 → landing" é mudança de
  IA grande numa superfície muito usada — merece spec e review dedicados
  (`feat/nav-overview-screens`). O que **entra** neste refresh: a tela de
  overview do Catálogo de Dados na rota `/` (PR 6), que hoje é só um
  `EmptyState` — adição pura, sem tirar nada da sidebar.
- **Compartilhamento de budget entre usuários** — já marcado como fora de
  escopo no brief. Sem modelo de dado, sem código.

---

## 5. Estado de execução

Sessão autônoma (usuário ausente até o review). Todas as branches são
**empilhadas** (cada uma parte da anterior) e estão em `origin`; a ordem da
tabela é a ordem de review/merge. `dev` reflete a ponta da pilha.
Verificação local por branch: `pnpm lint` + `pnpm build` (frontend) e
`uv run pytest tests/unit` + `ruff` (quando toca backend). **Validação
visual é do usuário, em `dev`.** Nada foi mergeado em `main`.

### Feito e no ar (`dev`)

| # | Branch | Escopo entregue | Verificação |
|---|--------|-----------------|-------------|
| 1 | `docs/frontend-refresh-plan` | harness (`docs/frontend/**`) + `docs/design-references/**` + brief + este plano | docs |
| 2 | `feat/fe-refresh-foundation` | `index.css`: `--radius` 10px + escala achatada; tokens `--primary-2`/`--glow`/`--shadow-glow`/`--ease-dp6`; utilitárias `.dp6-hoverable`/`.dp6-glass`/`.dp6-headline-glow`/`.dp6-gradient-primary`. `MetricTile` (prop `icon` + hover). `PageHeader` (glow). `ChartTooltip` + `useChartTooltip` novos. Harness §Vida + `ui-ux-rules.md` §Identidade/§Movimento + `CHANGELOG`. | lint+build |
| 3 | `feat/fe-refresh-rename-catalogo` | "Catálogo" → "Catálogo de Dados" (sidebar, breadcrumb Admin, `<h1>`, `docs/site`) | lint+build |
| 4 | `feat/fe-refresh-sidebar` | item ativo Q-001 (`.dp6-nav-active`), hover glow (`.dp6-nav-item`), ícone `Boxes` nos datasets, ícone do serviço em `--primary`, mais respiro | lint+build |
| 5 | `feat/fe-refresh-tables` | hover de linha global (`[data-slot=table-body] tr:hover` → gradiente + barra `inset 3px`) — vale pras ~30 tabelas | lint+build |
| 6 | `feat/catalogo-de-dados-overview` | rota `/` vira overview do domínio (`CatalogOverviewPage` + `DatasetOverviewCard` + `SlaDistributionBar` compartilhada + `KpiCards.icon`). ACs `AC-CAT-OV-*` em `catalog.md`; `SlaDistributionBar` em `freshness.md` | lint+build |
| 7 | `feat/catalog-dataset-description` | **backend, PARCIAL** — `DatasetSummary.description` (campo/tipo/card ok). A leitura via `SCHEMATA_OPTIONS` + `SAFE.JSON_VALUE` **quebrou `/validate` em `dev`** ("Failed to fetch") e foi revertida no PR 12 — o repository devolve `description: None` fixo. Repopular exige teste de integração (AC-CAT-DESC-03). | `pytest` ✓, ruff ✓ (mas mock não pega SQL inválido — ver PR 12) |
| 8 | `feat/fe-refresh-freshness` | `SlaRow` + `DatasetFreshnessTable` usam a `SlaDistributionBar` (coluna "Distribuição" + barra agregada). Cosmético | lint+build |
| 9 | `feat/fe-refresh-kpi-icons` | ícone no chip de cada KPI (mapeamento do brief) em `CatalogDatasetPage`, `BudgetPage`, `ProfilingDialog`, `LoginAnalyticsSection`, `AccessRequestAnalyticsSection` | lint+build |
| 10 | `feat/fe-refresh-primary-cta` | `.dp6-gradient-primary` nos CTAs herói (`DatasetScopeGate`, `ProfilingDialog`, `ColumnTypeSuggestionsTab`, `FinOpsPage`) | lint+build |
| 11 | `docs/fe-refresh-deferred-specs` | esta atualização de §5 + ACs/notas de "implementação pendente" nas specs de lineage/quality/finops/storage/admin | docs |
| 12 | `fix/catalog-description-safe` | **hotfix** — reverte a query de `description` da PR 7 que quebrou `/validate` em `dev` ("Failed to fetch"). `get_datasets_summary` volta ao original; `description: None`. Ver `CHANGELOG` §"Erros cometidos e aprendizados" | `pytest tests/unit` 783 ✓, ruff ✓; **backend redeployado em `dev`** |

### Especificado, implementação PENDENTE (precisa de iteração visual em `dev` com o usuário)

Os pedidos do brief que são **feature de dataviz nova**, não polish — grandes
demais pra fechar às cegas numa sessão autônoma sem ver o resultado. Cada um
tem ACs escritos na spec do domínio (seção "Refresh visual — pendente");
viram branch própria depois do review, com o usuário validando em `dev` a
cada iteração.

| Domínio | O que falta | Spec |
|---|---|---|
| Lineage | arestas "vivas" (animadas), layout maior, hover nas arestas, painéis impacto-a-montante (com contagem) / fontes / consumidores, indicador "cache há X · profundidade Y hops" | `lineage.md` §"Refresh visual — pendente" |
| Análises de qualidade | sair do dialog pequeno → submódulo em tela cheia; tela de escolha de tipo de análise (cards Schema/Qualidade/PII/Tipos/Histórico/Acesso); cardinalidade em barra horizontal + `ChartTooltip` (substitui os gauges) | `profiling.md` + `quality.md` §"Refresh visual — pendente" |
| FinOps | combo bar+linha (acumulado × diário) filtrável (dataset/tabela/mês-dia/tipo); Top ofensores com tendência; **dois scores** (eficiência geral em anel; score por tabela — Q-002); budget por dataset **e** por tabela | `finops-budget.md` + `finops-waste-scanner.md` §"Refresh visual — pendente" |
| Buckets (Storage) | cards de bucket com mini-sparkline + lifecycle tag + storage class + tamanho/objetos/região; scanner agrupado por recomendação + mini-gráfico por linha | `storage.md` §"Refresh visual — pendente" |
| Administração | combo linha+coluna com **controle de troca** de métrica (ASM-004); granularidade dia/mês + **filtro de período de/até** (novo); funil de retenção em **trapézios** com rótulos FORA do trapézio | `admin.md` §"Refresh visual — pendente" |

### Carve-out (spec + branch próprios, fora deste refresh)

- IA "todo item de nível 1 abre overview" na `DatasetSidebar` (a sidebar
  hoje dá drill-down direto no dataset) — `feat/nav-overview-screens`.
- Compartilhamento de budget entre usuários — já fora de escopo no brief.

---

## 6. Riscos / notas de execução

- **Sem app rodando localmente** (deploy é Cloud Run no push). Verificação
  local = `pnpm lint` + `pnpm build` + `pytest`/`ruff` + leitura de diff.
  A validação visual (glow calibrado? raio ok nos dois temas? contraste do
  item ativo? tilt sutil o suficiente?) é do usuário, em `dev`, no review.
- **Pilha de branches:** cada PR tem base `main` mas contém os commits das
  anteriores até elas mergearem. Revisar na ordem da tabela §5, ou revisar
  a ponta (`docs/fe-refresh-deferred-specs`) que tem o diff acumulado
  inteiro. Merge na ordem.
- **Efeitos de fundo do protótipo não adotados** (constelação, aurora,
  grain, scanline, sweep, parallax) — ASM-006. Se o usuário quiser algum,
  é decisão explícita no review.
- **`--radius-xl == --radius-lg`** quebra a monotonicidade da escala shadcn
  de propósito (card `rounded-xl` e botão `rounded-lg` precisam bater em
  10px). Documentado em `design-system.md` §Raio.
