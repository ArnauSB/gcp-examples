variable "project_id" {
  description = "The GCP Project ID"
  type        = string
}

variable "region" {
  description = "The region for the GCP resources"
  type        = string
  default     = "europe-west1"
}

variable "github_owner" {
  description = "The GitHub user or organization owning the repository"
  type        = string
}

variable "github_repo" {
  description = "The GitHub repository name"
  type        = string
}
