# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

locals {
  effective_trace_project_id = coalesce(var.trace_project_id, var.project_id)

  # Unique projects hosting CES apps and logs
  unique_ces_projects = distinct(compact(concat(
    [var.project_id],
    [for cfg in var.app_configs : try(cfg.ces_project_id, null)]
  )))

  # Unique target projects where Cloud Trace spans may be written
  unique_trace_projects = distinct(compact(concat(
    [local.effective_trace_project_id],
    local.unique_ces_projects,
    [for cfg in var.app_configs : try(cfg.trace_project_id, null)]
  )))
}

# Enable required services for the project (conditional)
resource "google_project_service" "services" {
  for_each = var.enable_apis ? toset([
    "run.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "logging.googleapis.com",
    "cloudtrace.googleapis.com",
    "ces.googleapis.com",
    "dialogflow.googleapis.com",
    "pubsub.googleapis.com"
  ]) : []
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# Runtime Service Account for Cloud Run
resource "google_service_account" "ces_tracer_sa" {
  project      = var.project_id
  account_id   = "${var.service_name}-run-sa"
  display_name = "CES Tracer Cloud Run Runtime SA"
}

# Grant Logging Viewer permission to read Dialogflow audit, incoming_call, and CES response logs
resource "google_project_iam_member" "logging_viewer" {
  for_each = var.grant_project_iam_roles ? toset(local.unique_ces_projects) : []
  project  = each.value
  role     = "roles/logging.viewer"
  member   = "serviceAccount:${google_service_account.ces_tracer_sa.email}"
}

# Grant Private Logs Viewer permission to read Dialogflow Data Access audit logs (private logs)
resource "google_project_iam_member" "logging_private_viewer" {
  for_each = var.grant_project_iam_roles ? toset(local.unique_ces_projects) : []
  project  = each.value
  role     = "roles/logging.privateLogViewer"
  member   = "serviceAccount:${google_service_account.ces_tracer_sa.email}"
}

# Grant Dialogflow Reader permission to resolve ConversationProfiles dynamically
resource "google_project_iam_member" "dialogflow_reader" {
  count   = var.grant_project_iam_roles ? 1 : 0
  project = var.project_id
  role    = "roles/dialogflow.reader"
  member  = "serviceAccount:${google_service_account.ces_tracer_sa.email}"
}

# Grant CES Viewer permission to fetch completed CES conversations via the CES v1 REST API
resource "google_project_iam_member" "ces_viewer" {
  for_each = var.grant_project_iam_roles ? toset(local.unique_ces_projects) : []
  project  = each.value
  role     = "roles/ces.viewer"
  member   = "serviceAccount:${google_service_account.ces_tracer_sa.email}"
}

# Grant Cloud Trace Agent permission to write spans to Cloud Trace
resource "google_project_iam_member" "cloudtrace_agent" {
  for_each = var.grant_project_iam_roles ? toset(local.unique_trace_projects) : []
  project  = each.value
  role     = "roles/cloudtrace.agent"
  member   = "serviceAccount:${google_service_account.ces_tracer_sa.email}"
}

# Grant Cloud Trace User permission to read existing traces (idempotency guard)
resource "google_project_iam_member" "cloudtrace_user" {
  for_each = var.grant_project_iam_roles ? toset(local.unique_trace_projects) : []
  project  = each.value
  role     = "roles/cloudtrace.user"
  member   = "serviceAccount:${google_service_account.ces_tracer_sa.email}"
}

# Pub/Sub Push Invoker Service Account (OIDC identity used by the push subscription)
resource "google_service_account" "push_invoker_sa" {
  project      = var.project_id
  account_id   = "${var.service_name}-trigger-sa"
  display_name = "CES Tracer Pub/Sub Push Invoker SA"
}

# Cloud Run v2 Service
resource "google_cloud_run_v2_service" "ces_tracer" {
  name                = var.service_name
  project             = var.project_id
  location            = var.region
  deletion_protection = false

  template {
    service_account = google_service_account.ces_tracer_sa.email
    timeout         = "${var.ack_deadline_seconds}s"

    containers {
      image = var.image_url

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "TRACE_PROJECT_ID"
        value = var.trace_project_id == null ? "" : var.trace_project_id
      }

      env {
        name  = "REDACT_PII"
        value = tostring(var.redact_pii)
      }

      env {
        name  = "SKIP_IF_TRACE_EXISTS"
        value = tostring(var.skip_if_trace_exists)
      }

      env {
        name  = "INITIAL_DELAY_SECONDS"
        value = tostring(var.initial_delay_seconds)
      }

      env {
        name = "APP_CONFIGS"
        value = jsonencode([
          for cfg in var.app_configs : {
            conversation_profile = coalesce(try(cfg.conversation_profile, null), "*")
            ces_project_id       = coalesce(try(cfg.ces_project_id, null), var.project_id)
            ces_location         = cfg.ces_location
            ces_app_id           = cfg.ces_app_id
            trace_project_id     = coalesce(try(cfg.trace_project_id, null), local.effective_trace_project_id)
          }
        ])
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }

    scaling {
      max_instance_count = 50
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.services
  ]
}

# Grant Invoker access to the Pub/Sub push invoker SA on Cloud Run
resource "google_cloud_run_v2_service_iam_member" "push_invoker" {
  count    = var.grant_project_iam_roles ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.ces_tracer.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.push_invoker_sa.email}"
}

# Pub/Sub topic receiving Dialogflow CompleteConversation audit log entries
resource "google_pubsub_topic" "complete_conversation" {
  project = var.project_id
  name    = "${var.service_name}-complete-conv"

  depends_on = [
    google_project_service.services
  ]
}

# Log Router sink routing Dialogflow CompleteConversation Data Access audit logs to the topic.
# Matches both v2 and v2beta1 method names.
resource "google_logging_project_sink" "complete_conversation" {
  project                = var.project_id
  name                   = "${var.service_name}-complete-conv"
  destination            = "pubsub.googleapis.com/${google_pubsub_topic.complete_conversation.id}"
  unique_writer_identity = true
  filter = join(" AND ", [
    "logName=\"projects/${var.project_id}/logs/cloudaudit.googleapis.com%2Fdata_access\"",
    "protoPayload.serviceName=\"dialogflow.googleapis.com\"",
    "protoPayload.methodName:\"Conversations.CompleteConversation\"",
  ])
}

# Allow the sink writer identity to publish to the topic
resource "google_pubsub_topic_iam_member" "sink_publisher" {
  count   = var.grant_project_iam_roles ? 1 : 0
  project = var.project_id
  topic   = google_pubsub_topic.complete_conversation.name
  role    = "roles/pubsub.publisher"
  member  = google_logging_project_sink.complete_conversation.writer_identity
}

# Push subscription delivering audit log entries to Cloud Run.
# The ack deadline must exceed the end-to-end processing time of a request,
# otherwise Pub/Sub treats slow (even successful) responses as nacks and redelivers.
resource "google_pubsub_subscription" "complete_conversation" {
  project                    = var.project_id
  name                       = "${var.service_name}-complete-conv-push"
  topic                      = google_pubsub_topic.complete_conversation.id
  ack_deadline_seconds       = var.ack_deadline_seconds
  message_retention_duration = "86400s"

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.ces_tracer.uri}/"

    oidc_token {
      service_account_email = google_service_account.push_invoker_sa.email
    }
  }

  depends_on = [
    google_cloud_run_v2_service_iam_member.push_invoker
  ]
}
