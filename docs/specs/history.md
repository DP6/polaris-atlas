# Spec — Domínio: Histórico de navegação (history)

**Versão:** 1.0
**Status:** Aprovada
**Fase:** 2 — MVP v1
**Última atualização:** 2026-08-24

> Domínio de plataforma (não é um dos 7 domínios de observabilidade da
> tabela do `CLAUDE.md`) e **não deve ser confundido** com o histórico de
> runs de profiling (`docs/specs/profiling.md`, endpoint
> `/quality/history/...`) — são dois domínios diferentes, "history" só
> nome coincidente. Esta spec foi escrita retroativamente, documentando
> o domínio que já estava implementado — gap identificado e fechado em
> 2026-08-24 (ver `CHANGELOG.md`). Comportamento descrito aqui é o que já
> roda em dev/prod, não um plano futuro.

---

## Objetivo

Lembrar as últimas tabelas visitadas e buscas feitas pelo usuário, pra
popular a seção "Recentes" da sidebar (`DatasetSidebar.tsx`) — retomar
contexto rápido sem precisar navegar de novo pela árvore de datasets ou
lembrar o termo buscado.

---

## Fonte de dados

Firestore, sem custo de BigQuery. **Duas subcoleções por usuário**,
não uma só:
- `users/{email}/history_table_views/{doc_id}` — auto-id
- `users/{email}/history_searches/{doc_id}` — auto-id

Design deliberado: uma única coleção "history" com um campo `type`
discriminando o evento seria mais "natural", mas exigiria um índice
composto pra `where(type == ...).order_by(timestamp)` (Firestore só
indexa automaticamente queries de campo único — equality filter + order
by campo diferente não é coberto pela indexação automática). Com duas
subcoleções de um tipo só cada, `order_by(timestamp)` sozinho já usa o
índice de campo único criado automaticamente, sem depender de nenhum
índice provisionado manualmente.

---

## Endpoints da API

### GET /api/v1/history
Devolve as duas listas do usuário autenticado, cada uma já limitada e
ordenada.

**Response 200:**
```json
{
  "recent_tables": [
    { "project_id": "observability-hub-dev", "dataset_id": "RAW", "table_id": "crm_leads",
      "viewed_at": "2026-08-24T10:00:00Z" }
  ],
  "recent_searches": [
    { "query": "crm", "mode": "table", "project_id": "observability-hub-dev",
      "searched_at": "2026-08-24T09:30:00Z" }
  ]
}
```

### POST /api/v1/history/table-view
Registra uma visita a uma tabela. Chamado pelo frontend toda vez que o
usuário abre uma tabela (schema, profiling, etc.).

**Request body:** `{ "project_id": ..., "dataset_id": ..., "table_id": ... }`
`204`, sem body de resposta.

### POST /api/v1/history/search
Registra uma busca. `mode` é uma string livre (o frontend usa hoje pra
distinguir modos de busca em `SearchPage.tsx`, mas o backend não valida
contra um enum — ver "Casos de borda").

**Request body:** `{ "query": ..., "mode": ..., "project_id": ... }`
`204`, sem body de resposta.

---

## Regra de retenção

`_MAX_ITEMS_PER_TYPE = 20` — cada subcoleção mantém só os 20 mais
recentes. A cada escrita (`add_table_view`/`add_search`),
`_trim_to_max` busca o que sobra além da posição 20 (já ordenado
descendente) via `.offset(20).stream()` e apaga. Trim é **por tipo**:
20 tabelas + 20 buscas, não 20 no total.

Diferente do histórico de profiling (`quality/history_repository.py`),
aqui **nenhum parâmetro/resultado é salvo** — só o evento em si
(o quê, quando). Não há necessidade de comparar runs, é puro "onde eu
estive".

---

## Critérios de aceite

| ID | Comportamento | Testado em |
|---|---|---|
| AC-001 | Registrar mais de 20 eventos do mesmo tipo trima os mais antigos, mantém só os 20 mais recentes | `test_add_table_view_writes_then_trims`, `test_trim_to_max_deletes_only_overflow_docs` |
| AC-002 | Listagem vem ordenada por timestamp descendente, limitada a 20 | `test_list_recent_table_views_orders_desc_and_limits`, `test_list_recent_searches_orders_desc_and_limits` |
| AC-003 | `GET /history` combina as duas listas (tabelas + buscas) numa única resposta | `test_get_history_builds_response` |

---

## Estrutura de arquivos

```
apps/backend/src/observability_hub/
├── api/v1/
│   └── history.py           # GET /history, POST /table-view, POST /search
├── domains/history/
│   ├── __init__.py
│   ├── service.py
│   ├── repository.py        # única camada que fala com Firestore
│   └── schemas.py
└── tests/unit/history/
    ├── test_service.py
    ├── test_repository.py
    └── test_schemas.py
```

Frontend: `features/history/hooks.ts` (`useHistory`), consumido por
`DatasetSidebar.tsx` (seção "Recentes" — filtra `recent_tables` pelo
`project_id` atual e corta em `MAX_RECENT_TABLES_SHOWN = 5` antes de
renderizar, um recorte de exibição, não de armazenamento).

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Mesma tabela visitada várias vezes seguidas | Cada visita vira um doc novo (auto-id, sem dedup) — a lista pode ter a mesma tabela repetida se revisitada dentro da janela de 20 |
| `mode` de busca com valor não reconhecido pelo frontend | Backend aceita qualquer string — validação de `mode` (se necessária) é responsabilidade do frontend, não documentada aqui como contrato |
| Histórico vazio (usuário novo) | `recent_tables: []`, `recent_searches: []` — sem erro |
| Sidebar filtrando por projeto | `recent_tables` do backend inclui tabelas de **qualquer** projeto que o usuário viu — o filtro por `project_id` atual é feito no frontend (`DatasetSidebar.tsx`), não no backend |

---

## Suposições

| ID | Suposição | Status |
|---|---|---|
| ASM-001 | Trim de 20 é por tipo (20 tabelas + 20 buscas), nunca 20 no total combinado | confirmada, cada subcoleção trima independente via sua própria `_trim_to_max` |
| ASM-002 | Backend não filtra por projeto — `GET /history` sempre devolve o histórico completo do usuário entre todos os projetos que ele acessou; filtragem por projeto atual é responsabilidade exclusiva do frontend | confirmada, ver `DatasetSidebar.tsx` (`recentTables = historyQuery.data?.recent_tables.filter(t => t.project_id === projectId)`) |

## Perguntas em aberto

| ID | Pergunta | Status | Resposta |
|---|---|---|---|
| Q-001 | Deveria haver uma ação de "limpar histórico" manual (privacidade/reset)? Hoje só existe trim automático por volume, sem ação do usuário | aberta | — |

---

## Fora do escopo desta spec

- Histórico compartilhado/sincronizado entre dispositivos além do que já
  é (é por usuário via Firestore, então já "sincroniza", mas sem
  indicação de qual dispositivo gerou cada evento).
- Analytics agregado de uso do Hub (login, frequência de acesso por
  domínio) — isso é `domains/admin/analytics_service`, domínio
  separado.
- Deduplicação de visitas repetidas à mesma tabela dentro da janela.
- Exportar/consultar o histórico de outro usuário (sempre escopado ao
  `email` da sessão autenticada).
