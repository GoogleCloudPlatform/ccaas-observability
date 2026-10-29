/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

variable "project_id" {
  type = string
}

variable "established_call_rate_upper_bound" {
  type    = number
  default = 110
}

variable "escalated_chat_rate_upper_bound" {
  type    = number
  default = 110
}

variable "enable_metadata_logger" {
  type        = bool
  default     = false
  description = "Whether to enable the metadata logger."
}

variable "metadata_logger" {
  type = object({
    # The regional location to deploy the Cloud Run service.
    region = optional(string, "us-central1")

    # The Google Cloud project ID hosting the GCS buckets, Eventarc, and Cloud Run service.
    storage_project_id = optional(string)

    # A map of GCS path URIs (e.g., 'gs://bucket/path/') to their target logging configurations.
    path_configs = optional(map(object({
      ccaas_project_id        = string
      ccaas_resource_location = string
      ccaas_resource_id       = string
    })), {})

    # The container image path in Artifact Registry for the metadata-logger Cloud Run service.
    image_url = optional(string)

    # Whether to let the metadata_logger module automatically create project-level IAM role bindings.
    grant_project_iam_roles = optional(bool, true)

    # Whether to let the metadata_logger module automatically enable project APIs.
    enable_apis = optional(bool, true)

    # The identifier for custom logs.
    custom_log_name = optional(string, "contactcenteraiplatform.googleapis.com%2Fmetadata")

    # Configuration for the interaction state tracking GCS bucket.
    state_bucket = optional(object({
      create_bucket  = optional(bool, true)
      name           = optional(string)
      location       = optional(string)
      retention_days = optional(number, 30)
    }))
  })
  default     = {}
  description = "Configuration settings for the metadata logger."
}

variable "enable_metadata_dashboards" {
  type        = bool
  default     = false
  description = "Whether to enable the metadata log-based calls and chats dashboards and metrics."
}

variable "metadata_dashboards" {
  type = object({
    custom_log_name                   = optional(string, "contactcenteraiplatform.googleapis.com%2Fmetadata")
    established_call_rate_upper_bound = optional(number)
    escalated_chat_rate_upper_bound   = optional(number)
    log_bucket = optional(object({
      location = string
      name     = string
      }), {
      location = "global"
      name     = "_Default"
    })
  })
  default     = {}
  description = "Configuration settings for the metadata log-based dashboards."
}

variable "enable_ces_tracer" {
  type        = bool
  default     = false
  description = "Whether to enable the CXAS Tracer Cloud Run service and its audit log delivery pipeline (Log Router sink, Pub/Sub topic and push subscription)."
}

variable "ces_tracer" {
  type = object({
    # The Google Cloud project ID hosting Dialogflow/CXAS, the Log Router sink, Pub/Sub, and the Cloud Run service (defaults to var.project_id).
    project_id = optional(string)

    # The regional location to deploy the Cloud Run service.
    region = optional(string, "us-central1")

    # The container image path in Artifact Registry for the ces-tracer Cloud Run service (required when enable_ces_tracer = true).
    image_url = optional(string)

    # Optional target Google Cloud project ID where Cloud Trace spans are written.
    trace_project_id = optional(string)

    # Optional static mappings from Dialogflow ConversationProfile to target CXAS App configurations.
    app_configs = optional(list(object({
      conversation_profile = optional(string, "*")
      ces_project_id       = optional(string)
      ces_location         = string
      ces_app_id           = string
      trace_project_id     = optional(string)
    })), [])

    # Ack deadline (seconds) of the Pub/Sub push subscription; also used as the Cloud Run request timeout.
    ack_deadline_seconds = optional(number, 300)

    # Whether to skip writing spans when a trace for the conversation already exists (best-effort idempotency).
    skip_if_trace_exists = optional(bool, true)

    # Whether to redact user utterances in turn span display names and sensitive PII fields in span attributes.
    redact_pii = optional(bool, false)

    # Number of seconds to wait before querying Cloud Logging so final conversation log entries are indexed.
    initial_delay_seconds = optional(number, 2)

    # Whether to let the ces_tracer module automatically create project-level IAM role bindings.
    grant_project_iam_roles = optional(bool, true)

    # Whether to let the ces_tracer module automatically enable project APIs.
    enable_apis = optional(bool, true)

    # The name of the Cloud Run service and prefix for related resources.
    service_name = optional(string, "ces-tracer")
  })
  default     = {}
  description = "Configuration settings for the CXAS Tracer service."
}