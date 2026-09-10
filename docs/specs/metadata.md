# Spec — Domínio: Metadados de Governança

**Versão:** 2.0
**Status:** v1.0 implementada; refino v2.0 aprovado pelo usuário (2026-09-06)
**Fase:** Governança — metadados de tabela/coluna
**Última atualização:** 2026-09-06

## Mudanças da v2.0

- **`certification_status` → `status`** — renomeado na API e no Firestore
  (rótulo "Status" na UI). Enum inalterado (`draft`/`in_review`/`approved`).
- **Fluxo de revisão** — `status` deixa de ser um campo livre do `PUT`
  genérico e passa por um endpoint dedicado
  (`PUT .../{table}/status`) com regras de transição: Admin de projeto
  envia pra revisão e aprova; superadmin auto-aprova. Ver "Fluxo de
  revisão".
- **`owner.steward` removido** — só `technical_owner` e `team`.
- **Histórico de edição de coluna** — passa a ser registrado (antes fora
  de escopo): `description`, `glossary_term` e `pii_flag` geram entrada
  com `column_name` preenchido.
- **Gestão de Admin de projeto na `MetadataOverviewPage`** — o painel
  "Gerenciar acesso" sai da aba de análise por tabela e vai pra visão
  geral do projeto (leitura visível a todos; conceder/revogar só pra
  Admin de projeto e superadmin).
- **UX de salvamento** — edição de campos de tabela e de coluna passa a
  ter botão "Salvar" explícito + toast, em vez de salvar no blur.

---

## Objetivo

Metadados editáveis de tabela e coluna — descrição, ownership,
classificação, estado de governança (`status`), links relacionados e
histórico de edição no nível tabela; descrição, PII confirmado e termo de
glossário no nível coluna, também com histórico — gated por escrita pelo
papel "Admin de projeto" (`docs/specs/admin.md` v1.11, escopo: metadados
+ budget). Leitura aberta a qualquer usuário com acesso ao projeto (mesma
regra de sempre, `require_project_access`).

**Princípio central**: linkar/exibir o que já existe (lineage, análise de
qualidade, freshness, budget) em vez de duplicar dado — `domains/metadata`
não importa nem espelha nada desses domínios, só carrega a mesma chave
`project_id/dataset_id/table_id` que todos eles já usam, e o frontend
monta os links a partir dela.

Nono domínio do produto (`CLAUDE.md`, tabela de domínios) — domínio
próprio, não camada sobre `catalog`: `catalog` é passthrough
somente-leitura do BigQuery (`INFORMATION_SCHEMA`/`get_table()`), sem
storage, sem permissão própria; este feature tem as três coisas.

---

## Fluxo de uso

Duas superfícies (decisão do usuário — não uma seção nova isolada no
sidebar nem só uma aba escondida):

1. **Sidebar → Governança → "Metadados"** (3º item, ao lado de Freshness
   e Tabelas sem consumidor, já existentes) → `MetadataOverviewPage`:
   lista/busca de tabelas do projeto com `status`, dono e tags — ponto de
   entrada geral, "quais tabelas estão documentadas e quais não". **v2.0**:
   também hospeda a fila "Pendentes de revisão" (com Aprovar/Devolver
   inline pra revisores) e o painel "Gerenciar acesso" (Admin de projeto).
2. **`/analyze/:datasetId/:tableId` → 8º card "Metadados"** (junto de
   Schema, Qualidade, PII, Tipos de coluna, Histórico, Acesso, Lineage) →
   `MetadataAnalysisPage`: edição de fato, tabela + colunas (botão
   "Salvar" explícito), painel "Estado de governança" com as ações do
   fluxo de revisão, e os links pras outras 6 análises da mesma tabela.

---

## Fonte de dados

Nenhuma leitura nova no GCP — este domínio é dado próprio do Atlas
(Firestore), mais reaproveitamento do que já existe:

| Necessidade | Fonte | Novo? |
|---|---|---|
| Descrição/ownership/classificação/certificação/links (tabela) | `hub_projects/{p}/metadata_tables/{id}` (novo) | Sim — storage próprio |
| Descrição/PII confirmado/glossário (coluna) | Mesmo doc, mapa `columns` | Sim — storage próprio |
| Histórico de edição | `.../metadata_tables/{id}/history` (novo) | Sim — storage próprio |
| Descrição nativa do BQ (referência) | `catalog.TableDetail.description`/`ColumnDetail.description` (`GET /catalog/{p}/datasets/{d}/tables/{t}`) | Não — já existe, só lido |
| Lineage da tabela | `GET /lineage/{p}/{d}/{t}` (cacheado, Job diário) | Não — deep link direto |
| Histórico de profiling ("análise de qualidade") | `GET /quality/history/{p}/{d}/{t}` | Não — deep link direto |
| Sugestão de PII por coluna | `pii_scan_history` (`collection_group`, já existe) | Não — lido, nunca escrito por este domínio |
| Freshness da tabela | `GET /freshness/{p}/{d}/{t}` | **Sim, pequeno** — hoje só existe por dataset |
| Budget da tabela/dataset/projeto | `GET /finops/{p}/budgets` (compartilhado, `docs/specs/finops-budget.md` v1.13) | Não — deep link, mas depende da v1.13 estar implementada |

Nenhuma role de IAM nova — tudo Firestore (SA de runtime já lê/escreve lá)
mais chamadas a endpoints que já existem.

---

## Modelo de dados

```
hub_projects/{project_id}/metadata_tables/{dataset_id}__{table_id}
{
  "description": "Eventos de e-commerce normalizados, granularidade de evento.",
  "owner": {
    "technical_owner": "ana@dp6.com.br",
    "team": "Dados — Cliente A"
  },
  "classification": {
    "domain": "e-commerce",
    "sensitivity": "confidencial"
  },
  "status": "approved",
  "status_changed_by": "ana@dp6.com.br",
  "status_changed_at": "2026-09-05T10:00:00Z",
  "review_note": null,
  "related_links": [
    {"label": "Runbook de troubleshooting", "url": "https://..."}
  ],
  "columns": {
    "event_id": {
      "description": "Identificador único do evento, gerado no client-side.",
      "glossary_term": "Event ID",
      "pii": {
        "flag": false,
        "source": "manual",
        "scanner_flagged": false,
        "scanner_confidence": null,
        "confirmed_by": "ana@dp6.com.br",
        "confirmed_at": "2026-09-05T10:00:00Z"
      }
    },
    "user_email": {
      "description": "E-mail do usuário no momento do evento.",
      "glossary_term": null,
      "pii": {
        "flag": true,
        "source": "manual",
        "scanner_flagged": true,
        "scanner_confidence": "high",
        "confirmed_by": "ana@dp6.com.br",
        "confirmed_at": "2026-09-05T10:00:00Z"
      }
    }
  },
  "created_at": "2026-09-01T10:00:00Z",
  "updated_at": "2026-09-05T10:00:00Z",
  "updated_by": "ana@dp6.com.br"
}
```

```
hub_projects/{project_id}/metadata_tables/{dataset_id}__{table_id}/history/{auto_id}
{
  "field": "status",
  "old_value": "in_review",
  "new_value": "approved",
  "changed_by": "ana@dp6.com.br",
  "changed_at": "2026-09-05T10:00:00Z",
  "column_name": null,
  "note": null
}
```

`status` ∈ `draft` | `in_review` | `approved` (enum fixo — sem estado
customizável). `classification.sensitivity` é texto livre (sem enum
fechado — times diferentes usam vocabulário diferente; um enum viria de
uma demanda real de padronização, não antecipado).

**Entradas de histórico de coluna** têm `column_name` preenchido e
`field` ∈ `description` | `glossary_term` | `pii_flag`. **`note`** é
preenchido só nas devoluções de revisão (`in_review → draft` com
comentário). Transições de `status` também geram entrada
(`field: "status"`, `column_name: null`).

**Colunas embutidas como mapa no doc da tabela, não subcoleção** — mais
simples de ler (uma leitura só carrega tabela + todas as colunas), mas
com um risco monitorado: o limite de 1MiB por documento do Firestore
(precedente real neste produto — `event_cache` foi pro GCS por causa
disso). Pro volume esperado de metadados por coluna (poucos campos curtos
por coluna), tabelas com centenas de colunas ainda ficam bem abaixo do
limite — ver ASM-004.

**Histórico registra campos de nível tabela** (`description`, `owner`,
`classification`, `related_links`) via `PUT` genérico, **transições de
`status`** via `PUT .../status`, e **edição de coluna** (`description`,
`glossary_term`, `pii_flag`) com `column_name` preenchido. Sem paginação
(volume esperado baixo).

---

## Endpoints da API

### GET /api/v1/metadata/{project_id}/{dataset_id}/{table_id}
Devolve o doc de metadados da tabela (mesmo shape do modelo de dados
acima) ou um objeto vazio com todos os campos `null`/`{}` se a tabela
nunca foi documentada — **nunca 404**: "sem metadados ainda" é um estado
válido, não um erro. Gated por `require_project_access`.

**Response 200:**
```json
{
  "project_id": "atlas-dev",
  "dataset_id": "RAW",
  "table_id": "ga4_events",
  "description": null,
  "owner": null,
  "classification": null,
  "status": null,
  "status_changed_by": null,
  "status_changed_at": null,
  "review_note": null,
  "related_links": [],
  "columns": {},
  "updated_at": null,
  "updated_by": null,
  "has_metadata": false
}
```

`has_metadata: false` deixa explícito o estado "nunca documentada" sem o
frontend precisar inferir isso de todos os campos estarem `null` — é o
sinal que a `MetadataOverviewPage` usa pra listar "tabelas sem
documentação".

### PUT /api/v1/metadata/{project_id}/{dataset_id}/{table_id}
Upsert dos campos de nível tabela. Body (`MetadataTableUpsertRequest`):
`{ description?, owner?, classification?, related_links? }` — todos
opcionais, só os campos enviados são atualizados (patch parcial, não
substituição do doc inteiro). Cada campo alterado gera uma entrada em
`history`. **`status` não entra aqui** — muda só por
`PUT .../{table}/status`. Gated por
`require_project_admin(project_id, dataset_id)`.

### PUT /api/v1/metadata/{project_id}/{dataset_id}/{table_id}/status
Transição do estado de governança. Body (`MetadataStatusUpdateRequest`):
`{ target: "draft"|"in_review"|"approved", note? }`. `note` só é
persistido (em `review_note` e na entrada de histórico) numa devolução
para ajustes (`in_review → draft`); nas demais transições é ignorado e
`review_note` é limpo. Gated por
`require_project_admin(project_id, dataset_id)`. Regras de transição em
"Fluxo de revisão" — transição não permitida devolve **409**
(`invalid_status_transition`); pedir o estado em que já está é no-op
(200, sem histórico). Toda transição efetiva grava
`status_changed_by`/`status_changed_at` e uma entrada de histórico
(`field: "status"`).

### PUT /api/v1/metadata/{project_id}/{dataset_id}/{table_id}/columns/{column_name}
Upsert dos campos de uma coluna. Body (`MetadataColumnUpsertRequest`):
`{ description?, glossary_term?, pii_flag? }`. Quando `pii_flag` é
enviado, `pii.source` vira `"manual"` e `confirmed_by`/`confirmed_at` são
gravados com o usuário atual — mesmo se o valor enviado for igual ao
`scanner_flagged` (confirmar "concordo com o scanner" também é uma
confirmação manual registrada, não um estado implícito). Gated por
`require_project_admin(project_id, dataset_id)`. 404 se `column_name` não
existir na tabela real (checado contra `catalog.get_table_detail`, não
contra o doc de metadados — não dá pra confirmar PII de uma coluna que
não existe no BigQuery).

### GET /api/v1/metadata/{project_id}/{dataset_id}/{table_id}/suggested-pii
Sugestão do scanner de PII pra popular a UI de confirmação **antes** de
qualquer edição manual — lê o scan mais recente de
`pii_scan_history/{project}_{dataset}_{table}/scans` (o mais recente por
`scanned_at`), devolve `{column_name, flagged, confidence}[]`. Vazio se a
tabela nunca foi escaneada (frontend mostra "não avaliada pelo scanner"
por coluna, ver "Casos de borda"). **Não dispara um scan novo** — só lê o
que já existe; disparar fica na tela de PII, não nesta.

### GET /api/v1/metadata/{project_id}/{dataset_id}/{table_id}/history
Lista o histórico de edições, mais recente primeiro — inclui campos de
nível tabela, transições de `status` e edições de coluna (`column_name`
preenchido). Sem paginação (volume esperado baixo — edição não é uma
ação de alta frequência).

### GET /api/v1/metadata/{project_id}
Listagem/busca pra `MetadataOverviewPage`. Enumera todas as tabelas do
projeto (reaproveita `catalog.list_all_table_refs`, custo $0,
`INFORMATION_SCHEMA`) e faz join em memória com os docs de
`metadata_tables` existentes — tabelas sem doc aparecem com
`has_metadata: false`. **Parâmetros opcionais**: `status`,
`datasets` (repetível), `owner_email`, `q` (busca substring em
description/tags). Filtro em Python, não em query Firestore (coleção
pequena pro volume esperado — poucas centenas de tabelas documentadas por
projeto, mesmo racional de `list_budgets`).

**Response 200 (`MetadataOverviewResponse`):**
```json
{
  "project_id": "atlas-dev",
  "tables": [
    {
      "dataset_id": "RAW", "table_id": "ga4_events",
      "has_metadata": true, "status": "approved",
      "owner": {"technical_owner": "ana@dp6.com.br", "team": "Dados"},
      "classification": {"domain": "e-commerce", "sensitivity": "confidencial"},
      "updated_at": "2026-09-05T10:00:00Z"
    }
  ],
  "total_tables": 1,
  "documented_count": 1
}
```

Todos os endpoints acima ficam sob `api/v1/metadata.py`, prefixo
`/api/v1/metadata`.

---

## Fluxo de revisão (v2.0)

`status` representa o estado de governança da tabela e só muda pelo
endpoint `PUT .../{table}/status`. Não há revisores designados,
notificação, nem trava de edição enquanto em revisão (o conteúdo
continua editável via `PUT` genérico) — é um fluxo leve.

**Regras de transição:**

| Quem | De | Para | Efeito |
|---|---|---|---|
| Admin de projeto | `draft` (ou nunca setado) | `in_review` | "Enviar para revisão" |
| Admin de projeto | `in_review` | `approved` | "Aprovar" — qualquer Admin de projeto do dataset, inclusive quem enviou |
| Admin de projeto | `in_review` | `draft` | "Devolver para ajustes" — `note` vira `review_note` e entra no histórico |
| Admin de projeto | `approved` | `draft` / `in_review` | Reabrir para edição |
| Admin de projeto | `draft` | `approved` (direto) | **409** — precisa passar por `in_review` |
| Superadmin | qualquer | qualquer | Sempre permitido; **`in_review` é resolvido direto pra `approved`** (auto-aprovar) |

**Decisões do usuário (2026-09-06):** qualquer Admin de projeto pode
aprovar, inclusive a própria submissão (sem segregação); superadmin
auto-aprova. Pedir a transição pro estado atual é no-op (200, sem
histórico).

---

## Freshness por tabela — endpoint novo (pré-requisito pequeno)

Hoje só existe `GET /freshness/{project_id}/datasets/{dataset_id}`
(rollup do dataset inteiro). Pra embutir um badge de freshness na aba de
metadados sem sobre-buscar, `docs/specs/freshness.md` ganha um endpoint
novo consistente com o resto do produto (lineage/qualidade/catalog já são
por tabela):

```
GET /api/v1/freshness/{project_id}/{dataset_id}/{table_id}
```

Reaproveita a mesma lógica de `FreshnessDatasetResponse.tables[]`, só
filtrada pra uma tabela — sem query BQ nova (mesma fonte de metadado,
`TABLE_STORAGE`/`get_table()`). **Esta mudança pertence a
`docs/specs/freshness.md`**, não a este arquivo — citada aqui porque é
consumida pela aba de metadados; a spec de freshness precisa ganhar sua
própria versão nova documentando o endpoint (fora do escopo desta spec
escrever essa prosa).

---

## Estrutura de arquivos

```
apps/backend/src/atlas/
├── api/v1/
│   └── metadata.py             # novo — todos os endpoints acima
├── domains/metadata/            # novo domínio
│   ├── __init__.py
│   ├── schemas.py                # MetadataTable, MetadataColumn, MetadataTableUpsertRequest,
│   │                              # MetadataColumnUpsertRequest, MetadataHistoryEntry,
│   │                              # SuggestedPiiResponse, MetadataOverviewResponse
│   ├── repository.py             # get/upsert_table_metadata, upsert_column_metadata,
│   │                              # list_history, get_latest_pii_scan (collection_group read-only)
│   └── service.py                # orquestra repository + catalog.list_all_table_refs
│                                  # (pra GET /metadata/{project_id})
├── domains/admin/
│   └── project_admin_repository.py   # ver docs/specs/admin.md v1.11 — reaproveitado, não duplicado
├── domains/freshness/
│   └── service.py                # + get_table_freshness() — endpoint novo, ver seção acima
│                                  # (spec de fato em docs/specs/freshness.md, versão nova)
└── tests/unit/
    ├── metadata/
    │   ├── test_repository.py
    │   └── test_service.py
    └── freshness/test_service.py  # + get_table_freshness

apps/frontend/src/
├── features/metadata/            # novo
│   ├── MetadataOverviewPage.tsx   # 3º card em GovernanceOverviewPage.tsx
│   ├── MetadataAnalysisPage.tsx   # 8º card em AnalysisChooserPage.tsx, rota nova em
│   │                              # router.tsx dentro do bloco /analyze/:datasetId/:tableId
│   ├── ColumnMetadataTable.tsx    # tabela editável de colunas (descrição, PII, glossário)
│   ├── PiiConfirmationBadge.tsx   # sugestão do scanner + confirmação manual (por coluna)
│   ├── ProjectAdminsPanel.tsx     # "Gerenciar acesso" — grant/revoke de Admin de projeto,
│   │                              # consome GET/PUT/DELETE /projects/{id}/admins (admin.md v1.11).
│   │                              # v2.0: renderizado na MetadataOverviewPage (era na aba por tabela)
│   ├── hooks.ts
│   └── types.ts (types/metadata.ts)
├── features/catalog/
│   └── DatasetSidebar.tsx        # + NavLink "Metadados" dentro da seção Governança existente
├── features/governance/
│   └── GovernanceOverviewPage.tsx  # + 3º OptionCard "Metadados"
├── features/quality/
│   └── AnalysisChooserPage.tsx     # + 8º OptionCard "Metadados"
├── app/router.tsx                  # + rota /metadados (overview) + rota metadata dentro
│                                    # de /analyze/:datasetId/:tableId
└── lib/api/metadata.ts             # novo
```

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Tabela nunca documentada | `GET .../metadata/{p}/{d}/{t}` devolve `has_metadata: false`, todos os campos `null`/vazios — nunca 404 |
| Coluna sem entrada em `pii_scan_history` (nunca escaneada) | `GET .../suggested-pii` não a inclui na resposta; frontend mostra "não avaliada pelo scanner" — admin ainda pode confirmar manualmente (`pii.source="manual"`, `scanner_flagged=null`) |
| `PUT .../columns/{column_name}` pra coluna que não existe mais na tabela real (dropada no BQ) | 404 — checado contra `catalog.get_table_detail`, não contra o doc de metadados |
| Coluna existe no BQ mas nunca teve metadados gravados | Aparece em `columns` como objeto vazio (`description: null`, `pii: null`, `glossary_term: null`) na resposta do `GET` da tabela — a enumeração de colunas vem de `catalog`, não do doc do Firestore, então uma coluna sem metadado ainda aparece na UI pra ser preenchida |
| `related_links` com URL malformada | Validação básica de schema (deve começar com `http://`/`https://`) — 422 se falhar, sem checagem de que a URL responde |
| `status` (body de `PUT .../status`) fora do enum | 422 |
| `PUT .../status` com transição não permitida pro papel (ex: Admin de projeto pedindo `draft → approved`) | 409 (`invalid_status_transition`) |
| `PUT .../status` pedindo o estado em que a tabela já está | 200, no-op — não regrava, não gera histórico |
| Superadmin faz `PUT .../status` com `target: "in_review"` | Resolvido direto pra `approved` na resposta (auto-aprovar) |
| Doc gravado na v1.0 com `owner.steward` | Ignorado na leitura (Pydantic descarta campo extra) — não quebra |
| Admin de projeto escopado a `datasets: ["RAW"]` tentando editar tabela de `TRUSTED` | 403 (`require_project_admin` nega) |
| Dois editores simultâneos no mesmo campo | Último `PUT` vence (sem lock otimista) — mesma premissa de `hub_users`/`hub_projects`/`hub_groups`, nenhum desses tem controle de concorrência hoje |
| `GET /metadata/{project_id}` num projeto com centenas de tabelas, poucas documentadas | Enumeração via `catalog.list_all_table_refs` ($0) continua rápida; o join com `metadata_tables` é uma leitura de coleção pequena (só as documentadas existem como doc) |
| Lineage/qualidade/freshness/budget indisponíveis (warning nas respectivas respostas) | A aba de metadados propaga o `warning` de cada painel individualmente (mesmo padrão de degradação do resto do produto) — nunca bloqueia a edição de metadados por causa de outro domínio estar fora do ar |

---

## Critérios de aceite

| ID | Comportamento | Teste |
|---|---|---|
| AC-META-001 | `GET .../metadata/{p}/{d}/{t}` nunca retorna 404 — tabela sem doc devolve `has_metadata: false` | `test_get_table_metadata_returns_empty_shape_when_undocumented` |
| AC-META-002 | `PUT .../metadata/{p}/{d}/{t}` é patch parcial — campo não enviado no body permanece com o valor anterior | `test_upsert_table_metadata_partial_update_preserves_other_fields` |
| AC-META-003 | Toda alteração de campo de nível tabela via `PUT` gera uma entrada em `history` com `old_value`/`new_value` | `test_upsert_table_metadata_writes_history_entry_per_changed_field` |
| AC-META-004 | `PUT .../columns/{column}` com `pii_flag` sempre grava `source="manual"` + `confirmed_by`/`confirmed_at`, mesmo quando o valor confirma exatamente o `scanner_flagged` | `test_upsert_column_metadata_pii_flag_always_records_manual_confirmation` |
| AC-META-005 | `PUT .../columns/{column}` pra uma coluna que não existe na tabela real (via `catalog`) retorna 404 | `test_upsert_column_metadata_404_when_column_missing_from_real_table` |
| AC-META-006 | Endpoints de escrita (`PUT` tabela, `PUT` status, `PUT` coluna) exigem `require_project_admin` escopado ao `dataset_id` da tabela; endpoints de leitura só `require_project_access` | `test_write_endpoints_require_project_admin_scoped_to_dataset`, `test_read_endpoints_require_only_project_access` |
| AC-META-007 | `GET /metadata/{project_id}` lista todas as tabelas do projeto (via `catalog`), marcando `has_metadata=false` pras sem doc, sem excluí-las da lista | `test_get_metadata_overview_includes_undocumented_tables` |
| AC-META-008 | `GET .../suggested-pii` lê o scan mais recente por coluna de `pii_scan_history`, vazio se a tabela nunca foi escaneada — nunca dispara um scan novo | `test_get_suggested_pii_returns_latest_scan_columns` |
| AC-META-009 | `PUT .../status` por Admin de projeto: `draft → in_review` e `in_review → approved` funcionam; `draft → approved` direto retorna 409 | `test_update_status_project_admin_submits_for_review`, `test_update_status_project_admin_can_approve_from_in_review`, `test_update_status_project_admin_cannot_skip_straight_to_approved` |
| AC-META-010 | `PUT .../status` por superadmin com `target: in_review` resolve direto pra `approved` | `test_update_status_superadmin_submit_auto_approves` |
| AC-META-011 | `PUT .../status` `in_review → draft` com `note` grava `review_note` e uma entrada de histórico com `note` | `test_update_status_return_for_changes_keeps_note` |
| AC-META-012 | Edição de coluna (`description`/`glossary_term`/`pii_flag`) gera entrada de `history` com `column_name` preenchido, e pula quando o valor não muda | `test_upsert_column_metadata_writes_history_for_changed_column_fields`, `test_upsert_column_metadata_skips_history_when_column_field_unchanged` |

---

## Suposições

| ID | Suposição | Status |
|---|---|---|
| ASM-001 | O papel "Admin de projeto" e o mecanismo `require_project_admin` são definidos em `docs/specs/admin.md` (v1.11) e só referenciados aqui, nunca redefinidos. | confirmada |
| ASM-002 | O deep link pra lineage/qualidade usa as rotas/endpoints já existentes (`GET /lineage/{p}/{d}/{t}`, `GET /quality/history/{p}/{d}/{t}`) sem nenhuma mudança neles — este domínio só monta a URL/chamada a partir da mesma chave `project/dataset/table`. | confirmada |
| ASM-003 | O endpoint de freshness por tabela (`GET /freshness/{p}/{d}/{t}`) é um pré-requisito pequeno desta feature, mas pertence à spec de `freshness.md`, não a esta — implementado em paralelo, sem query BQ nova. | confirmada |
| ASM-004 | Colunas embutidas como mapa no doc da tabela (não subcoleção) — risco de aproximar o limite de 1MiB do Firestore em tabelas com centenas de colunas é considerado baixo pro volume esperado de campos por coluna, mas é um risco monitorado, não uma garantia. Se um projeto real bater o limite, a correção é mover `columns` pra subcoleção (mudança de storage, não de contrato de API). | confirmada, monitorada |
| ASM-005 | PII por coluna é sugestão-do-scanner + confirmação manual (não "só scanner, sem edição" nem "totalmente manual") — decisão do usuário. O valor "oficial" fica salvo na metadata (`pii.flag`), não depende de reexecutar o scan pra continuar visível. | confirmada com o usuário |
| ASM-006 | Glossário é campo de texto livre por coluna (`glossary_term: string \| null`), sem registro/validação — decisão do usuário. Um registro de termos de verdade (CRUD, dropdown, glossário compartilhado entre tabelas) fica pra uma spec futura. | confirmada com o usuário |
| ASM-007 | Fluxo de revisão sem segregação de função: qualquer Admin de projeto aprova qualquer submissão, inclusive a própria. Superadmin auto-aprova ao enviar pra revisão. | confirmada com o usuário (2026-09-06) |
| ASM-008 | `status` foi renomeado de `certification_status` na API e no Firestore; docs v1.0 existentes precisam ser reprocessados ou migrados. Volume pré-produção baixo, migração não é bloqueante. | confirmada com o usuário (2026-09-06) |

---

## Fora do escopo desta spec

- **Registro de glossário como CRUD de termos** (dropdown, catálogo
  compartilhado, validação de termo existente) — v1 é campo livre; ver
  ASM-006. Spec futura se houver demanda real.
- **Lock otimista / edição concorrente** — último `PUT` vence, mesma
  premissa do resto do ACL do Atlas.
- **Delegação de Admin de projeto pra grupo** — coberto (como fora de
  escopo) em `docs/specs/admin.md` v1.11.
- **Fluxo de revisão pesado** (v2.0 traz um leve, ver "Fluxo de
  revisão") — sem revisores designados, sem trava de edição enquanto em
  revisão, sem SLA. Segregação de função ("quem envia não aprova") foi
  explicitamente descartada pelo usuário.
- **Notificação quando um campo de metadado muda ou entra em revisão** —
  sem e-mail/alerta, só o histórico e a fila de pendentes dentro da tela.
- **Metadados a nível de dataset ou projeto** (só tabela/coluna) —
  "quanto o dataset X representa" não tem um doc próprio; a visão de
  dataset é agregada a partir das tabelas na `MetadataOverviewPage`
  (contagem de documentadas/aprovadas), não um registro editável
  separado.
- **Exportar/importar metadados em lote** (CSV, API bulk) — cadastro é
  um a um pela UI nesta v1.
- **Sincronizar a descrição do Atlas de volta pro BigQuery** (escrever em
  `bq_table.description`) — a descrição do Atlas e a descrição nativa do BQ
  continuam duas coisas paralelas, nunca uma sobrescrevendo a outra.
