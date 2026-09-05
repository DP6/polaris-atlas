terraform {
  required_version = ">= 1.7"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    # iap_enabled em google_cloud_run_v2_service só existe no provider beta
    # (launch_stage = "BETA") — ver modules/cloud-run/main.tf.
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
  }

  # Nome do bucket vem do output `state_bucket_name` do bootstrap (único,
  # compartilhado com prod — topologia single-project). Ver
  # infra/terraform/bootstrap/README.md. O `prefix` é quem isola o state
  # de dev do de prod dentro do mesmo bucket.
  backend "gcs" {
    bucket = "dp6-ci-polaris-tfstate"
    prefix = "environments/dev"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region

  # Taxonomia de labels FinOps — ver docs/finops-labels.md. Precisa estar
  # nos dois providers (google e google-beta): o Cloud Run service roda
  # em google-beta por causa de iap_enabled (ver modules/cloud-run/main.tf).
  default_labels = {
    environment = "dev"
    app         = "atlas"
    managed-by  = "terraform"
  }
}

provider "google-beta" {
  project = var.project_id
  region  = var.region

  default_labels = {
    environment = "dev"
    app         = "atlas"
    managed-by  = "terraform"
  }
}
