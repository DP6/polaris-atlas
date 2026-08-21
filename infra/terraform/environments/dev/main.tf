module "backend_cloud_run" {
  source = "../../modules/cloud-run"

  project_id = var.project_id
  region     = var.region
  # Sufixado por ambiente: dev e prod rodam no mesmo projeto GCP (topologia
  # single-project deste repositório), então "backend" sozinho colidiria
  # com o serviço Cloud Run de prod (e com a SA de runtime, derivada do
  # mesmo nome — ver modules/cloud-run/main.tf).
  service_name = "backend-dev"
  image        = var.backend_image

  # Ambiente de dev: sem proteção contra destroy, permite scale-to-zero.
  deletion_protection = false
  # Backend não fica atrás do IAP: o frontend chama via fetch() cross-site,
  # e o cookie de sessão do IAP não sobrevive isso (ver comentário em
  # modules/cloud-run/main.tf). Protegido só pelo próprio OAuth+JWT.
  iap_enabled          = false
  invoker_iam_disabled = true

  # Libera CORS pro domínio customizado (primeiro da lista de propósito —
  # core/domains/auth/service.py::build_redirect_uri usa a primeira https://
  # da lista como redirect_uri do OAuth, então o domínio customizado vira o
  # canônico pós-login) + as duas URLs *.run.app (canônica + legada por
  # número do projeto, ver environments/prod/main.tf, mantidas por segurança
  # durante a transição) + o Vite dev server local.
  env = {
    OBSERVABILITY_HUB_CORS_ORIGINS = "https://observability-hub-dev.dp6.io,${module.frontend_cloud_run.service_url},${module.frontend_cloud_run.service_url_alt},http://localhost:5173"
    # Único sinal de ambiente do backend (core/config.py::settings.environment)
    # — nunca mais inferido do project_id, que é o mesmo pros dois ambientes
    # nesta topologia.
    OBSERVABILITY_HUB_ENVIRONMENT = "dev"
    # Conta do Workspace impersonada via domain-wide delegation pra ler
    # grupos reais (core/workspace_directory.py, domains/admin v1.5) —
    # indicada pela TI ao autorizar a delegação, ver
    # docs/onboarding-cliente.md (2026-08-21).
    OBSERVABILITY_HUB_WORKSPACE_IMPERSONATE_EMAIL = "matheus.fuzati@dp6.com.br"
  }
}

module "frontend_cloud_run" {
  source = "../../modules/cloud-run"

  project_id   = var.project_id
  region       = var.region
  service_name = "frontend-dev"
  image        = var.frontend_image

  # Frontend estático (serve -s dist) não tem endpoint /health — a raiz
  # responde 200 e serve pros probes de startup/liveness.
  health_check_path = "/"

  # Reaproveita o repositório Artifact Registry criado pelo backend_cloud_run
  # deste ambiente, em vez de tentar criar um segundo "apps" — o mesmo repo
  # é compartilhado por backend-dev, frontend-dev, backend-prod e
  # frontend-prod (todos no mesmo projeto), ver environments/prod/main.tf.
  manage_artifact_registry = false

  # Ambiente de dev: sem proteção contra destroy, permite scale-to-zero.
  deletion_protection = false
  iap_enabled         = true
  iap_access_members  = var.iap_access_members
}

# Firestore named database do ambiente dev — dev e prod estão no mesmo
# projeto GCP, então não dá pra usar o banco "(default)" implícito pros
# dois (misturaria dados). Precisa existir antes do primeiro deploy do
# backend (core/firestore.py::get_firestore_client usa database="hub-dev").
# Nome prefixado com "hub-" porque database_id do Firestore exige no
# mínimo 4 caracteres — "dev" sozinho (3) é rejeitado pela API.
resource "google_firestore_database" "hub" {
  project     = var.project_id
  name        = "hub-dev"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  # Ambiente de dev: sem proteção, permite destroy/recriação sem fricção.
  delete_protection_state = "DELETE_PROTECTION_DISABLED"
  deletion_policy         = "DELETE"
}
