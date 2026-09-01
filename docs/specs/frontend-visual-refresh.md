# Brief — Refresh visual do Hub (protótipo → app real, dev → prod)

> **Isto não é uma spec formal ainda.** É o brief organizado de decisões de
> design tomadas em cima de um protótipo visual, pronto pra outra sessão
> de Claude Code transformar em plano + specs por domínio. Não implementar
> direto daqui sem passar pelo fluxo normal (spec aprovada por domínio
> tocado, `docs/frontend/CHECKLIST.md`, dev → validação → aprovação
> explícita do usuário → prod).

## Contexto

Depois de construir um protótipo visual fora do repo (não funcional,
`~/polaris-hub-mockup/index.html`, servido em `localhost:4477`, ~1200
linhas de HTML/CSS/JS auto-contido) explorando uma direção mais
"moderna" pro Hub — gradientes sutis, glow amarelo, glassmorphism leve,
tooltips flutuantes, micro-animações — sobre a mesma paleta/identidade
dp6 já usada no app, o usuário quer levar essas decisões pro app real
(`apps/frontend/`), começando em dev e só indo pra prod com aprovação.

**Ler antes de tocar em código:** `docs/frontend/` (harness — `README.md`
dá o roteiro de leitura). Este refresh **muda várias convenções** desse
harness — ver seção abaixo. O harness precisa ser atualizado no mesmo PR
de qualquer mudança de token, por regra própria dele
(`design-system.md`: "nenhum token muda no `index.css` sem atualizar
este arquivo no mesmo PR").

**Referências visuais:**
- `~/polaris-hub-mockup/index.html` — protótipo local (pode não estar
  mais no ar; pedir pro usuário resubir se `localhost:4477` não
  responder — `python3 -m http.server 4477 --directory
  ~/polaris-hub-mockup`).
- `docs/design-references/` (já no repo) — capturas de dp6.com.br e
  Jellyfish.
- Sem PDF de identidade visual adicional — o usuário confirmou seguir só
  com o que já está no protótipo.

**Regra de deploy (CLAUDE.md, não muda):** nunca fazer push, merge pra
`main` ou aprovar o gate de prod sem confirmação explícita do usuário a
cada vez. Este brief cobre até "implementado e validado em dev" — prod é
uma decisão separada, feita depois, com o usuário.

---

## Convenções de design que MUDAM

Atualizar `docs/frontend/design-system.md` (tokens) e
`docs/frontend/ui-ux-rules.md` (regras) **no mesmo PR** de qualquer
mudança de token/componente.

1. **Raio de borda — todo retângulo vira `10px`** (quase quadrado):
   cards, painéis, tabelas, inputs, botões. Substitui o
   `--radius-control` atual. **Elementos pill continuam 100% arredondados**
   (badge, toggle, avatar, `--radius-pill`) — a mudança é só em
   quadrados/retângulos, não em tudo.
2. A regra atual "sem gradiente, sem sombra pesada, flat" fica **relaxada**:
   gradiente sutil, glow amarelo, glassmorphism leve e animação passam a
   ser aceitos — na medida do protótipo (ver `.panel`, `.kpi`, `.btn.primary`
   no mock), não ilimitado. Revisar a seção "Identidade visual" do
   harness junto com este PR.
3. **Hover com glow amarelo** vira o padrão: cards, linha de tabela, item
   de menu — sombra/glow, não só borda ou cor.
4. **Tabelas**: linha com hover em gradiente + barra lateral amarela
   (glow) — ver `.tbl tbody tr:hover` no protótipo.
5. **Ícone em todo "big number"/KPI** e em mini-gráfico onde fizer
   sentido — mapeamento já validado no protótipo, ver tabela abaixo
   (ajustável).
6. **Sidebar**: ícone ao lado do nome do item (parcialmente já existe),
   barra amarela + leve gradiente de fundo no item ativo, mais
   espaçamento entre grupos/tópicos.
   ⚠️ **Q-001** (ver "Perguntas em aberto") — "contorno mais moderno,
   completo" no item ativo não ficou claro o suficiente pra especificar;
   perguntar pro usuário com exemplo antes de desenhar.
7. **Animação leve em card** (tilt 3D sutil no hover) — ver `.kpi` no
   protótipo pra calibrar intensidade (é sutil, não exagerar).
8. **Tooltip flutuante compartilhado** em gráfico/mini-gráfico (crosshair
   em linha, hover em barra) — ver `#hoverTip`/`tipShow` no protótipo
   como referência de comportamento, não de implementação (o app real
   usa a stack de componentes existente, não o JS vanilla do protótipo).
9. **Glow amarelo atrás do cabeçalho** (`<h1>` de página, todo
   `PageHeader`) — ver `.page-head::before` no protótipo. Confirmado: sem
   PDF adicional, é só essa referência.

## Renomeação de produto

- **"Catálogo" → "Catálogo de Dados"** em toda a UI (sidebar,
  breadcrumbs, títulos de página, `docs/site/` se citar o nome).

## Mudança de navegação (vale pra todo item de nível 1 do menu)

Clicar num item de nível 1 (Catálogo de Dados, Análises de qualidade,
…) abre uma **tela de opções/overview** — nunca cai direto num
dataset/tabela específico (não é mais drill-down direto). Já é a
convenção validada no protótipo (`catalogo` → `catalogo-dataset`,
`qualidade-tables` → `qualidade-menu` → detalhe); aplicar o mesmo
princípio em qualquer tela nova.

---

## Por domínio

### Catálogo de Dados (renomeado; overview reformulada)

- Big numbers com mini-gráfico **baseado em metadado real** (não
  decorativo): total de datasets, total de tabelas.
  ⚠️ **Q-003** — fonte de dado exata do mini-gráfico não foi
  especificada (crescimento de tabelas? volume? últimos N dias?) —
  perguntar antes de implementar; confirmar se `INFORMATION_SCHEMA` já
  expõe isso sem custo alto.
- Busca com filtro por **dataset e por tabela** (busca cruzada).
- Visão padrão = "por dataset": card com
  - ícone
  - qtd de tabelas
  - **mini-gráfico de barras**: distribuição de tabelas por faixa de SLA
    dentro do dataset — **mesmo componente visual** do painel
    "Distribuição por dataset" do Freshness (reaproveitar, não duplicar
    implementação).
  - **descrição do dataset, puxada do BigQuery** (campo `description`
    do dataset). Sem descrição cadastrada no BQ → mensagem genérica
    ("Sem descrição cadastrada no BigQuery").
  - 🔧 **Backend:** confirmar se o endpoint atual de metadados de
    dataset (`domains/catalog/`) já expõe `description`; se não, é
    mudança de domínio — precisa de critério de aceite novo em
    `docs/specs/catalog.md` antes de implementar (regra do CLAUDE.md,
    não é só front-end).

### Freshness

- Distribuição de SLA por dataset (gráfico de barras) — já existe; deve
  virar o mesmo componente reaproveitado pelos cards do Catálogo de
  Dados (ver acima).

### Lineage

- Linhas "vivas" (animadas fluindo), layout maior, **hover nas arestas**
  também (não só nos nós).
- Painel "tabelas afetadas se o schema mudar" — com quantidade.
- Painel de fontes.
- Painel de consumidores.
- Indicador "cache atualizado há X [tempo] · profundidade limitada a Y
  hops".

### Análises de qualidade (submódulo real — sai do dialog pequeno)

- Lista de datasets/tabelas disponíveis para análise, com informações
  atuais — **reformular pro padrão visual de tabela do protótipo**
  (hover em gradiente + barra lateral).
- O botão "Analisar" — tanto no Catálogo de Dados quanto na lista
  própria de Qualidade — leva pra uma **tela de escolha de tipo de
  análise**: cards com ícone + descrição (Schema, Análise de qualidade,
  PII, Tipos de coluna, Histórico, Acesso). Cada card abre o módulo
  correspondente em tela cheia — não mais um dialog pequeno com tabs.
- Tela "Análise de qualidade": **tela cheia**, com gráfico de
  cardinalidade por coluna em **barra horizontal + tooltip no hover**
  (substitui os gauges pequenos).

### FinOps

- Custo acumulado e diário — coluna (bar) + linha, relacionado a query e
  armazenamento — **filtrável** por dataset, tabela, mês/dia e tipo de
  custo (query vs. armazenamento).
- Top ofensores: custo + gráfico de tendência.
- **Dois scores distintos** (confirmado com o usuário — não é o mesmo
  item):
  1. **Score de eficiência de custo**, geral do projeto/FinOps — já
     prototipado como anel composto.
  2. **Score geral por tabela**, individual, com gráfico próprio.
     ⚠️ **Q-002** — onde esse score por tabela aparece na UI não foi
     definido (tela própria? coluna extra numa tabela existente?) —
     perguntar antes de desenhar.
- **Cadastro de budget** por dataset e por tabela (granularidade).
  **Escopo travado com o usuário: só cadastro simples nesta fase — sem
  compartilhamento entre usuários.** (Compartilhamento de budget
  — convite/aceite entre pessoas — foi levantado e **descartado do
  escopo por enquanto**; se voltar a ser pedido, é feature de produto
  própria, precisa de spec/ADR dedicado antes de qualquer código, não
  entra "de carona" num PR de refresh visual.)

### Buckets (Storage)

- Cards de resumo com mini-gráfico, lifecycle tag, tipo de
  armazenamento, tamanho, objetos, região.
- Scanner de desperdício: tabela **agrupada** (por recomendação) com
  mini-gráfico por linha.

### Administração

- **"Acessos"**: gráfico combo linha + coluna (diário × acumulado), mas
  **sem mapeamento fixo** — confirmado com o usuário: quem decide qual
  métrica vira linha e qual vira coluna é **o usuário final do Hub**, via
  um controle de troca na própria tela (não uma convenção travada no
  design).
- Selecionar granularidade por **dia ou mês**.
- **Filtro de período (de/até)** — novo, além da granularidade.
- **Funil de retenção**: formato de funil geométrico de verdade
  (trapézios afunilando), não barras.
  ⚠️ **Nota técnica de quem tentou isso no protótipo primeiro:** um funil
  de trapézio com o rótulo centralizado por dentro colide texto (rótulo
  + valor sobrepostos) nos estágios mais estreitos (ex.: 38%). Troquei
  pra barra por causa disso. **Se for fazer o funil de verdade, colocar
  os rótulos FORA do trapézio (ao lado, não dentro)** — senão o mesmo bug
  se repete.

---

## Mapeamento de ícones por KPI (validado no protótipo — ajustável)

| Contexto | KPI | Ícone (estilo lucide) |
|---|---|---|
| Catálogo — dataset | Região | `MapPin` |
| Catálogo — dataset | Tabelas | grade/tabela (`Table2`) |
| Catálogo — dataset | Views | `Eye` |
| Catálogo — dataset | Volume | `HardDrive` |
| Catálogo — dataset | Linhas | linhas (`AlignJustify`) |
| Catálogo / Freshness | Freshness | `Clock` |
| PII | Colunas | `Columns` |
| PII | Sinalizadas | `ShieldAlert` |
| PII | Amostragem | `Percent` |
| PII | Custo (dry-run) | `Calculator`/recibo |
| FinOps | Gasto no mês | `DollarSign` |
| FinOps | Budget | alvo/gauge (`Target`) |
| FinOps | Desperdício | `Trash2` |
| FinOps | Tabelas sem uso | `Archive` |
| Admin | Acessos hoje | `Users` |
| Admin | Usuários únicos | usuário (`UserCircle`) |
| Admin | Esta semana | `Calendar` |
| Admin | Solicitações pend. | `MessageSquare` |

---

## Suposições

- **ASM-001** (aberta) — ícones e mini-gráficos por seção seguem o
  mapeamento validado no protótipo (tabela acima); ajustável se o
  usuário pedir outra coisa durante a implementação.
- **ASM-002** (confirmada) — raio de 10px se aplica a
  retângulos (cards/painéis/tabelas/inputs/botões); elementos pill
  (badge, toggle, avatar) continuam totalmente arredondados.
- **ASM-003** (confirmada) — glow amarelo nos cabeçalhos segue só o
  protótipo (`.page-head::before`); não há PDF de referência adicional.
- **ASM-004** (confirmada) — combo do gráfico "Acessos" do Admin não tem
  mapeamento fixo linha/coluna — o usuário final escolhe via controle na
  tela.
- **ASM-005** (confirmada) — budget do FinOps é cadastro simples
  (dataset/tabela), sem compartilhamento entre usuários nesta fase.

## Perguntas em aberto

- **Q-001** (aberta) — Sidebar: "contorno mais moderno, completo" no
  item ativo — o usuário não detalhou o suficiente. Perguntar com
  exemplo/referência antes de desenhar o CSS final.
- **Q-002** (aberta) — Onde exatamente o "score geral por tabela"
  (FinOps) aparece na UI — tela própria, ou coluna numa tabela
  existente? Perguntar antes de implementar.
- **Q-003** (aberta) — Fonte de dado exata do mini-gráfico dos cards de
  dataset no Catálogo de Dados (crescimento de tabelas? volume? outra
  métrica?) — perguntar antes de implementar; confirmar custo de query
  se vier de `INFORMATION_SCHEMA`.

## Fora de escopo deste plano

- Compartilhamento de budget entre usuários (convite/aceite) —
  descartado por decisão do usuário nesta rodada. Não implementar, nem
  desenhar modelo de dado pra isso, até voltar a ser pedido
  explicitamente com spec própria.

## Checklist antes de considerar este brief "pronto pra virar plano"

- [ ] Q-001, Q-002, Q-003 respondidas com o usuário
- [ ] Confirmado se `description` de dataset já vem de algum endpoint
      existente ou é mudança de backend
- [ ] `docs/frontend/design-system.md` e `ui-ux-rules.md` revisados
      junto com a primeira mudança de token (raio, hover, glow)
- [ ] Specs de domínio tocadas (`docs/specs/catalog.md`,
      `finops-budget.md`, etc.) atualizadas com ACs novos, quando o
      comportamento mudar de verdade (não só cosmético)
- [ ] Plano fatiado em PRs pequenos, dev primeiro, aprovação explícita
      do usuário antes de qualquer push/merge/deploy de prod
