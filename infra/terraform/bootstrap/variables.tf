variable "project_id" {
  description = "ID do único projeto GCP, usado tanto por dev quanto por prod."
  type        = string
  default     = "dp6-ci-polaris"
}

variable "region" {
  description = "Região padrão dos recursos."
  type        = string
  default     = "us-central1"
}

variable "github_repository" {
  description = "Repositório GitHub autorizado a assumir as identidades (org/repo)."
  type        = string
  # Renomeado no GitHub de DP6/atlas para DP6/polaris-atlas (2026-09-06).
  # Precisa bater com `assertion.repository` do token OIDC do GitHub
  # Actions, senão o WIF rejeita com "credential is rejected by the
  # attribute condition" (ver attribute_condition e wif_binding no módulo
  # wif-bootstrap). Requer `terraform apply` no stack bootstrap.
  default = "DP6/polaris-atlas"
}
