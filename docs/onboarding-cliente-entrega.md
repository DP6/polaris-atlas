# Onboarding de projeto GCP — acesso do Observability Hub

**Objetivo:** checklist completo de tudo que precisa ser configurado no seu
projeto GCP para que o Observability Hub consiga observá-lo. O Hub cobre
oito frentes — catálogo, freshness, profiling/qualidade, lineage/tabelas
órfãs, fingerprinting de PII, mapa de acesso, FinOps e Cloud Storage — e
usa exatamente as roles e APIs listadas abaixo, sem exceção nem role extra.

**Modelo de acesso:** o Hub roda fora do seu projeto GCP e nunca instala
nada nele — você (administrador do projeto) concede acesso de **somente
leitura** à service account de runtime do Hub, uma única vez. O
`project_id` do seu projeto é digitado por quem for usar o Hub a cada
sessão, sem nenhuma credencial armazenada do seu lado.

**Quem executa:** o administrador do projeto GCP a ser observado. Nosso
time só fornece os comandos prontos abaixo — nunca temos credenciais
próprias do seu lado.

---

## 1. Habilitar APIs no projeto

```bash
gcloud services enable bigquery.googleapis.com logging.googleapis.com \
  storage.googleapis.com --project={PROJECT_ID}
```

`logging.googleapis.com` é necessário mesmo que o projeto não gere logs
propositalmente — é o transporte usado pelas funcionalidades de lineage e
mapa de acesso. `storage.googleapis.com` só é necessário se for usar a
funcionalidade de Cloud Storage (catálogo de buckets e scanner de
desperdício).

---

## 2. IAM — conceder acesso à service account do Hub

Service account de runtime do Hub que vai consultar o seu projeto (nosso
time informa o e-mail exato a usar, conforme o ambiente combinado com
você):

| Role | Por quê |
|---|---|
| `roles/bigquery.metadataViewer` | Ler `INFORMATION_SCHEMA` (schemas, tabelas, colunas, particionamento) |
| `roles/bigquery.jobUser` | Executar queries — inclusive as de `INFORMATION_SCHEMA`, que rodam como job no BigQuery |
| `roles/bigquery.dataViewer` | Ler dados reais de tabela (amostragem, contagem de nulos/duplicatas, valores distintos, fingerprinting de PII, sugestão de tipo de coluna) |
| `roles/logging.viewer` | Chamar a API de Cloud Logging sem erro de permissão — sozinha **não é suficiente** pra ver Data Access audit logs, ver nota abaixo |
| `roles/logging.privateLogViewer` | Ver especificamente os **Data Access audit logs** — sem essa role a chamada não falha, só retorna sempre vazio |
| `roles/storage.bucketViewer` | Listar/ler metadado de **bucket** (nome, storage class, região, lifecycle rule) — `storage.objectViewer` **não** cobre isso (só objeto) |
| `roles/storage.objectViewer` | Ler metadado + conteúdo de **objeto** dentro de um bucket já conhecido |
| `roles/browser` | **Opcional** (não bloqueia nenhuma funcionalidade) — só visibilidade via Cloud Resource Manager, pra este projeto aparecer sozinho no seletor de projeto do Hub em vez de precisar digitar o `project_id` de cabeça. Sem ela, o projeto continua 100% funcional — só não aparece na lista |

> **Atenção:** `roles/logging.viewer` sozinha deixa a API responder
> normalmente, mas Data Access audit logs (categoria diferente de Admin
> Activity, que fica sempre visível) só ficam visíveis pra quem também tem
> `roles/logging.privateLogViewer` — sem ela, a consulta não erra, só
> nunca retorna nenhuma entrada dessa categoria. As duas roles são
> necessárias juntas, não uma ou outra.

```bash
SA_EMAIL="{SA_EMAIL_INFORMADA_PELO_TIME_DP6}"

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

# Opcional — só pro projeto aparecer no seletor de projeto do Hub,
# ver linha "roles/browser" na tabela acima
gcloud projects add-iam-policy-binding {PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/browser" --condition=None
```

Todos os oito comandos são idempotentes — seguro rodar de novo mesmo que
algum já tenha sido aplicado. Se faltar qualquer uma das três primeiras de
BigQuery, o Hub responde com um erro que já traz esses mesmos comandos
prontos; se faltar `logging.viewer`, o mesmo acontece só pras
funcionalidades de lineage e mapa de acesso; se faltar só
`logging.privateLogViewer` (com `logging.viewer` presente), não há erro
nenhum — só o aviso de "nenhum evento encontrado" (ver Troubleshooting);
se faltar `storage.bucketViewer` e/ou `storage.objectViewer`, a
funcionalidade de Cloud Storage responde com erro e os comandos prontos —
**as duas são necessárias juntas**.

---

## 3. Data Access audit logs do BigQuery — habilitar

`roles/logging.viewer` sozinho não é suficiente. As funcionalidades de
lineage e tabelas órfãs dependem de um evento específico estar sendo
escrito nos logs, e isso só acontece se **Data Access audit logs** do
BigQuery estiverem habilitados no projeto — Admin Activity logs (sempre
ativos, não precisam de configuração) não incluem esse evento.

Sem isso, essas funcionalidades respondem normalmente, só que sempre com
lista vazia — não é um erro, mas o dado fica vazio até habilitar.

**Via console:** IAM & Admin → Audit Logs → localizar "BigQuery API" →
marcar "Data Read" e "Data Write" → Save.

**Via gcloud** (cuidado para não sobrescrever outras configurações de
audit já existentes no projeto; sempre leia a política atual primeiro):

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

Caso queira também habilitar a funcionalidade equivalente pra Cloud
Storage (checagem de objetos sem leitura recente no scanner de
desperdício), o mesmo bloco de `auditConfigs` se aplica ao serviço
`storage.googleapis.com`, com `logType: DATA_READ`. **Atenção:** isso gera
um evento de log por leitura de objeto — meça o volume esperado antes de
habilitar em um bucket de tráfego intenso.

---

## 4. O que NÃO é necessário (e o que este processo não faz)

- Nenhum agente, VM ou service account do seu lado rodando código — o Hub
  só lê, via API, a partir de fora do seu projeto.
- Nenhuma permissão de escrita, alteração ou exclusão — toda role deste
  documento é de leitura, em todos os passos.
- `roles/billing.viewer` / Cloud Billing API não são necessárias — a
  estimativa de custo (FinOps) usa os bytes processados nos audit logs de
  job já cobertos pelas roles de `logging.*` acima, combinados com o
  preço público on-demand do BigQuery.
- Nenhum recurso interno do Hub (banco de dados, filas, segredos) vive no
  seu projeto — tudo isso roda na infraestrutura própria do Hub.
- Nada permanente — todo acesso concedido aqui é revogável a qualquer
  momento sem efeito colateral no resto do seu projeto (seção 5).

---

## Checklist resumido

```
[ ] bigquery.googleapis.com habilitada no projeto
[ ] logging.googleapis.com habilitada no projeto
[ ] roles/bigquery.metadataViewer concedida à service account do Hub
[ ] roles/bigquery.jobUser concedida à service account do Hub
[ ] roles/bigquery.dataViewer concedida à service account do Hub
[ ] roles/logging.viewer concedida à service account do Hub
[ ] roles/logging.privateLogViewer concedida à service account do Hub —
    sem ela, logging.viewer sozinha NÃO mostra Data Access audit logs
    (falha silenciosa, sem erro, só resultado sempre vazio)
[ ] Data Access audit logs (DATA_READ + DATA_WRITE) do BigQuery
    habilitados — só necessário pras funcionalidades de lineage/tabelas
    órfãs/mapa de acesso
[ ] storage.googleapis.com habilitada no projeto — só necessário se for
    usar a funcionalidade de Cloud Storage
[ ] roles/storage.bucketViewer concedida à service account do Hub — idem,
    necessária pro catálogo listar buckets
[ ] roles/storage.objectViewer concedida à service account do Hub — idem,
    necessária pro tamanho agregado do catálogo e pelo scanner de
    desperdício
[ ] storage.googleapis.com — Data Access audit log DATA_READ habilitado
    no projeto — opcional, refina a precisão do scanner de desperdício de
    Cloud Storage (ver seção 3)
[ ] roles/browser concedida à service account do Hub — opcional, só pro
    projeto aparecer no seletor de projeto do Hub (não bloqueia nada)
[ ] gcloud projects get-iam-policy confirmado (não só "rodei o comando")
[ ] Testado no Hub com um usuário já autorizado pelo seu contato DP6
```

---

## 5. Revogar o acesso

Para encerrar o acesso a qualquer momento, remova as mesmas roles
concedidas na seção 2 — sem efeito colateral no restante do seu projeto (a
service account do Hub nunca ganha nenhuma permissão de escrita, então
revogar é só desfazer os `add-iam-policy-binding` de leitura):

```bash
SA_EMAIL="{SA_EMAIL_INFORMADA_PELO_TIME_DP6}"

for ROLE in roles/bigquery.metadataViewer roles/bigquery.jobUser \
            roles/bigquery.dataViewer roles/logging.viewer \
            roles/logging.privateLogViewer roles/storage.bucketViewer \
            roles/storage.objectViewer roles/browser; do
  gcloud projects remove-iam-policy-binding {PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" --role="${ROLE}"
done
```

Os Data Access audit logs (seção 3) não precisam ser desabilitados — não
são específicos da service account do Hub, e desligá-los pode afetar
outras integrações do seu projeto que dependam deles.

---

## 6. Validar

1. **Confirme de verdade** que as roles foram concedidas — não assuma que
   o comando rodou:
   ```bash
   gcloud projects get-iam-policy {PROJECT_ID} \
     --flatten="bindings[].members" \
     --filter="bindings.members:${SA_EMAIL}" \
     --format="table(bindings.role)"
   ```
2. **Avise seu contato DP6** de que o acesso foi concedido, pra testarmos
   pelo Hub. Se faltar alguma role de IAM, o erro já vem com os comandos
   de correção prontos.

---

## Troubleshooting

| Sintoma | Causa provável |
|---|---|
| Erro de permissão ao selecionar o projeto no Hub | Falta alguma das 3 primeiras roles de BigQuery (seção 2) — a própria resposta já traz o comando pronto |
| Lineage/tabelas órfãs/mapa de acesso sempre "sem atividade", mesmo com dados reais | `logging.viewer` presente mas `logging.privateLogViewer` faltando — a API responde normalmente, mas nunca mostra Data Access audit logs (falha silenciosa) |
| Lineage responde com erro de permissão em vez de vazio | Falta `logging.viewer` |
| Tudo liberado mas ainda "sem atividade" | Confirme se os Data Access audit logs (seção 3) estão realmente habilitados — o campo pode ter sido sobrescrito por outra alteração de política depois |
| Erro de permissão no catálogo de buckets (Cloud Storage) | Falta `roles/storage.bucketViewer` e/ou `roles/storage.objectViewer` — a própria resposta traz os dois comandos |
| Scanner de desperdício de Cloud Storage nunca confirma uso real, só estimativa por configuração | Data Access audit log `DATA_READ` de `storage.googleapis.com` não habilitado — opcional, não bloqueia o resto da funcionalidade |
| Projeto não aparece no seletor, mas digitar manualmente funciona normalmente | Falta `roles/browser` (role opcional) — comportamento esperado, não é erro |

---

## Suporte

Em caso de dúvida durante a configuração, entre em contato com o time
responsável pelo Observability Hub na DP6.
