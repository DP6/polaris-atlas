resource "google_cloud_run_v2_job" "job" {
  project  = var.project_id
  name     = var.job_name
  location = var.region

  labels = {
    environment = var.environment
    managed-by  = "terraform"
  }

  template {
    template {
      service_account = var.service_account
      timeout         = "${var.timeout_seconds}s"

      containers {
        image   = var.image
        command = var.command

        resources {
          limits = {
            cpu    = var.cpu
            memory = var.memory
          }
        }

        dynamic "env" {
          for_each = var.env
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }

  # A imagem é atualizada pelos workflows de deploy via `gcloud run jobs
  # update --image ...`, fora do Terraform — mesmo racional de
  # modules/cloud-run/main.tf (evita reverter pra imagem antiga no próximo
  # apply).
  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }
}

# Identidade dedicada só pra invocação via Cloud Scheduler — mínima
# (só roles/run.invoker sobre este Job específico, grant local ao
# projeto do Hub, não cross-project).
resource "google_service_account" "scheduler_invoker" {
  project      = var.project_id
  account_id   = var.scheduler_service_account_id
  display_name = "Cloud Scheduler invoker (${var.job_name})"
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.job.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_invoker.email}"
}

# Cloud Run Job sempre exige roles/run.invoker pra ser executado (não tem
# o bypass invoker_iam_disabled do Service) — a própria SA de runtime do
# backend precisa dessa role pra o gatilho manual de admin
# (domains/admin::trigger_event_cache_refresh) funcionar, sem precisar de
# nenhum segredo/token customizado.
resource "google_cloud_run_v2_job_iam_member" "backend_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.job.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.backend_service_account_email}"
}

resource "google_cloud_scheduler_job" "refresh" {
  project     = var.project_id
  region      = var.region
  name        = "${var.job_name}-scheduler"
  schedule    = var.schedule
  time_zone   = "UTC"
  description = "Dispara 1x/dia o Cloud Run Job ${var.job_name} (refresh do cache de audit log de lineage/access)."

  http_target {
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${var.job_name}:run"
    http_method = "POST"

    oauth_token {
      service_account_email = google_service_account.scheduler_invoker.email
    }
  }

  depends_on = [google_cloud_run_v2_job_iam_member.scheduler_invoker]
}
