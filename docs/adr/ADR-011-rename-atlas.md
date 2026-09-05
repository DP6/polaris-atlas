# ADR-011 — Rename do produto para Atlas

**Status:** Aceito
**Data:** 2026-09-04

---

## Contexto

O produto nasceu com o nome "Observability Hub" — genérico, descritivo
da categoria, sem identidade própria. O usuário decidiu adotar um nome
mais distintivo: **Atlas**, remetendo ao mapa/catálogo do território de
dados da empresa (datasets, lineage, acessos, custo), coerente com os
domínios que o produto cobre hoje (catálogo, lineage, PII, mapa de
acesso, qualidade, freshness, FinOps, Cloud Storage, metadados de
governança).

Levantamento prévio confirmou um ponto importante: **o project_id GCP
real já é `dp6-ci-polaris`**, não `observability-hub` — esse nome era
resquício do projeto piloto/repo de origem (ver correção registrada em
`docs/onboarding-cliente.md`, 2026-08-21, e o próprio
[ADR-010](ADR-010-single-project-topology.md), que já documentava essa
mesma deriva de nomenclatura entre o piloto e este repositório). Ou
seja, o rename para Atlas é majoritariamente cosmético — nome do
pacote Python, prefixo de env var, título/UI, label FinOps — e **não**
envolve criar um projeto GCP novo nem migrar dados.

## Decisão

Renomear o produto de "Observability Hub" para **Atlas** em todo o
código e documentação viva deste repositório:

- Pacote Python: `apps/backend/src/observability_hub/` →
  `apps/backend/src/atlas/`; `pyproject.toml` (`name`, `description`,
  `packages`); `Dockerfile` (entrypoint `uvicorn atlas.main:app`).
- Prefixo de env var: `OBSERVABILITY_HUB_*` → `ATLAS_*`
  (`core/config.py::env_prefix`, sincronizado com as env vars do
  Terraform em `environments/{dev,prod}/main.tf` e com os literais de
  `core/run_client.py` que constroem overrides de env do Cloud Run Job).
- Label FinOps `app`: `observability-hub` → `atlas`
  (`environments/{dev,prod}/versions.tf`, `default_labels`) — requer
  novo `terraform apply` em dev e prod pra refletir nos recursos já
  criados (ver `docs/finops-labels.md`).
- Frontend: `package.json`, título da aba, tela de login, chaves de
  `localStorage` (`observability-hub:*` → `atlas:*` — reseta
  tema/sidebar/último projeto salvos dos usuários atuais, efeito
  colateral aceito).
- Documentação viva: `CLAUDE.md`, `docs/gcp-components.md`,
  `docs/finops-labels.md`, `docs/onboarding-cliente.md` (partes que
  descrevem o presente, não o log histórico), `docs/specs/*.md`,
  `docs/playbooks/`, `docs/site/*` (GH Pages).
- Repositório GitHub: `polaris-hub-gcp` → `atlas` (ação manual,
  separada — inclui atualizar `github_repository` no bootstrap WIF,
  `terraform apply` manual, e o remote local).

## Fora do escopo desta decisão (deferido)

- **Domínio customizado + OAuth redirect_uri**
  (`observability-hub[-dev].dp6.io`) — o de prod é o redirect_uri
  canônico do Google OAuth Client, configurado manualmente fora do
  Terraform. Migrar exige novo domain mapping no Cloud Run + atualizar
  Authorized redirect URIs, com janela de transição — registrado como
  pendência em `docs/gcp-components.md`, não feito nesta mudança.
- **Firestore named databases** (`hub-dev`/`hub-prod`) e **buckets de
  cache** (`dp6-ci-polaris-hub-cache-{dev,prod}`) — nomes de recurso já
  em produção; renomear exigiria criar recurso novo e migrar dado,
  fora do escopo de um rename de nome de produto.
- **Registro histórico** (`CHANGELOG.md`, `SESSIONLOG.md`, ADRs
  existentes, payloads de audit log reais em `docs/specs/storage.md` e
  notas de validação datadas em outras specs) — mantido como estava,
  documentando o nome em uso no momento de cada evento.

## Alternativas consideradas

Outras direções de nome foram levantadas (técnicas: DataScope, Meridian;
metafóricas: Sentinel, Watchtower, Farol; abstratas: Lumen, Vantage;
combinações `data-`/`hub-` + conceito: data-compass, data-clarity). O
usuário optou por Atlas por já haver, em paralelo, documentação
descrevendo esta mesma ferramenta sob esse nome no Docusaurus do
`polaris-heap` (`docs/engenharia-de-dados/ferramentas/atlas.md`) — reforço
de que o nome já estava sendo adotado organicamente antes desta decisão
formal.

## Consequências

- Toda referência nova ao produto em código/docs usa "Atlas", nunca mais
  "Observability Hub".
- `terraform apply` pendente em dev e prod para propagar a label `app`
  nos recursos já criados.
- Rename do repositório GitHub é uma ação separada, que exige
  confirmação explícita antes de ser executada (afeta CI/WIF).
- Migração de domínio customizado/OAuth fica como trabalho futuro,
  documentada mas não realizada.
