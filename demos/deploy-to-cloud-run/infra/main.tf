# 1. Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com"
  ])
  service            = each.key
  disable_on_destroy = false
}

# 2. Create Artifact Registry repository
resource "google_artifact_registry_repository" "api_repo" {
  location      = var.region
  repository_id = "api-repo"
  description   = "Docker repository for the GCP Bootcamp Masterclass"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

# 3. Create the Service Account
resource "google_service_account" "cloudbuild_sa" {
  account_id   = "gh-to-cloud-run"
  display_name = "Cloud Build Service Account for Canary Deployments"
  project      = var.project_id
}

# 4. Create Cloud Build Trigger
resource "google_cloudbuild_trigger" "api_trigger" {
  name        = "deploy-api-canary"
  description = "Deploy API to Cloud Run"
  
  service_account = google_service_account.cloudbuild_sa.id

  github {
    owner = var.github_owner
    name  = var.github_repo
    push {
      branch = "^main$"
    }
  }

  included_files = ["demos/deploy-to-cloud-run/**"]
  ignored_files  = ["demos/deploy-to-cloud-run/infra/**"]
  filename       = "demos/deploy-to-cloud-run/cloudbuild.yaml"

  depends_on = [google_project_service.apis]
}
