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

Atualizado a cada branch concluída e empurrada pra `dev`.

| PR | Status | Commit(s) / nota |
|----|--------|------------------|
| 1 | _em andamento_ | branch criada de `origin/docs/frontend-harness` + merge `origin/main` (#51) + brief + este plano |
| 2–13 | pendente | — |

---

## 6. Riscos / o que pode não caber nesta sessão

- PRs 9–13 (lineage, quality, finops, storage, admin) são telas ricas de
  dataviz — arestas animadas, funil geométrico, combo charts, barras
  horizontais com tooltip compartilhado, mini-sparklines. Implementar +
  verificar `pnpm lint`/`pnpm build` em todas numa sessão pode não caber.
  Onde não couber, a branch fica com o esqueleto + a spec com os ACs
  escritos, e o estado real é anotado em §5 — o usuário decide no review
  se mergeia o que tem ou pede a continuação.
- Não há como rodar o app localmente aqui (deploy é em Cloud Run no push);
  a verificação local é `pnpm lint` + `pnpm build` + leitura de diff. A
  validação visual real é do usuário, em `dev`, no review final.
