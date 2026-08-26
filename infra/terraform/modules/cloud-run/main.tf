data "google_project" "current" {
  project_id = var.project_id
}

resource "google_artifact_registry_repository" "apps" {
  count = var.manage_artifact_registry ? 1 : 0

  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_repository_id
  format        = "DOCKER"
  description   = "Imagens Docker dos apps do Observability Hub (backend, frontend)."
}

# O recurso ganhou `count` para permitir instâncias do módulo que reaproveitam
# um repositório criado por outra instância (ex: frontend + backend no mesmo
# projeto). Este `moved` remapeia o endereço de state de instâncias já
# aplicadas (ex: backend em dev/prod) sem destruir/recriar o repositório real.
moved {
  from = google_artifact_registry_repository.apps
  to   = google_artifact_registry_repository.apps[0]
}

# Identidade runtime do Cloud Run — hoje sem papéis próprios, já que ainda
# não há lógica de domínio (BigQuery/Cloud Logging) para autorizar. Papéis
# específicos entram conforme os domínios forem implementados.
resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "${var.service_name}-run"
  display_name = "Cloud Run runtime SA (${var.service_name})"
}

resource "google_cloud_run_v2_service" "service" {
  # iap_enabled só existe no provider google-beta, com launch_stage = "BETA"
  # — a feature em si (IAP nativo no Cloud Run, sem Load Balancer) é GA no
  # GCP, mas o suporte no provider Terraform ainda está atrás desse gate.
  provider = google-beta

  project  = var.project_id
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  # BETA só é necessário quando iap_enabled=true; serviços sem IAP (ex:
  # backend, que usa invoker_iam_disabled em vez de IAP — ver variables.tf)
  # ficam em GA normalmente.
  launch_stage        = var.iap_enabled ? "BETA" : "GA"
  deletion_protection = var.deletion_protection
  iap_enabled         = var.iap_enabled
  # Desliga a checagem de IAM do invoker sem criar nenhum binding de IAM
  # (nem allUsers nem outro member) — não esbarra na Org Policy
  # iam.allowedPolicyMemberDomains, que rege members de IAM policy, não
  # essa flag de configuração do recurso. Usado no backend, que fica
  # protegido pelo próprio OAuth+JWT (domains/auth) em vez de IAP — o
  # frontend chama o backend via fetch() cross-site, e o cookie de sessão
  # do IAP (que não controlamos o SameSite) não sobrevive esse tipo de
  # request; o cookie do app, sim (SameSite=None de propósito).
  invoker_iam_disabled = var.invoker_iam_disabled

  template {
    service_account = google_service_account.runtime.email
    timeout         = "${var.timeout_seconds}s"

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    containers {
      image = var.image

      ports {
        container_port = var.container_port
      }

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        # Declarado explicitamente (não é o default seguro assumir) —
        # cpu_idle=false ("CPU sempre alocada", cobra pelo tempo de vida
        # da instância inteira, não só durante o processamento da
        # requisição) já foi encontrado ligado nos 4 serviços uma vez
        # antes, mudado manualmente fora do Terraform, sem registro de
        # quando ou por quê (ver CHANGELOG.md, "Diagnóstico de custo do
        # Cloud Run") — sem estar no IaC, recorreu. Nenhum dos 4
        # serviços (backend/frontend × dev/prod) faz trabalho depois de
        # responder a requisição (sem BackgroundTasks, sem thread solta,
        # sem streaming), então CPU só-durante-requisição é seguro.
        cpu_idle = true
      }

      # E-mail da própria SA de runtime, injetado automaticamente (não fica a
      # cargo do caller do módulo) — usado pelo backend em vez de reconstruir
      # o nome a partir do project_id, que sozinho não distingue dev de prod
      # na topologia single-project (ver core/config.py::runtime_sa_email).
      env {
        name  = "OBSERVABILITY_HUB_RUNTIME_SA_EMAIL"
        value = google_service_account.runtime.email
      }

      dynamic "env" {
        for_each = var.env
        content {
          name  = env.key
          value = env.value
        }
      }

      startup_probe {
        http_get {
          path = var.health_check_path
          port = var.container_port
        }
        # failure_threshold=3 (~15s) era curto demais — revisões observadas
        # levando até 24.8s pra ficar prontas, causando 503 em instâncias
        # novas de autoscaling mesmo com a revisão já Ready.
        period_seconds    = 5
        failure_threshold = 8
      }

      liveness_probe {
        http_get {
          path = var.health_check_path
          port = var.container_port
        }
        period_seconds = 15
      }
    }
  }

  # A imagem é atualizada pelos workflows de deploy via `gcloud run deploy
  # --image ...`, fora do Terraform. Sem isso, o próximo `terraform apply`
  # reverteria a revisão em produção para a imagem placeholder default.
  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }

  depends_on = [google_artifact_registry_repository.apps]
}

resource "google_iap_web_cloud_run_service_iam_member" "access" {
  for_each = var.iap_enabled ? toset(var.iap_access_members) : toset([])

  # Apesar da doc do resource dizer "project id", a API espera project
  # number aqui — confirmado em issue real do provider (hashicorp/
  # terraform-provider-google#23092). Com project_id o binding é aceito
  # mas o acesso via IAP não funciona.
  project                = tostring(data.google_project.current.number)
  location               = google_cloud_run_v2_service.service.location
  cloud_run_service_name = google_cloud_run_v2_service.service.name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = each.value
}

# O IAP nativo do Cloud Run intercepta a requisição, valida a identidade e
# repassa pro serviço usando sua própria identidade de serviço — que
# precisa de roles/run.invoker no projeto pra isso funcionar. NÃO gerenciado
# aqui: exige resourcemanager.projects.setIamPolicy, permissão maior do que
# a SA de deploy do CI tem (só roles/iap.admin, que não cobre IAM genérico
# de projeto) — pedir isso pra SA de deploy seria uma concessão mais ampla
# do que o allUsers que esta mudança inteira existe pra evitar. Aplicado
# manualmente uma única vez por projeto (dev e prod compartilham o mesmo
# projeto GCP nesta topologia single-project), mesmo padrão de
# infra/terraform/bootstrap:
#
#   gcloud projects add-iam-policy-binding <project_id> \
#     --member="serviceAccount:service-<PROJECT_NUMBER>@gcp-sa-iap.iam.gserviceaccount.com" \
#     --role="roles/run.invoker"
#
# Já aplicado em dp6-ci-polaris (ver docs/onboarding-cliente.md).
