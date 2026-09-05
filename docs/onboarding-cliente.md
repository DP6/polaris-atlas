# Onboarding de projeto GCP — acesso do Atlas

> **Uso interno.** Este documento acumula o log vivo de concessões (seção
> "Registro de acessos concedidos" no fim) e notas de processo — não deve
> ser enviado a um cliente como está. A versão limpa, pronta pra entrega,
> fica em [`docs/onboarding-cliente-entrega.md`](onboarding-cliente-entrega.md)
> (sem log, sem notas internas, sem referências a arquivos deste repo) —
> mantenha as duas em sincronia quando o checklist de roles/APIs mudar.

**Objetivo:** checklist completo de tudo que precisa ser configurado em um
projeto GCP "alvo" (projeto de cliente, ou qualquer projeto que não seja
o próprio projeto onde o Atlas roda — `dp6-ci-polaris`, hospedando dev
e prod juntos nesta topologia, ver `CLAUDE.md`) para que o Atlas consiga
observá-lo — os oito domínios (catálogo, freshness, profiling/qualidade,
lineage/tabelas órfãs, fingerprinting de PII, mapa de acesso, FinOps e
Cloud Storage, ver `CLAUDE.md`) usam exatamente as roles e APIs listadas
abaixo, sem exceção nem role extra por domínio.

Modelo de acesso: **Modelo A — service account com acesso cross-project**
(ver [ADR-006](adr/ADR-006-cross-project.md)). O Atlas nunca instala nada no
projeto alvo — o administrador do lado do cliente concede acesso de leitura
à service account de runtime do Atlas, uma vez, e o `project_id` é digitado
pelo usuário no frontend a cada sessão.

**Quem executa:** o administrador do projeto alvo (cliente). O time do Atlas
só fornece os comandos prontos — nunca tem credenciais próprias do lado do
cliente.

---

## 1. Habilitar APIs no projeto alvo

```bash
gcloud services enable bigquery.googleapis.com logging.googleapis.com \
  storage.googleapis.com --project={PROJECT_ID}
```

`logging.googleapis.com` é necessário mesmo que o projeto não gere logs
propositalmente — é o transporte usado por lineage e mapa de acesso.
`storage.googleapis.com` só é necessário se o cliente for usar o domínio
`storage` (catálogo/freshness/waste scanner de Cloud Storage e a extensão
de lineage que usa bucket como nó).

---

## 2. IAM — conceder acesso à service account de runtime do Atlas

Qual service account usar depende de qual ambiente do Atlas vai consultar o
projeto:

| Ambiente do Atlas | Service account |
|---|---|
| Produção (uso real com cliente) | `backend-prod-run@dp6-ci-polaris.iam.gserviceaccount.com` |
| Dev (teste interno) | `backend-dev-run@dp6-ci-polaris.iam.gserviceaccount.com` |

Dev e prod rodam no mesmo projeto GCP (`dp6-ci-polaris`, repo real
`polaris-hub-gcp`) — o que diferencia as duas service accounts é o nome,
não o projeto. (Nota: os nomes acima referenciavam o projeto do
piloto/repo de origem, `observability-hub` — corrigido em 2026-08-21 pra
refletir o projeto real deste repositório.)

Roles necessárias — granularidade sempre a nível de **projeto** (nenhum
domínio hoje opera com IAM a nível de dataset ou tabela):

| Role | Por quê | Domínio(s) que usa |
|---|---|---|
| `roles/bigquery.metadataViewer` | Ler `INFORMATION_SCHEMA` (schemas, tabelas, colunas, particionamento) | catalog, freshness, quality, pii, lineage (`discover_regions`) |
| `roles/bigquery.jobUser` | Executar queries — inclusive as de `INFORMATION_SCHEMA`, que rodam como job no BigQuery | catalog, freshness, quality, pii, lineage, finops |
| `roles/bigquery.dataViewer` | Ler dados reais de tabela (amostragem, contagem de nulos/duplicatas, valores distintos, fingerprinting de PII via `TABLESAMPLE`, sugestão de tipo de coluna) | quality (profiling e histórico), pii, finops (column-type suggestions) |
| `roles/logging.viewer` | Chamar a API de Cloud Logging sem 403 — sozinha **não é suficiente** pra ver Data Access audit logs, ver nota abaixo | lineage (tabelas órfãs, upstream/downstream), access (mapa de acesso), finops (budget, scanner de desperdício) |
| `roles/logging.privateLogViewer` | Ver especificamente os **Data Access audit logs** — é onde vive o `jobCompletedEvent` que lineage/access/finops leem; sem essa role a chamada não falha, só retorna sempre vazio | idem |
| `roles/storage.bucketViewer` | Listar/ler metadado de **bucket** (nome, storage class, região, lifecycle rule) — `storage.objectViewer` **não** cobre isso (só objeto), confirmado em dev 2026-08-17, ver `docs/specs/storage.md` seção 8 | storage (catálogo) |
| `roles/storage.objectViewer` | Ler metadado + conteúdo de **objeto** dentro de um bucket já conhecido — nenhuma role nova pra lineage, o audit log de load/extract já vive dentro do `bigquery_resource`/`data_access` já lido pelas duas roles de logging acima | storage (freshness, waste scanner) |
| ~~`roles/browser`~~ | **Não usar** (desde v1.7 da spec catalog, 2026-08-31). O seletor de projeto do frontend passou a listar só os projetos cadastrados em Admin → Projetos (`hub_projects`), não mais os que a SA alcança via Cloud Resource Manager — `core/resourcemanager.py` foi removido. Onde já foi concedida, pode ser revogada; onde ainda não, não conceda | — |

> **Pegadinha confirmada em produção (2026-08-14):** `roles/logging.viewer`
> sozinha deixa a API responder 200 normalmente, mas Data Access audit logs
> (categoria diferente de Admin Activity, que fica sempre visível) só ficam
> visíveis pra quem também tem `roles/logging.privateLogViewer` — sem ela,
> `entries.list` não erra, só nunca retorna nenhuma entrada da categoria
> Data Access. As duas roles são necessárias juntas, não uma ou outra.
> ([doc oficial](https://docs.cloud.google.com/logging/docs/access-control))

> **Org policy do cliente (`iam.allowedPolicyMemberDomains`):** num projeto
> de cliente cuja organização restringe binding de IAM ao próprio domínio,
> o `add-iam-policy-binding` das SAs do Atlas (externas ao cliente) falha com
> `One or more users named in the policy do not belong to a permitted
> customer`. É o mesmo tipo de barreira que já mordeu o próprio repo em
> 2026-08-21 (`iam.allowedPolicyMemberDomains` bloqueando `allUsers` no
> Cloud Run — ver "Registro de acessos concedidos", linha do `roles/iap.admin`).
> Solução do lado do cliente: um admin da **organização** aplica exceção
> da constraint no projeto alvo, ou adiciona o customer ID do Cloud
> Identity da DP6 (projeto `dp6-ci-polaris`, número `209825626529`) à
> allowlist. Documentado no `onboarding-cliente-entrega.md` como aviso
> antes dos comandos da seção 2.

**Cliente real recebe as duas SAs.** A instância `dev` do Atlas é usada pelo
time DP6 pra validar o onboarding antes de liberar o `prod` pro cliente —
conceder o mesmo conjunto de roles às duas SAs de uma vez evita um segundo
round-trip com o admin do cliente. O `onboarding-cliente-entrega.md` já
traz o `for SA_EMAIL in (dev, prod)` pronto.

```bash
SA_EMAIL="backend-prod-run@dp6-ci-polaris.iam.gserviceaccount.com"  # ou backend-dev-run@...

gcloud projects add-iam-policy-binding {PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/bigquery.metadataViewer" --condition=None

gcloud projects add-iam-policy-binding {PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/bigquery.jobUser" --condition=None

gcloud projects add-iam-policy-binding {PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/bigquery.dataViewer" --condition=None

gcloud projects add-iam-policy-binding {PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/logging.viewer" --condition=None

gcloud projects add-iam-policy-binding {PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/logging.privateLogViewer" --condition=None

gcloud projects add-iam-policy-binding {PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/storage.bucketViewer" --condition=None

gcloud projects add-iam-policy-binding {PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/storage.objectViewer" --condition=None
```

Todos os sete comandos são idempotentes — seguro rodar de novo mesmo que
algum já tenha sido aplicado. Se faltar qualquer uma das três primeiras, a
API responde 403 com esses mesmos comandos prontos no corpo do erro
(`ProjectAccessDeniedError`); se faltar `logging.viewer`, o mesmo acontece
só pros endpoints de lineage (`LoggingAccessDeniedError`, que já sugere as
duas roles de logging juntas); se faltar só `logging.privateLogViewer`
(com `logging.viewer` presente), não há erro nenhum — só o aviso de
"nenhum evento encontrado", indistinguível à primeira vista de "sem
atividade real" ou "audit logs desabilitados" (checar as três
possibilidades nessa ordem quando o aviso aparecer sem explicação óbvia);
se faltar `storage.bucketViewer` e/ou `storage.objectViewer`, os endpoints
de `storage` respondem 403 com os comandos prontos (`StorageAccessDeniedError`,
sempre sugere as duas juntas), mesmo padrão das demais — **as duas são
necessárias juntas** (`objectViewer` sozinha não cobre `storage.buckets.*`,
ver seção 8 de `docs/specs/storage.md`).

---

## 3. Data Access audit logs do BigQuery — habilitar

`roles/logging.viewer` sozinho não é suficiente. Lineage, tabelas órfãs,
mapa de acesso e FinOps (budget) dependem de o evento `jobCompletedEvent`
estar sendo escrito nos logs, e isso só acontece se **Data Access audit
logs** do BigQuery estiverem habilitados no projeto — Admin Activity logs
(sempre ativos, não precisam de configuração) não incluem esse evento.

Sem isso, os endpoints de lineage respondem `200 OK` com uma lista vazia e
um aviso — não é um erro, mas o dado fica sempre vazio até habilitar.

**Via console:** IAM & Admin → Audit Logs → localizar "BigQuery API" →
marcar "Data Read" e "Data Write" → Save.

**Via gcloud** (getIamPolicy/setIamPolicy — cuidado para não sobrescrever
outras configurações de audit já existentes no projeto; sempre ler a
política atual primeiro):

```bash
gcloud projects get-iam-policy {PROJECT_ID} --format=json > policy.json
# editar policy.json, adicionar/mesclar o bloco abaixo em "auditConfigs"
```

```json
{
  "auditConfigs": [
    {
      "service": "bigquery.googleapis.com",
      "auditLogConfigs": [
        { "logType": "DATA_READ" },
        { "logType": "DATA_WRITE" }
      ]
    }
  ]
}
```

```bash
gcloud projects set-iam-policy {PROJECT_ID} policy.json
```

`ADMIN_READ` não é necessário para lineage (não captura `jobCompletedEvent`
de query/load), mas não atrapalha se já estiver habilitado por outro
motivo.

---

## 4. O que NÃO é necessário (e o que este processo não faz)

- Nenhum agente, VM ou service account do lado do cliente rodando código —
  o Atlas só lê, via API, a partir de fora do projeto.
- Nenhuma permissão de escrita, alteração ou exclusão — toda role deste
  documento é de leitura, em todos os passos.
- `roles/billing.viewer` / Cloud Billing API — FinOps (budget, scanner de
  desperdício) estima custo a partir de `totalBilledBytes` dos audit logs
  de job (já cobertos pelas roles de `logging.*` acima) + preço público
  on-demand do BigQuery, nunca do Cloud Billing Export real — decisão
  documentada em `docs/specs/finops-budget.md` ("Billing Export só quebra
  custo por projeto+SKU, nunca por dataset/tabela — não resolveria a
  pergunta que a feature responde").
- Secret Manager, Artifact Registry, Cloud Run, Firestore — recursos
  internos do Atlas, vivem só em `dp6-ci-polaris` (ou no par de projetos
  usado pra hospedar aquela instância do Atlas), nunca no projeto alvo.
- Cache pré-computado de audit log de lineage/mapa de acesso/FinOps/
  Storage (job diário D-1 incremental + bucket GCS, ver
  `docs/specs/lineage.md`) — mesmo racional: o bucket, o Cloud Run Job e
  o Cloud Scheduler vivem só no projeto do Atlas. As roles
  `logging.viewer`/`logging.privateLogViewer` desta seção continuam sendo
  as únicas necessárias no projeto alvo; nenhuma concessão nova é exigida
  dele por causa do cache.
- Nada permanente — todo acesso concedido aqui é revogável a qualquer
  momento sem efeito colateral no resto do projeto alvo (seção 5).

---

## Checklist resumido

```
[ ] (cliente cross-org) exceção de iam.allowedPolicyMemberDomains no
    projeto alvo, ou customer ID da DP6 na allowlist — sem isso o
    add-iam-policy-binding das SAs externas falha (ver seção 2)
[ ] bigquery.googleapis.com habilitada no projeto alvo
[ ] logging.googleapis.com habilitada no projeto alvo
[ ] roles/bigquery.metadataViewer concedida à(s) SA(s) do Atlas
[ ] roles/bigquery.jobUser concedida à(s) SA(s) do Atlas
[ ] roles/bigquery.dataViewer concedida à(s) SA(s) do Atlas
[ ] roles/logging.viewer concedida à(s) SA(s) do Atlas
[ ] roles/logging.privateLogViewer concedida à(s) SA(s) do Atlas — sem ela,
    logging.viewer sozinha NÃO mostra Data Access audit logs (falha
    silenciosa, sem erro, só resultado sempre vazio)
[ ] (cliente real) as roles acima concedidas às DUAS SAs (backend-dev-run
    e backend-prod-run) — não só a de prod
[ ] Data Access audit logs (DATA_READ + DATA_WRITE) do BigQuery habilitados
    — só necessário se o cliente for usar lineage/tabelas órfãs/mapa de
    acesso/FinOps (budget)
[ ] storage.googleapis.com habilitada no projeto alvo — só necessário se o
    cliente for usar o domínio storage
[ ] roles/storage.bucketViewer concedida à SA do Atlas — idem, necessária
    pro catálogo listar buckets (storage.objectViewer sozinha NÃO cobre
    metadado de bucket, só de objeto)
[ ] roles/storage.objectViewer concedida à SA do Atlas — idem, necessária
    pro tamanho agregado do catálogo e pra checagem 6.1 do waste scanner
    (metadado e leitura de objeto)
[ ] storage.googleapis.com — Data Access audit log DATA_READ habilitado
    no projeto (config de auditConfigs, não é IAM role — ver exemplo em
    observability-hub-dev) — só necessário pra checagem 6.2 do waste
    scanner do domínio storage (objeto sem leitura recente,
    confidence: "usage_confirmed")
    Atenção: gera um evento de log por leitura de objeto — volume pode
    ser alto em bucket de tráfego intenso. Medir volume esperado antes
    de habilitar em projeto de produção ou projeto-cliente com uso real.
[ ] gcloud projects get-iam-policy confirmado (não só "rodei o comando")
[ ] Testado na UI do Atlas com um usuário já autorizado no ACL interno
[ ] Linha registrada na tabela "Registro de acessos concedidos" abaixo
```

---

## 5. Revogar o acesso

Para encerrar o acesso a qualquer momento, remova as mesmas roles
concedidas na seção 2 — sem efeito colateral no restante do projeto
alvo (a SA do Atlas nunca ganha nenhuma permissão de escrita, então
revogar é só desfazer os `add-iam-policy-binding` de leitura):

```bash
SA_EMAIL="backend-prod-run@dp6-ci-polaris.iam.gserviceaccount.com"  # ou backend-dev-run@...

for ROLE in roles/bigquery.metadataViewer roles/bigquery.jobUser \
            roles/bigquery.dataViewer roles/logging.viewer \
            roles/logging.privateLogViewer roles/storage.bucketViewer \
            roles/storage.objectViewer roles/browser; do
  gcloud projects remove-iam-policy-binding {PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" --role="${ROLE}"
done
```

Os Data Access audit logs (seção 3) não precisam ser desabilitados —
não são específicos da SA do Atlas, e desligá-los pode afetar outras
integrações do projeto alvo que dependam deles.

---

## 6. Validar e registrar

1. **Confirme de verdade** que as roles foram concedidas — não assuma
   que o comando rodou:
   ```bash
   gcloud projects get-iam-policy {PROJECT_ID} \
     --flatten="bindings[].members" \
     --filter="bindings.members:${SA_EMAIL}" \
     --format="table(bindings.role)"
   ```
2. **Teste pela UI do Atlas**: logado como um usuário com acesso liberado
   a esse `project_id` no ACL interno do Atlas (ver
   [`docs/specs/admin.md`](specs/admin.md)), digite (ou selecione, ver
   spec `catalog.md` v1.6) o `project_id` no seletor. Se faltar alguma
   role de IAM, o erro (`ProjectAccessDeniedError`) já vem com os
   comandos de correção prontos no corpo da resposta. Se a IAM estiver
   certa mas o usuário não estiver autorizado no Atlas, o erro é outro
   (`ProjectNotAuthorizedError`) e orienta pedir a um admin do Atlas — não
   rodar `gcloud` de novo.
3. **Registre a concessão** na tabela "Registro de acessos concedidos"
   abaixo — obrigatório por convenção do `CLAUDE.md` ("Registro de
   acessos e configurações"), antes de considerar a tarefa concluída.

---

## Troubleshooting

| Sintoma | Causa provável |
|---|---|
| 403 `ProjectAccessDeniedError` ao digitar/selecionar o projeto no seletor | Falta alguma das 3 primeiras roles de BigQuery (seção 2) — a própria resposta já traz o comando pronto |
| 403 `ProjectNotAuthorizedError` | IAM do GCP está OK, mas o usuário não está liberado no ACL interno do Atlas — pedir a um admin do Atlas, não rodar `gcloud` |
| Lineage/tabelas órfãs/mapa de acesso sempre "sem atividade", mesmo com dados reais | `logging.viewer` presente mas `logging.privateLogViewer` faltando — a API responde 200, mas nunca mostra Data Access audit logs (falha silenciosa) |
| Lineage responde 403 em vez de vazio | Falta `logging.viewer` (erro `LoggingAccessDeniedError`, já sugere as duas roles de logging juntas) |
| Tudo liberado mas ainda "sem atividade" | Confirmar se os Data Access audit logs (seção 3) estão realmente habilitados — checar o campo `auditConfigs` via `get-iam-policy`, não só assumir que a config aplicada anteriormente ainda está lá |
| 403 `StorageAccessDeniedError` no catálogo de buckets (domínio `storage`) | Falta `roles/storage.bucketViewer` e/ou `roles/storage.objectViewer` — a própria resposta traz os dois comandos |
| Waste scanner nunca mostra `confidence: "usage_confirmed"`, só `config_based`, com um aviso na resposta | Data Access audit log `DATA_READ` de `storage.googleapis.com` não habilitado — opcional, não bloqueia o resto do domínio `storage` |
| Projeto não aparece no dropdown do seletor, mas digitar manualmente funciona normalmente | O projeto não está cadastrado em **Admin → Projetos** (`hub_projects`) ou o usuário não tem acesso liberado a ele. Desde v1.7 da spec catalog o dropdown lista só projetos registrados — cadastre o projeto e conceda acesso ao usuário; o campo de texto livre valida qualquer ID enquanto isso |

---

## Registro de acessos concedidos (log vivo)

> **Nota:** o log abaixo foi herdado do repositório de origem
> (`observability-hub`, topologia com dois projetos GCP separados,
> `observability-hub-dev`/`observability-hub-prod`) — documenta o
> histórico de concessões *daquele* par de projetos, não deste
> repositório single-project. Ainda não há nenhuma concessão registrada
> no projeto único deste repositório; a primeira entrada real deve ser
> adicionada na primeira vez que este checklist for seguido aqui (ver
> `CLAUDE.md`, "Registro de acessos e configurações").

Nenhum projeto de cliente real foi onboardado ainda. As únicas concessões
cross-project existentes até agora (no repositório de origem) são entre
os dois ambientes do próprio Atlas (`observability-hub-dev` ↔
`observability-hub-prod`), usadas como projeto "alvo" de teste um do
outro — seguem exatamente este mesmo checklist, e servem de precedente
real de que o processo funciona.

| Data | Projeto alvo | SA concedida | O que foi feito | Confirmado via |
|---|---|---|---|---|
| Sprint 2 (antes de 2026-08-13) | `observability-hub-dev` | `backend-run@...-prod` | `bigquery.metadataViewer` + `jobUser` + `dataViewer` | `gcloud projects get-iam-policy` |
| Sprint 2 (antes de 2026-08-13) | `observability-hub-prod` | `backend-run@...-dev` | `bigquery.metadataViewer` + `jobUser` + `dataViewer` | `gcloud projects get-iam-policy` |
| Antes de 2026-08-14 (sessão não documentada no SESSIONLOG) | `observability-hub-dev` e `observability-hub-prod` | SA própria de cada projeto (self, não cross) | `roles/logging.viewer` concedida | `gcloud projects get-iam-policy` |
| Antes de 2026-08-14 (sessão não documentada no SESSIONLOG) | `observability-hub-dev` e `observability-hub-prod` | — | Data Access audit logs do BigQuery (`DATA_READ`, `DATA_WRITE`, `ADMIN_READ`) habilitados | `gcloud projects get-iam-policy` (campo `auditConfigs`) |
| 2026-08-14 | `observability-hub-prod` | `backend-run@...-dev` | `roles/logging.viewer` (cross) | `gcloud projects get-iam-policy` |
| 2026-08-14 | `observability-hub-dev` | `backend-run@...-prod` | `roles/logging.viewer` (cross) | `gcloud projects get-iam-policy` |
| 2026-08-17 (comando fornecido em 2026-08-14) | `observability-hub-prod` | `backend-run@...-dev` | `roles/logging.privateLogViewer` (cross) | `gcloud projects get-iam-policy` |
| 2026-08-17 (comando fornecido em 2026-08-14) | `observability-hub-dev` | `backend-run@...-prod` | `roles/logging.privateLogViewer` (cross) | `gcloud projects get-iam-policy` |
| 2026-08-17 | `observability-hub-dev` | `backend-run@...-dev` (self) | `roles/storage.objectViewer` (domínio `storage`, ver `docs/specs/storage.md`) | `gcloud projects get-iam-policy` |
| 2026-08-17 | `observability-hub-dev` | `backend-run@...-dev` (self) | `roles/storage.bucketViewer` (faltava pra `objectViewer` sozinha ser suficiente, ver nota da seção 8 de `docs/specs/storage.md`) | `gcloud projects get-iam-policy` |
| 2026-08-18 | `observability-hub-dev` | — | Data Access audit log `DATA_READ` habilitado para `storage.googleapis.com` (via `auditConfigs` do projeto) — domínio `storage`, checagem de objeto sem leitura recente (spec `storage.md` v1.1, seção 6.2) | `gcloud projects get-iam-policy` (campo `auditConfigs`) |
| 2026-08-18 | `observability-hub-prod` | `backend-run@...-prod` (self) | `roles/storage.bucketViewer` + `roles/storage.objectViewer` | `gcloud projects get-iam-policy` |
| 2026-08-18 | `observability-hub-prod` | `backend-run@...-dev` (cross) | `roles/storage.bucketViewer` + `roles/storage.objectViewer` | `gcloud projects get-iam-policy` |
| 2026-08-18 | `observability-hub-dev` | `backend-run@...-prod` (cross) | `roles/storage.bucketViewer` + `roles/storage.objectViewer` | `gcloud projects get-iam-policy` |
| 2026-08-18 | `observability-hub-prod` | — | Data Access audit log `DATA_READ` habilitado para `storage.googleapis.com` (mesma config de dev, aplicada em prod nesta sessão — decisão do usuário, ciente da nota de volume da seção 6.2) | `gcloud projects get-iam-policy` (campo `auditConfigs`) |
| 2026-08-21 | `dp6-ci-polaris` (repo real `polaris-hub-gcp`, projeto single dev+prod) | `group:gcp-ci-polaris@dp6.com.br` | `roles/iap.admin` — TI concedeu ao grupo humano em vez das SAs de deploy, substituindo o pedido anterior de `roles/run.invoker` a `allUsers` (bloqueado pela Org Policy `iam.allowedPolicyMemberDomains`) | `gcloud projects get-iam-policy dp6-ci-polaris` (policy completa colada pelo usuário nesta sessão) — confirmou o grant, mas no principal errado, causando 403 em CI (PR #1, runs 32501467924/32501493798) |
| 2026-08-21 | `dp6-ci-polaris` | `gh-deploy-dev@...` e `gh-deploy-prod@...` | `roles/iap.admin` — fix da linha acima: adicionado a `deployer_roles` em `infra/terraform/bootstrap/modules/wif-bootstrap/main.tf`, aplicado via `terraform apply` no bootstrap (fora do CI, mesmo padrão dos demais papéis das SAs de deploy) | `terraform apply` confirmou criação dos 2 bindings (`...deployer_roles["dev-roles/iap.admin"]`/`["prod-roles/iap.admin"]`) |
| 2026-08-21 | `dp6-ci-polaris` | — | Google Group `gcp-ci-polaris@dp6.com.br` criado pela TI — recebe `roles/iap.httpsResourceAccessor` nos 4 serviços Cloud Run (backend/frontend × dev/prod) via `google_iap_web_cloud_run_service_iam_member`, substitui o antigo `allUsers` como controle de acesso | Não confirmado via `gcloud` — mesma ressalva da linha acima (o binding em si depende da role acima existir na SA de deploy) |
| 2026-08-21 | `dp6-ci-polaris` | — | `roles/run.invoker` concedido manualmente (via `gcloud`, sessão pessoal `matheus.fuzati@dp6.com.br`, **não** pela SA de deploy) ao service agent do IAP (`service-209825626529@gcp-sa-iap.iam.gserviceaccount.com`) — necessário pro IAP nativo do Cloud Run repassar a requisição autenticada ao serviço. **Não gerenciado pelo Terraform** (exige `resourcemanager.projects.setIamPolicy`, que a SA de deploy do CI não tem e não deve ganhar só pra isso — ver comentário em `modules/cloud-run/main.tf`); tratado como passo manual único, mesmo padrão de `infra/terraform/bootstrap`. Replicar em prod não é necessário — grant de projeto único, já cobre os dois ambientes nesta topologia single-project. | `terraform apply` local confirmou criação (`...iap_service_agent_invoker[0]: Creation complete...`) — não reconfirmado depois via `gcloud get-iam-policy` (sessão expirou nesta sessão) |
| 2026-08-21 | `dp6-ci-polaris` | `backend-dev-run@...` e `backend-prod-run@...` (self) | `roles/bigquery.jobUser` — gap do playbook (passo 10 nunca incluiu essa role): sem ela no próprio projeto do Atlas, `core/bigquery.py::get_client()` não consegue criar job de query em nenhum projeto alvo, mesmo com as roles do checklist corretas lá. Descoberto testando `observability-hub-dev` como primeiro projeto alvo real (erro `ProjectAccessDeniedError` mesmo com as 7 roles do checklist confirmadas no alvo) | `gcloud projects get-iam-policy dp6-ci-polaris --flatten='bindings[].members' --filter='bindings.members:backend-dev-run@...'` confirmou a role presente após o `add-iam-policy-binding` |
| 2026-08-21 | `dp6-ci-polaris` | `group:gcp-ci-polaris@dp6.com.br` (self) | `roles/iam.serviceAccountAdmin` — necessária pra gerenciar IAM policy a nível de recurso SA individual (`iam.serviceAccounts.{get,set}IamPolicy`), diferente de `resourcemanager.projectIamAdmin` (que o grupo já tinha, mas não cobre isso). Motivo: preparar o self-binding abaixo pra integração com grupos do Workspace (v1.5 da spec admin) | `gcloud projects get-iam-policy dp6-ci-polaris --flatten='bindings[].members' --filter='bindings.members:gcp-ci-polaris@dp6.com.br AND bindings.role:serviceAccountAdmin'` confirmou a role presente |
| 2026-08-21 | `dp6-ci-polaris` | `backend-dev-run@...` e `backend-prod-run@...` (self, nível de recurso da própria SA — não nível de projeto) | `roles/iam.serviceAccountTokenCreator` concedida por cada SA a si mesma — permite assinar o JWT de domain-wide delegation (`google.auth.iam.Signer`/`signBlob`) sem precisar de chave baixada. Propagação anormalmente lenta (~21min) e `gcloud ... add-iam-policy-binding` seguiu falhando mesmo depois de `get-iam-policy` já funcionar — contornado com `get-iam-policy` + editar JSON + `set-iam-policy` explícito, que funcionou de primeira. Causa exata do `add-iam-policy-binding` falhar mesmo com a leitura já liberada não totalmente esclarecida | `gcloud iam service-accounts get-iam-policy <SA>` confirmou a role presente nas duas SAs |
| 2026-08-21 | `dp6-ci-polaris` | `backend-dev-run@...` e `backend-prod-run@...` (self) | `roles/browser` — visibilidade via Cloud Resource Manager pra este projeto aparecer no seletor de projeto do frontend (`GET /api/v1/projects`, v1.6 da spec catalog). Opcional/não-bloqueante, ver linha da tabela de roles na seção 2 | `gcloud projects get-iam-policy dp6-ci-polaris --flatten='bindings[].members' --filter='bindings.role:roles/browser'` confirmou as duas SAs presentes |
| 2026-08-31 | `dp6-ci-polaris` | `backend-dev-run@...` e `backend-prod-run@...` (self) | **`roles/browser` deixou de ser necessária** — v1.7 da spec catalog: `GET /api/v1/projects` passou a listar só `hub_projects` (não mais via Cloud Resource Manager), `core/resourcemanager.py` foi removido. O binding concedido em 2026-08-21 pode ser revogado (`gcloud projects remove-iam-policy-binding dp6-ci-polaris --member=... --role=roles/browser`); não urgente, não expõe nada. IaC não alterada nesta mudança | Pendente de revogação manual |
| 2026-08-25 | `dp6-ci-polaris` (dev e prod) | — | Conta impersonada via domain-wide delegation (`OBSERVABILITY_HUB_WORKSPACE_IMPERSONATE_EMAIL`, `core/workspace_directory.py`) trocada de `matheus.fuzati@dp6.com.br` para `admin.victoria@dp6.com.br` — teste com uma conta de admin do Workspace, pra validar leitura real de grupos (`hub_groups`, v1.4/v1.5). Não é uma role/API nova, só troca do sujeito da delegação já autorizada (ver linha 2026-08-21 acima, `roles/iam.serviceAccountTokenCreator`) | Alteração via Terraform (`environments/{dev,prod}/main.tf`) — não reconfirmado via chamada real à Directory API nesta sessão |

**Nota:** os dois itens "antes de 2026-08-14" foram descobertos ao vivo
nesta sessão via `gcloud projects get-iam-policy` — o SESSIONLOG.md
registrava esse estado como pendente (backlog itens 8 e 9), mas já tinha
sido resolvido manualmente pelo usuário em algum momento entre sessões sem
atualizar a documentação. Ver SESSIONLOG.md para a correção desses itens.

**Nota 2 (correção):** a primeira versão deste documento, escrita mais
cedo nesta mesma sessão, listava `roles/logging.privateLogViewer` como
"não lida por nenhum código atual, não replicar em onboarding de
cliente" — **isso estava errado**. Só ficou claro depois que o usuário
testou lineage cross-project em produção e recebeu "nenhum evento
encontrado" mesmo com dados reais existindo (confirmado via
`gcloud logging read` direto): `roles/logging.viewer` deixa a API
responder sem erro, mas **não é suficiente** pra ver Data Access audit
logs — só `roles/logging.privateLogViewer` mostra essa categoria
especificamente. As duas roles voltaram a fazer parte do checklist
oficial (seção 2 acima). Erro registrado aqui de propósito, como exemplo
do próprio processo que este documento existe pra evitar.

Roles concedidas às SAs do Atlas que **não fazem parte deste checklist**
(específicas da infraestrutura própria do Atlas, nunca pedidas a um projeto
cliente): `roles/datastore.user`, `roles/secretmanager.secretAccessor`,
`roles/bigquery.jobUser` (cada uma só no próprio projeto, `dev` na SA de
dev e `prod` na SA de prod).

> **Gap descoberto em 2026-08-21:** `roles/bigquery.jobUser` faltava no
> próprio projeto do Atlas (`dp6-ci-polaris`) — só tinha sido concedida no
> projeto **alvo** (parte do checklist acima), mas `core/bigquery.py::
> get_client()` cria `bigquery.Client()` sem projeto explícito, então o
> job de query é criado/cobrado no projeto de casa da SA (`dp6-ci-polaris`),
> não no projeto alvo. Sem essa role lá, toda consulta a qualquer projeto
> alvo falhava com `ProjectAccessDeniedError`, mesmo com as roles do
> checklist corretas no projeto alvo. Corrigido manualmente via `gcloud`;
> `docs/playbooks/hospedar-hub-em-novo-projeto.md` (passo 10) atualizado
> pra incluir essa role desde o primeiro hosting.

---

## Como manter este documento atualizado

Ver CLAUDE.md, seção "Registro de acessos e configurações" — toda vez que
um acesso, role, API ou audit config for concedido/alterado em qualquer
projeto (cliente real ou os próprios `dev`/`prod` do Atlas servindo de
projeto-alvo um do outro), a linha correspondente entra na tabela acima
antes de considerar a tarefa concluída.

---

## Referências

- [ADR-006 — Modelo de acesso cross-project](adr/ADR-006-cross-project.md)
- [ADR-009 — ACL de usuário × projeto](adr/ADR-009-acl-usuario-projeto.md)
- [`docs/specs/admin.md`](specs/admin.md) — como liberar um usuário do
  Atlas para um `project_id` já autorizado a nível de infraestrutura por
  este documento
- [`docs/playbooks/hospedar-hub-em-novo-projeto.md`](playbooks/hospedar-hub-em-novo-projeto.md)
  — playbook complementar, sobre onde o Atlas *em si* roda (este documento
  é sobre os projetos que o Atlas *observa*)
