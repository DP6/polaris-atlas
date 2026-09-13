# ADR-013 — Histórico além de 30 dias em lineage/access/finops/storage

**Status:** Aceito
**Data:** 2026-09-12

---

## Contexto

`lineage`, `access`, `finops` (scan events) e o waste scanner de storage
(seção 6.2, "objeto nunca lido") reconstroem tudo a partir de leitura ao
vivo do Cloud Logging do projeto-cliente: `jobservice.jobcompleted` (Data
Access audit logs, formato legado `AuditData`) para os três primeiros,
`storage.objects.get` (Data Access audit logs do GCS) para o waste
scanner. O job diário (`jobs/refresh_event_cache.py`) e as constantes de
cada domínio (`LOOKBACK_DAYS=30` em lineage/access/finops,
`_JOB_WINDOW_DAYS=31`, `storage.LOOKBACK_DAYS=90`) já documentam a causa
raiz nos próprios comentários: o teto real não é o cache do atlas, é a
**retenção padrão de 30 dias do bucket `_Default` do Cloud Logging de
cada projeto-cliente** — um recurso que vive dentro do projeto observado,
não do Hub, e que o atlas nunca escreve, só lê. Passado esse prazo, o log
já foi apagado pelo próprio Cloud Logging — não é cache-miss, é ausência
física do dado na fonte, e não é retroativo: aumentar a retenção hoje não
recupera o que já expirou antes da mudança.

Isso aparece na prática assim: ao integrar um projeto com anos de
histórico, telas que anunciam janela de 90 dias (storage) ou mês
corrente (finops budget) na verdade só enxergam ~30 dias reais — porque
não existe "mais atrás" pra ler no Cloud Logging, não importa quando o
onboarding aconteceu. Confirmado com o usuário que **não há acesso pra
alterar essa retenção do lado do cliente** — qualquer solução precisa
funcionar só com o acesso de leitura que o atlas já tem hoje, ou com um
acréscimo de IAM padrão pedido uma única vez no próprio onboarding, nunca
uma mudança de configuração pedida ao cliente depois do fato.

Importante: isso **não piora com o tempo de uso do atlas**. Uma vez que
um projeto está sob monitoramento, o cache incremental
(`core/event_cache.py`) e os agregados próprios do atlas (ex.: série
diária de custo do finops-budget, retenção de 24 meses no Firestore)
acumulam corretamente dia a dia e não perdem profundidade. O problema é
especificamente **a foto do dia 0**: o instante em que um projeto já
existente entra pro atlas só enxerga os últimos ~30 dias de audit log
que ainda não expiraram, e depois disso não tem mais como voltar atrás
por essa via.

## Decisão

Atacar o problema em dois eixos independentes, sem depender de nenhuma
mudança de configuração do lado do cliente:

**Eixo 1 — maximizar a fotografia do dia 0 (resgate de histórico
pré-onboarding).** Usar `INFORMATION_SCHEMA.JOBS_BY_PROJECT` do BigQuery
como fonte complementar ao Cloud Logging pros três domínios que leem
`jobservice.jobcompleted` (lineage, access, finops scan-events). Essa
visão tem **retenção nativa de 180 dias, fixada pelo Google**,
totalmente independente da configuração de Cloud Logging do projeto —
6x mais histórico que os ~30 dias reais de hoje, disponível desde o
primeiro dia de onboarding, exigindo só uma role de leitura padrão de
BigQuery (equivalente a `roles/bigquery.resourceViewer` + listar jobs de
terceiros) pedida na mesma etapa de onboarding que já concede as roles
de hoje — nunca uma concessão avulsa posterior. O schema já expõe
`referenced_tables`/`destination_table` como structs, mapeando quase 1:1
no `JobEvent` existente em `domains/lineage/repository.py`: o trabalho é
escrever um parser novo, não redesenhar o modelo de evento. Usado só no
full scan inicial de cada projeto, mesclado com o que vier do Cloud
Logging via o mesmo `event_cache.merge_dedup` (chave `job_id`) já usado
no merge incremental.

180 dias é o teto absoluto desse eixo — não é parâmetro, não muda com
plano/tier do BigQuery. Sem o cliente já ter um sink próprio de audit log
rodando há mais tempo, não existe como resgatar histórico pré-onboarding
além disso.

**Eixo 2 — parar de esquecer o que já foi capturado.** O cache
incremental já lê só o delta novo por dia e faz merge com o que guardou
antes; o motivo dele hoje esquecer tudo que passou de 31 dias (domínios
de job) é só a linha de evicção explícita em
`jobs/refresh_event_cache.py::_refresh_job_caches`
(`kept = [e for e in merged if e.timestamp >= cutoff]`). Alargando esse
`cutoff` (proposta: 730 dias, alinhado aos 24 meses já usados pelo
agregado de finops-budget) ou removendo a evicção, o cache do atlas passa
a **acumular indefinidamente a partir do dia em que o projeto foi
integrado** — sem depender de Cloud Logging nem de `INFORMATION_SCHEMA`
pra nada além do delta diário. Controle 100% nosso, custo de storage
baixo (a avaliar: shardar o blob por mês/ano se o tamanho crescer demais
num projeto de alto volume).

Combinação final: um projeto integrado há 8 meses fica com ~8 meses
completos de lineage/access/finops (eixo 2 já superou o teto de 180d do
eixo 1 nesse ponto); um projeto integrado hoje começa com até 180 dias de
fotografia inicial em vez de ~30. Os anos anteriores ao onboarding
continuam irrecuperáveis em qualquer um dos dois eixos — isso é
comunicado explicitamente nas telas afetadas e no site (ver "Comunicação
da limitação" abaixo), não escondido atrás de uma janela que promete mais
do que entrega.

**Sem alternativa equivalente pro waste scanner de storage (6.2).** A
detecção de "objeto nunca lido" depende de `storage.objects.get` via Data
Access audit log do GCS — não existe um `INFORMATION_SCHEMA` equivalente
pra "quem leu este objeto e quando" (não é metadado de job, é acesso a
objeto). Sem fonte alternativa que não dependa de configuração do
cliente, o teto real permanece ~30 dias — a decisão aqui é parar de
anunciar 90 dias que na prática não chegam lá (`storage.LOOKBACK_DAYS`
revisado pra refletir o teto real) e comunicar isso como limitação
conhecida, não como bug.

**Comunicação da limitação.** As duas condições (teto de 180d pro resgate
pré-onboarding; acúmulo próprio sem teto daí em diante; o caso à parte de
storage, ~30d reais, sem alternativa) passam a aparecer diretamente nas
telas dos domínios afetados (`LineagePage`/`OrphansPage`,
`AccessTab`, `BudgetPage`/`FinOpsOverviewPage`/`PartitionCandidatesPage`,
`WastePage`) via o padrão `WarningCallout` já usado hoje, e como seção
resumo em `docs/site/produto/index.html` (visão de produto) e
`docs/site/tecnico/index.html` (detalhe técnico, linkando pra este ADR).

## Alternativas consideradas

**Pedir ao cliente pra aumentar a retenção do `_Default` log bucket
(30d → ex. 400d) via `gcloud logging buckets update` ou Terraform
(`google_logging_project_bucket_config`).** Resolveria o problema de
forma mais direta e sem teto de 180 dias — mas exige acesso de escrita
na configuração de Logging do projeto do cliente, que não temos e não
vamos ter. Rejeitada por não ser executável no modelo de acesso atual;
registrada aqui como o que faria mais sentido se algum dia um cliente
específico topar fazer essa mudança do lado dele.

**Criar um Log Sink dedicado (não editar o `_Default`, só adicionar um
sink novo) exportando os logs relevantes pra um destino nosso (BigQuery/
GCS no projeto do Hub) a partir de agora.** Daria retenção
verdadeiramente indefinida a partir da criação do sink, sem depender do
teto de 180 dias do `INFORMATION_SCHEMA`. Mas criar um sink também exige
uma role de escrita em Logging no projeto do cliente
(`roles/logging.admin`/`configWriter`) — mesma categoria de pedido que
já não temos hoje. Não descartada de vez: registrar como evolução natural
do Eixo 1 se algum dia o modelo de acesso permitir uma role adicional
(ainda assim menos invasiva que pedir pra mudar a retenção do
`_Default`, já que é aditivo em vez de alterar config existente).

**Deixar o waste scanner de storage também usar 180 dias "de mentira"
(mesmo sem fonte que sustente isso).** Rejeitada — geraria a mesma
frustração que motivou esta ADR, só que maior (promete 180d, entrega 30d
igual antes). Preferível ser explícito sobre o teto real.

## Consequências

- Lineage, access e finops passam a ter até 180 dias de fotografia
  inicial em qualquer projeto novo, e crescimento indefinido dali em
  diante — sem exigir nenhuma ação do cliente além de uma role de IAM a
  mais no onboarding padrão.
- Histórico anterior ao onboarding além de 180 dias continua
  irrecuperável — comunicado explicitamente nas telas e no site, não é
  mais tratado como "detalhe de rodapé" de um aviso de cache vazio.
- Waste scanner de storage (6.2) mantém teto real de ~30 dias
  indefinidamente — única exceção sem solução neste ADR; registrada como
  limitação conhecida, não como pendência a resolver.
- Tamanho do cache (blob no GCS) cresce com o alargamento do `cutoff` de
  evicção — acompanhar em produção; shard por mês/ano é a válvula de
  escape se necessário, não implementado nesta fase.
- `INFORMATION_SCHEMA.JOBS_BY_PROJECT` é uma query de BigQuery (não é
  grátis como `entries.list` do Cloud Logging, ainda que seja metadado) —
  rodada só uma vez por projeto no full scan inicial, não no delta
  diário, pra manter o custo previsível.
