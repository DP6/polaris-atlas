# Spec — Telas de overview de grupo (nav)

Carve-out do refresh visual (brief `frontend-visual-refresh.md`
§"Mudança de navegação"; plano `frontend-visual-refresh-plan.md` §4).
Implementado nas branches R2-6+ da rodada 2.

## Objetivo

O brief queria "clicar num item de nível 1 abre uma tela de opções/overview
— nunca cai direto num dataset/tabela". A `DatasetSidebar` real tem cada
grupo como `CollapsibleTrigger` puro (drill-down inline), sem página. Este
carve-out dá ao cabeçalho de grupo **duas afordâncias**:

- **chevron** → abre/fecha o drill-down inline (lista à esquerda) — comportamento atual;
- **nome + ícone** → `NavLink` pra `/{grupo}`, uma tela de overview com cards
  de função (`<OptionCard>` / `<OptionCardGrid>`, estilo Catálogo de Dados).

Decisão do usuário (rodada 2): "chevron abre a lista, label abre a tela".

## Rotas

| Rota | Componente | Cards |
|---|---|---|
| `/` | `CatalogOverviewPage` (já existia — rodada 1) | cards de dataset + `<TableSearchPanel>` |
| `/governanca` | `GovernanceOverviewPage` | Freshness & SLA (`/freshness`), Tabelas sem consumidor (`/orphans`) |
| `/quality` | **redirect → `/quality/folders`** (rodada 3 — o overview mostrava um card "Analisar uma tabela" que o usuário pediu pra tirar; sobrou só pastas). `/quality/tables` continua alcançável pelo botão "Analisar" do `AssetsTable`. |
| `/quality/tables` | `QualityTablesPage` | — (select de dataset → tabela → `/analyze/:d/:t`) |
| `/storage` | `StorageOverviewPage` (rodada 3 — antes a lista de buckets fazia esse papel) | Buckets (`/storage/buckets`), Scanner de desperdício (`/storage/waste`) |
| `/finops` | `FinOpsOverviewPage` (R2-12) — o scanner de 2 abas moveu pra `/finops/scanner` | big numbers + `ComboChart` de custo + anel de eficiência + Top ofensores + `OptionCardGrid` (Scanner de desperdício, Budget de custo, Configurar budget) |

`SidebarSection` / `SidebarServiceGroup` ganharam prop opcional `to` — quando
presente, o nome vira `NavLink`; o chevron isola o disclosure.

## Critérios de aceite

| ID | Comportamento | Teste |
|---|---|---|
| AC-NAV-OV-01 | O cabeçalho de "Governança" / "FinOps" / "Análises de qualidade" / "Catálogo de Dados" / "Cloud Storage" na sidebar tem um `NavLink` (nome) separado do chevron (disclosure). Clicar no nome navega; clicar no chevron só expande/recolhe. | `DatasetSidebar` — visual |
| AC-NAV-OV-02 | `/governanca` renderiza `PageHeader` + `<OptionCardGrid>` com cards que linkam pras funções do grupo. (`/quality` virou redirect na rodada 3.) | `GovernanceOverviewPage` — visual |
| AC-NAV-OV-03 | `/quality/tables` deixa escolher um dataset, lista as tabelas e cada "Analisar" navega pra `/analyze/:datasetId/:tableId` (a tela de escolha de tipo de análise — R2-7). | `QualityTablesPage` — visual |

## Fora do escopo

- Trocar a lista de datasets da sidebar por uma grade de cards (a lista
  inline com favoritos/filtro/histórico continua). Só o **cabeçalho** de
  grupo ganhou o `NavLink`.
- A overview de FinOps saiu de escopo desta spec e virou parte da R2-12
  (ver `finops-budget.md` AC-FIN-RV-*). A overview de Storage
  (`StorageOverviewPage`) e a de FinOps ganharam telas próprias na rodada
  3 (padrão Governança).
