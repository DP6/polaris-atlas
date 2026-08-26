variable "project_id" {
  description = "ID do projeto GCP onde o Job e o Scheduler são criados — sempre o projeto do próprio Hub (nunca um projeto-alvo/cliente, ver CLAUDE.md)."
  type        = string
}

variable "region" {
  description = "Região do Cloud Run Job e location do Cloud Scheduler."
  type        = string
}

variable "environment" {
  description = "\"dev\" ou \"prod\" — vira label environment nos recursos deste módulo (topologia single-project, os dois ambientes compartilham o mesmo projeto GCP)."
  type        = string
}

variable "job_name" {
  description = "Nome do Cloud Run Job, sufixado por ambiente (ex: \"backend-dev-refresh-cache\")."
  type        = string
}

variable "image" {
  description = "Imagem do container — mesma tag já promovida pelo deploy do Cloud Run Service correspondente (ver environments/{dev,prod}/main.tf::var.backend_image)."
  type        = string
}

variable "command" {
  description = "Entrypoint do container, sobrescrevendo o ENTRYPOINT/CMD da imagem (ex: [\"python\", \"-m\", \"observability_hub.jobs.refresh_event_cache\"])."
  type        = list(string)
}

variable "env" {
  description = "Variáveis de ambiente injetadas no container em runtime — mesmas exigidas pelo processo Python (core/config.py::Settings), já que é a mesma imagem do backend."
  type        = map(string)
  default     = {}
}

variable "cpu" {
  description = "CPU alocada ao container (formato Cloud Run, ex: \"1\")."
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memória alocada ao container. Default maior que o Cloud Run Service (512Mi) porque este Job sempre faz o scan completo de audit log (sem cache, sem gate de dataset) para todo projeto conhecido."
  type        = string
  default     = "1Gi"
}

variable "timeout_seconds" {
  description = "Timeout de cada execução do Job, em segundos (Cloud Run Jobs aceitam até 24h)."
  type        = number
  default     = 3600
}

variable "service_account" {
  description = "E-mail da service account que roda o Job — deve ser a MESMA SA de runtime do Cloud Run Service correspondente (ex: backend-dev-run), nunca uma nova: é essa identidade que já tem roles/logging.privateLogViewer concedida manualmente em cada projeto-alvo onboardado (ver docs/onboarding-cliente.md). Uma SA nova reabriria esse onboarding para todo cliente já liberado."
  type        = string
}

variable "backend_service_account_email" {
  description = "E-mail da SA de runtime do Cloud Run Service do backend — recebe roles/run.invoker sobre este Job (além da SA dedicada do Scheduler) para o gatilho manual de admin (domains/admin::trigger_event_cache_refresh) poder disparar uma execução sob demanda. Normalmente o mesmo valor de var.service_account."
  type        = string
}

variable "scheduler_service_account_id" {
  description = "account_id (não o e-mail completo) da service account dedicada só à invocação via Cloud Scheduler — curto de propósito (ex: \"backend-dev-cache-sched\"), já que account_id de SA tem limite de 30 caracteres do GCP e job_name sufixado por ambiente facilmente estoura isso se usado como base."
  type        = string
}

variable "schedule" {
  description = "Cron do Cloud Scheduler (formato unix-cron). Default: 1x/dia às 03:00 UTC (D-1)."
  type        = string
  default     = "0 3 * * *"
}
