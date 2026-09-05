# Spec — Domínio: Favoritos (favorites)

**Versão:** 1.0
**Status:** Aprovada
**Fase:** 2 — MVP v1
**Última atualização:** 2026-08-24

> Domínio de plataforma (não é um dos 7 domínios de observabilidade da
> tabela do `CLAUDE.md`). Esta spec foi escrita retroativamente,
> documentando o domínio que já estava implementado — gap identificado
> e fechado em 2026-08-24 (ver `CHANGELOG.md`). Comportamento descrito
> aqui é o que já roda em dev/prod, não um plano futuro.

---

## Objetivo

Deixar o usuário marcar datasets inteiros ou tabelas específicas como
favoritos, com apelido opcional, pra acesso rápido pela sidebar
(`DatasetSidebar.tsx`, seção "Favoritos") sem precisar navegar pela
árvore de datasets toda vez.

---

## Fonte de dados

Firestore, sem custo de BigQuery. Coleção
`users/{email}/favorites/{doc_id}` — um documento por alvo favoritado,
sempre escopada ao e-mail da sessão (favoritos nunca são compartilhados
entre usuários, diferente das pastas de profiling do domínio `quality`).

`doc_id` é **determinístico**, não um auto-id:
- `{project_id}__{dataset_id}` — favorito de dataset inteiro.
- `{project_id}__{dataset_id}__{table_id}` — favorito de tabela.

(`__` em vez de `_` como separador, pra reduzir colisão com `_` que já
aparece normalmente em nomes de dataset/tabela.) Isso torna favoritar o
mesmo alvo duas vezes idempotente (mesmo doc, `set()` sobrescreve) e
`DELETE` consegue apontar direto pro doc exato, sem precisar de query.

---

## Endpoints da API

### GET /api/v1/favorites
Lista os favoritos do usuário autenticado, ordenados por `added_at`
descendente (mais recente primeiro).

**Response 200:**
```json
{
  "favorites": [
    { "project_id": "atlas-dev", "dataset_id": "RAW", "table_id": "crm_leads",
      "nickname": "Leads brutos", "added_at": "2026-08-20T10:00:00Z" },
    { "project_id": "atlas-dev", "dataset_id": "RAW", "table_id": null,
      "nickname": null, "added_at": "2026-08-19T09:00:00Z" }
  ]
}
```

### POST /api/v1/favorites
Upsert — favorita um dataset (`table_id` omitido/`null`) ou uma tabela
específica. Chamado tanto pelo toggle de favorito (estrela na sidebar,
sem `nickname`) quanto pelo editor de apelido (`FavoriteNickname.tsx`).

**Request body:**
```json
{ "project_id": "atlas-dev", "dataset_id": "RAW", "table_id": "crm_leads", "nickname": "Leads brutos" }
```

`nickname` tem **três estados**, não dois:
- Campo **ausente**/`null` — não mexe no apelido já salvo (toggle
  favorito on/off nunca envia `nickname`, não deve apagar um apelido
  existente).
- `""` (string vazia) — remove o apelido de propósito.
- Qualquer outra string — define o apelido.

`added_at` é **preservado** em upsert repetido do mesmo alvo (mesmo
racional de `domains/admin/repository.py::upsert_user` pra `created_at`)
— sem isso, editar só o apelido de um favorito existente reordenaria a
lista (ordenada por `added_at` desc), efeito colateral indesejado de uma
ação que devia ser só renomear.

### DELETE /api/v1/favorites/{project_id}/{dataset_id}/{table_id}
Remove o favorito de uma tabela específica.

### DELETE /api/v1/favorites/{project_id}/{dataset_id}
Remove o favorito do dataset inteiro (`table_id=None`).

Ambos `204`, idempotentes (remover um favorito que não existe não
levanta erro — `delete()` do Firestore em doc inexistente é no-op).

---

## Critérios de aceite

| ID | Comportamento | Testado em |
|---|---|---|
| AC-001 | Favoritar o mesmo alvo duas vezes é idempotente (mesmo `doc_id`, sem duplicata) | `test_favorite_doc_id_with_table_is_deterministic`, `test_add_favorite_preserves_added_at_on_repeat_call` |
| AC-002 | Favorito de dataset usa `doc_id` de 2 segmentos; favorito de tabela usa 3 segmentos — nunca colidem | `test_favorite_doc_id_without_table_has_two_segments`, `test_add_favorite_dataset_uses_two_segment_doc_id_and_null_table` |
| AC-003 | `nickname` ausente/`None` em upsert preserva o apelido já salvo | `test_add_favorite_with_nickname_none_preserves_existing_nickname` |
| AC-004 | `nickname=""` remove o apelido existente | `test_add_favorite_with_empty_string_nickname_clears_it` |
| AC-005 | `nickname` com texto novo sobrescreve o existente | `test_add_favorite_with_new_nickname_overwrites_existing` |
| AC-006 | `added_at` não muda em upsert repetido do mesmo alvo (não reordena a lista só por editar o apelido) | `test_add_favorite_preserves_added_at_on_repeat_call` |
| AC-007 | Lista vem ordenada por `added_at` descendente | `test_list_favorites_queries_collection_ordered_desc` |
| AC-008 | Remover favorito de tabela vs. de dataset usa o `doc_id` certo (3 vs. 2 segmentos) | `test_remove_table_favorite_deletes_by_three_segment_doc_id`, `test_remove_dataset_favorite_deletes_by_two_segment_doc_id` |

---

## Estrutura de arquivos

```
apps/backend/src/atlas/
├── api/v1/
│   └── favorites.py         # GET/POST/DELETE /favorites
├── domains/favorites/
│   ├── __init__.py
│   ├── service.py
│   ├── repository.py        # única camada que fala com Firestore
│   └── schemas.py
└── tests/unit/favorites/
    ├── test_service.py
    ├── test_repository.py
    └── test_schemas.py
```

Frontend: `features/favorites/hooks.ts` (`useFavorites`, `useToggleFavorite`,
`useUpdateFavoriteNickname`, `isFavoriteDataset`), consumido por
`DatasetSidebar.tsx` (seção "Favoritos") e `FavoriteNickname.tsx`
(editor inline do apelido).

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Favoritar o mesmo alvo duas vezes seguidas | Idempotente — mesmo `doc_id`, `set()` sobrescreve, `added_at` preservado |
| Toggle de favorito (sem `nickname` no request) num alvo que já tinha apelido | Apelido preservado — toggle nunca envia `nickname`, então cai no caso "ausente = não mexe" |
| Remover um favorito que não existe | No-op, `204` — `delete()` do Firestore em doc inexistente não levanta erro |
| Dois favoritos do mesmo dataset em projetos diferentes | Não colidem — `doc_id` inclui `project_id` |
| `table_id` vazio (`""`) vs. ausente (`null`) | Schema não distingue — `table_id: str \| None`, `""` seria tratado como um `table_id` literal, não como "nenhum". Frontend sempre envia `null`/omite o campo pra favorito de dataset. |

---

## Suposições

| ID | Suposição | Status |
|---|---|---|
| ASM-001 | Favoritos são sempre por usuário, nunca compartilhados — diferente do modelo de pastas de profiling (`docs/specs/profiling.md` v1.4), que tem compartilhamento configurável | confirmada, `users/{email}/favorites` sempre escopado ao e-mail da sessão |
| ASM-002 | Não há limite de quantidade de favoritos por usuário — sem trim, diferente de `history` (que limita a 20 por tipo) | confirmada, `repository.py` não tem nenhuma lógica de `_trim_to_max` |

## Perguntas em aberto

| ID | Pergunta | Status | Resposta |
|---|---|---|---|
| Q-001 | Favoritos deveriam ter algum limite de quantidade, como o histórico? Hoje pode crescer sem bound | aberta | — |

---

## Fora do escopo desta spec

- Favoritar objetos além de dataset/tabela (ex: uma query salva, um
  bucket do GCS) — cada extensão futura de escopo do Atlas (Storage,
  Scheduler, Workflows) decide se ganha favoritos próprios ou reaproveita
  este schema.
- Compartilhar favoritos entre usuários.
- Reordenar manualmente a lista (hoje é sempre `added_at` desc, sem
  drag-and-drop nem pin).
