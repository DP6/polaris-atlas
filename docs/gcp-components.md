# Registro de componentes GCP — recurso → app/projeto

> **Formato pensado pra ser reaproveitado.** Este documento não é só um
> inventário pontual de `dp6-ci-polaris` — é o modelo de registro vivo que
> qualquer projeto que hospede o Hub (ver
> `docs/playbooks/hospedar-hub-em-novo-projeto.md`) deve manter, no mesmo
> espírito de `docs/onboarding-cliente.md`. Ao clonar o Hub pra outro
> projeto GCP, copie a estrutura de seções e o schema de colunas abaixo,
> só troca o conteúdo da tabela.

**Objetivo:** responder "esse recurso GCP pertence a qual app/projeto?" —
o inverso do que o Console/Billing já respondem bem ("o que esse
app/projeto tem?"). Fica crítico no momento em que mais de uma app do
Polaris divide o mesmo projeto GCP (ver `docs/finops-labels.md`).

**Quando atualizar:** toda vez que uma sessão (humana ou do Claude Code)
criar, renomear ou descobrir um recurso GCP relacionado ao Hub — mesma
disciplina que já existe pra `docs/onboarding-cliente.md` (ver
`CLAUDE.md`, "Registro de acessos e configurações"). Não é opcional
mesmo pra recurso criado manualmente/fora do Terraform — esses são os que
mais fica fácil esquecer de registrar.

**Schema de colunas:**

| Coluna | Significado |
|---|---|
| Recurso | Nome/identificador real no GCP |
| Tipo | Tipo de recurso (Cloud Run service, SA, bucket, etc.) |
| App | Valor da label `app` (ver `docs/finops-labels.md`) — ou `n/a` se o tipo de recurso não suporta label |
| Ambiente | `dev` / `prod` / `-` (recurso não é sufixado por ambiente) |
| Gerenciado por | `terraform` (caminho: qual `.tf`) ou `manual` (como foi feito) |
| Observações | Contexto que não cabe nas outras colunas |

---

## Inventário — `dp6-ci-polaris`

App hoje: **`observability-hub`** (único app neste projeto até o
momento — ver `docs/finops-labels.md` sobre o valor da label `app`).

**Status da label `app`/`environment`/`managed-by`:** ✅ aplicada de
fato via `default_labels` em 2026-08-26 (confirmado via `terraform
plan`/apply real) em: Cloud Run — serviços, Cloud Run — Job de cache,
Cloud Storage (buckets), Artifact Registry. **Não suportam
`default_labels` neste provider** (não apareceram no `plan`, ficam sem
label): service accounts, Firestore — marcado em cada tabela abaixo.
Secrets do Secret Manager e recursos de bootstrap/CI continuam
pendentes (comando manual documentado em `docs/finops-labels.md`).

### Cloud Run — serviços

| Recurso | Tipo | App | Ambiente | Gerenciado por | Observações |
|---|---|---|---|---|---|
| `backend-dev` | Cloud Run service | observability-hub | dev | terraform (`environments/dev/main.tf`, módulo `modules/cloud-run`) | API FastAPI |
| `backend-prod` | Cloud Run service | observability-hub | prod | terraform (`environments/prod/main.tf`) | `deletion_protection = true` |
| `frontend-dev` | Cloud Run service | observability-hub | dev | terraform (`environments/dev/main.tf`) | React/Vite build estático servido via container |
| `frontend-prod` | Cloud Run service | observability-hub | prod | terraform (`environments/prod/main.tf`) | `deletion_protection = true` |

### Cloud Run — service accounts de runtime

⚠️ Service accounts não suportam `default_labels` neste provider
(confirmado via `terraform plan` em 2026-08-26) — ficam sem label
`app`/`environment`/`managed-by`, mesmo com a taxonomia já aplicada em
todo o resto.

| Recurso | Tipo | App | Ambiente | Gerenciado por | Observações |
|---|---|---|---|---|---|
| `backend-dev-run@dp6-ci-polaris.iam.gserviceaccount.com` | Service Account | observability-hub | dev | terraform (`modules/cloud-run/main.tf`) | Também usada pelo Cloud Run Job de refresh de cache (mesma SA, não uma nova) |
| `backend-prod-run@dp6-ci-polaris.iam.gserviceaccount.com` | Service Account | observability-hub | prod | terraform | Autorizada pra domain-wide delegation (Workspace) — ver seção "Manual" |
| `frontend-dev-run@dp6-ci-polaris.iam.gserviceaccount.com` | Service Account | observability-hub | dev | terraform | |
| `frontend-prod-run@dp6-ci-polaris.iam.gserviceaccount.com` | Service Account | observability-hub | prod | terraform | |

### Cloud Run — Job de cache + Cloud Scheduler

| Recurso | Tipo | App | Ambiente | Gerenciado por | Observações |
|---|---|---|---|---|---|
| `backend-dev-refresh-cache` | Cloud Run Job | observability-hub | dev | terraform (`modules/cloud-run-job/main.tf`) | Roda 1x/dia (D-1), popula cache de lineage/acesso |
| `backend-prod-refresh-cache` | Cloud Run Job | observability-hub | prod | terraform | |
| `backend-dev-refresh-cache-scheduler` | Cloud Scheduler job | observability-hub | dev | terraform | Cron `0 3 * * *` UTC |
| `backend-prod-refresh-cache-scheduler` | Cloud Scheduler job | observability-hub | prod | terraform | |
| `backend-dev-cache-sched@dp6-ci-polaris.iam.gserviceaccount.com` | Service Account | observability-hub | dev | terraform | Só invoca o Job (`roles/run.invoker` local ao Job) — nome curto de propósito, limite de 30 chars do `account_id` |
| `backend-prod-cache-sched@dp6-ci-polaris.iam.gserviceaccount.com` | Service Account | observability-hub | prod | terraform | |

### Firestore

⚠️ Também não suporta `default_labels` neste provider (não apareceu no
`terraform plan`) — sem label por enquanto.

| Recurso | Tipo | App | Ambiente | Gerenciado por | Observações |
|---|---|---|---|---|---|
| `hub-dev` | Firestore named database | observability-hub | dev | terraform (`environments/dev/main.tf`) | `hub_users`, `hub_groups`, `hub_projects`, `access_requests` |
| `hub-prod` | Firestore named database | observability-hub | prod | terraform | |

### Cloud Storage

| Recurso | Tipo | App | Ambiente | Gerenciado por | Observações |
|---|---|---|---|---|---|
| `dp6-ci-polaris-hub-cache-dev` | Bucket | observability-hub | dev | terraform (`environments/dev/main.tf`) | Cache de eventos de audit log (lineage/acesso) — payload grande, workaround do limite de 1MiB do Firestore |
| `dp6-ci-polaris-hub-cache-prod` | Bucket | observability-hub | prod | terraform | |
| `dp6-ci-polaris-tfstate` | Bucket | n/a (plataforma/CI, não é do app) | - | terraform (`bootstrap/modules/wif-bootstrap/main.tf`) | State do Terraform, compartilhado dev+prod via `prefix` |

### Artifact Registry

| Recurso | Tipo | App | Ambiente | Gerenciado por | Observações |
|---|---|---|---|---|---|
| `apps` | Artifact Registry repo | observability-hub | - (compartilhado dev+prod) | terraform (`modules/cloud-run/main.tf`, gerenciado pela instância `backend_cloud_run` de dev) | Imagens dos 4 serviços — se outro app do Polaris entrar neste projeto, decidir se ganha repo próprio (ver nota abaixo) |

### Secret Manager (manual, fora do Terraform)

| Recurso | Tipo | App | Ambiente | Gerenciado por | Observações |
|---|---|---|---|---|---|
| `GOOGLE_OAUTH_CLIENT_ID_DEV` / `_PROD` | Secret | observability-hub | dev/prod | manual | Sem label hoje — candidato a `gcloud secrets update --update-labels` quando a taxonomia for aplicada |
| `GOOGLE_OAUTH_CLIENT_SECRET_DEV` / `_PROD` | Secret | observability-hub | dev/prod | manual | |
| `JWT_SECRET_DEV` / `_PROD` | Secret | observability-hub | dev/prod | manual | Crítico manter sufixado — ver `CLAUDE.md` |
| `OAUTH_ALLOWLIST` | Secret | observability-hub | - (compartilhado, intencional) | manual | Controla só quem loga, não isolamento de sessão — por isso sem sufixo |

### Bootstrap / CI (WIF, deploy)

| Recurso | Tipo | App | Ambiente | Gerenciado por | Observações |
|---|---|---|---|---|---|
| `github-actions-pool` | Workload Identity Pool | n/a (plataforma/CI) | - | terraform (`bootstrap/modules/wif-bootstrap/main.tf`) | Único, compartilhado |
| `github-provider-dev` | WIF Provider | n/a | dev | terraform | Sem restrição de branch |
| `github-provider-prod` | WIF Provider | n/a | prod | terraform | Restrição `refs/heads/main` no `attribute_condition` — ver ADR-010 |
| `gh-deploy-dev@dp6-ci-polaris.iam.gserviceaccount.com` | Service Account | n/a | dev | terraform | SA de deploy do CI, impersonada via WIF |
| `gh-deploy-prod@dp6-ci-polaris.iam.gserviceaccount.com` | Service Account | n/a | prod | terraform | Só impersonável a partir de `main` |

> **Nota em aberto:** hoje as SAs/pool de deploy não carregam label `app`
> porque servem só a um app (observability-hub). Se um segundo app do
> Polaris passar a fazer deploy neste mesmo projeto, decidir se cada app
> ganha seu próprio par de SAs de deploy (`gh-deploy-<app>-{dev,prod}`) ou
> se o pool/SAs continuam compartilhados — não decidido ainda, revisitar
> quando isso deixar de ser hipotético.

### Manual, fora do Terraform (bindings e configuração externa)

| Recurso | Tipo | App | Ambiente | Gerenciado por | Observações |
|---|---|---|---|---|---|
| Domínio customizado `observability-hub-dev.dp6.io` | Mapeamento de domínio (Cloud Run) | observability-hub | dev | manual | Aponta pro `frontend-dev`; mecanismo exato de mapeamento não documentado ainda — levantar na próxima sessão que mexer nisso |
| Domínio customizado `observability-hub.dp6.io` | Mapeamento de domínio (Cloud Run) | observability-hub | prod | manual | Aponta pro `frontend-prod`; usado como redirect_uri canônico do OAuth |
| `roles/run.invoker` ao service agent do IAP | IAM binding, nível de projeto | observability-hub | - | manual | Ver comentário em `modules/cloud-run/main.tf` — exige permissão maior que a SA de deploy do CI tem |
| Domain-wide delegation (`backend-{dev,prod}-run` impersonando `admin.victoria@dp6.com.br`) | Autorização no Google Workspace Admin Console | observability-hub | dev/prod | manual | **Vinculada ao Client ID interno da SA, não ao e-mail** — se a SA de runtime for recriada, esta autorização fica órfã e precisa ser refeita manualmente (ver `docs/onboarding-cliente.md`, 2026-08-25) |

---

## Fora de escopo deste documento

- Recursos dentro de projetos-alvo observados pelo Hub (ex.: IAM
  concedido no lado do cliente) — isso é `docs/onboarding-cliente.md`,
  não este documento (este é só sobre o que roda o Hub em si).
- Aplicação de fato da label `app`/`environment`/`managed-by` — ver
  `docs/finops-labels.md`.
