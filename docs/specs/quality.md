# Spec — Módulo de análise de tabela (rotas `/analyze/*`)

Criado na rodada 2 do refresh visual (R2-7). O fluxo de análise de uma
tabela deixou de ser um `Dialog` (`ProfilingDialog`, **deletado**) e virou
uma subárvore de rotas em tela cheia. Contratos de dados de cada tipo de
análise vivem nas specs próprias: `profiling.md`, `pii.md`, `access.md`,
`history.md` (profiling history), `finops-column-types.md`, `lineage.md`.

## Objetivo

Brief `frontend-visual-refresh.md` §"Análises de qualidade": "Analisar"
abre uma tela cheia com uma tela de escolha de tipo de análise (cards) e
uma rota própria por módulo. Decisão do usuário (rodada 2): os **7 tipos
ativos** (nada "em breve").

## Rotas

`apps/frontend/src/app/router.tsx`, aninhadas sob `analyze/:datasetId/:tableId`
→ `AnalysisLayout` (element pai — provê `AnalysisContext` com `projectId`,
`datasetId`, `tableId`, `tableDetail`, `isView`; só `<Outlet/>`).

| Rota | Página | Corpo (liftado do ex-tab) |
|---|---|---|
| `/analyze/:d/:t` (index) | `AnalysisChooserPage` | `OptionCardGrid` de 7 cards |
| `…/schema` | `SchemaAnalysisPage` | `SchemaTable` |
| `…/quality` | `QualityAnalysisPage` | `QualityAnalysisPanel` (fluxo config→estimar→executar) |
| `…/pii` | `PiiAnalysisPage` | `PiiTab` |
| `…/column-types` | `ColumnTypesAnalysisPage` | `ColumnTypeSuggestionsTab` |
| `…/history` | `HistoryAnalysisPage` | `HistoryTab` |
| `…/access` | `AccessAnalysisPage` | `AccessTab` |
| `/lineage/:d/:t` | `LineagePage` (R2-8) | `LineageGraph` + painéis |

Entradas: `AssetsTable` "Analisar" (`navigate('/analyze/:d/:t', { state:{
from } })`) e `QualityTablesPage` (função → tabela). Cada página de módulo
tem seu `PageHeader` com `back` pra `..` (o chooser); o chooser volta pra
`location.state.from` ?? `/datasets/:datasetId`.

## Critérios de aceite

| ID | Comportamento | Teste |
|---|---|---|
| AC-QUAL-RV-01 | O fluxo de análise é rota/tela cheia (`/analyze/*`), não `Dialog`. `ProfilingDialog.tsx` não existe mais. | `AnalysisLayout` — visual |
| AC-QUAL-RV-02 | "Analisar" (no `AssetsTable` do Catálogo de Dados **e** no `QualityTablesPage`) abre `/analyze/:d/:t` — grade de cards Schema / Análise de qualidade (destaque) / PII / Tipos de coluna / Histórico / Mapa de acesso / Lineage. Cada card abre o módulo em tela cheia. | `AnalysisChooserPage` — visual |
| AC-QUAL-RV-03 | `QualityAnalysisPage` mostra, além da tabela de resultado: um `<CompositeScoreRing>` "Quality Score" (completude média + densidade + cobertura de tipo) e um `<HBarList>` "Cardinalidade por coluna" (barra horizontal + `ChartTooltip` no hover) — substitui os gauges pequenos. `CompletenessBar` continua na coluna de completude do `ColumnResultsTable`. | `QualityAnalysisPanel` — visual |
| AC-QUAL-RV-04 | Lista de tabelas pra análise (`QualityTablesPage`) segue o padrão de tabela do refresh (hover gradiente + barra — regra global de R1). | visual |

## Suposições

- **ASM-QUAL-RV-01** (resolvida — R2-7): chegar por Catálogo (dataset →
  Analisar) ou pela lista de Qualidade (função → tabela) leva à MESMA
  subárvore `/analyze/:d/:t`. O `state.from` só muda o alvo do `back`.

## Fora do escopo

- Persistir a última aba/tipo escolhido por tabela. Cada visita começa no
  chooser.
- Deep-link com o resultado de profiling já materializado (o
  `runMutation` é sempre disparado pelo botão, nunca no mount).
