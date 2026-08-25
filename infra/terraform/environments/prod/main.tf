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
    OBSERVABILITY_HUB_CORS_ORIGINS = "https://observability-hub.dp6.io,${module.frontend_cloud_run.service_url},${module.frontend_cloud_run.service_url_alt}"
    # Único sinal de ambiente do backend (core/config.py::settings.environment)
    # — nunca mais inferido do project_id, que é o mesmo pros dois ambientes
    # nesta topologia.
    OBSERVABILITY_HUB_ENVIRONMENT = "prod"
    # Conta do Workspace impersonada via domain-wide delegation pra ler
    # grupos reais (core/workspace_directory.py, domains/admin v1.5) —
    # indicada pela TI ao autorizar a delegação, ver
    # docs/onboarding-cliente.md (2026-08-25).
    OBSERVABILITY_HUB_WORKSPACE_IMPERSONATE_EMAIL = "admin.victoria@dp6.com.br"
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
