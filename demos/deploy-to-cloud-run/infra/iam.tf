# Permission to push Docker images to Artifact Registry
resource "google_artifact_registry_repository_iam_member" "sa_ar_writer" {
  project    = var.project_id
  location   = google_artifact_registry_repository.api_repo.location
  repository = google_artifact_registry_repository.api_repo.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
}

# Permission to manage Cloud Run deployments and traffic splitting
resource "google_project_iam_member" "sa_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
}

# Permission to act as a Service Account in Cloud Run
resource "google_project_iam_member" "sa_service_account_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
}
