module "backend_cloud_run" {
  source = "../../modules/cloud-run"

  project_id = var.project_id
  region     = var.region
  # Sufixado por ambiente: dev e prod rodam no mesmo projeto GCP (topologia
  # single-project deste repositório), então "backend" sozinho colidiria
  # com o serviço Cloud Run de dev (e com a SA de runtime, derivada do
  # mesmo nome — ver modules/cloud-run/main.tf).
  service_name = "backend-prod"
  image        = var.backend_image

  # O repositório Artifact Registry "apps" já é gerenciado pelo
  # backend_cloud_run de dev, neste mesmo projeto — só uma instância do
  # módulo pode ser dona, as outras três (frontend-dev, backend-prod,
  # frontend-prod) reaproveitam via manage_artifact_registry = false.
  manage_artifact_registry = false

  # Override do default do módulo (300s/512Mi): lineage/acesso/órfãs
  # dependem de um fallback síncrono em cache miss (scan completo de
  # audit log via Cloud Logging, ver docs/specs/lineage.md) que pode
  # estourar o timeout/memória default do Cloud Run — causa raiz
  # original do "Failed to fetch" nessas telas.
  timeout_seconds = 600
  memory          = "1Gi"

  # Ambiente de prod: protege o serviço contra destroy acidental.
  deletion_protection = true
  # Backend não fica atrás do IAP: o frontend chama via fetch() cross-site,
  # e o cookie de sessão do IAP não sobrevive isso (ver comentário em
  # modules/cloud-run/main.tf). Protegido só pelo próprio OAuth+JWT.
  iap_enabled          = false
  invoker_iam_disabled = true

  # Libera CORS pro domínio customizado (primeiro da lista de propósito —
  # core/domains/auth/service.py::build_redirect_uri usa a primeira https://
  # da lista como redirect_uri do OAuth, então o domínio customizado vira o
  # canônico pós-login) + as duas URLs *.run.app válidas do frontend em prod
  # (canônica + legada por número do projeto, mantidas por segurança durante
  # a transição).
  env = {
    ATLAS_CORS_ORIGINS = "https://observability-hub.dp6.io,${module.frontend_cloud_run.service_url},${module.frontend_cloud_run.service_url_alt}"
    # Único sinal de ambiente do backend (core/config.py::settings.environment)
    # — nunca mais inferido do project_id, que é o mesmo pros dois ambientes
    # nesta topologia.
    ATLAS_ENVIRONMENT = "prod"
    # Conta do Workspace impersonada via domain-wide delegation pra ler
    # grupos reais (core/workspace_directory.py, domains/admin v1.5) —
    # indicada pela TI ao autorizar a delegação, ver
    # docs/onboarding-cliente.md (2026-08-25).
    ATLAS_WORKSPACE_IMPERSONATE_EMAIL = "admin.victoria@dp6.com.br"
    # Usados só pelo gatilho manual de admin (domains/admin::
    # trigger_event_cache_refresh, ver core/run_client.py) pra endereçar o
    # Cloud Run Job de refresh do cache — e pelo cache em si
    # (core/event_cache.py) pra saber onde gravar/ler o payload de eventos.
    ATLAS_REGION                  = var.region
    ATLAS_EVENT_CACHE_BUCKET_NAME = google_storage_bucket.event_cache.name
  }
}

module "frontend_cloud_run" {
  source = "../../modules/cloud-run"

  project_id   = var.project_id
  region       = var.region
  service_name = "frontend-prod"
  image        = var.frontend_image

  # Frontend estático (serve -s dist) não tem endpoint /health — a raiz
  # responde 200 e serve pros probes de startup/liveness.
  health_check_path = "/"

  # Reaproveita o repositório Artifact Registry criado pelo backend_cloud_run
  # de dev, neste mesmo projeto (ver comentário acima).
  manage_artifact_registry = false

  # Ambiente de prod: protege o serviço contra destroy acidental.
  deletion_protection = true
  iap_enabled         = true
  iap_access_members  = var.iap_access_members
}

# Firestore named database do ambiente prod — dev e prod estão no mesmo
# projeto GCP, então não dá pra usar o banco "(default)" implícito pros
# dois (misturaria dados). Precisa existir antes do primeiro deploy do
# backend (core/firestore.py::get_firestore_client usa database="hub-prod").
# Nome prefixado com "hub-" pro mesmo padrão do ambiente dev (lá é
# obrigatório — database_id exige 4+ caracteres — aqui é só consistência).
resource "google_firestore_database" "hub" {
  project     = var.project_id
  name        = "hub-prod"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  # Ambiente de prod: protege contra destroy acidental do banco inteiro.
  delete_protection_state = "DELETE_PROTECTION_ENABLED"
  deletion_policy         = "ABANDON"
}

# Bucket dedicado ao cache de audit log de lineage/access
# (core/event_cache.py) — ver comentário equivalente em
# environments/dev/main.tf. Dado 100% recomputável (o job de refresh
# regrava do zero todo dia) — sem necessidade de deletion_protection,
# mas force_destroy=false por padrão de prod (nada aqui depende de
# destroy rápido/sem fricção como em dev).
resource "google_storage_bucket" "event_cache" {
  name                        = "${var.project_id}-hub-cache-prod"
  project                     = var.project_id
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  lifecycle_rule {
    condition {
      age = 2
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = "prod"
    managed-by  = "terraform"
  }
}

# Bucket não concede acesso a nenhuma SA por padrão — a SA de runtime do
# backend (mesma usada pelo Service e pelo Job, ver módulo cloud-run-job)
# precisa desse binding explícito pra ler/escrever o cache
# (core/event_cache.py). Faltou na v2.3 original: causou 403 Forbidden
# não tratado (só NotFound era capturado) em toda leitura/escrita de
# cache, um "Failed to fetch" novo e mais rápido que o original.
resource "google_storage_bucket_iam_member" "event_cache_runtime_access" {
  bucket = google_storage_bucket.event_cache.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.backend_cloud_run.runtime_service_account_email}"
}

# Job periódico (1x/dia, D-1) que popula o cache acima — ver
# infra/terraform/modules/cloud-run-job e
# apps/backend/src/atlas/jobs/refresh_event_cache.py.
module "backend_event_cache_job" {
  source = "../../modules/cloud-run-job"

  project_id  = var.project_id
  region      = var.region
  environment = "prod"
  job_name    = "backend-prod-refresh-cache"
  image       = var.backend_image
  command     = ["python", "-m", "atlas.jobs.refresh_event_cache"]

  service_account               = module.backend_cloud_run.runtime_service_account_email
  backend_service_account_email = module.backend_cloud_run.runtime_service_account_email
  scheduler_service_account_id  = "backend-prod-cache-sched"

  env = {
    ATLAS_ENVIRONMENT             = "prod"
    ATLAS_REGION                  = var.region
    ATLAS_EVENT_CACHE_BUCKET_NAME = google_storage_bucket.event_cache.name
    ATLAS_RUNTIME_SA_EMAIL        = module.backend_cloud_run.runtime_service_account_email
  }
}
