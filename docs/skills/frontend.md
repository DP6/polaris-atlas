# Frontend Design Skill — Observability Hub

Identidade visual baseada no brand dp6 (part of the brandtech group).
Referência de produto: Metabase — denso, funcional, orientado a dados.
Filosofia: minimalismo com personalidade. Menos decoração, mais clareza.

---

## Paleta de cores

```css
/* Cores primárias dp6 */
--color-primary:       #FFB302;   /* amarelo dp6 — ações, destaques, CTAs */
--color-bg-dark:       #1D1D1B;   /* fundo escuro principal */
--color-bg-surface:    #2A2A28;   /* superfícies elevadas (cards, sidebar) */
--color-bg-muted:      #3A3A38;   /* hover states, bordas sutis */
--color-text-primary:  #FFFFFF;   /* texto principal no dark */
--color-text-muted:    #8F96A1;   /* texto secundário, labels — >=4.5:1 (WCAG AA) contra --color-bg-dark/-surface; #5B626C original tinha ~2.74:1, quase ilegível */
--color-text-inverse:  #1D1D1B;   /* texto sobre fundo amarelo */

/* Cores de status — DOIS papéis, não confundir:                       */
/* 1. preenchimento/gráfico (chip /10-/12, borda /30, barra) — os      */
/*    valores abaixo bastam (3:1 como fill), idênticos nos 2 temas     */
--status-ok:    #34D399;   --status-warn:  #FFB302;
--status-error: #E53E3E;   --status-info:  #63B3ED;
/* 2. texto/ícone sobre superfície tintada — variante `-foreground`,   */
/*    definida POR TEMA, contraste >= 4.5:1 nos dois. Classe:          */
/*    text-status-{ok,warn,error,info}-foreground                      */
/* :root (claro):  ok #0b7a43 · warn #8a5700 · error #c1291f · info #1a6ba8 */
/* .dark:          ok #34d399 · warn #ffb302 · error #f87171 · info #63b3ed */

/* Acento secundário */
--color-accent-blue:    #1A365D;
--color-accent-purple:  #6B46C1;
--color-accent-green:   #059669;
```

- **Nunca** usar `text-status-*` (sem `-foreground`) nem `text-primary`
  como cor de texto sobre `--background`/`--card` — falham AA no tema
  claro (amarelo dp6 ≈ 1.7:1). O `#FFB302` é para preenchimento (botão
  primário, barra dp6, indicador ativo), não para texto.
- Raio: `--radius-control` (botão/input/card/tabela/popover) e
  `--radius-pill` (badge/toggle). Não re-hardcodar `rounded-[Npx]`.

---

## Tipografia

Fonte **Ubuntu**, carregada via `<link>` em `apps/frontend/index.html`
(`family=Ubuntu:wght@300;400;500;700`) — **não** por `@import` no CSS.
Pesos disponíveis: 300, 400, **500**, 700. O peso **600
(`font-semibold`) não existe no Ubuntu** — usar `font-bold` (700) em
título e `font-medium` (500) onde precisa de peso médio.

Escala tipográfica **semântica** (tokens em `@theme inline` no
`src/index.css`), cada um com `--text-*--line-height`:

```css
--text-label:    0.75rem;   /* 12px — rótulo de campo, header de tabela, badge, caption */
--text-body:     0.875rem;  /* 14px — corpo, célula de tabela, descrição (mínimo de leitura) */
--text-subtitle: 1rem;      /* 16px — <h3> de subseção, valor de KPI */
--text-title:    1.25rem;   /* 20px — <h2> de seção, valor de MetricTile */
--text-display:  1.75rem;   /* 28px — <h1> de página (via PageHeader) */
```

- Usar as classes `text-label`/`text-body`/`text-subtitle`/`text-title`/`text-display`.
  Não usar `text-[11px]`/`text-[13px]` ad-hoc nem a escala antiga `text-xs..text-3xl` para hierarquia.
- Corpo nunca abaixo de 14px (`text-body`). `text-label`/12px só para rótulo/caption/badge.
- Bloco de texto corrido (descrição, callout) com `max-w-[65ch]`.

---

## Layout e espaçamento

O layout é **denso como Metabase** — máximo de informação na viewport sem scroll desnecessário.

```
┌─────────────────────────────────────────────────────────┐
│  Topbar: seletor de projeto + logo dp6          [240px] │
├──────────┬──────────────────────────────────────────────┤
│          │                                              │
│ Sidebar  │  Área principal de conteúdo                  │
│ 240px    │  (catálogo, freshness, tabelas)              │
│          │                                              │
│ datasets │                                              │
│ listados │                                              │
│          │                                              │
└──────────┴──────────────────────────────────────────────┘
```

- Sidebar: `240px` fixa, fundo `#2A2A28`, lista de datasets clicáveis
- Topbar: `56px`, fundo `#1D1D1B`, linha amarela inferior `2px solid #FFB302`
- Conteúdo: padding `24px`, dentro de um container `max-w-[1400px] mx-auto`
  (não estica de ponta a ponta em monitor largo)
- Cards: `border-radius: 8px`, fundo `#2A2A28`, sem sombras pesadas

**Escala de espaçamento** (4/8/12/16/24/32) — convenção de uso:

| Entre o quê | gap |
|---|---|
| Seções de página (separação semântica forte) | `gap-8` (32) |
| Blocos dentro de uma seção | `gap-4` (16) |
| Elementos relacionados (label+control, ícone+texto) | `gap-2`/`gap-1.5` |
| Padding interno de card/callout | `p-4`; célula de tabela `p-2` |

---

## Elementos gráficos dp6

### Linha vertical amarela (divisor de identidade)
```css
.dp6-divider {
  width: 2px;
  background: #FFB302;
  height: 100%;
}
```
Usar como separador entre logo e título, ou como accent lateral em seções.

### Cards com borda amarela em hover
```css
.card {
  background: #2A2A28;
  border: 1px solid #3A3A38;
  border-radius: 8px;
  transition: border-color 0.15s;
}
.card:hover {
  border-color: #FFB302;
}
```

### Botão primário (CTA)
```css
.btn-primary {
  background: #FFB302;
  color: #1D1D1B;
  font-weight: 700;
  border-radius: 6px;
  padding: 8px 16px;
}
.btn-primary:hover {
  background: #E6A000;
}
```

### Botão secundário (outline)
```css
.btn-secondary {
  background: transparent;
  color: #FFB302;
  border: 1px solid #FFB302;
  border-radius: 6px;
  padding: 8px 16px;
}
```

---

## Componentes compartilhados

Vieram da auditoria de UI/acessibilidade (branch `fix/ui-a11y-tokens`,
2026-08). **Usar estes em vez de recriar o padrão à mão** — todos em
`apps/frontend/src/components/`.

| Componente | Quando usar |
|---|---|
| `PageHeader` | Cabeçalho de rota: um `<h1>` (`text-display`) + subtítulo + slot `actions` + link `back` opcional. Um por rota, fora dos ramos de loading/erro. Empilha em `< sm`. |
| `SectionHeading` | `<h2>`/`<h3>` reais dentro de uma página (`text-title`/`text-subtitle`), com slot `actions`. Nunca `<h2 class="text-xs uppercase muted">`. |
| `WarningCallout` | Aviso/degradação (`role="status"`, ícone + texto, `variant="warning"|"info"`). Substitui os banners de `warning` copiados à mão. |
| `ApiErrorNotice` | Erro de query (`role="alert"`, mostra a mensagem real da API + comando `gcloud` de correção quando existe). Não usar `<p class="text-status-error">Erro ao carregar…</p>`. |
| `LoadingState` | Carregando (spinner + texto). Substitui os `<p>Carregando…</p>` soltos. |
| `EmptyState` / `EmptyStateRow` | Estado vazio (ícone + título + descrição/ação). `EmptyStateRow` para dentro de `<TableBody>`. |
| `StatusBadge` | Badge de estado com ícone (`status="ok|warn|error|info|running|neutral"`). Nunca comunicar estado só por cor. |
| `MetricTile` / `MetricGrid` | Tile de KPI (valor `text-title`, label `text-label uppercase`) em grid auto-fill. Substitui tiles à mão. |
| `ChoiceToggle` | Grupo "escolher um" em pills (`aria-pressed`, `size="sm|md"`). Substitui pill/Button-group/Select ad-hoc. |
| `DateField` | `<input type="date">` com `<Label>` associada e altura consistente. |
| `SortableTableHead` | `<th>` clicável com seta de ordenação. |

---

## Acessibilidade (WCAG 2.1 AA) — obrigatório

- **Contraste**: texto ≥ 4.5:1, ícone/borda/gráfico ≥ 3:1, **nos dois temas**. Usar as variantes `-foreground` das cores de status.
- **Foco visível**: regra global em `index.css` (`:focus-visible { outline: 2px solid var(--color-ring) }`) — não remover com `outline-none` sem repor.
- **Nunca só por cor**: todo estado/erro = ícone + texto (`WarningCallout`, `StatusBadge`, input inválido com ícone + `role="alert"`).
- **Semântica**: um `<h1>` por rota (via `PageHeader`); `<h2>`/`<h3>` reais nas seções; toda `<label>` associada (usar o componente `<Label>`); `aria-label` em filtro/combobox sem rótulo visível.
- **Alvo de toque ≥ 24×24 px** (2.5.8) — botões pequenos (estrela de favoritar etc.) com `size-6` mínimo.
- **`prefers-reduced-motion`**: reset global já cobre animação/transição/scroll — não adicionar animação que ignore a preferência.
- Ícone decorativo com `aria-hidden="true"`; ícone informativo com rótulo (`<span class="sr-only">` ou texto ao lado).

---

## Componentes principais

### Topbar — seletor de projeto
```
┌─────────────────────────────────────────────────────────┐
│ ▌ dp6   │  GCP Project: [observability-hub-dev    ▾]   │
└─────────────────────────────────────────────────────────┘
```
- Logo dp6 à esquerda com linha vertical amarela divisora
- Input de projeto com ícone de busca, validação visual (verde = acessível, vermelho = sem acesso)
- Ao validar com sucesso: sidebar popula com os datasets do projeto

### Sidebar — lista de datasets
```
DATASETS DISPONÍVEIS
━━━━━━━━━━━━━━━━━━━
● RAW          [3 tabelas]
  TRUSTED      [2 tabelas]
  REFINED      [2 views]
```
- Item ativo: fundo `#FFB302`, texto `#1D1D1B`, font-weight 700
- Item inativo: texto `#FFFFFF`, hover fundo `#3A3A38`
- Ponto colorido de status SLA ao lado do nome (verde/amarelo/vermelho)

### Cards de resumo do dataset (KPI row)
```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  REGIÃO  │ │  TABELAS │ │  TAMANHO │ │   LINHAS │ │  FRESHNESS│
│    US    │ │    3     │ │  1.98 MB │ │  30.000  │ │  >1 mês  │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
```
- `MetricGrid` + `MetricTile` (grid auto-fill)
- Valor em `text-title` bold, label em `text-label` muted uppercase
- Card de alerta (`alert` prop): borda `--status-error`

### Tabela de ativos
- Header: uppercase, `--text-xs`, `--color-text-muted`, border-bottom `#3A3A38`
- Linhas: hover fundo `#3A3A38`, cursor pointer
- Badge de tipo (TABLE / VIEW / EXTERNAL): pill com fundo `#3A3A38`, texto `--text-xs`
- Botão "Analisar": outline amarelo, só aparece no hover da linha
- Colunas: Nome/ID, Tipo, Qtd Colunas, Criação, Atualização, Linhas, Volume, Região

### SLA de atualização (freshness row)
```
Até 12h    12h a 24h   24h a 48h   48h a 7d    7d a 1m    >1 mês
   0           0           0           0           0          3
```
- 6 colunas em row, label `--text-xs` muted, valor `--text-xl` bold
- Valor > 0: colorido conforme status (verde → vermelho)
- Valor = 0: `--color-text-muted`

### Modal de profiling
- Overlay: `rgba(0,0,0,0.7)`, blur backdrop
- Modal: `max-width: 900px`, fundo `#2A2A28`, padding `32px`
- Header: "MÓDULO DE QUALIDADE" em `--text-xs` uppercase amarelo, tabela em `--text-lg`
- Linha de controles: Amostragem | Método Unicidade | Coluna de Data | Janela | [Estimar Custo] [Executar Profile]
- Seção de resultado SQL: fundo `#1D1D1B`, `font-family: monospace`, texto branco, botão "Copiar SQL"
- Tabela de resultados por coluna:
  - Completude: barra de progresso (verde se >80%, amarelo se 50-80%, vermelho se <50%)
  - Unicidade HLL: valor % em roxo se alta cardinalidade, laranja se baixa
  - Min/Max: texto muted

---

## Ícones

Usar `lucide-react` (já disponível no projeto). Ícones outline, tamanho padrão `16px` inline, `20px` em botões.

Mapeamento de domínios:
- Catálogo: `Database`
- Freshness: `Clock`
- Profiling: `BarChart2`
- FinOps: `DollarSign`
- Qualidade: `CheckCircle`
- Alerta: `AlertTriangle`
- Projeto GCP: `Cloud`

---

## Regras de UI — o que NÃO fazer

- Não usar gradientes — identidade dp6 é flat
- Não usar sombras pesadas (`box-shadow`) — bordas sutis são suficientes
- Não usar mais de 2 cores de destaque por tela
- Não centralizar texto em tabelas — sempre left-align exceto números (right-align)
- Não usar skeleton loaders elaborados — usar `LoadingState` (spinner + texto, cor muted)
- Não adicionar animações longas — transitions máximo `200ms`; sempre respeitar `prefers-reduced-motion`
- Não usar fontes além de Ubuntu/Verdana
- Não criar páginas separadas por domínio — tudo na mesma SPA com sidebar

---

## Modo claro

Implementado (pedido do usuário, 2026-08-22) — `apps/frontend/src/hooks/useTheme.ts` alterna a classe `.dark` em `<html>`, persistida em `localStorage` (`observability-hub:theme`), com botão de alternância no Topbar (`components/ThemeToggle.tsx`). Dark continua sendo o padrão (ausência de valor salvo = dark); script bloqueante em `index.html` aplica a classe antes do primeiro paint pra evitar flash do tema errado.

Variáveis de cor em `src/index.css`: `--color-bg-*`/`--color-text-*` invertidos entre `:root` (light) e `.dark`. O `#FFB302` e os valores de **preenchimento** `--status-*`/accent-* são idênticos nos dois temas; as variantes de **texto** `--status-*-foreground` (adicionadas na auditoria de 2026-08) **diferem por tema** para passar contraste AA no claro.

---

## Tailwind (v4 — sem arquivo de config)

O projeto usa **Tailwind v4**: os tokens vivem num bloco `@theme inline`
em `apps/frontend/src/index.css` (pares `--color-*: var(--*)`,
`--text-*`, `--radius-*`, `--shadow-*`), com `:root` (claro) + `.dark`
logo abaixo. **Não existe `tailwind.config.js`** — para adicionar/alterar
um token, editar o `@theme inline` e os blocos `:root`/`.dark`.

Regras plain-CSS relevantes no mesmo arquivo (fora de `@layer`):
`:focus-visible` global, `@media (prefers-reduced-motion: reduce)` reset,
`.dp6-divider`, scrollbar fina.
