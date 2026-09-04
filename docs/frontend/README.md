# Harness de front-end

Tudo que uma sessão (humana ou do Claude Code) precisa saber para mexer em
`apps/frontend/` sem reabrir decisões já tomadas nem reinventar padrão que
já existe.

## Regra de ouro

> **O código é a fonte de verdade dos _valores_. Este harness é a fonte de
> verdade das _decisões_ e do _porquê_.**
>
> - Os tokens reais vivem em `apps/frontend/src/index.css`. Os componentes
>   reais vivem em `apps/frontend/src/components/`. Se o número (um hex, um
>   `rem`, um raio) está aqui e não bate com o código, **o código vence** —
>   e este doc está com bug, conserte.
> - As regras normativas (`ui-ux-rules.md`, `accessibility.md`) e o
>   racional vivem aqui. Se o código faz diferente de uma regra sem
>   justificativa registrada, **o doc vence** — o código está com bug.

## Arquivos

| Arquivo | O que é | Muda quando |
|---|---|---|
| [`design-system.md`](design-system.md) | O contrato com o código: tokens (espelho de `index.css`), catálogo dos componentes compartilhados, regra dos primitivos shadcn | um token ou componente muda — **no mesmo PR** |
| [`ui-ux-rules.md`](ui-ux-rules.md) | Regras normativas ("sempre / nunca") com 1 linha de porquê | decisão de produto/design |
| [`accessibility.md`](accessibility.md) | WCAG 2.1 AA como checklist acionável + como verificar | raro |
| [`patterns.md`](patterns.md) | Composições recorrentes (tabela filtrável, linha de KPIs, fluxo de análise, gate de escopo…) e qual componente/hook usar | surge um padrão novo repetido em 2+ telas |
| [`behaviors.md`](behaviors.md) | Comportamento esperado: loading / erro / vazio, data fetching, feedback, formatação, tema | raro |
| [`references.md`](references.md) | Índice de referências: telas canônicas internas + capturas externas (`docs/design-references/`) | continuamente (só cresce) |
| [`CHECKLIST.md`](CHECKLIST.md) | Checklist de entrega de qualquer tarefa de front-end | quando uma regra vira item obrigatório |

## O que ler antes de cada tarefa

| Tarefa | Ler antes |
|---|---|
| Ajustar um token (cor, tipografia, espaçamento, raio) | `design-system.md` → editar `apps/frontend/src/index.css` **e** `design-system.md` no mesmo PR |
| Criar ou alterar um componente compartilhado (`src/components/`) | `design-system.md` (§Catálogo) + `ui-ux-rules.md` + `patterns.md` |
| Adicionar um primitivo shadcn (`src/components/ui/`) | `design-system.md` (§Primitivos) |
| Montar uma tela / feature nova | os quatro acima + `behaviors.md` + `references.md` |
| Mexer só em acessibilidade | `accessibility.md` |
| Revisar um PR de front-end | `ui-ux-rules.md` + `accessibility.md` + `CHECKLIST.md` |

## O que este harness NÃO é

- **Não é `docs/site/`.** `docs/site/` é material de **produto** (slide
  deck, guia técnico funcionalidade a funcionalidade, vitrine de
  componentes GCP) — depende de print de tela real e curadoria manual, e
  não é mantido em sincronia numa sessão de código.
- **Não é spec de domínio.** O contrato de dados de cada tela (endpoints,
  response schema, parâmetros) está em `docs/specs/<domínio>.md`.
- **Não define arquitetura de app** (rotas, providers, camadas). Isso está
  em `CLAUDE.md` (§"Convenções — Frontend" e §"Estrutura de pastas").
