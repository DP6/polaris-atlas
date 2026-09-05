# Labels de FinOps — taxonomia e consulta de custo

**Objetivo:** este projeto GCP (`dp6-ci-polaris`, ver `CLAUDE.md`) roda
dev e prod do Atlas hoje, e pode vir a hospedar outras
iniciativas do Polaris no mesmo projeto amanhã — a topologia
single-project não separa custo por fronteira de projeto (ver
`CLAUDE.md`, "Projetos e ambientes GCP"). Sem label, o custo de uma app
não se distingue do de outra na mesma fatura. Este documento define a
taxonomia de label obrigatória em todo recurso GCP do Atlas e como usá-la
depois pra consultar/filtrar custo.

Não confundir com convenção de **nome** de recurso — isso é outro assunto
(nomenclatura de recurso, código curto etc.), fora do escopo deste
documento por decisão explícita (avaliado como baixo custo-benefício
frente ao risco de renomear recurso já em produção).

---

## 1. Labels vs. Tags (não é a mesma coisa no GCP)

| | **Labels** | **Tags** (Resource Manager) |
|---|---|---|
| Pra que serve | Metadado `key:value`, aparece no Billing/Cost Table | Controle de acesso condicional (IAM Conditions) e Org Policy |
| Cobertura de recursos | Quase universal (Cloud Run, Storage, BigQuery, Secret Manager, SA...) | Só recursos/níveis específicos (projeto, pasta, alguns recursos) |
| Usado pra filtrar custo | Sim — mecanismo padrão e testado | Não confiar sem checar a doc atual do Billing antes de desenhar em cima disso |

**Pra FinOps, o mecanismo é `labels`.** Tags resolve outro problema
(IAM/governança), não "quanto cada coisa custou".

## 2. Taxonomia

| Chave | Valores válidos | Obrigatório em |
|---|---|---|
| `environment` | `dev` \| `prod` | Todo recurso que suporte label |
| `app` | `atlas` (nome do produto, ver rename registrado no `CHANGELOG.md`) | Todo recurso do Atlas |
| `managed-by` | `terraform` \| `manual` | Todo recurso |

Não usar nenhuma outra chave sem atualizar esta tabela primeiro — em
particular, **não** introduzir `team`/`cost-center`: só o time de CI/dev
do Polaris consome esses dados hoje (ver decisão registrada nesta
conversa), `app` já basta pra saber de quem é cada linha de custo. Se
isso mudar (ex.: financeiro/gestão da DP6 passar a consultar), esta
tabela precisa ganhar uma linha nova antes de qualquer label novo ser
aplicado.

Restrições de sintaxe do GCP (label, não nome de recurso): só minúsculas,
números, `-` e `_`; sem `:`; chave e valor até 63 caracteres cada.

## 3. Como aplicar

**Recursos gerenciados por Terraform** — usar `default_labels` no bloco
do provider, uma vez por ambiente, em vez de repetir em todo
`resource {}`:

```hcl
# infra/terraform/environments/{dev,prod}/versions.tf
provider "google" {
  project = var.project_id
  region  = var.region
  default_labels = {
    environment = "dev"  # ou "prod", conforme o ambiente
    app         = "atlas"
    managed-by  = "terraform"
  }
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
  default_labels = {
    environment = "dev"
    app         = "atlas"
    managed-by  = "terraform"
  }
}
```

Duas ressalvas importantes:
- **Os dois providers** (`google` e `google-beta`) precisam do mesmo
  bloco — o Cloud Run service roda no provider beta
  (`provider = google-beta` em `modules/cloud-run/main.tf`, por causa de
  `iap_enabled`), então só declarar `default_labels` no provider `google`
  deixaria os serviços Cloud Run de fora.
- `default_labels` cobre todo recurso Terraform que suporte label
  automaticamente — não precisa (e não deve) declarar `labels = {...}`
  de novo dentro de cada `resource`, exceto se um recurso específico
  precisar de uma label a mais além das 3 padrão.

**Recursos criados fora do Terraform** (hoje: secrets no Secret Manager,
qualquer binding/config manual documentado em `docs/onboarding-cliente.md`)
— `default_labels` não alcança. Aplicar manualmente:

```bash
gcloud secrets update NOME_DO_SECRET \
  --update-labels=environment=prod,app=atlas,managed-by=manual
```

**Status:** ✅ aplicado via `default_labels` em dev e prod em 2026-08-26
(dev confirmado via CI: `Apply complete! Resources: 0 added, 5 changed,
0 destroyed.`; prod aplica no merge do PR correspondente). Valor de `app`
atualizado de `observability-hub` para `atlas` no rename do produto —
requer novo `terraform apply` em dev e prod pra refletir nos recursos já
criados (ver `CHANGELOG.md`). Cobre os 4
serviços Cloud Run, os 2 Cloud Run Jobs, os 2 buckets de cache e o
Artifact Registry — confirmado no `terraform plan` real. **Service
accounts e Firestore não suportam `default_labels` neste provider**
(não apareceram no plan) — ficam sem label até existir outro mecanismo;
ver `docs/gcp-components.md` pra status por recurso. Secrets no Secret
Manager continuam pendentes (comando manual acima, ainda não executado).

## 4. Billing Export pro BigQuery (passo manual, fora do que a SA do Atlas alcança)

Sem isso, a única forma de investigar custo é o Console (Billing Report)
ou um resumo do Gemini Cloud Assist — como foi feito na investigação do
`cpu_idle` (ver `CHANGELOG.md`). Com o export habilitado, dá pra rodar
SQL contra o detalhe de custo, dia a dia, SKU a SKU, com a coluna de
labels junto.

**Quem faz:** alguém com papel de billing account admin/user na conta de
billing vinculada a `dp6-ci-polaris` — não é uma permissão que a service
account de runtime do Atlas tem ou deveria ter.

**Status:** 🔴 bloqueado, aguardando TI (desde 2026-08-26). Billing
account vinculada identificada: **DP6 Self Billing (Voucher)**,
`008012-F93445-DFD798`. `matheus.fuzati@dp6.com.br` não tem nenhuma role
nela hoje (dropdown de "Billing export" vazio, página `/export` retorna
erro genérico de carregamento — consistente com 403 mascarado, não
confirmado como problema de rede). Pedido feito à TI: `roles/billing.admin`
nessa billing account. Atualizar esta linha quando a role for concedida
e/ou o export for de fato habilitado.

**Passos (Console):**
1. [Cloud Billing Console](https://console.cloud.google.com/billing) →
   selecionar a billing account do projeto.
2. **Billing export** → aba **BigQuery export** → **Edit settings**.
3. Habilitar **Standard usage cost data export** (obrigatório) e,
   se quiser granularidade de preço público por SKU, também **Pricing
   data export**.
4. Escolher (ou criar) um dataset BigQuery de destino — recomendado um
   dataset dedicado no próprio `dp6-ci-polaris` (ex.: `billing_export`),
   já que a SA do Atlas tem acesso de BigQuery nesse projeto.
5. Aguardar até 24h pela primeira exportação — export é incremental daí
   em diante (não retroage antes da data de ativação).

## 5. Como consultar/filtrar depois

Três formas, por ordem de sofisticação:

**a) Console → Billing → Reports** — filtro por label na própria UI,
sem SQL, funciona assim que o label existir no recurso (leva 24-48h pra
refletir na fatura). Bom pra checagem rápida.

**b) BigQuery, uma vez o export existir** — a via de verdade pra FinOps
recorrente/dashboard:

```sql
SELECT
  service.description AS servico,
  SUM(cost) AS custo_total,
  currency
FROM `dp6-ci-polaris.billing_export.gcp_billing_export_v1_XXXXXX`
WHERE DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND EXISTS (
    SELECT 1 FROM UNNEST(labels) AS l
    WHERE l.key = 'app' AND l.value = 'atlas'
  )
  AND EXISTS (
    SELECT 1 FROM UNNEST(labels) AS l
    WHERE l.key = 'environment' AND l.value = 'prod'
  )
GROUP BY servico, currency
ORDER BY custo_total DESC;
```

`service.description` já vem nativo no export (`"Cloud Run"`,
`"BigQuery"`, `"Cloud Storage"`, etc.) — não precisa de label nenhuma pra
separar por serviço, só pra separar **quem dentro daquele serviço**
gerou o custo (a linha `EXISTS ... labels` acima).

**c) `gcloud asset search-all-resources`** — não serve pra custo, serve
pra auditoria de cobertura (quais recursos ainda não têm label aplicada):

```bash
gcloud asset search-all-resources \
  --project=dp6-ci-polaris \
  --query="-labels.app:*" \
  --asset-types="run.googleapis.com/Service,storage.googleapis.com/Bucket,firestore.googleapis.com/Database,iam.googleapis.com/ServiceAccount"
```

## Fora de escopo deste documento

- Convenção de **nome** de recurso (ver decisão de não renomear
  componentes existentes; nomenclatura pra recursos novos fica pendente).
- Aplicação de fato da taxonomia nos recursos já existentes hoje —
  execução futura, à parte.
- Habilitação de fato do Billing Export — ação manual do usuário, só
  documentada aqui.

Ver também [`docs/gcp-components.md`](gcp-components.md) — registro de
qual recurso pertence a qual app/projeto, usando a mesma taxonomia
`app`/`environment` definida aqui.
