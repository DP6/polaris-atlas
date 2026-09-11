# ADR-012 — Fluxo `branch → develop → main` com PR automática e duplo gate

**Status:** Aceito
**Data:** 2026-09-11

---

## Contexto

Até aqui o `polaris-atlas` era trunk-based sem branch intermediária: um push
em qualquer branch (exceto `main`) disparava build + deploy em dev **direto,
sem PR, sem review, sem gate nenhum** (`backend-deploy-dev.yml`/
`frontend-deploy-dev.yml`/`terraform-apply-dev.yml`, trigger
`push: branches-ignore: [main]`). PRs iam direto pra `main`, que não tinha
nenhuma branch protection configurada. O único gate manual existente era o
GitHub Environment `production` (required reviewers) nos jobs de deploy de
app — nunca no `terraform apply`, decisão já registrada na ADR-008.

Esse desenho deixava dev sem nenhum controle: qualquer commit, revisado ou
não, ia parar em produção-de-teste sozinho, e não existia trilha de PR
nenhuma antes de `main`. O pedido era formalizar duas etapas de promoção —
`branch → develop → main` — cada uma com PR obrigatória e um gate de
aprovação manual antes do deploy de fato acontecer.

## Decisão

Introduzir a branch `develop` como estágio intermediário. Fluxo final:

1. Push em qualquer branch → `auto-pr-develop.yml` abre automaticamente uma
   PR pra `develop` (idempotente — não duplica se já existe uma aberta).
2. Merge da PR (branch protegida — só entra via PR) → dispara
   `backend-deploy-dev.yml`/`frontend-deploy-dev.yml` (agora com
   `environment: dev`, novo) e `terraform-apply-dev.yml` (sem gate,
   inalterado). O deploy de app fica "Waiting" até aprovação manual.
3. Deploy(s) de dev concluindo com sucesso → `promote-develop-to-main.yml`
   espera (mesmo padrão de polling do `wait-for-terraform` já usado no
   repo) e abre automaticamente a PR `develop → main`.
4. Merge dessa PR (branch `main`, agora também protegida) → dispara
   `backend-deploy-prod.yml`/`frontend-deploy-prod.yml` (`environment:
   production`, gate que já existia) e `terraform-apply-prod.yml` (sem
   gate, inalterado, ADR-008).

Decisões específicas dentro desse desenho:

- **Sem `required_approving_review_count` em `develop`/`main`.** O GitHub
  não permite o autor de uma PR aprovar a própria PR — e o repo é de
  contribuidor único hoje. Exigir uma contagem de aprovação formal
  travaria todo merge permanentemente (ou exigiria bypass de admin toda
  vez, o que anula o controle). A branch protection exige PR (bloqueia
  push direto); o merge em si é o ato de aprovação. O bloqueio real é o
  gate de Environment, que aceita self-review (`prevent_self_review:
  false`, já é assim no `production` de hoje).
- **`terraform-apply-dev`/`terraform-apply-prod` continuam sem Environment
  gate.** Mesma lógica da ADR-008: a mudança de infra já passa por
  `terraform plan` revisado dentro da PR, e agora também pela própria PR
  obrigatória — gatear de novo seria redundante. Só o deploy de app (sobe
  imagem nova, sem revisão automatizada nenhuma) ganha o gate.
- **`auto-pr-develop.yml`/`promote-develop-to-main.yml` usam o
  `GITHUB_TOKEN` padrão, sem PAT dedicado.** Consequência aceita: uma PR
  aberta com `GITHUB_TOKEN` não dispara `pull_request` no evento
  `opened` (restrição do GitHub pra evitar loop de automação) — então
  `terraform-plan.yml` não roda automaticamente nessas PRs a menos que
  alguém empurre um commit novo na branch antes do merge. Mesmo princípio
  já aceito pra prod na ADR-008 (revisão de plan pode ser manual).
- **`promote-develop-to-main.yml` dispara em `push: branches: [develop]`
  com um job de espera (polling via `gh run list --commit`), não em
  `workflow_run`.** Reaproveita o padrão já existente no repo
  (`wait-for-terraform`) em vez de introduzir um mecanismo novo que
  depende de casar o campo `name:` de cada workflow.
- **Branch default do repo passa de `main` pra `develop`.** Faz o dropdown
  de "New Pull Request" da UI do GitHub já vir com `develop` (evita PR
  manual acidental indo direto pra `main`) e faz PRs do Dependabot
  mirarem `develop`, entrando no mesmo fluxo de revisão.
- **`deployment_branch_policy` das Environments `dev`/`production`
  restrito a `develop`/`main` respectivamente** (branches protegidas) —
  hoje `production` aceitava deploy de qualquer branch no nível do
  Environment; só o `attribute_condition` do WIF de prod impedia na
  prática. Fecha essa lacuna redundante.

## Alternativas consideradas

**Exigir aprovação formal de PR (contagem ≥ 1) e adicionar um segundo
revisor.** Resolveria o problema do self-review "de verdade", mas exige
decidir agora quem é esse segundo revisor e dar acesso de escrita — fora de
escopo desta mudança. Fica registrado como evolução natural se o time
crescer: nesse caso, ligar `required_approving_review_count: 1` em
`develop`/`main` é a única mudança de config necessária, o resto do desenho
não muda.

**PAT dedicado pras automações de auto-PR**, pra garantir que
`terraform-plan.yml` dispare em toda PR aberta automaticamente. Mais robusto,
mas adiciona um secret extra pra gerenciar/rotacionar. Rejeitado por ora —
aceitar a lacuna (mesmo princípio da ADR-008) é suficiente enquanto o volume
de PRs de infra for baixo.

**Gatear também `terraform-apply-dev`/`terraform-apply-prod` com Environment
reviewers**, uniformizando com o deploy de app. Rejeitado: redundante com a
revisão que já acontece via `terraform plan` no PR + a própria PR agora ser
obrigatória; adicionaria fricção sem ganho de segurança correspondente.

**`workflow_run` em vez do padrão `push` + polling** pra disparar
`promote-develop-to-main.yml` só depois dos deploys de dev. Tecnicamente
mais direto (reage a eventos de conclusão em vez de fazer polling), mas
exige casar o `promote-develop-to-main.yml` com o campo `name:` exato de
cada um dos três workflows de dev — mais um ponto de acoplamento frágil (um
rename de `name:` quebra o gatilho silenciosamente). O padrão de polling já
está provado em produção neste repo (`wait-for-terraform`, usado 3 vezes).

## Consequências

- Nenhum push isolado chega mais em dev sem passar por uma PR + merge —
  fecha o gap que existia desde o início do projeto.
- Dois pontos de espera manual novos (merge da PR em `develop`, gate de
  `dev`) se somam aos dois que já existiam (merge da PR em `main`, gate de
  `production`) — quatro confirmações humanas no caminho de uma mudança até
  prod, todas cobertas pela regra de "nunca fazer deploy/aprovar gate sem
  confirmação explícita" já existente em `CLAUDE.md`, agora estendida.
- `terraform-plan.yml` não é garantido rodar antes do merge em PRs abertas
  automaticamente sem commit adicional — risco aceito, mesmo padrão da
  ADR-008.
- Imagem Docker continua sendo buildada separadamente em cada etapa (não há
  promoção do mesmo digest de dev pra prod) — o commit squash-mergeado em
  `main` tem SHA diferente do testado em `develop`, então "o que roda em
  prod" não é bit-a-bit "o que foi testado em dev", só o mesmo código-fonte.
  Já era uma lacuna conhecida antes desta mudança (`CLAUDE.md` já registrava
  isso como pendência); não resolvida aqui — fica como possível ADR futura
  se "promoção de artefato idêntico" virar requisito real.
- Se o time crescer, a mudança pra exigir aprovação formal de PR é
  incremental (ver alternativa acima), não exige redesenhar o fluxo.
