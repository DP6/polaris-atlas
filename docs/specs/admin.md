# Spec — Domínio: Admin (controle de acesso por usuário × projeto)

**Versão:** 1.11 (2026-09-05 — novo eixo de autorização: "Admin de
projeto" (`project_admins`, subcoleção de `hub_projects`). Papel
delegável (sem trava de redelegação), escopado por dataset ou projeto
inteiro, revogação simétrica entre pares, superadmin sempre com bypass
total. Nova dependency `require_project_admin` em `core/auth.py`,
aplicada por endpoint — não por router inteiro como `require_admin`.
Escopo do papel hoje: `domains/metadata` (spec nova,
`docs/specs/metadata.md`) e o budget compartilhado por projeto
(`docs/specs/finops-budget.md` v1.13). Ver "Admin de projeto")
v1.10 (aba "Caches" — cache de audit log incremental: toggle
"forçar completo" + **multi-seleção de projetos** no disparo manual,
freshness com `never_run`/`window_start`/`mode`, histórico de execuções em
`GET /event-cache/runs` (separado de `/status`) com card de resumo +
tabela filtrável/paginada no cliente, retenção de 200 execuções; ver
"Acompanhamento do cache de audit log")
**Status:** Aprovada
**Fase:** Transversal (não faz parte do roadmap de observabilidade de `docs/prd.md`) — plataforma
**Última atualização:** 2026-09-05

---

## Objetivo

Controle de acesso do Atlas em duas camadas, administradas por uma tela
nova (`/admin`), sem senha nova e sem serviço novo — reaproveita 100% da
sessão Google OAuth já existente:

1. **Quem é administrador do Atlas** — pode gerenciar a allowlist de
   acesso a projeto de outros usuários.
2. **A quais `project_id` cada usuário tem acesso** — o buraco de
   segurança real que motivou esta spec: até aqui, qualquer usuário
   autenticado podia digitar qualquer `project_id` no seletor do Topbar
   e ler dados dele, porque a service account de runtime tem IAM em
   vários projetos-cliente ao mesmo tempo (modelo cross-project do
   ADR-006) e a única barreira era `Depends(get_current_user)` — que só
   valida a sessão, não o projeto.

**Novo na v1.1** (feedback de uso da v1.0 em produção): mensagens de
erro mais visíveis, visão inversa projeto→usuários com opção de liberar
um projeto pra todo mundo (`hub_projects`), e um fluxo de solicitação de
acesso self-service (`access_requests`) — ver seções abaixo.

**Novo na v1.2**: painel de uso/gestão pra admins — aba "Uso do Atlas" em
`/admin` com acessos ao Atlas (contagem por dia/semana/mês, quem acessou e
quando), bases mais favoritadas e favoritos com drill-down bidirecional
(usuário → itens, base → usuários) e histórico global de execuções de
profiling (tabela, quem, quando) — ver "Analytics de uso (v1.2)" abaixo.

**Novo na v1.3**: mais 3 mapeamentos na mesma aba — solicitações de
acesso (pedidos por mês por status, taxa de aprovação, projetos mais
pedidos, zero gravação nova), navegação agregada (tabelas mais vistas,
buscas mais frequentes, agregando o histórico por-usuário que já
existia) e atividade de scans de PII (mesmo padrão do profiling,
gravação nova em `pii_scan_history`) — ver "Analytics de uso (v1.3)"
abaixo.

**Novo na v1.4**: terceiro eixo de acesso — grupos (`hub_groups`). Um
grupo tem membros (e-mails) e projetos liberados; cada membro herda o
acesso do grupo, além do que já tiver individualmente. Aba "Grupos" nova
em `/admin`; aba "Por usuário" ganhou uma coluna mostrando de quais
grupos cada usuário faz parte. Ver "Grupos (`hub_groups`, v1.4)" abaixo.

Ver [ADR-009](../adr/ADR-009-acl-usuario-projeto.md) para o contexto da
decisão arquitetural (não revisado nesta versão — as extensões v1.1-v1.4
são extensões da mesma decisão, não mudança de arquitetura).

---

## Como se relaciona com o login (OAUTH_ALLOWLIST)

Login (**quem pode entrar no Atlas**) continua controlado pelo secret
`OAUTH_ALLOWLIST` (Secret Manager, `domains/auth`) — domínio ou e-mail
específico, sem mudança nesta spec. O que muda: passar no login **não dá
mais acesso implícito a nenhum projeto**. Acesso a `project_id` é
sempre controlado por `hub_users/{email}` (Firestore, este domínio) —
um e-mail sem documento aqui loga normalmente, mas não vê dado de
nenhum projeto até um admin liberar.

---

## Fonte de dados

Coleção Firestore `hub_users/{email}` — documento único por e-mail,
mesmo mecanismo já usado por `domains/favorites`/`domains/history`
(a service account de runtime já tem leitura/escrita no Firestore do
próprio projeto, nenhuma role de IAM nova é necessária).

```json
{
  "email": "consultor.a@dp6.com.br",
  "is_admin": false,
  "allowed_projects": ["client-a-project", "client-b-project"],
  "created_at": "2026-08-18T10:00:00Z",
  "updated_at": "2026-08-18T10:00:00Z",
  "updated_by": "admin@dp6.com.br"
}
```

`allowed_projects` pode conter o literal `"*"`, que libera qualquer
`project_id` que a service account de runtime alcançar — para
admins/líderes que precisam ver todos os projetos-cliente de uma vez.

**Sem cache de leitura em nenhuma consulta** — leitura sempre fresca do
Firestore. O `@lru_cache` sem TTL de `core/secrets.py::get_oauth_allowlist`
já causou staleness real (instância quente do Cloud Run não pegava
mudança de allowlist até reiniciar); um controle de acesso que precisa
refletir revogação imediatamente não pode repetir esse erro.

---

## Projeto liberado a todos (`hub_projects`, v1.1)

Coleção `hub_projects/{project_id}` — eixo **independente** do
`allowed_projects` de cada usuário:

```json
{
  "project_id": "client-shared-project",
  "is_public": true,
  "created_at": "2026-08-20T10:00:00Z",
  "updated_at": "2026-08-20T10:00:00Z",
  "updated_by": "admin@dp6.com.br"
}
```

`is_public: true` libera o projeto pra **qualquer** usuário do Atlas —
inclusive quem ainda não tem doc em `hub_users` (usuário futuro, criado
depois da liberação). `has_project_access` checa `hub_projects` primeiro,
antes de olhar o usuário:

```python
def has_project_access(client, email, project_id):
    project = repository.get_project(client, project_id)
    if project and project.get("is_public"):
        return True
    user = repository.get_user(client, email)
    if not user:
        return False
    allowed = user.get("allowed_projects", [])
    return "*" in allowed or project_id in allowed
```

A tela `/admin` → aba "Por projeto" é a visão inversa da aba "Por
usuário": em vez de editar um usuário e listar os projetos dele, o admin
escolhe um projeto e vê (e gerencia) quem tem acesso — via
`GET /admin/projects/{id}/users`, que consulta `hub_users` com
`array_contains_any [project_id, "*"]` (uma query só, sem escanear a
coleção inteira) e marca cada resultado como `granted_via: "explicit"`
ou `"wildcard"`. **Não inclui acesso concedido via grupo** (v1.4,
abaixo) — só os dois eixos que já existiam quando este endpoint foi
escrito; ver "Fora do escopo desta versão".

### Apagar projeto (v1.9)

`DELETE /api/v1/admin/projects/{project_id}` — remove só o doc
`hub_projects/{project_id}` (`repository.delete_project`, mirror exato
de `delete_group`). **Não cascateia**: `allowed_projects` de usuários e
grupos que já citavam esse `project_id` continuam intactos até alguém
revogar manualmente em "Por usuário"/"Grupos" — mesmo racional de "dois
eixos independentes" do resto desta seção. Sem confirmação modal na UI,
mesmo padrão do botão de revogar acesso em `ProjectUsersDetail`.

---

## Grupos (`hub_groups`, v1.4 + integração Workspace v1.5 + descoberta automática v1.6)

Terceiro eixo de acesso, independente dos outros dois (`hub_users.
allowed_projects` e `hub_projects.is_public`) — todos se somam, nenhum
substitui o outro. Motivação: liberar de uma vez todos os projetos de um
"time Cliente A" pra um conjunto de consultores, sem repetir a mesma
lista de `project_id` em cada `hub_users/{email}` manualmente (e sem
esquecer de atualizar todo mundo se a lista mudar).

**Modelo híbrido (v1.5)**: cada grupo tem dois eixos de membro,
somados:

- **`manual_members`** — e-mails cadastrados direto no Atlas, persistidos
  em `hub_groups`. Editável pela UI.
- **`workspace_members`** — membros reais de um grupo do Google
  Workspace, lidos ao vivo via Admin SDK Directory API (domain-wide
  delegation), **nunca persistidos em Firestore**. Só leitura na UI.
  Vazio se a integração ainda não estiver configurada, se o
  `group_id` não corresponder a um grupo real do Workspace, ou se
  qualquer chamada à API falhar — nunca um erro (fail-closed, ver
  `core/workspace_directory.py`).

`group_id` (doc ID em `hub_groups`, escolhido pelo admin ao criar) só
ativa o lado automático se coincidir com o e-mail de um grupo real do
Workspace — um nome livre funciona normalmente, só com
`manual_members` (`workspace_members` fica sempre `[]`).

```json
{
  "group_id": "cliente-a-consultores@dp6.com.br",
  "manual_members": ["consultor.avulso@dp6.com.br"],
  "allowed_projects": ["client-a-project-1", "client-a-project-2"],
  "created_at": "2026-08-21T10:00:00Z",
  "updated_at": "2026-08-21T10:00:00Z",
  "updated_by": "admin@dp6.com.br"
}
```

`allowed_projects` de um grupo aceita `"*"` com a mesma semântica de
`hub_users.allowed_projects` — libera qualquer projeto que a SA de
runtime alcançar pra todo membro (manual ou Workspace) do grupo.

### Integração com o Workspace — `core/workspace_directory.py`

Domain-wide delegation **sem chave de service account**: a SA de
runtime assina o JWT de delegação usando sua própria identidade
(`google.auth.iam.Signer`, que chama a IAM Credentials API — `signBlob`
— em vez de precisar de uma chave privada baixada), depois impersona
`settings.workspace_impersonate_email` (novo setting,
`ATLAS_WORKSPACE_IMPERSONATE_EMAIL`) pra ler o grupo via
`google.oauth2.service_account.Credentials.with_subject(...)`.

Pré-requisitos, nenhum gerenciado pelo Terraform/código deste domínio:
- Admin SDK API habilitada no projeto.
- `roles/iam.serviceAccountTokenCreator` da SA de runtime **sobre si
  mesma** (self-binding) — permite assinar o JWT.
- Domain-wide delegation autorizada no Admin Console do Workspace pro
  Client ID da SA de runtime, escopos `admin.directory.group.readonly`
  + `admin.directory.group.member.readonly` (só leitura) — só um Super
  Admin do Workspace faz (pedido formal registrado em
  `docs/onboarding-cliente.md`, 2026-08-21).

Cache em memória de 5min por `group_id` (mesmo padrão de
`domains/pii/service.py::_scan_cache`) — `get_group_members` roda no
caminho de `has_project_access`, chamado em quase todo endpoint;
consultar o Workspace sem cache adicionaria latência e risco de cota a
cada requisição.

### `has_project_access` — três checkpoints

```python
def has_project_access(client, email, project_id):
    project = repository.get_project(client, project_id)
    if project and project.get("is_public"):
        return True
    user = repository.get_user(client, email)
    if user and _grants_project(user.get("allowed_projects", []), project_id):
        return True
    for group in repository.list_groups(client):
        if not _grants_project(group.get("allowed_projects", []), project_id):
            continue
        if email in group.get("manual_members", []):
            return True
        if email in workspace_directory.get_group_members(group["group_id"]):
            return True
    return False
```

Sem query direcionada possível pro terceiro checkpoint (diferente de
`users_with_project_access`, que usa `array_contains`): membros do
Workspace não ficam no Firestore, só `manual_members` — precisa
escanear os grupos (coleção pequena, mesmo racional de
`list_access_requests`). A checagem de `allowed_projects` vem **antes**
da consulta ao Workspace, de propósito — evita chamada externa
desnecessária pra grupos que nem liberam este `project_id`.

A tela `/admin` → aba "Grupos" lista os grupos existentes, permite criar
um novo e editar `manual_members`/projetos liberados inline
(`ProjectChipEditor`, reaproveitado também pra e-mail de membro apesar
do nome do componente). `workspace_members` aparece na mesma tela, só
leitura, com nota se estiver vazio ("ou a integração ainda não foi
configurada" — não dá pra distinguir "grupo sem membros no Workspace"
de "integração desligada" só pelo payload, e a UI é honesta sobre essa
ambiguidade em vez de fingir certeza). A aba "Por usuário" mostra de
quais grupos cada usuário é membro (manual OU Workspace), derivada no
frontend a partir da mesma lista de grupos já buscada pra aba "Grupos"
(sem endpoint novo pra isso).

**v1.6 — descoberta automática de grupos no diálogo "Criar grupo":** a
v1.5 já resolvia membros ao vivo pra um `group_id` existente, mas quem
criava um grupo novo ainda precisava digitar o e-mail exato de um grupo
do Workspace de cabeça — sem lista, sem autocomplete. `GET
/api/v1/admin/workspace-groups` (`workspace_directory.list_domain_groups`)
lista todos os grupos do domínio via Admin SDK Directory API
(`groups?domain=...`, paginado, mesmo cache de 5min e mesmo fail-closed
— lista vazia em qualquer erro, nunca 500) e o diálogo "Criar grupo" virou
um `Select` populado com esses grupos (já filtrando os que já viraram
`hub_group`), com uma opção "Nome livre" que volta pro campo de texto
antigo pra quem quer um grupo só com `manual_members`.

### Endpoints (mesmo `dependencies=[Depends(require_admin)]` do router)

- `GET /api/v1/admin/groups` — lista todos os `hub_groups`, ordenados
  por `group_id`, cada um enriquecido com `workspace_members` resolvido
  on-the-fly (não vem do Firestore).
- `PUT /api/v1/admin/groups/{group_id}` — upsert (cria se não existe,
  atualiza se existe). Body: `{"manual_members": [...],
  "allowed_projects": [...]}` — `workspace_members` nunca é definido
  pelo cliente, sempre derivado. `created_at` preservado em updates,
  mesmo padrão de `hub_users`/`hub_projects`.
- `DELETE /api/v1/admin/groups/{group_id}` — remove o documento
  (idempotente). Membros perdem só o acesso concedido por este grupo —
  acesso individual (`hub_users`) não é afetado. Não afeta o grupo no
  Workspace em si (a Atlas nunca escreve lá, só lê).
- `GET /api/v1/admin/workspace-groups` (v1.6) — lista `{email, name}` de
  todos os grupos do domínio do Workspace (não filtrado por já-importado
  como `hub_group` — o frontend faz esse filtro). Lista vazia se a
  integração não estiver configurada ou a Directory API falhar
  (fail-closed, mesmo padrão de `get_group_members`). Não depende do
  Firestore.

Diferente de `hub_users`, não existe `LastAdminLockoutError` equivalente
pra grupos — grupos não carregam status de admin, só acesso a projeto.

---

## Admin de projeto (`project_admins`, v1.11)

Quinto eixo de autorização, mas de natureza diferente dos quatro
anteriores (`hub_users.allowed_projects`, `hub_projects.is_public`,
`hub_groups`, e o próprio `hub_users.is_admin`) — aqueles controlam
**leitura** de projeto ou administração global; este controla **escrita
elevada dentro de um projeto que o usuário já pode ler**, delegável por
quem já tem o papel, sem passar por superadmin a cada concessão.
Motivação: dois domínios de escrita precisam de um autor autorizado que
não seja superadmin — `domains/metadata` (`docs/specs/metadata.md`) e o
budget compartilhado por projeto (`docs/specs/finops-budget.md`, v1.13).

**Escopo do papel, hoje**: gerenciar metadados de tabela/coluna e
gerenciar budget compartilhado (criar/editar/excluir, nos níveis
projeto/dataset/tabela) — nada além disso. Se um domínio novo quiser gate
por Admin de projeto no futuro, é decisão de spec nova, não extensão
automática deste documento.

Superadmin (`hub_users.is_admin`) continua administrador de **todos** os
projetos por regra — não precisa de doc em `project_admins` pra nada,
mesmo bypass que já vale em `require_admin`.

### Modelo de dados

Subcoleção de `hub_projects` — diferente do padrão dos outros três eixos
de acesso, que guardam a lista de projetos **dentro do documento do
usuário/grupo** (`hub_users.allowed_projects`). Aqui é o inverso: o
documento vive **dentro do projeto**, porque a pergunta mais frequente
deste eixo é "quem administra o projeto X" (mostrado dentro da própria
tela de metadados/budget daquele projeto), não "quais papéis o usuário Y
tem em todo lugar" — o layout segue o padrão de leitura mais comum, mesmo
racional já usado na aba "Por projeto" existente.

```json
// hub_projects/{project_id}/project_admins/{email}
{
  "email": "consultor.a@dp6.com.br",
  "datasets": null,
  "granted_by": "consultor.b@dp6.com.br",
  "granted_at": "2026-09-05T10:00:00Z",
  "updated_at": "2026-09-05T10:00:00Z"
}
```

`datasets: null` = projeto inteiro (todos os datasets, presentes e
futuros — reavaliado contra o catálogo real a cada request, dinâmico por
natureza). `datasets: ["RAW", "TRUSTED"]` = só esses datasets, estático
até alguém editar o grant — sem meio-termo "todos os atuais, mas não os
futuros".

### `require_project_admin` — nova dependency em `core/auth.py`

```python
def require_project_admin(
    project_id: str,
    dataset_id: str | None = None,   # None em endpoints project-scoped (ex: budget de projeto)
    user=Depends(get_current_user),
    client=Depends(get_firestore_client),
) -> UserInfo:
    """403 (ProjectAdminRequiredError) se o usuário não for superadmin
    (bypass total) nem tiver doc em
    hub_projects/{project_id}/project_admins/{email} cujo `datasets`
    seja null ou contenha dataset_id."""
```

Aplicada **por endpoint**, não por router inteiro (diferente de
`require_admin`, que gate-a `/api/v1/admin` inteiro): os endpoints de
escrita de `domains/metadata` e do budget compartilhado usam
`require_project_admin`; os de leitura continuam `require_project_access`
(o acesso comum já existente, sem mudança nenhuma nele).

**Não implica acesso de leitura ao projeto** — é uma checagem
independente de `has_project_access`. Se o alvo de um grant ainda não tem
acesso básico ao projeto (nenhum dos três eixos de leitura), ganhar Admin
de projeto não libera a leitura sozinho; quem concede precisa garantir os
dois separadamente, se for o caso. Ver ASM-005.

### Delegação e revogação

Qualquer Admin de projeto (superadmin, ou com doc próprio cobrindo o
`dataset_id` em questão) pode **conceder** o mesmo papel a outro
usuário — sem trava de redelegação: quem recebe também pode delegar.
`granted_by` registra quem concedeu **este** grant especificamente, não
uma cadeia de delegação completa até o superadmin original.

**Revogação**: superadmin revoga qualquer Admin de projeto de qualquer
projeto (mesmo bypass de sempre). Entre Admins de projeto, revogação é
**simétrica** — qualquer um pode revogar qualquer outro do mesmo projeto,
independente de quem concedeu a quem ou do escopo relativo de cada um (um
admin com `datasets: ["RAW"]` pode revogar um admin com `datasets: null`,
projeto inteiro). Deliberadamente simples: não há hierarquia de escopo a
arbitrar, e não existe risco de "projeto sem admin" — superadmin sempre
cobre qualquer projeto, então não há aqui um `LastAdminLockoutError`
equivalente. Ver ASM-004.

Concessão só pra indivíduo (e-mail) — delegar pra um `hub_groups` inteiro
fica fora de escopo desta versão, ver "Fora do escopo".

### Endpoints

- `GET /api/v1/projects/{project_id}/admins` — lista os `project_admins`
  do projeto. Gated por `require_project_access` (qualquer um com acesso
  de leitura ao projeto vê quem o administra — não precisa ser admin pra
  consultar).
- `PUT /api/v1/projects/{project_id}/admins/{email}` — concede/atualiza
  (upsert). Body: `{"datasets": ["RAW"] | null}`. Gated por
  `require_project_admin(project_id)` (sem `dataset_id` — conceder o
  papel é uma ação de escopo de projeto, mesmo que o grant resultante
  seja restrito a datasets). `granted_by`/`granted_at` fixos na criação;
  `updated_at` em toda atualização subsequente.
- `DELETE /api/v1/projects/{project_id}/admins/{email}` — revoga.
  Idempotente. Gated por `require_project_admin(project_id)`.

---

## Solicitação de acesso (`access_requests`, v1.1; `request_type` na v1.9)

Qualquer usuário autenticado (não precisa ser admin) pode pedir acesso a
uma lista de `project_id` — `POST /api/v1/access-requests` (fora do
prefixo `/admin`, de propósito: pedir acesso é exatamente o caso de uso
de quem ainda não tem acesso a nada). Cria um doc por `project_id` em
`access_requests/{auto_id}`:

```json
{
  "request_id": "abc123",
  "email": "consultor.b@dp6.com.br",
  "project_id": "client-c-project",
  "request_type": "access",
  "status": "pending",
  "requested_at": "2026-08-20T10:00:00Z",
  "resolved_at": null,
  "resolved_by": null
}
```

`create_access_requests` filtra automaticamente: pula `project_id` que
o usuário já tem acesso (`has_project_access`, já considera `hub_projects`
e wildcard) e pula `project_id` com pedido `pending` já existente do
mesmo usuário **e mesmo `request_type`** — nunca cria pedido redundante,
mas um "access" e um "inclusion" pendentes pro mesmo projeto não se
bloqueiam entre si (efeitos diferentes na aprovação, ver abaixo).

Admin vê pendências na aba "Solicitações" de `/admin` (mais um badge
discreto no ícone de admin do Topbar, com contador — `usePendingAccessRequests`
no frontend, `refetchInterval` de 60s, sem WebSocket) e aprova/nega:
`approve_access_request` concede o acesso de fato (mesma função
`grant_project_to_user` usada na aba "Por projeto") e marca
`status="approved"`; negar só marca `status="denied"`, sem conceder
nada.

### `request_type` (v1.9): "access" vs. "inclusion"

`request_type: "access"` (default — cobre também docs antigos no
Firestore, gravados antes deste campo existir) é o fluxo original acima:
o projeto já está onboardado no Atlas, o usuário só precisa de um grant
individual.

`request_type: "inclusion"` cobre o caso em que o projeto **não está
onboardado** — o seletor de projeto (`ProjectSelector.tsx`) oferece essa
opção quando a validação (`GET /api/v1/projects/{id}/validate`) devolve
`access_denied` (SA do Atlas sem IAM no projeto-alvo) ou `project_not_found`
(404) — os dois casos ganham a mesma CTA "Solicitar inclusão no Atlas",
já que o usuário comum não consegue diferenciá-los; o admin investiga
qual é qual ao revisar o pedido (ver "Checklist de onboarding" abaixo).

Aprovar (`_resolve_access_request`) um pedido `"inclusion"` faz **dois
passos num clique só**: `repository.upsert_project(project_id, is_public=False)`
(registra o projeto em `hub_projects`) seguido de `grant_project_to_user`
(libera o solicitante) — pressupõe que o admin já fez o onboarding real
no GCP (`docs/onboarding-cliente.md`) fora do Atlas antes de clicar
aprovar. Negar um pedido `"inclusion"` não registra nada, igual ao fluxo
`"access"`.

---

## Acompanhamento do cache de audit log (aba "Caches")

O Atlas mantém um cache diário de audit log de Cloud Logging pra lineage,
mapa de acesso, FinOps (budget) e Storage (waste scanner) — ver
`docs/specs/lineage.md`, "Cache pré-computado". A aba **Caches** de
Administração dá visibilidade granular disso:

- **Disparo**: `POST /api/v1/admin/event-cache/refresh` (202) executa o
  Cloud Run Job de refresh sob demanda, fora do ciclo diário
  (`domains/admin/service.py::trigger_event_cache_refresh` →
  `core/run_client.py`; a SA de runtime precisa de `roles/run.invoker`
  **sobre o Job**, concedido no módulo Terraform `cloud-run-job`).
  Dois modificadores, injetados como env só naquela execução via
  `run_v2.RunJobRequest.Overrides` (o ciclo diário do Scheduler nunca os
  seta):
  - `?force_full=true` (toggle **"forçar completo"** da tela) →
    `ATLAS_CACHE_FORCE_FULL=1`: o Job ignora o delta
    incremental e re-escaneia a janela inteira
    (`core/config.py::settings.cache_force_full`).
  - `?project=a&project=b` (multi-seleção de projetos na tela) →
    `ATLAS_CACHE_ONLY_PROJECTS=a,b`: o Job roda **só** esses
    projetos, **substituindo** a união `hub_projects` ∪ "vistos"
    (`settings.cache_only_projects` / `_list`). Ausente = todos. A tela
    lista os `project_id` que já aparecem na freshness (dropdown, sem
    texto livre).

**Leitura de estado** — dois endpoints, **só a partir do Firestore** (nada
de Cloud Logging nem Cloud Run Admin API — evita depender de
`roles/run.viewer`), com cadências de polling separadas:

- **Freshness**: `GET /api/v1/admin/event-cache/status`
  (`get_event_cache_status`) — pra cada projeto conhecido (união
  `hub_projects` ∪ "vistos" que o Job varre, menos o wildcard `*`) e cada
  um dos 4 `_CACHE_KIND`, de `event_cache_metadata`: `cached_at`,
  `event_count`, **`never_run`** (`true` = nenhum metadado ainda — a tela
  mostra "nunca rodou" em vez de uma janela), `window_start` (piso da
  janela rolante no blob atual), `last_full_scan_at`, `mode`. Payload
  pequeno, polling constante (30s).
- **Histórico de execuções**: `GET /api/v1/admin/event-cache/runs`
  (`list_event_cache_runs`) — **todas** as execuções retidas (~200, mais
  recentes primeiro; `event_cache_runs`, gravado pelo próprio Job).
  `run_id`, `started_at`/`finished_at`, `status` (`running`/`done`), e um
  mapa `projects[project_id] → {status, finished_at, contagens, mode,
  raw_entries}` preenchido incrementalmente conforme cada projeto termina.
  `status` por projeto: `ok` | `access_denied` | `quota_exceeded` |
  `api_error` | `unexpected_error`. Polling rápido (8s) só enquanto há
  execução `running`. Foi separado de `/status` na v1.10 pra o polling
  frequente da freshness não arrastar ~200 runs a cada tick.
- **Cache não gerado no request path**: quando um usuário abre uma tela de
  lineage/access/finops/storage de um projeto ainda sem cache, o serviço
  degrada pra resposta vazia com um `warning` orientando "Administração →
  Caches" (não 503). O modelo incremental **não escaneia mais o Cloud
  Logging no request path** — e o cache só é populado pelo run do Job pra
  projetos de `hub_projects`, então a freshness lista exatamente os
  projetos registrados no ADM.
- **Frontend** (`AdminCachesTab.tsx`): **card de resumo** da execução
  atual/última (badge de status, `N/M` projetos, duração, modo, lista dos
  projetos com problema) + botão "Atualizar agora" com **seletor de
  projetos** (Popover + Command, multi-seleção dos `project_id` da
  freshness; vazio = todos) e checkbox **"forçar completo"**; **tabela de
  execuções** (linha = resumo do run, linha
  expansível com o detalhe por projeto) **filtrável** — status (runs com
  ao menos um projeto naquele status), projeto (substring), período (data
  de `started_at`), "só com falha" — e **paginada**. Filtro e paginação
  rodam **no cliente** sobre a lista inteira (~200), mesmo padrão das
  outras seções de analytics do admin (`usePagination` + `PaginationBar`).
- **Retenção**: `event_cache_runs` guarda só as ~200 execuções mais
  recentes (`core/event_cache.py::_CACHE_RUNS_KEEP` / `_prune_cache_runs`,
  chamado no início de cada execução; é também o `limit` default de
  `list_cache_runs`).

## Checklist de onboarding (best-effort, v1.9)

`GET /api/v1/admin/projects/{project_id}/checklist` (admin-only) —
`domains/admin/checklist_service.py::check_project_checklist` — ajuda o
admin a confirmar que um projeto está pronto **antes** de registrá-lo em
"Por projeto" ou de aprovar um pedido de inclusão. Reaproveitado nos
dois pontos de uso pelo mesmo componente de frontend
(`ProjectChecklistPanel.tsx`).

**Best-effort de propósito**: confirmar de verdade que uma role IAM foi
concedida exigiria ler a IAM policy do projeto-alvo
(`resourcemanager.projects.getIamPolicy`), permissão que **não faz
parte** do checklist de onboarding hoje. Em vez disso, cada item tenta a
operação real (probing) e reporta se funcionou:

| Item | Como verifica | Limitação |
|---|---|---|
| `bigquery` | Reaproveita `core/bigquery.py::discover_regions` — o mesmo probe que `validate_project` já faz | Nenhuma além das já conhecidas de `discover_regions` |
| `logging` | `list_entries(resource_names=[...], page_size=1)` | **Não detecta** `logging.privateLogViewer` faltando — a chamada não falha, só devolve vazio (mesma ambiguidade já documentada em lineage/access) |
| `storage` | `list_buckets(project=...)` | — |
| `audit_logs` | Não verificável — sempre `not_checked` | Não é uma permissão de leitura de dado, é config do projeto; `detail` traz o comando `gcloud projects get-iam-policy` manual já usado no onboarding |

Cada item devolve `status: "ok" | "denied" | "not_found" | "not_checked"`
+ `detail` (texto explicativo, inclusive a ressalva do `privateLogViewer`
sempre presente no item `logging`, mesmo quando `ok`). Disparado só sob
demanda (botão "Verificar checklist"), nunca automático — cada chamada
faz 2-3 leituras reais no GCP.

---

## Analytics de uso (v1.2)

Três leituras cross-usuário/cross-tabela pra dar visão gerencial em
`/admin` → aba "Uso do Atlas". Diferente do resto do domínio (`hub_users`,
`hub_projects`, `access_requests`, todos com dado próprio), essas
analytics leem/agregam dado que **já existe em outros domínios**
(favorites, quality) mais uma coleção nova (login events) — service.py
deste domínio orquestra, mas o dado de origem não pertence a `admin`.

### Login events (novo)

Antes da v1.2, login no Atlas era 100% stateless (JWT em cookie,
`domains/auth`) — nenhum registro de quem/quando. Nova coleção
`login_events/{auto_id}` (top-level, dado gerencial do Atlas, mesmo
raciocínio de `hub_users`/`hub_projects`):

```json
{"email": "consultor.a@dp6.com.br", "logged_in_at": "2026-08-17T09:00:00Z"}
```

Gravado em `POST /auth/callback` (best-effort — falha aqui **nunca**
pode impedir o login, que é o caminho crítico; erro só é logado). Sem
trim-to-max (ao contrário de `history`/`profiling_history`): volume
esperado é baixo pra escala de time interno, revisitar se isso mudar.

### Favoritos entre usuários

`domains/favorites` já guarda favoritos em `users/{email}/favorites/`
(um doc por usuário). A v1.2 lê **todos** os usuários via
`collection_group("favorites")` sem filtro nem `order_by` (evita
qualquer necessidade de índice manual de collection-group) — cada doc
ganha `owner_email` derivado do path (`users/{email}/...`, o e-mail é o
ID do documento-pai). O endpoint devolve a lista achatada; o front-end
agrupa dos dois lados (por usuário, por base) a partir do mesmo payload
— drill-down bidirecional sem precisar de dois endpoints.

### Atividade de profiling

`domains/quality/history_repository.py::save_run` passou a gravar
`project_id`/`dataset_id`/`table_id` dentro de cada run (antes só
existiam implícitos no ID do documento-pai, com separador `_` ambíguo
pra parsear de volta). A v1.2 lê tudo via `collection_group("runs")`,
filtra runs antigos sem `project_id` (saem sozinhos da janela quando o
cap de 30/tabela rotacionar — sem backfill) e ordena por `executed_at`
desc em Python.

### Endpoints (mesmo `dependencies=[Depends(require_admin)]` do router)

- `GET /api/v1/admin/analytics/logins?lookback_days=90` — buckets
  diário/semanal/mensal (`login_count` + `unique_users`, no padrão
  DAU/WAU/MAU) desde o cutoff, mais os últimos 50 eventos (`recent_events`).
- `GET /api/v1/admin/analytics/favorites` — lista achatada de favoritos
  de todos os usuários, com `owner_email`.
- `GET /api/v1/admin/analytics/profiling?limit=200` — runs de profiling
  mais recentes de todas as tabelas.

---

## Analytics de uso (v1.3)

Mais 3 leituras na mesma aba "Uso do Atlas", dois casos sem gravação nova
e um com:

### Solicitações de acesso (zero gravação nova)

`access_requests` (já existe desde a v1.1) já tem tudo que precisa —
`status`, `project_id`, `requested_at`, `resolved_at`, `resolved_by`.
`GET /api/v1/admin/analytics/access-requests` agrupa em Python por mês
(`{period, total, approved, denied, pending}`), lista os 10 projetos
mais pedidos e calcula `approval_rate` (`approved / (approved + denied)
* 100`) — `null` quando ainda não houve nenhum pedido resolvido (evita
mostrar "0%" quando não há dado nenhum).

### Navegação agregada (zero gravação nova)

`domains/history` já persiste, por usuário, `history_table_views` e
`history_searches` (capados em **20 itens por usuário** — bem menos que
os 30/tabela do profiling ou o favorites sem cap). `GET /api/v1/admin/
analytics/navigation` lê os dois via `collection_group` (mesmo padrão
de `list_all_favorites`, `owner_email` derivado do path) e devolve as
listas achatadas — o front agrega "tabelas mais vistas"/"buscas mais
frequentes" a partir do payload bruto. **Por causa do cap de 20/usuário,
isso é uma métrica de uso recente, não histórico completo** — texto
explícito na UI, não escondido.

### Atividade de scans de PII (gravação nova)

Até a v1.3, scan de PII (`domains/pii`) não persistia nada — só um cache
em memória com TTL de 5min, sem `executed_by`. Ganhou o mesmo tratamento
que profiling já tinha: `domains/pii/history_repository.py` (novo)
grava em `pii_scan_history/{project}_{dataset}_{table}/scans/{auto-id}`
a cada execução real (**não** em cache hit — ver `docs/specs/pii.md`,
"Histórico de scans"). Cap de 30/tabela, mesmo trim-to-max de sempre.

**Nome da subcoleção é `scans`, não `runs`** — de propósito: a
agregação lê via `collection_group`, que ignora o caminho do
documento-pai e enxerga só o nome da subcoleção; se PII usasse `runs`
também, a leitura global de profiling passaria a devolver scans de PII
junto (e vice-versa). Confirmado por grep antes de implementar que
nenhum domínio usava esse nome.

`GET /api/v1/admin/analytics/pii-scans?limit=200` — mesmo formato de
`/analytics/profiling` (tabela, executado por, quando + `flagged_columns_count`).

---

## Analytics de uso — visualizações (v1.7, ranking removido na v1.8)

Mais 2 leituras na aba "Uso do Atlas", nenhuma com gravação nova — as 2
combinam sinais já rastreados pelas seções anteriores (login, profiling,
scan de PII, table view, busca).

### Ranking de domínios mais usados — removido na v1.8

Existiu entre v1.7 e v1.8. Comparava só profiling vs. PII scan (2 de 8
domínios do produto — catalog/lineage/freshness/finops/storage sem
tracking de uso, `access_requests` não estava integrado). Usuário
decidiu remover em vez de completar a instrumentação dos domínios
faltantes: "exclua essa seção por enquanto, não faz sentido ter ela".
Endpoint (`GET /api/v1/admin/analytics/domain-usage`), service
(`get_domain_usage_ranking`), schemas (`DomainUsageMonthBucket`/
`DomainUsageRankingResponse`) e componente (`DomainUsageRankingSection.tsx`)
removidos por completo, não comentados.

### Mapa de calor de horário de uso (zero gravação nova)

`GET /api/v1/admin/analytics/usage-heatmap?lookback_days=90` combina os
5 sinais de timestamp já existentes — `login_events`, `profiling_history`,
`pii_scan_history`, `history_table_views`, `history_searches` — num
bucket só `(weekday, hour) -> count` (`weekday` = `datetime.weekday()`,
0=segunda...6=domingo). Só `list_login_events` tem filtro de data nativo
(`since=...`); os outros 4 não têm parâmetro de data — filtro por
`lookback_days` é feito em Python dentro de
`analytics_service.get_usage_heatmap`, comparando o timestamp de cada
evento contra o cutoff.

**Sem heatmap nativo no recharts** (confirmado — só `LineChart`/`BarChart`
são usados em todo o frontend hoje) — `UsageHeatmapGrid.tsx` é uma grade
CSS customizada (7 linhas × 24 colunas), sem recharts, com intensidade
de cor por opacity sobre `--color-primary` (relativo à célula de maior
contagem) e tooltip nativo (`title`) por célula.

### Funil de retenção (zero gravação nova, 4 estágios na v1.8)

`GET /api/v1/admin/analytics/retention-funnel?lookback_days=90` — 4
estágios sobre os mesmos 5 sinais do heatmap (login + as 4 fontes de
ação): `users_with_login` (e-mails distintos em `login_events` na
janela), `users_with_action` (desses, quantos tiveram ≥1 evento de
profiling/PII scan/table view/busca na mesma janela),
`users_with_5plus_actions` (≥5 eventos), `users_with_10plus_actions`
(≥10 eventos, qualquer combinação dos 4 tipos).

**Decisão de design**: "ação" não precisa vir depois do login
temporalmente, só estar na mesma janela de `lookback_days` — evita
lógica frágil de "qual foi o primeiro login de cada usuário" só pra um
funil que já cumpre o propósito (leitura aproximada de engajamento) sem
essa precisão. Frontend (`RetentionFunnelSection.tsx`) mostra as 4
contagens como `BarChart` horizontal (`layout="vertical"`, mesmo padrão
de `NavigationAnalyticsSection.tsx`), rotuladas "Acesso"/"Ação"/"+4
Ações"/"+9 Ações" (os dois últimos rótulos são relativos ao 1º estágio
de ação, não ao literal do campo — o valor real é ≥5 e ≥10), +
percentual de cada estágio relativo ao anterior.

---

## Duas dependencies novas em `core/auth.py`

```python
def require_admin(user=Depends(get_current_user), client=Depends(get_firestore_client)) -> UserInfo:
    """403 (AdminAccessRequiredError) se hub_users/{email}.is_admin != True."""

def require_project_access(project_id: str, user=Depends(get_current_user), client=Depends(get_firestore_client)) -> UserInfo:
    """403 (ProjectNotAuthorizedError) se project_id não estiver em
    hub_users/{email}.allowed_projects (nem "*" presente). Usuário sem
    documento tem allowed_projects vazio -> nega tudo (fail closed)."""
```

`require_project_access` substitui `get_current_user` como dependency de
router em **todo** endpoint que recebe `project_id` como path param:
`catalog`, `freshness`, `profiling`, `quality`, `lineage`, `pii`,
`access`, `finops`, `projects` (inclusive `GET /projects/{id}/validate`,
o primeiro endpoint chamado quando o usuário digita um projeto no
seletor — barra ali, antes de qualquer outra tela). `favorites`/`history`
não mudam: `project_id` ali só aparece como escopo do próprio doc do
usuário (`users/{email}/favorites/...`), nunca dispara consulta real
contra o projeto alvo.

Distinção importante de mensagem de erro:
- `ProjectAccessDeniedError` (já existia) — a service account não tem
  IAM no GCP; orienta rodar `gcloud add-iam-policy-binding`.
- `ProjectNotAuthorizedError` (nova) — a SA pode até ter IAM, mas o
  **usuário não está autorizado no ACL do Atlas**; orienta pedir a um
  admin do Atlas, não rodar `gcloud`.

---

## Endpoints da API

Todos sob `dependencies=[Depends(require_admin)]` — 403
(`AdminAccessRequiredError`) para quem não é admin.

### GET /api/v1/admin/users
Lista todos os `hub_users`, ordenados por e-mail.

### PUT /api/v1/admin/users/{email}
Upsert (cria se não existe, atualiza se existe). `created_at` é
preservado em updates.

**Body:**
```json
{"is_admin": false, "allowed_projects": ["client-a-project"]}
```

### DELETE /api/v1/admin/users/{email}
Remove o documento (idempotente — deletar e-mail inexistente não é
erro). Não afeta a allowlist de **login** — só remove acesso a projeto
e/ou status de admin.

Ambos `PUT`/`DELETE` bloqueiam remover `is_admin` (ou deletar) do
**último** administrador restante (`LastAdminLockoutError`, HTTP 400) —
sem isso, ninguém mais conseguiria abrir `/admin` pra reverter.

### GET /api/v1/admin/projects
Lista `hub_projects`, ordenados por `project_id`.

### PUT /api/v1/admin/projects/{project_id}
Upsert — cria o projeto (registra pra aparecer na aba "Por projeto") ou
atualiza `is_public`. Body: `{"is_public": true}`.

### DELETE /api/v1/admin/projects/{project_id} (v1.9)
Remove o doc `hub_projects/{project_id}` (idempotente). **Não cascateia**
pra `allowed_projects` de usuários/grupos que já citavam esse projeto.

### GET /api/v1/admin/projects/{project_id}/checklist (v1.9)
Checklist best-effort do onboarding (BigQuery/Logging/Storage, probing
real, sem exigir role nova) — ver seção "Checklist de onboarding" acima.

### GET /api/v1/admin/projects/{project_id}/users
Quem tem acesso a este projeto — `is_public` + lista de
`{email, is_admin, granted_via}` (explícito ou wildcard). Não lista
"todo mundo" quando `is_public=true` (é uma população não-finita, não
uma lista de e-mails).

### POST /api/v1/admin/projects/{project_id}/users/{email}
Concede — idempotente, cria o usuário (`is_admin=False`) se ainda não
existir, adiciona `project_id` à lista dele preservando o resto.

### DELETE /api/v1/admin/projects/{project_id}/users/{email}
Revoga — remove só este `project_id` da lista do usuário. **Não afeta**
`hub_projects.is_public`: se o projeto está público, o usuário continua
acessando por esse eixo independente mesmo depois da revogação explícita.

### GET /api/v1/admin/groups
Lista `hub_groups`, ordenados por `group_id`.

### PUT /api/v1/admin/groups/{group_id}
Upsert (cria se não existe, atualiza se existe). `created_at` é
preservado em updates.

**Body:**
```json
{"manual_members": ["a@dp6.com.br"], "allowed_projects": ["client-a-project"]}
```

### DELETE /api/v1/admin/groups/{group_id}
Remove o documento (idempotente). Membros perdem só o acesso concedido
por este grupo — `hub_users` não é afetado.

### GET /api/v1/admin/workspace-groups (v1.6)
Lista `{email, name}` dos grupos do domínio do Workspace, pra popular o
seletor de "criar grupo" na UI. Exclui grupos com `directMembersCount
<= 1` — em domínios reais é comum haver um Google Group pessoal por
funcionário (nome + `firstname.lastname@dominio`), que não são grupos
de time/acesso e só teriam poluído o seletor (descoberto testando
contra o Workspace real da DP6, 2026-08-25). Lista vazia se a
integração não estiver configurada ou a Directory API falhar — nunca
erro.

### GET /api/v1/admin/access-requests?status=pending
Lista `access_requests`, mais recente primeiro. `status` opcional
(`pending`/`approved`/`denied`); sem o parâmetro, lista todas.

### POST /api/v1/admin/access-requests/{request_id}/approve
Concede o projeto (via `grant_project_to_user`) e marca `status="approved"`.
Se `request_type == "inclusion"`, registra o projeto primeiro
(`upsert_project`, `is_public=False`) — ver "`request_type`" acima.
404 (`AccessRequestNotFoundError`) se `request_id` não existir.

### POST /api/v1/admin/access-requests/{request_id}/deny
Só marca `status="denied"` — não concede nada.

### POST /api/v1/access-requests (fora de `/admin`, qualquer usuário autenticado)
Cria pedidos pra si mesmo. Body: `{"project_ids": ["proj-a", "proj-b"]}`.
Filtra silenciosamente projetos já acessíveis ou com pedido pendente
duplicado — ver "Solicitação de acesso" acima.

### GET /api/v1/admin/analytics/logins?lookback_days=90

Params opcionais (refresh visual rodada 2, AC-ADM-RV-03): `from` e `to`
(datas `YYYY-MM-DD`). Quando `from` é dado, ele vira o `since` da busca no
Firestore (no lugar de `lookback_days`); `to` filtra o limite superior
(fim do dia UTC, inclusivo) depois. Sem `from`/`to` → comportamento antigo
(`lookback_days`). ASM-ADM-RV-01 resolvida.

### GET /api/v1/admin/analytics/favorites
### GET /api/v1/admin/analytics/profiling?limit=200
Ver "Analytics de uso (v1.2)" acima.

### GET /api/v1/admin/analytics/access-requests
### GET /api/v1/admin/analytics/navigation
### GET /api/v1/admin/analytics/pii-scans?limit=200
Ver "Analytics de uso (v1.3)" acima.

### GET /api/v1/admin/analytics/usage-heatmap?lookback_days=90
### GET /api/v1/admin/analytics/retention-funnel?lookback_days=90
Ver "Analytics de uso — visualizações (v1.7, ranking removido na v1.8)" acima.

---

## `is_admin` exposto só em `GET /auth/me`

`UserInfo` (payload do JWT de sessão) ganhou o campo `is_admin: bool = False`,
mas **só `GET /auth/me` o popula de verdade** (uma leitura Firestore
extra, só nessa rota). `get_current_user` (usado em todo request
autenticado) não ganha I/O novo — seria desperdício ler Firestore em
toda chamada de catálogo/freshness/etc. quando só o frontend, ao montar
a sessão, precisa saber se mostra o link de admin.

**Consequência de design:** `user.is_admin` só é confiável quando o
`UserInfo` vem de `/auth/me`. `require_admin` nunca confia nesse campo —
sempre faz sua própria checagem fresca no Firestore.

---

## Bootstrap do primeiro admin

No primeiro deploy, `hub_users` está vazio → `require_project_access`
nega todo `project_id` pra todo mundo (fail closed, esperado) e
`require_admin` nega `/admin` pra todo mundo — ninguém consegue criar o
primeiro registro pela UI (problema de ovo-e-galinha). Resolvido com
`scripts/seed_admin.py` (credenciais do operador via
`gcloud auth application-default login`, não a SA de runtime):

```bash
cd apps/backend
uv run python ../../scripts/seed_admin.py --project atlas-dev --email <primeiro-admin>
```

Rodar em dev primeiro, validar o fluxo ponta a ponta, só depois em prod.

---

## Estrutura de arquivos

```
apps/backend/src/atlas/
├── api/v1/
│   ├── admin.py                # GET/PUT/DELETE users + projects + access-requests
│   ├── access_requests.py      # novo (v1.1) — POST público, fora de /admin
│   └── auth.py                 # + is_admin em GET /me
├── core/
│   ├── auth.py                 # require_admin, require_project_access
│   │                           # + require_project_admin (v1.11)
│   └── exceptions.py           # ProjectNotAuthorizedError, AdminAccessRequiredError,
│                                # LastAdminLockoutError, AccessRequestNotFoundError (v1.1)
│                                # + ProjectAdminRequiredError (v1.11)
├── domains/
│   ├── admin/                  # schemas, repository, service — hub_users + hub_projects (v1.1)
│   │                           # + access_requests (v1.1, request_type na v1.9)
│   │                           # + analytics_{schemas,repository,service}.py (v1.2, +3 funções v1.3)
│   │                           # + hub_groups (v1.4) — service.list_workspace_groups (v1.6)
│   │                           # + checklist_service.py (v1.9) — checklist best-effort de onboarding
│   │                           # + project_admin_repository.py (v1.11) — grant/revoke/list de
│   │                           #   hub_projects/{p}/project_admins, mesmo estilo de repository.py
│   ├── quality/history_repository.py  # + project_id/dataset_id/table_id no run (v1.2)
│   ├── pii/history_repository.py      # novo (v1.3) — pii_scan_history/{doc}/scans
│   └── auth/schemas.py         # UserInfo + is_admin
└── tests/unit/
    ├── admin/                  # + test_analytics_repository.py, test_analytics_service.py (v1.2, estendidos v1.3)
    │                           # + test_project_admin_repository.py, test_project_admin_service.py (v1.11)
    ├── pii/test_history_repository.py  # novo (v1.3)
    └── core/test_auth.py       # require_admin/require_project_access
                                 # + require_project_admin (v1.11)

scripts/seed_admin.py           # bootstrap do primeiro admin

apps/frontend/src/
├── components/
│   ├── ui/checkbox.tsx         # via shadcn CLI
│   └── ApiErrorNotice.tsx      # + prop `action` (v1.1) — CTA opcional junto da mensagem
├── features/
│   ├── admin/
│   │   ├── AdminPage.tsx        # shell de abas: Por usuário / Por projeto / Grupos (v1.4) / Solicitações
│   │   ├── AdminUsersTab.tsx    # conteúdo da v1.0, extraído (v1.1); + coluna "Grupos" (v1.4)
│   │   ├── AdminProjectsTab.tsx # novo (v1.1) — visão projeto -> usuários + is_public
│   │   ├── AdminGroupsTab.tsx   # novo (v1.4) — CRUD de hub_groups (membros + projetos)
│   │   │                        # + seletor de grupos do Workspace no "Criar grupo" (v1.6)
│   │   ├── AdminAccessRequestsTab.tsx  # novo (v1.1)
│   │   ├── ProjectChipEditor.tsx       # novo (v1.1) — compartilhado, reaproveitado
│   │   │                               # também pra e-mail de membro de grupo (v1.4)
│   │   ├── RequestAccessDialog.tsx     # novo (v1.1)
│   │   ├── RequireAdmin.tsx
│   │   ├── AdminUsageTab.tsx           # v1.2 (3 seções) + 3 novas (v1.3)
│   │   ├── LoginAnalyticsSection.tsx   # novo (v1.2)
│   │   ├── FavoritesAnalyticsSection.tsx  # novo (v1.2)
│   │   ├── ProfilingActivitySection.tsx   # novo (v1.2)
│   │   ├── AccessRequestAnalyticsSection.tsx  # novo (v1.3)
│   │   ├── NavigationAnalyticsSection.tsx     # novo (v1.3)
│   │   ├── PiiScanActivitySection.tsx         # novo (v1.3)
│   │   └── hooks.ts
│   └── projects/ProjectSelector.tsx    # erro visível + CTA "Solicitar acesso" (v1.1)
├── app/
│   ├── router.tsx               # rota /admin, gated por RequireAdmin
│   ├── topbar.tsx                # link + badge de pendentes (v1.1) + botão "Solicitar acesso"
│   └── layout.tsx                # CTA "Solicitar acesso" no estado vazio (v1.1); fix (v1.4):
│                                  # /admin não depende mais de projectId selecionado — só as
│                                  # rotas de dado de projeto dependem
├── lib/
│   ├── http-client.ts            # + método put
│   └── api/accessRequests.ts     # novo (v1.1)
└── types/
    ├── auth.ts                   # + is_admin
    └── admin.ts                  # + HubProject, AccessRequest, etc. (v1.1)
                                   # + LoginAnalyticsResponse, FavoritesAnalyticsResponse,
                                   #   ProfilingActivityResponse (v1.2)
                                   # + AccessRequestAnalyticsResponse, NavigationAnalyticsResponse,
                                   #   PiiScanActivityResponse (v1.3)
                                   # + HubGroup, HubGroupsListResponse, UpsertHubGroupRequest (v1.4)
                                   # + ProjectAdmin, ProjectAdminsListResponse (v1.11)
```

A UI de conceder/revogar Admin de projeto **não** vive em `features/admin/`
(gated por `RequireAdmin`, exclusivo de superadmin) — vive dentro de
`features/metadata/` (`ProjectAdminsPanel`), porque o próprio propósito do
papel é permitir que alguém sem ser superadmin administre; ver
`docs/specs/metadata.md`, "Frontend". **Desde metadata.md v2.0 o painel é
renderizado na `MetadataOverviewPage`** (visão geral de Metadados do
projeto), não mais na aba de metadados de cada tabela — leitura visível a
qualquer um com acesso ao projeto, conceder/revogar só pra Admin de
projeto (`datasets: null`) e superadmin.

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| Usuário sem doc em `hub_users` | Loga normalmente (login é allowlist de domínio/email, separado) mas `allowed_projects` vazio → `ProjectNotAuthorizedError` em qualquer projeto |
| `"*"` em `allowed_projects` | Acesso a qualquer `project_id` que a SA de runtime alcançar |
| Remover `is_admin` (ou deletar) do último admin | Bloqueado (`LastAdminLockoutError`, 400) |
| `DELETE` de e-mail inexistente | Idempotente, 204 |
| E-mail digitado com maiúsculas no formulário de admin | Normalizado pra lowercase em `service.py` antes de gravar/consultar |
| Primeiro deploy, `hub_users` vazio | Fail closed total (login funciona, nenhum projeto acessível, `/admin` inacessível) até rodar `scripts/seed_admin.py` |
| SA tem IAM no projeto mas usuário não tem ACL no Atlas | `ProjectNotAuthorizedError` (403) — nunca chega a tentar a query real no BigQuery |
| `hub_projects/{id}.is_public = true` | Libera geral, inclusive usuário sem doc em `hub_users` — checado antes de qualquer coisa em `has_project_access` |
| Solicitar acesso a projeto que já tem (explícito, wildcard ou público) | Filtrado silenciosamente pelo backend, não cria pedido |
| Solicitar acesso a projeto com pedido `pending` já existente do mesmo usuário | Filtrado, não duplica |
| Aprovar pedido de projeto que virou público nesse meio-tempo | `grant_project_to_user` roda normalmente (idempotente — resultado final é o mesmo) |
| Revogar (`DELETE .../projects/{id}/users/{email}`) o único acesso explícito de alguém a um projeto público | Sem efeito real — o projeto continua público, `is_public` não muda por essa chamada (eixos independentes) |
| `request_id` inexistente em approve/deny | 404 (`AccessRequestNotFoundError`) |
| Usuário é membro de um grupo com acesso a um projeto e também tem o mesmo projeto individualmente | Sem efeito duplo — `has_project_access` já retorna `True` no primeiro checkpoint que bater; revogar um dos dois eixos não afeta o outro |
| Grupo com `"*"` em `allowed_projects` | Libera qualquer projeto que a SA de runtime alcançar pra todo membro do grupo, mesma semântica do wildcard individual |
| Remover um grupo (`DELETE /admin/groups/{id}`) | Membros perdem só o acesso concedido por esse grupo — acesso individual (`hub_users`) e outros grupos não são afetados |
| `GET /admin/projects/{id}/users` com usuário que só tem acesso via grupo | Não aparece na lista — esse endpoint reflete só `hub_users`/`hub_projects`, não soma acesso de grupo (fora do escopo desta versão, ver abaixo) |
| Firestore indisponível no momento do login | Login continua funcionando; gravação de `login_events` falha silenciosamente (logada), sem expor erro ao usuário |
| Run de profiling gravado antes da v1.2 (sem `project_id`) | Filtrado da visão global de atividade; sai da janela sozinho quando o cap de 30/tabela rotacionar |
| Favorito de dataset inteiro (`table_id: null`) na visão "por base" | Agrupado como linha própria, separado de favoritos de tabelas específicas do mesmo dataset |
| Nenhuma solicitação de acesso resolvida ainda | `approval_rate: null` (não `0%`) |
| Usuário com mais de 20 tabelas vistas/buscas | Só as 20 mais recentes entram na agregação de navegação — janela recente, não histórico completo |
| Cache hit num scan de PII repetido | Não grava novo doc em `pii_scan_history` — não houve execução real |
| `collection_group("runs")` (profiling) vs PII | Nomes de subcoleção diferentes (`runs` vs `scans`) — sem risco de mistura na agregação |
| Apagar um projeto que ainda tem grants explícitos em `hub_users`/`hub_groups` | Grants continuam intactos — `DELETE /admin/projects/{id}` só remove o doc `hub_projects`, não cascateia (dois eixos independentes) |
| Apagar um projeto que estava `is_public=true` | Quem tinha acesso só por esse eixo perde o acesso (`has_project_access` não encontra mais o doc); grants explícitos/wildcard continuam valendo |
| Checklist verificado num projeto sem `logging.privateLogViewer` (só `logging.viewer`) | Item `logging` reporta `"ok"` — o probe não distingue disso de "sem atividade", `detail` sempre traz essa ressalva |
| Pedido `"inclusion"` aprovado pra um `project_id` que já tinha doc em `hub_projects` (registrado por outro caminho nesse meio-tempo) | `upsert_project` é idempotente — sobrescreve `is_public=False` (comportamento normal de upsert), sem erro |
| Pedido `"access"` e pedido `"inclusion"` pendentes ao mesmo tempo, mesmo usuário e projeto | Coexistem — dedupe é por `(project_id, request_type)`, não só `project_id` |
| Superadmin consultado em `GET /projects/{id}/admins` | Não aparece na lista — a coleção só guarda grants explícitos; superadmin é admin de tudo por regra, não por doc |
| Grant com `datasets: []` (lista vazia, não `null`) | Equivale a "nenhum dataset" coberto — distinto de `null` (projeto inteiro). Documentado, não é bug |
| Dataset novo criado no projeto depois de um grant com `datasets: ["RAW"]` | Não coberto automaticamente — só `datasets: null` acompanha datasets futuros |
| Admin de projeto revoga o próprio acesso | Permitido (mesma regra simétrica de revogação entre pares) — sem confirmação extra |
| `require_project_admin` chamado sem `dataset_id` (endpoint project-scoped, ex: budget de projeto) | Só passa quem tem `datasets: null` (projeto inteiro) — um admin restrito a datasets específicos não passa nessa checagem, mesmo que `dataset_id` não se aplique à ação |
| `PUT /projects/{id}/admins/{email}` pra um usuário sem nenhum acesso de leitura ao projeto | Grant é criado normalmente — não injeta acesso de leitura (ver ASM-005) |

---

## Critérios de aceite

| ID | Comportamento | Testado em |
|---|---|---|
| AC-001 | Apagar um projeto remove só o doc `hub_projects`, sem afetar `allowed_projects` de usuários/grupos | `test_delete_project_delegates_to_repository` |
| AC-002 | Checklist reaproveita `discover_regions` pro item BigQuery (mesmo probe de `validate_project`) | `test_check_project_checklist_all_ok`, `test_check_project_checklist_bigquery_denied`, `test_check_project_checklist_bigquery_not_found` |
| AC-003 | Item `logging` do checklist reporta `denied`/`not_found`/`ok` conforme o probe, sempre com a ressalva do `privateLogViewer` no `detail` | `test_check_project_checklist_logging_denied`, `test_check_project_checklist_logging_not_found` |
| AC-004 | Item `audit_logs` do checklist é sempre `not_checked`, com o comando manual no `detail` | `test_check_project_checklist_audit_logs_always_not_checked_with_command_detail` |
| AC-005 | Criar um pedido de acesso sem especificar tipo assume `"access"` (compatibilidade com o fluxo original) | `test_create_access_requests_creates_for_new_project` |
| AC-006 | Criar um pedido `"inclusion"` propaga o tipo pro dedupe e pro doc criado | `test_create_access_requests_passes_inclusion_type_through` |
| AC-007 | Aprovar um pedido `"inclusion"` registra o projeto (`upsert_project`) **antes** de liberar o solicitante (`grant_project_to_user`) | `test_approve_inclusion_request_registers_project_and_grants_access` |
| AC-008 | Aprovar um pedido `"access"` (default, sem `request_type` no doc) nunca chama `upsert_project` — regressão do comportamento original | `test_approve_access_request_grants_project_and_marks_approved` |
| AC-009 | Superadmin passa em `require_project_admin` pra qualquer projeto/dataset, sem doc em `project_admins` | `test_require_project_admin_superadmin_bypasses` |
| AC-010 | Admin de projeto com `datasets: null` passa pra qualquer `dataset_id` do projeto; com `datasets: ["RAW"]` passa só pra `"RAW"`, nega pros demais | `test_require_project_admin_null_covers_any_dataset`, `test_require_project_admin_scoped_denies_outside_scope` |
| AC-011 | `PUT /projects/{id}/admins/{email}` por um Admin de projeto existente concede o papel a um novo usuário, sem checagem de hierarquia de escopo (sem trava de redelegação) | `test_grant_project_admin_no_redelegation_lock` |
| AC-012 | `DELETE /projects/{id}/admins/{email}` por qualquer Admin de projeto do mesmo projeto revoga outro Admin de projeto, independente de quem concedeu a quem | `test_revoke_project_admin_symmetric_between_peers` |
| AC-013 | `PUT`/`DELETE /projects/{id}/admins/...` por um usuário que não é superadmin nem Admin de projeto daquele projeto é rejeitado (403) | `test_require_project_admin_denies_regular_user` |

## Suposições

| ID | Suposição | Status |
|---|---|---|
| ASM-001 | Checklist não detecta `logging.privateLogViewer` faltando — só `logging.viewer` (mesma ambiguidade de lineage/access) | confirmada |
| ASM-002 | Checklist não lê a IAM policy do projeto-alvo (probing, não introspecção) — não exige nenhuma role nova da SA do Atlas além do que já está em `docs/onboarding-cliente.md` | confirmada |
| ASM-003 | Apagar `hub_projects/{id}` não cascateia pra `allowed_projects` de usuários/grupos — mesmo racional de eixos independentes já documentado nesta spec | confirmada |
| ASM-004 | `access_denied` e `project_not_found` no seletor de projeto ganham a mesma CTA de inclusão — usuário comum não distingue os dois casos, admin investiga ao revisar o pedido | confirmada com o usuário |
| ASM-005 | Revogação entre Admins de projeto é simétrica (qualquer um revoga qualquer outro do mesmo projeto), sem hierarquia por escopo nem proteção de "último admin" — superadmin é fallback permanente, então não há aqui um `LastAdminLockoutError` equivalente. | confirmada com o usuário (aprovação do plano da spec, 2026-09-05) |
| ASM-006 | Conceder Admin de projeto **não** concede acesso de leitura ao projeto — checagens independentes (`require_project_admin` não chama `has_project_access`). Quem concede o papel garante o acesso básico separadamente, se necessário. | confirmada com o usuário (aprovação do plano da spec, 2026-09-05) |

## Perguntas em aberto

| ID | Pergunta | Status | Resposta |
|---|---|---|---|
| Q-001 | Vale um botão de "desfazer" ou histórico de projetos apagados? | aberta | — |

---

## Fora do escopo desta spec

- **Gerenciar a allowlist de login (`OAUTH_ALLOWLIST`)** pela tela de
  admin — continua manual via `gcloud secrets versions add`, como hoje.
  Escreve-la exigiria conceder `secretmanager.versions.add` à SA de
  runtime, uma permissão mais sensível que Firestore read/write (que a
  SA já tem); decisão consciente de manter o escopo desta v1 menor.
- **Histórico/audit log de mudanças de ACL** — `updated_by`/`updated_at`
  no próprio documento cobrem "quem mudou por último", não um log
  completo de mudanças ao longo do tempo.
- **Expiração automática de acesso** (ex: acesso temporário por N dias)
  — todo acesso concedido é permanente até um admin revogar manualmente.
- **`GET /admin/projects/{id}/users` refletir acesso via grupo** — esse
  endpoint (aba "Por projeto") continua mostrando só `hub_users`/
  `hub_projects`; um usuário que só tem acesso via `hub_groups` (v1.4)
  não aparece nessa lista, ainda que `has_project_access` já retorne
  `True` pra ele. Juntar os três eixos nessa visão específica é mais
  complexo (não dá pra fazer com uma query `array_contains_any` simples)
  e não fazia parte do pedido original — revisitar se virar necessidade
  real de uso.
- **Grupos aninhados** (grupo dentro de grupo) — `hub_groups` é uma
  estrutura plana, um membro é sempre um e-mail, nunca outro `group_id`.
- **Tela de acompanhamento do próprio usuário** ("minhas solicitações")
  — só o admin vê/gerencia `access_requests`; quem solicita só recebe a
  confirmação de envio no momento, sem histórico de status depois.
- **Notificação por e-mail** ao aprovar/negar uma solicitação — só
  reflete dentro do Atlas (badge de pendentes some da visão do admin; o
  solicitante percebe na próxima vez que tentar acessar o projeto).
- **Delegação de Admin de projeto pra um `hub_groups` inteiro** — só
  indivíduo (e-mail) nesta versão.
- **Escopo do papel crescer além de metadados + budget** — decisão de
  spec nova, não extensão automática deste documento.
- **Histórico de concessões/revogações de Admin de projeto** — mesmo
  racional do resto do domínio (`updated_at`/`granted_by` cobrem "por
  último", não um log completo ao longo do tempo).
- **Expiração automática do papel** — permanente até alguém revogar,
  mesma premissa do resto do ACL do Atlas.


---

## Refresh visual - pendente (2026-09)

Ver brief `frontend-visual-refresh.md` (sec. Administracao) e
`frontend-visual-refresh-plan.md` sec.5.

| ID | Comportamento | Teste |
|---|---|---|
| AC-ADM-RV-01 | ✅ (R2-5) "Acessos ao Atlas" = `<ComboChart>` coluna + linha; `<ChoiceToggle>` "Coluna: Acumulado / Período" troca qual série é coluna e qual é linha (eixo Y duplo). | `LoginAnalyticsSection` — visual |
| AC-ADM-RV-02 | ✅ (R2-5) `<ChoiceToggle>` "Granularidade: Dia / Mês" — usa os buckets `daily`/`monthly` que a resposta já traz. | `LoginAnalyticsSection` — visual |
| AC-ADM-RV-03 | ✅ (R2-5) dois `<DateField>` "De"/"Até" → `?from=&to=` no endpoint (backend B7). Sem eles, janela `lookback_days=90`. | `test_get_login_analytics_from_to_window` |
| AC-ADM-RV-04 | ✅ (R2-5; reescrito na rodada 3) `<Funnel>` = barras horizontais **centradas** afunilando de cima pra baixo (largura ∝ contagem), rótulo + valor + % **acima** de cada barra. A versão R2-5 usava `<polygon>` SVG esticado, que distorcia dentro do container de altura fixa (`h-56`) — trocado por `<div>`s com `width: %` + `mx-auto`. `role="img"` + `aria-label` + `<table>` sr-only. | `Funnel` — visual |

Suposicao **ASM-ADM-RV-01** (resolvida — R2-5): AC-ADM-RV-03 exigiu sim
parametro novo no endpoint (`?from=&to=`) — implementado (B7). Layout:
`AdminUsageTab` deixou de ser `flex-col gap-8` de `CollapsibleSection` e
virou blocos — combo de acessos full-width, funil + heatmap numa linha
2-col, seções de tabela empilhadas.
