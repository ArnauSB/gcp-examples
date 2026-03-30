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

# 5. Create the base Cloud Run service
resource "google_cloud_run_v2_service" "api_service" {
  name     = "my-api-service"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      # Dummy image just to initialize the service so Terraform can track it
      image = "us-docker.pkg.dev/cloudrun/container/hello"
    }
  }

  # Tell Terraform to ignore changes made by Cloud Build
  lifecycle {
    ignore_changes = [
      template[0].containers[0].image, # Ignore when Cloud Build pushes the Python API
      traffic,                         # Ignore when Cloud Build splits 90/10
      client,
      client_version
    ]
  }

  depends_on = [google_project_service.apis]
}

# 6. Make the Cloud Run service public
resource "google_cloud_run_service_iam_member" "public_access" {
  location = google_cloud_run_v2_service.api_service.location
  service  = google_cloud_run_v2_service.api_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
