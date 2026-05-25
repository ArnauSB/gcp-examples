# =============================================================================
# Automated rollback on SLO breach
#
# Cloud Monitoring watches Cloud Run 5xx request rate per revision. When the
# threshold is exceeded, the alert is delivered to a Pub/Sub topic, which
# triggers a Cloud Function. The function inspects the offending revision and,
# if it looks like a canary (small traffic share or carrying the canary tag),
# rewrites the traffic split so the previous stable revision serves 100%.
# =============================================================================

data "google_project" "current" {
  project_id = var.project_id
}

# ---------------------------------------------------------------------------
# Pub/Sub topic + notification channel
# ---------------------------------------------------------------------------

resource "google_pubsub_topic" "rollback_alerts" {
  name       = "canary-rollback-alerts"
  depends_on = [google_project_service.apis]
}

# Cloud Monitoring's per-project service agent must be allowed to publish.
resource "google_pubsub_topic_iam_member" "monitoring_publisher" {
  topic  = google_pubsub_topic.rollback_alerts.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-monitoring-notification.iam.gserviceaccount.com"
}

resource "google_monitoring_notification_channel" "pubsub" {
  display_name = "Canary rollback alerts (Pub/Sub)"
  type         = "pubsub"
  labels = {
    topic = google_pubsub_topic.rollback_alerts.id
  }
  depends_on = [google_pubsub_topic_iam_member.monitoring_publisher]
}

# ---------------------------------------------------------------------------
# Alert policy: 5xx rate per Cloud Run revision
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "canary_5xx" {
  display_name = "Cloud Run canary 5xx rate"
  combiner     = "OR"

  conditions {
    display_name = "5xx request rate too high (per revision)"
    condition_threshold {
      filter = join(" AND ", [
        "resource.type = \"cloud_run_revision\"",
        "resource.labels.service_name = \"${google_cloud_run_v2_service.api_service.name}\"",
        "metric.type = \"run.googleapis.com/request_count\"",
        "metric.labels.response_code_class = \"5xx\"",
      ])
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 2

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.label.revision_name"]
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.pubsub.name]

  documentation {
    content   = "Auto-rollback triggered: Cloud Run revision is serving >2 5xx req/min over 60s. The canary-rollback function will revert traffic to the previous stable revision."
    mime_type = "text/markdown"
  }
}

# ---------------------------------------------------------------------------
# Cloud Function source: zip the local directory, upload to GCS
# ---------------------------------------------------------------------------

resource "google_storage_bucket" "fn_source" {
  name                        = "${var.project_id}-rollback-fn-source"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
  depends_on                  = [google_project_service.apis]
}

data "archive_file" "rollback_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../rollback-function"
  output_path = "${path.module}/.terraform/tmp/rollback-source.zip"
}

resource "google_storage_bucket_object" "rollback_src" {
  name   = "rollback-${data.archive_file.rollback_zip.output_md5}.zip"
  bucket = google_storage_bucket.fn_source.name
  source = data.archive_file.rollback_zip.output_path
}

# ---------------------------------------------------------------------------
# Function service account + IAM
# ---------------------------------------------------------------------------

resource "google_service_account" "rollback_sa" {
  account_id   = "canary-rollback-fn"
  display_name = "Service account for the canary-rollback Cloud Function"
}

# Allow the function to rewrite Cloud Run traffic.
resource "google_project_iam_member" "rollback_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.rollback_sa.email}"
}

# Required for Eventarc-triggered Cloud Functions (2nd gen).
resource "google_project_iam_member" "rollback_eventarc_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.rollback_sa.email}"
}

# Function runs on Cloud Run under the hood; the Eventarc trigger needs to invoke it.
resource "google_project_iam_member" "rollback_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.rollback_sa.email}"
}

# ---------------------------------------------------------------------------
# Cloud Function (2nd gen)
# ---------------------------------------------------------------------------

resource "google_cloudfunctions2_function" "rollback" {
  name        = "canary-rollback"
  location    = var.region
  description = "Rolls Cloud Run traffic back to the previous stable revision when a canary alert fires."

  build_config {
    runtime     = "python311"
    entry_point = "rollback"
    source {
      storage_source {
        bucket = google_storage_bucket.fn_source.name
        object = google_storage_bucket_object.rollback_src.name
      }
    }
  }

  service_config {
    available_memory      = "256M"
    timeout_seconds       = 120
    service_account_email = google_service_account.rollback_sa.email
    environment_variables = {
      PROJECT_ID   = var.project_id
      REGION       = var.region
      SERVICE_NAME = google_cloud_run_v2_service.api_service.name
    }
  }

  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic          = google_pubsub_topic.rollback_alerts.id
    service_account_email = google_service_account.rollback_sa.email
    retry_policy          = "RETRY_POLICY_DO_NOT_RETRY"
  }

  depends_on = [
    google_project_iam_member.rollback_run_admin,
    google_project_iam_member.rollback_eventarc_receiver,
    google_project_iam_member.rollback_run_invoker,
  ]
}
