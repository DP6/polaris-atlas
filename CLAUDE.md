# Atlas

Plataforma de observabilidade de dados no GCP. Monorepo com backend, frontend e infraestrutura versionados juntos, com dois ambientes (`dev` e `prod`) espelhados por Terraform — **rodando no mesmo projeto GCP** (topologia single-project: a empresa cliente só autoriza um único projeto pra esta aplicação, permanente, não uma fase transitória). O isolamento entre os dois ambientes vem inteiramente de nomes de recurso sufixados por ambiente (Cloud Run, service accounts, Firestore named database), nunca de fronteira de projeto — ver seção "Projetos e ambientes GCP" abaixo.

Este documento é a fonte de verdade das convenções do projeto. Qualquer sessão (humana ou do Claude Code) deve seguir o que está aqui. Se uma convenção mudar, atualize este arquivo no mesmo PR.

## Visão geral do domínio

O produto monitora BigQuery (todos os datasets/tabelas da organização) e, a partir da expansão iniciada em 2026-08-18, também Cloud Storage — primeiro passo de uma frente maior de cobertura pra além do BigQuery (Storage → Scheduler → Workflows, nessa ordem de prioridade, ver `docs/specs/storage.md` seção 1):

| Funcionalidade | O que faz | Fonte de dados principal |
|---|---|---|
| Catálogo | Inventário navegável de datasets/tabelas | `INFORMATION_SCHEMA` (BigQuery) |
| Lineage e tabelas órfãs | Reconstrói relações de dependência entre tabelas (incluindo bucket do GCS como nó, via jobs LOAD/EXTRACT) e identifica tabelas sem consumidores conhecidos | Cloud Logging (audit logs de jobs BigQuery) |
| Fingerprinting de PII | Detecta colunas com dados pessoais sensíveis | `INFORMATION_SCHEMA` + amostragem de dados |
| Mapa de acesso | Quem acessou o quê e quando | Cloud Logging (data access audit logs) |
| Qualidade de dados e schema drift | Detecta mudanças de schema e quebras de contrato | `INFORMATION_SCHEMA` (snapshots ao longo do tempo) |
| Freshness com SLA | Monitora se tabelas estão sendo atualizadas dentro do esperado | Metadados de última modificação (BigQuery) |
| FinOps | Scanner de desperdício (tabelas não usadas, partições mal configuradas) e acompanhamento de budget | BigQuery + Cloud Billing |
| Cloud Storage | Catálogo de buckets, scanner de desperdício (idade + config, com confirmação opcional de uso real via audit log) | Cloud Storage API + Cloud Logging (audit logs de leitura de objeto) |
| Metadados de governança | Descrição, ownership, classificação, certificação e histórico de edição por tabela/coluna, com PII confirmado e glossário livre; linka lineage/qualidade/freshness/budget em vez de duplicar | Firestore (dado próprio do Hub, não do GCP) — ver `docs/specs/metadata.md` |

Esses nove domínios são a espinha dorsal da estrutura de pastas do backend e do frontend — cada um vira um módulo isolado, não uma feature espalhada por camadas transversais. `storage` é o único que não segue o agrupamento "BigQuery" da sidebar (`SidebarServiceGroup` próprio, "Cloud Storage") — ver `docs/specs/storage.md`. `metadata` é o único cuja escrita é gated por um papel específico (Admin de projeto, `docs/specs/admin.md`), não por acesso comum ao projeto.

## Stack

- **Backend**: Python + FastAPI, gerenciado com `uv`
- **Frontend**: React + Vite + TypeScript + shadcn/ui + Tailwind, gerenciado com `pnpm`
- **Container**: Docker (build multi-stage)
- **IaC**: Terraform, diretórios por ambiente (`environments/dev`, `environments/prod`) — **não** usar Terraform workspaces
- **CI/CD**: GitHub Actions + Workload Identity Federation (sem chaves de service account)

## Projetos e ambientes GCP

| Ambiente | Projeto GCP | Serviço Cloud Run | Branch/gatilho |
|---|---|---|---|
| dev | `dp6-ci-polaris` (compartilhado) | `backend-dev`, `frontend-dev` | qualquer push em qualquer branch (exceto `main`) |
| prod | `dp6-ci-polaris` (compartilhado) | `backend-prod`, `frontend-prod` | merge/push em `main` |

Dev e prod **compartilham o mesmo projeto GCP** — não há isolamento por
fronteira de projeto. O isolamento entre os dois ambientes é garantido
inteiramente por convenção de nomenclatura:

- **Cloud Run**: nome do serviço sempre sufixado (`backend-dev`/
  `backend-prod`, idem frontend) — a SA de runtime herda o sufixo
  (`account_id = "${service_name}-run"`, ver `modules/cloud-run/main.tf`).
- **Firestore**: named database por ambiente (`dev`/`prod`), nunca o
  banco `(default)` implícito — ver `core/firestore.py`.
- **Ambiente do backend**: nunca inferido do `project_id` (é o mesmo pros
  dois) — vem de `ATLAS_ENVIRONMENT`, injetada pelo Terraform
  (ver `core/config.py::settings.environment`, `core/secrets.py::_is_prod`).
- **Secret Manager**: secrets com valor distinto por ambiente têm nome
  sufixado (`GOOGLE_OAUTH_CLIENT_ID_DEV`/`_PROD`, `JWT_SECRET_DEV`/`_PROD`
  — este último crítico: sem sufixo, um token de sessão de dev validaria
  em prod); só `OAUTH_ALLOWLIST` é intencionalmente compartilhado sem
  sufixo (controla apenas quem loga, não isolamento de sessão).
- **Terraform state**: mesmo bucket GCS, isolado só por `prefix`
  (`environments/dev` vs `environments/prod`).
- **Deploy (WIF)**: um pool compartilhado, mas **um provider por
  ambiente** (`github-provider-dev`/`github-provider-prod`) — a
  restrição "prod só via `refs/heads/main`" vive no
  `attribute_condition` do provider de prod, igual ao padrão do
  repositório de origem. Tentativas de usar um provider único
  compartilhado + restrição no binding da SA (subject exato, atributo
  customizado, IAM Condition) falharam todas em produção — ver
  `infra/terraform/bootstrap/modules/wif-bootstrap/main.tf` e
  [ADR-010](docs/adr/ADR-010-single-project-topology.md).
- **Artifact Registry**: um repositório `apps` só, compartilhado pelos
  quatro serviços (backend/frontend × dev/prod).

Nunca remova um sufixo de ambiente de um nome de recurso "pra simplificar" — sem ele, dev e prod colidem no mesmo projeto.

## Serviços GCP e seu papel

- **Cloud Run**: hospeda backend (FastAPI) e frontend (build estático servido via container)
- **BigQuery**: fonte de metadados via `INFORMATION_SCHEMA`; alvo de análise de todos os domínios
- **Cloud Logging**: audit logs usados para lineage e mapa de acesso
- **Artifact Registry**: imagens Docker do backend e frontend
- **Secret Manager**: credenciais e segredos em runtime (nunca em variáveis de ambiente estáticas ou baked na imagem)
- **GCS**: remote state do Terraform (bucket criado uma vez em `infra/terraform/bootstrap`, um prefixo por ambiente)

## Estrutura de pastas

```
.
├── .github/workflows/          # Pipelines de CI/CD (Fase 1)
├── apps/
│   ├── backend/
│   │   ├── src/atlas/
│   │   │   ├── api/            # Routers FastAPI, schemas de request/response (camada HTTP)
│   │   │   ├── domains/        # Lógica de negócio, um subpacote por funcionalidade
│   │   │   │   ├── catalog/
│   │   │   │   ├── lineage/
│   │   │   │   ├── pii/
│   │   │   │   ├── access/
│   │   │   │   ├── quality/
│   │   │   │   ├── freshness/
│   │   │   │   ├── finops/
│   │   │   │   ├── metadata/    # ver docs/specs/metadata.md
│   │   │   │   ├── auth/        # Domínio de plataforma (não é dos 8 de observabilidade) — login OAuth, sessão
│   │   │   │   └── admin/       # Domínio de plataforma — ACL de usuário×projeto, ver docs/specs/admin.md
│   │   │   └── core/            # Config, clients GCP compartilhados, logging, exceptions, auth
│   │   └── tests/
│   │       ├── unit/            # Espelha domains/, sem chamadas reais ao GCP
│   │       └── integration/     # Testes contra emuladores/projeto dev
│   └── frontend/
│       ├── src/
│       │   ├── app/             # Setup de rotas, providers, layout raiz
│       │   ├── features/        # Um subpacote por funcionalidade (mesmos 7 domínios)
│       │   ├── components/ui/   # Primitivas shadcn/ui (geradas via CLI, não escritas à mão)
│       │   ├── hooks/           # Hooks compartilhados entre features
│       │   ├── lib/             # Cliente HTTP, utils
│       │   └── types/           # Tipos compartilhados (ex: gerados a partir do OpenAPI do backend)
│       └── public/
├── infra/terraform/
│   ├── bootstrap/                # Recursos fundacionais: bucket de state, pool WIF (apply manual, uma vez)
│   ├── modules/                  # Módulos reutilizáveis (cloud-run, cloud-run-job, bigquery, artifact-registry, secret-manager, logging-sink)
│   └── environments/
│       ├── dev/                  # Root module do ambiente dev, consome modules/
│       └── prod/                 # Root module do ambiente prod, consome modules/
├── docs/adr/                     # Architecture Decision Records
├── docs/onboarding-cliente.md    # Como liberar acesso de leitura a um projeto GCP que o
│                                 # Hub vai observar (APIs, IAM, audit logs) + registro vivo
│                                 # de concessões já feitas
├── docs/finops-labels.md         # Taxonomia de labels (environment/app/managed-by),
│                                 # Billing Export pro BigQuery e como consultar/filtrar
│                                 # custo depois — ver "Registro de componentes e labels FinOps"
├── docs/gcp-components.md        # Registro vivo "recurso GCP → app/projeto" — formato
│                                 # reaproveitável em futuros projetos do Hub
├── docs/frontend/               # Harness de front-end: design system (espelho de
│                                 # index.css), regras de UI/UX, acessibilidade,
│                                 # patterns, behaviors, referências, checklist.
│                                 # Índice em docs/frontend/README.md
├── docs/design-references/      # Capturas de tela de sites externos (referência
│                                 # visual dp6/brandtech) + script de captura.
│                                 # Linkado por docs/frontend/references.md
├── docs/specs/                  # Specs de domínio — uma por funcionalidade (objetivo,
│                                 # fonte de dados, endpoints, ACs, suposições)
├── docs/skills/                 # (legado) frontend.md virou tombstone → docs/frontend/
├── docs/playbooks/                # Roteiros operacionais de execução rápida — hoje só
│                                   # hospedar o Hub em projetos novos (clonar, ajustar
│                                   # variáveis, bootstrap)
├── docs/site/                     # Site GitHub Pages com 4 abas superiores
│                                   # compartilhadas (workflow pages-site.yml, só
│                                   # este subdiretório de docs/), nesta ordem:
│   ├── produto/                   #   Descritivo de produto/portfólio — slide deck
│   │                               #   HTML autocontido (prints + descrição, tela
│   │                               #   a tela); era docs/manual/ antes da unificação
│   ├── tecnico/                   #   Guia técnico — funcionalidade por
│   │                               #   funcionalidade, sidebar de navegação
│   ├── componentes/               #   Vitrine do inventário de docs/gcp-components.md
│   │                               #   (não precisa ser cópia literal)
│   └── desenvolvimento/           #   Processo de desenvolvimento com IA
│                                   #   (spec-driven, riscos, gates, IaC, CI/CD) —
│                                   #   doc interno da equipe, não material de
│                                   #   produto; era desenvolvimento-ia/ antes de
│                                   #   virar a última aba (2026-08-26)
├── scripts/                      # Scripts de apoio (setup local, seed, etc.)
├── CLAUDE.md
└── .gitignore
```

Regra geral: **domains/ (backend) e features/ (frontend) espelham exatamente os domínios da tabela acima**. Ao adicionar uma funcionalidade nova, ela ganha uma pasta própria nos dois lados — não se mistura lógica de domínios diferentes no mesmo módulo.

## Convenções — Backend

- Python 3.12, dependências e ambiente virtual via `uv` (`uv.lock` é commitado).
- Lint e formatação: `ruff` (lint + format em uma ferramenta só, sem Black/isort/flake8 separados).
- Validação e config: Pydantic v2 + `pydantic-settings`. Nunca ler `os.environ` diretamente fora de `core/config.py`.
- Endpoints FastAPI ficam em `api/`; lógica de negócio nunca vive no router — o router chama uma função/classe de `domains/`.
- Clients de GCP (BigQuery, Logging, Secret Manager) são inicializados uma vez em `core/` e injetados via `Depends`, nunca instanciados dentro de um domínio.
- As libs oficiais do GCP (`google-cloud-*`) são majoritariamente síncronas. Endpoints que as chamam devem ser `def` (não `async def`) para que o FastAPI rode em threadpool, ou usar `run_in_threadpool` explicitamente — nunca bloquear o event loop.
- Logs estruturados em JSON (compatível com Cloud Logging), nunca `print()`.
- Testes com `pytest`. `tests/unit` não toca GCP (mocka os clients); `tests/integration` roda contra o projeto `dev`.

## Convenções — Frontend

- TypeScript estrito (`strict: true`), sem `any` implícito.
- Componentes de UI vêm do `shadcn/ui` — adicionar via CLI (`npx shadcn add ...`), não copiar/colar manualmente.
- Lint e formatação: `biome` (substitui ESLint + Prettier, uma config só, coerente com a filosofia de baixa manutenção da stack).
- Data fetching: TanStack Query — nenhuma chamada `fetch` direta dentro de componentes de página.
- Roteamento: React Router.
- Estado: preferir estado de servidor via TanStack Query + estado local de componente. Só introduzir uma lib de estado global (ex: Zustand) se houver necessidade concreta — não antecipar.
- Node 22 LTS, gerenciador de pacotes `pnpm` (lockfile `pnpm-lock.yaml` é commitado).
- Testes com Vitest + React Testing Library (planejado — o setup ainda não existe em `apps/frontend/`).
- Convenções visuais, de UX e de acessibilidade: **harness de front-end em `docs/frontend/`** — comece pelo `README.md`, que dá o roteiro de leitura por tipo de tarefa. O design system (`docs/frontend/design-system.md`) é **espelho de `apps/frontend/src/index.css`**: mudou um, muda o outro no mesmo PR.

## Convenções — Docker

- Build multi-stage (stage de build separado do stage final de runtime).
- Imagem final roda como usuário não-root.
- Um `Dockerfile` por app (`apps/backend/Dockerfile`, `apps/frontend/Dockerfile`).
- Tag de imagem no Artifact Registry: `<region>-docker.pkg.dev/<gcp-project>/<repo>/<app>:<git-sha>`. Nunca usar `:latest` em deploy.

## Convenções — Terraform

- Diretórios por ambiente (`environments/dev`, `environments/prod`), **não** workspaces — cada ambiente é uma raiz de execução independente.
- Módulos reutilizáveis em `modules/`; cada ambiente só declara `module "..." { source = "../../modules/..." }` + variáveis específicas do ambiente + backend.
- `infra/terraform/bootstrap` é aplicado manualmente (fora do CI), **uma única vez** (não por ambiente — dev e prod compartilham projeto), para criar o bucket GCS de state, o pool/provider de Workload Identity Federation e as duas SAs de deploy (`gh-deploy-dev`, `gh-deploy-prod`) — ele não pode depender de um backend remoto que ainda não existe.
- Backend do state: GCS, um bucket único compartilhado, isolado por `prefix` (`environments/dev`/`environments/prod`) definido em `bootstrap`.
- Nenhum valor sensível em `.tfvars` commitado — usar `*.tfvars.example` como referência e injetar valores reais via CI ou `.tfvars` local (gitignored).
- Nomenclatura de recursos: **sempre** sufixar com o ambiente (`-dev`/`-prod`) todo recurso que não seja naturalmente único por natureza (Cloud Run, service accounts, Firestore database) — não há projeto GCP separando dev de prod pra fazer esse trabalho por conta própria.

## CI/CD e deploy

Gatilhos (a implementar em `.github/workflows/` na Fase 1, mas já são a política oficial de deploy):

- **Push em qualquer branch** (exceto `main`) → build + deploy automático no ambiente **dev** (`dp6-ci-polaris`, serviços `backend-dev`/`frontend-dev`).
- **Merge/push em `main`** → build + deploy **de app** (`backend-deploy-prod.yml`, `frontend-deploy-prod.yml`) só roda depois de aprovação manual — os dois jobs usam `environment: production` (GitHub Environment com "required reviewers" configurado nas Settings do repo), então ficam em "Waiting" até alguém aprovar. `terraform-apply-prod.yml` continua automático (decisão consciente, 2026-08-18 — mudança de infra já passa por `terraform plan` revisado antes do merge; só o deploy de app, que sobe uma imagem nova sem revisão nenhuma no meio, ganhou o gate).

Diretrizes para os workflows quando forem criados:

- Autenticação no GCP exclusivamente via Workload Identity Federation — nenhuma service account key em segredo do GitHub.
- Workflows separados por app e por ambiente (ex: `backend-deploy-dev.yml`, `backend-deploy-prod.yml`, `frontend-deploy-dev.yml`, `frontend-deploy-prod.yml`, `terraform-plan.yml`, `terraform-apply-dev.yml`, `terraform-apply-prod.yml`), todos vivendo em `.github/workflows/`.
- `terraform plan` roda em todo PR que toca `infra/terraform/**` — mas só para **dev**. A SA `gh-deploy-prod` só pode ser impersonada por um workflow rodando na branch `main` (restrição no IAM binding da SA, não no provider WIF — ele é único e compartilhado com dev, ver `infra/terraform/bootstrap/`), então nunca autentica em `pull_request` (roda em `refs/pull/N/merge`); revisar `terraform plan` de prod localmente antes de merges que tocam infra é responsabilidade manual até essa restrição ser revisitada. `apply` só roda após merge, no ambiente correspondente.
- Deploy em prod não deve exigir Terraform workspace switch nem lógica condicional complexa — o ambiente é determinado pelo diretório (`environments/dev` vs `environments/prod`), não por uma flag em runtime.
- Imagem Docker é buildada uma vez e promovida (mesma tag/digest) de dev para prod quando possível, evitando rebuild entre ambientes — a validar na Fase 1 conforme a estratégia de branch adotada.

## Git e Claude Code

- Claude Code está autorizado a rodar `git add` e `git commit` automaticamente ao longo do desenvolvimento.
- **Sempre pedir aprovação explícita do usuário antes de qualquer `git push`** — commits locais não pedem aprovação, pushes sim.
- Commits seguem [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`).
- Branches: `feature/<descrição>`, `fix/<descrição>`, `chore/<descrição>`. Lembre-se: qualquer push nessas branches dispara deploy em dev — evitar pushes intermediários "quebrados" quando possível.
- **Nunca fazer deploy (push, merge de PR pra `main`, ou aprovar o gate de prod) sem confirmação explícita do usuário a cada vez** — uma aprovação anterior não vale como aprovação permanente pras próximas, mesmo dentro da mesma sessão. Ao pedir essa confirmação, incluir um resumo breve dos commits envolvidos (título de cada um + 1 linha do que muda), sem alongar.
- PRs abertos via `gh pr create` **não** levam o rodapé "🤖 Generated with Claude Code" no corpo — o PR sobe em nome do usuário (`gh` já autentica com a conta dele). Commits continuam normalmente com o trailer `Co-Authored-By: Claude`.

## Colaboração

- **Perguntar mais, presumir menos**: decisões de produto ambíguas (nome, escopo, comportamento, formato de dado) sempre passam por uma pergunta direta ao usuário antes de implementar — mesmo que pareçam pequenas ou óbvias. Melhor uma pergunta a mais do que implementar a coisa errada e ter que refazer.
- **Sugerir funcionalidades quando fizer sentido**: ao identificar uma lacuna, melhoria ou efeito colateral relacionado ao que está sendo pedido, apontar a sugestão explicitamente na resposta — sem implementar por conta própria, só levantar a ideia pro usuário decidir.

## Guardrails

- Nunca commitar segredos, chaves de service account ou arquivos `.env` reais (ver `.gitignore`).
- Nunca misturar recursos/dados de `dev` e `prod` — dev e prod estão no mesmo projeto GCP, então esse isolamento depende inteiramente de nomes de recurso sufixados por ambiente (Cloud Run, SA de runtime, Firestore database) estarem sempre corretos. Nunca remover um sufixo de ambiente "pra simplificar".
- Nunca usar Terraform workspaces — a separação de ambiente é sempre por diretório.
- Nunca colocar lógica de negócio em `api/` (backend) ou chamadas HTTP direto em componentes de página (frontend).
- Fase 0 (estrutura e documentação) e Fase 1 (bootstrap do Terraform, módulo `infra/terraform/modules/cloud-run/`, root modules de `environments/{dev,prod}`, workflows em `.github/workflows/` e backend skeleton com `GET /health` em `apps/backend/`) concluídas — dev e prod com Cloud Run, Artifact Registry e CI/CD funcionando de ponta a ponta. Ainda não existem: os demais módulos de `infra/terraform/modules/` (artifact-registry standalone já é interno ao módulo cloud-run; faltam bigquery, secret-manager, logging-sink), lógica de domínio em `apps/backend/src/atlas/domains/`, e nenhum código em `apps/frontend/`.

## Registro de acessos e configurações

O produto existe pra ser apontado a projetos GCP de clientes (ver
[ADR-006](docs/adr/ADR-006-cross-project.md), modelo de acesso
cross-project). `docs/onboarding-cliente.md` é o checklist vivo de tudo
que um projeto alvo precisa ter (APIs habilitadas, roles IAM concedidas à
service account de runtime do Hub, audit logs configurados) para aceitar
leitura do Hub — vira a base do documento de implementação entregue a um
cliente real no futuro.

**Toda vez que uma sessão liberar, alterar ou descobrir algum dos itens
abaixo — em qualquer projeto GCP, incluindo o próprio `dp6-ci-polaris`
(o único projeto onde dev e prod rodam) servindo de projeto-alvo do
próprio Atlas —, isso entra na tabela "Registro de acessos concedidos" de
`docs/onboarding-cliente.md` antes de considerar a tarefa concluída:**
- `gcloud services enable` de qualquer API num projeto alvo
- `gcloud projects add-iam-policy-binding` (ou remoção) de qualquer role
  pra uma service account do Hub
- Mudança em `auditConfigs` (Data Access audit logs) de um projeto
- Qualquer nova role passando a ser lida pelo código (ex: um domínio novo
  que passa a exigir uma permissão que nenhum outro pedia)

Isso vale tanto para mudanças aplicadas via Terraform quanto para comandos
`gcloud` rodados manualmente pelo usuário (via `!`) — não assumir que o
comando fornecido foi executado; confirmar com `gcloud ... get-iam-policy`
(ou equivalente) antes de marcar a linha como concedida. Se o checklist de
roles necessárias mudar (ex: um domínio novo passa a precisar de uma role
que a lista atual não cobre), atualizar também a tabela de roles do
próprio `docs/onboarding-cliente.md`, não só o log de concessões.

## Registro de componentes e labels FinOps

Este projeto GCP (`dp6-ci-polaris`) pode vir a hospedar mais de uma
iniciativa do Polaris no mesmo projeto — a topologia single-project não
separa custo por fronteira de projeto (ver "Projetos e ambientes GCP").
`docs/finops-labels.md` define a taxonomia de label obrigatória
(`environment`/`app`/`managed-by`) e `docs/gcp-components.md` é o
registro vivo de qual recurso pertence a qual app/projeto.

**Toda vez que uma sessão criar, renomear ou descobrir um recurso GCP
relacionado ao Hub — via Terraform ou manualmente —, isso entra em
`docs/gcp-components.md` e na aba "Componentes" de `docs/site/` antes de
considerar a tarefa concluída.** Essa obrigação **não** se estende às
outras 3 abas do site (`produto`, `tecnico`, `desenvolvimento`) — elas
dependem de print de tela real ou de curadoria manual do processo, e não
podem ser mantidas sincronizadas sozinhas numa sessão de código.

## Contextos de trabalho

Dependendo do escopo da tarefa, assuma o contexto correspondente abaixo.
Cada contexto define foco, prioridades e checklist antes de considerar uma tarefa concluída.

---

### Contexto: IaC (infra/terraform/)

**Foco:** segurança, idempotência, custo e rastreabilidade.

Antes de criar ou editar qualquer .tf:
- Verificar se existe módulo reutilizável em modules/ antes de duplicar código
- Nunca hardcodar project_id, region ou valores de ambiente — sempre variáveis
- Sempre rodar terraform fmt + terraform validate antes de commitar
- Rodar terraform plan e apresentar o output para aprovação antes de apply
- Confirmar que deletion_protection = true em recursos de prod
- Labels obrigatórias em todo recurso que suporte label: `environment`,
  `app`, `managed-by` — taxonomia completa em `docs/finops-labels.md`,
  nunca inventar valor novo sem checar lá primeiro

Checklist de entrega:
- [ ] terraform validate passou
- [ ] terraform plan revisado e aprovado
- [ ] Nenhum secret ou credencial em .tf ou .tfvars commitados
- [ ] README.md do módulo atualizado se necessário
- [ ] Se o recurso concede acesso a um projeto alvo (IAM binding
      cross-project, API habilitada, audit config) — registrado em
      `docs/onboarding-cliente.md`, ver "Registro de acessos e configurações"
- [ ] Labels completas aplicadas (`environment`/`app`/`managed-by`, ver
      `docs/finops-labels.md`) **e** recurso novo/alterado registrado em
      `docs/gcp-components.md` antes de marcar a tarefa como concluída

---

### Contexto: Backend (apps/backend/)

**Foco:** corretude do domínio, testabilidade e custo de queries BQ.

Antes de implementar qualquer domínio:
- Ler a spec em docs/specs/<domínio>.md — não implementar sem spec aprovada
- Lógica de negócio fica em domains/, nunca em api/
- Clients GCP inicializados em core/, injetados via Depends
- Endpoints que chamam libs GCP síncronas devem ser def, não async def
- Toda query BigQuery deve ter estimativa de custo (dry run) antes de implementar
- Logs estruturados em JSON, nunca print()

Checklist de entrega:
- [ ] Spec do domínio existe e foi seguida
- [ ] Testes unitários em tests/unit/ cobrindo lógica principal
- [ ] Critérios de aceite novos/alterados na spec têm teste referenciando o ID (ver "Contexto: Spec e documentação")
- [ ] pytest passou sem erros
- [ ] Nenhuma chamada GCP em tests/unit/ (usar mocks)
- [ ] ruff check e ruff format sem erros

---

### Contexto: Frontend (apps/frontend/)

**Foco:** fidelidade à identidade visual dp6, densidade de informação estilo Metabase, UX funcional.

Antes de criar qualquer componente:
- Ler `docs/frontend/README.md` e seguir o roteiro de leitura por tipo de tarefa
- Usar só os tokens de `apps/frontend/src/index.css` (documentados em `docs/frontend/design-system.md`) — nenhum hex, px de tipografia ou `rounded-[Npx]` solto
- Reusar os componentes de `apps/frontend/src/components/` (§Catálogo do design-system) e os padrões de `docs/frontend/patterns.md` em vez de recriar
- Componentes de UI via shadcn/ui — nunca escrever CSS do zero para primitivas
- Data fetching exclusivamente via TanStack Query — nunca fetch direto em componentes
- TypeScript strict — sem any

Checklist de entrega: seguir `docs/frontend/CHECKLIST.md`.

---

### Contexto: CI/CD (.github/workflows/)

**Foco:** segurança de secrets, ordem de execução e falha rápida.

Regras obrigatórias:
- Autenticação GCP exclusivamente via WIF — nunca service account keys
- Workflows de deploy de app sempre com needs: apontando para o terraform apply correspondente quando o push tocar infra/ e apps/ juntos
- Secrets referenciados sempre como ${{ secrets.NOME }} — nunca valores literais
- Todo workflow deve ter permissions: explícito (principle of least privilege)
- Usar actions fixadas em SHA ou tag de versão (ex: actions/checkout@v4)

Checklist de entrega:
- [ ] Nenhum secret literal no YAML
- [ ] permissions: definido explicitamente
- [ ] Ordem de jobs garantida com needs: onde necessário
- [ ] Testado com um push real ou via act localmente

---

### Contexto: Spec e documentação (docs/)

**Foco:** clareza, completude e rastreabilidade de decisões.

Ao criar uma spec de domínio (docs/specs/<domínio>.md), incluir obrigatoriamente:
- Objetivo e problema que resolve
- Fonte de dados (qual API/tabela BQ/log)
- Endpoints da API (método, path, parâmetros, response schema)
- Queries BigQuery planejadas com estimativa de custo
- Critérios de aceite numerados (`AC-xxx`) pros comportamentos centrais —
  não precisa ser Dado/Quando/Então rígido, só uma frase clara do
  comportamento esperado, numa tabela apontando o teste que prova
  (`test_nome_da_funcao`). Regra prática de quando isso vale: só pra
  mudança que altera (ou passa a documentar) comportamento de um domínio
  numa spec — ajuste cosmético/de configuração sem lógica nova não
  precisa de AC.
- Seções `## Suposições` (`ASM-xxx`) e `## Perguntas em aberto` (`Q-xxx`),
  cada uma com status (`aberta`/`confirmada`/`invalidada` pra suposição;
  `aberta`/`respondida` pra pergunta). Toda decisão de produto esclarecida
  com o usuário via pergunta direta durante a implementação de algo que
  uma spec já cobre (ou passa a cobrir) fica registrada aqui — não só no
  histórico da conversa, que não sobrevive a um `/clear` nem a uma sessão
  nova lendo a spec meses depois.
- Casos de borda e comportamento esperado
- O que está fora do escopo desta spec
- Se a spec introduz infraestrutura GCP nova (ex.: `storage.md`
  introduzindo buckets) — citar `docs/finops-labels.md` e
  `docs/gcp-components.md` como pré-requisito de implementação na seção
  de "Fonte de dados" ou "O que está fora do escopo", pra garantir que
  labels/registro de componente não fiquem de fora quando o domínio for
  implementado

Ao atualizar o CHANGELOG.md:
- Registrar o que foi feito, erros cometidos e aprendizados
- "Erros cometidos e aprendizados" só recebe entrada amarrada a uma
  falha real que ocorreu durante a implementação (algo quebrou, foi
  corrigido, um teste pegou um caso errado) — não é espaço pra opinião
  solta sobre o que "seria melhor".
- Registrar qualquer mudança de arquitetura com justificativa
- Atualizar o status das fases na tabela de próximas fases

Ao criar um ADR:
- Seguir o padrão: contexto → decisão → alternativas consideradas → consequências
- Nunca apagar um ADR — se a decisão mudar, criar um novo ADR referenciando o anterior

---

## Gestão de contexto de sessão

### Quando atualizar o SESSIONLOG.md
- Quando /status mostrar uso acima de 60% do contexto
- Ao final de cada fase concluída
- Antes de qualquer reset ou /compact de sessão
- Quando o usuário pedir explicitamente

### O que o SESSIONLOG.md deve conter
- Status atual (fase, próximo passo exato)
- Lista de commits desta sessão
- Decisões importantes tomadas e por quê
- Erros encontrados e como foram resolvidos
- Estado atual da infraestrutura (GCP, GitHub Secrets, etc.)
- Como retomar após reset

### Ao iniciar uma nova sessão
1. Ler CLAUDE.md obrigatoriamente (sempre)
2. Verificar se existe SESSIONLOG.md — se sim, ler antes de qualquer ação
3. Confirmar com o usuário o próximo passo antes de executar
4. Nunca assumir o estado do projeto sem ler os dois arquivos

### Comandos úteis de contexto
- `/status` — ver uso atual de contexto e limites da sessão
- `/compact` — comprimir histórico preservando contexto essencial
- `/clear` — resetar sessão completamente (usar SESSIONLOG.md para retomar)
