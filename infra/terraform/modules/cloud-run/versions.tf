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
}
