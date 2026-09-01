# Referências

Onde olhar quando precisa de um exemplo — de layout, de padrão ou de
comportamento. Duas fontes: **telas reais do Hub** (a autoridade sobre
"como fazemos") e **capturas de sites externos** (inspiração de linguagem
visual, não de densidade).

---

## Internas — telas canônicas do Hub

Para cada necessidade, a tela que melhor a resolve hoje. Abrir o arquivo,
ver como foi feito, seguir o mesmo caminho.

| Preciso de exemplo de… | Olhar |
|---|---|
| Cabeçalho de rota + ações + estado de carregamento | `features/catalog/CatalogOverviewPage.tsx` |
| Tabela grande filtrável / ordenável / paginada | `features/storage/WastePage.tsx`, `features/lineage/OrphansPage.tsx` |
| Linha de KPIs | `features/catalog/KpiCards.tsx`, `features/finops/BudgetPage.tsx` |
| Fluxo "config → estimar custo → executar → resultado" | `features/quality/ProfilingDialog.tsx`, `features/finops/ColumnTypeSuggestionsTab.tsx` |
| Gate de escopo antes de scan de projeto | `features/lineage/OrphansPage.tsx` (`DatasetScopeGate`) |
| Página longa em seções colapsáveis | `features/admin/AdminUsageTab.tsx` + `features/admin/*Section.tsx` |
| Dialog com formulário | `features/admin/RequestAccessDialog.tsx` |
| Dado servido de cache + refresh manual | `features/lineage/LineageTab.tsx` |
| Sidebar de navegação em dois níveis | `features/catalog/DatasetSidebar.tsx` |
| Tela de login / identidade dp6 | `features/auth/LoginPage.tsx`, `app/topbar.tsx` |
| Gráfico (Recharts) | `features/admin/UsageHeatmapGrid.tsx`, seções de analytics do Admin |
| Tooltip flutuante de gráfico (segue o cursor) | `components/ChartTooltip.tsx` + `useChartTooltip` — sem tela canônica ainda (chega com os PRs de quality/finops/admin do refresh visual) |
| Grafo de nós (xyflow) | `features/lineage/LineageGraph.tsx` |

Ver também os padrões descritos em [`patterns.md`](patterns.md) — cada um
já aponta seu arquivo canônico.

### Registro visual do produto em uso

`docs/site/produto/images/*.png` — prints tela a tela do Hub rodando
(login, catálogo, qualidade, lineage, PII, acesso, freshness, FinOps,
storage, admin). Servem para ver o resultado montado, não o código.
São material de **produto** (mantidos à mão) — não confundir com o
harness.

---

## Externas — `docs/design-references/`

Capturas de **The Brandtech Group** e **Jellyfish** (o Hub é da dp6, que
é parte do brandtech group; Jellyfish é uma empresa irmã). Ficam em
`docs/design-references/captures/<site>/`, com `manifest.json` (URL +
data de cada captura) e `README.md` próprios. Regeração:
`node scripts/capture-design-refs.mjs` (ver o README de lá).

**O que emprestar destas referências:**

- Linguagem visual *flat* — sem gradiente, sem sombra pesada.
- Amarelo como acento único e forte sobre neutros escuros.
- Tipografia com peso alto em título, contraste de tamanho generoso entre
  título e corpo.
- Divisor/linha vertical amarela como elemento de identidade
  (`.dp6-divider` no Hub).

**O que NÃO copiar:**

- **A densidade.** Esses sites são marketing — hero de tela cheia, muito
  respiro, blocos gigantes. O Hub é uma ferramenta de análise densa
  ([`ui-ux-rules.md`](ui-ux-rules.md) §Layout e densidade).
- Animações de scroll, parallax, transições longas.
- Imagens fotográficas de fundo.

Quando adicionar telas novas ao corpus externo (ou outros sites): editar
`docs/design-references/sources.json` e rodar o script; anotar aqui se a
referência passar a ser citada por um padrão específico.
