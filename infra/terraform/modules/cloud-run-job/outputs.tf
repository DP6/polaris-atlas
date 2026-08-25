output "job_name" {
  description = "Nome do Cloud Run Job (usado por `gcloud run jobs update` nos workflows de deploy)."
  value       = google_cloud_run_v2_job.job.name
}
