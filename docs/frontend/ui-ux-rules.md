# Regras de UI/UX

Regras normativas. Cada uma: **o quê** + **por quê** + (quando útil) onde
no código. Se for quebrar uma, registre a justificativa no PR e no
`CHANGELOG.md`.

Valores e tokens: [`design-system.md`](design-system.md).
Acessibilidade (é obrigatória, tem arquivo próprio): [`accessibility.md`](accessibility.md).

---

## Identidade visual

Relaxada no refresh visual 2026-09 (brief:
`docs/specs/frontend-visual-refresh.md`; tokens/utilitárias em
[`design-system.md`](design-system.md) §Vida). Gradiente sutil, glow
amarelo, glass leve e movimento passam a ser aceitos **na medida do
protótipo** — não ilimitado.

| Regra | Por quê |
|---|---|
| **Gradiente sutil só em elemento pequeno de ação/estado** (rodada 3) — topo `--primary-2` → `--primary` em botão herói (`.dp6-gradient-primary`), barra ativa da sidebar (`.dp6-nav-active`), preenchimento de gráfico. **Nada de gradiente em tela cheia ou cabeçalho** (o wash do `PageHeader` foi removido). Superfície é cor chapada (`bg-card`). | O gradiente marca o elemento; espalhado numa tela/cabeçalho, vira ruído. |
| **Hover é discreto** (rodada 3) — card, painel, linha clicável, item de menu usam `.dp6-hoverable` = só contorno fino de 1px em `--primary` (+ `translateY` gated). **Sem glow grande** (`--shadow-glow` aposentado). Card não-clicável (big number) não tem hover nenhum. | Numa tela densa o glow cheio vira ruído; a borda fina já sinaliza. |
| **`box-shadow` pesado continua proibido** fora de `--shadow-elevation-1/2` (popover/dialog/opt-card hover). Profundidade estática ainda vem de **borda**. | Consistência; borda lê melhor em tela densa. |
| **Nada de efeito de fundo de tela cheia nem de cabeçalho** — constelação, aurora/blobs, grain, scanlines, "sweep", parallax, **e o glow radial do cabeçalho / as brand-bars** (removidos na rodada 3). | O Hub é ferramenta de análise densa — "rapidez > espetáculo". |
| **Cor de card é sempre `bg-card`** — nenhum card usa amarelo (`--primary`) ou outra cor como fundo/destaque. Diferenciação de um card sobre os outros vem **só do hover**. | O amarelo chapado num card compete com o conteúdo e falha AA como texto sobre ele. |
| **No máximo 2 cores de destaque por tela.** | O amarelo dp6 perde força se competir com 3+ acentos. Acentos secundários (`--accent-*`) são pontuais. |
| **Só as fontes Ubuntu / Verdana.** | `--font-sans` já resolve; qualquer outra família quebra a identidade e adiciona peso de carregamento. |
| **Amarelo `#FFB302` / `--primary-2` é preenchimento, nunca texto** sobre `--background`/`--card`. | ≈1.7:1 de contraste no tema claro — falha WCAG AA. Vale para `text-primary` e `text-status-*` sem `-foreground`. |

## Layout e densidade

| Regra | Por quê |
|---|---|
| **Denso, estilo Metabase.** Máximo de informação na viewport sem scroll desnecessário; padding de card `p-4`, célula de tabela `p-2`. | É uma ferramenta de análise de dados, não um site de marketing. As referências externas em [`references.md`](references.md) são *arejadas* — não copiar a densidade delas. |
| **Conteúdo dentro de `max-w-[1400px] mx-auto`.** | Já aplicado em `apps/frontend/src/app/layout.tsx`. Linha de texto/tabela não deve esticar de ponta a ponta em monitor largo. |
| **Uma SPA só, com sidebar.** Não criar página/rota isolada por domínio fora do shell (`AppLayout` + `Topbar` + `DatasetSidebar`). | Navegação previsível; o contexto de projeto/dataset é compartilhado. |
| **Cabeçalho de grupo da sidebar = nome (`NavLink` pra `/{grupo}`) + chevron (disclosure) separados.** Clicar no nome abre a tela de overview do grupo; o chevron só expande/recolhe a lista inline. | Decisão do usuário (rodada 2): drill-down e overview são dois caminhos, não um. Ver `docs/specs/nav-overview-screens.md`. |
| **Grupos da `DatasetSidebar` começam recolhidos e o estado não é persistido.** | Decisão de produto confirmada (2026-08-30) — "sidebar menos carregada no primeiro acesso". Não inverter sem reconfirmar. (O recolhedor da sidebar **inteira**, `useSidebarCollapsed`, é outra coisa e é persistido — ver [`behaviors.md`](behaviors.md).) |
| **Espaçamento pela escala 4/8/12/16/24/32** (`gap-2`/`gap-4`/`gap-8`), não valores ad-hoc. | Ritmo visual consistente entre telas feitas por sessões diferentes. |

## Tipografia e hierarquia

| Regra | Por quê |
|---|---|
| **Um `<h1>` por rota, via `PageHeader`** (`text-display`), renderizado fora dos ramos de loading/erro. | Antes cada rota copiava o bloco à mão — algumas com `<h1>` duplicado entre estados, a rota índice sem `<h1>` nenhum. |
| **Seções são `<h2>`/`<h3>` reais** (`SectionHeading` ou `CollapsibleSection`), com tamanho/peso visível. **Nunca** `<h2 class="text-xs uppercase text-muted-foreground">` nem `<div>`/`<p>` fazendo as vezes de título. | Navegação por cabeçalho no leitor de tela; hierarquia real, não só aparência. |
| **Hierarquia pela escala semântica** `text-label/body/subtitle/title/display`. Nada de `text-[13px]` ad-hoc nem `text-xs…text-3xl` para hierarquia. | A escala tem propósito fixo por nível; ad-hoc diverge entre telas. |
| **Peso 700 (`font-bold`) ou 500 (`font-medium`) — nunca 600.** | O Ubuntu não tem peso 600; `font-semibold` renderiza como 400 ou 700 dependendo do fallback. |
| **Corpo nunca abaixo de 14px** (`text-body`). Texto corrido com `max-w-[65ch]`. | Legibilidade. |

## Cor e estado

| Regra | Por quê |
|---|---|
| **Estado nunca só por cor** — sempre ícone + texto (`StatusBadge`, `WarningCallout`, input inválido com ícone + `role="alert"`). | WCAG 1.4.1. Daltonismo, tema de alto contraste, print em P&B. |
| **Cor de estado como texto/ícone = `text-status-*-foreground`** (calibrada por tema para ≥4.5:1). `--status-*` sem sufixo só como preenchimento/borda (`bg-status-warn/12`, `border-status-warn/30`). | Os valores de fill têm ~1.7–3.9:1 como texto no claro. |
| **Reusar os componentes de estado** (`LoadingState`, `ApiErrorNotice`, `EmptyState`, `WarningCallout`, `StatusBadge`) em vez de montar o bloco à mão. | Já existem porque foram deduplicados de ~10–17 cópias divergentes cada. Ver [`behaviors.md`](behaviors.md). |

## Tabelas

| Regra | Por quê |
|---|---|
| **Left-align sempre, exceto números → right-align.** Não centralizar texto em célula. | Leitura em coluna; números alinham pela unidade. |
| **Ordenação via `SortableTableHead` + `useTableFilterSort`**; paginação via `PaginationBar` + `usePagination`. | Pipeline único (filtra → ordena → pagina) em vez de reimplementar por tabela. Ver [`patterns.md`](patterns.md). |
| **Estado vazio da tabela = `EmptyStateRow`** (dentro do `<TableBody>`, com `colSpan`), não uma linha "—" solta. | — |
| **Hover de linha = gradiente amarelo sutil + barra lateral `inset 3px`** em `--primary` (refresh visual — regra global em `index.css`, não precisa de classe por tabela). | Sinaliza a linha sob o cursor melhor que o `bg-muted` chapado numa tela densa; consistente com o hover de card/menu. |

## Movimento

| Regra | Por quê |
|---|---|
| **Transições ≤ 300ms** (era ≤200; subiu no refresh visual 2026-09 — o protótipo usa .25–.28s nos hovers "com vida"). Entradas de gráfico (draw de linha/barra) podem ir a ~1.4s **uma vez**, no mount. Nada de loop decorativo. | Ferramenta de trabalho: rapidez > espetáculo, mas o hover/entrada ganhou um respiro. |
| **Curva padrão = `--ease-dp6`** (`ease-dp6`) pros hovers/entradas do refresh. | Consistência entre telas de sessões diferentes. |
| **Respeitar `prefers-reduced-motion` sempre.** O reset global em `index.css` já cobre animação/transição/scroll — não adicionar efeito que o ignore (`.dp6-hoverable` já gate o `translateY` em `no-preference`). | WCAG 2.3.3 / boa prática AA; enjôo vestibular. |
| **Sem skeleton loader elaborado.** Carregando = `LoadingState` (spinner + texto, cor `muted`). | Skeleton fiel dá manutenção alta e engana sobre o layout final; o ganho percebido é baixo numa tela densa. |
