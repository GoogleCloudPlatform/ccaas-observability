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

variable "project_id" {
  type        = string
  description = "The Google Cloud project ID hosting Dialogflow/CXAS, the Log Router sink, Pub/Sub, and the Cloud Run service."
}

variable "region" {
  type        = string
  description = "The region to deploy the Cloud Run service."
  default     = "us-central1"
}

variable "image_url" {
  type        = string
  description = "The container image path in Artifact Registry (e.g., us-central1-docker.pkg.dev/my-project/my-repo/ces-tracer:latest)."
}

variable "trace_project_id" {
  type        = string
  description = "Optional target Google Cloud project ID where Cloud Trace spans are written. Defaults to the resolved CXAS project ID or project_id."
  default     = null
}

variable "app_configs" {
  type = list(object({
    conversation_profile = optional(string, "*")
    ces_project_id       = optional(string)
    ces_location         = string
    ces_app_id           = string
    trace_project_id     = optional(string)
  }))
  description = "Optional static mappings from Dialogflow ConversationProfile (full resource name, short ID, or '*' for default fallback) to target CXAS App configurations. When empty, CXAS apps are resolved dynamically from the Dialogflow ConversationProfile API."
  default     = []
}

variable "ack_deadline_seconds" {
  type        = number
  description = "Ack deadline (seconds) of the Pub/Sub push subscription, also used as the Cloud Run request timeout. Must exceed the end-to-end processing time of a conversation trace to avoid redeliveries."
  default     = 300
  validation {
    condition     = var.ack_deadline_seconds >= 10 && var.ack_deadline_seconds <= 600
    error_message = "ack_deadline_seconds must be between 10 and 600."
  }
}

variable "skip_if_trace_exists" {
  type        = bool
  description = "Whether to skip writing spans when a trace for the conversation already exists in Cloud Trace (best-effort idempotency guard against Pub/Sub redeliveries)."
  default     = true
}

variable "redact_pii" {
  type        = bool
  description = "Whether to redact user utterances in turn span display names and sensitive PII fields in span attributes."
  default     = false
}

variable "initial_delay_seconds" {
  type        = number
  description = "Number of seconds to wait before querying Cloud Logging so final conversation log entries are indexed."
  default     = 2
}

variable "grant_project_iam_roles" {
  type        = bool
  description = "Whether to let the module automatically create the project-level IAM role bindings for Cloud Run, Cloud Logging, Cloud Trace, and Pub/Sub. Set to false if these are managed externally (e.g., via a project factory)."
  default     = true
}

variable "enable_apis" {
  type        = bool
  description = "Whether to let the module automatically enable necessary Google Cloud service APIs (run, cloudresourcemanager, logging, cloudtrace, ces, dialogflow, pubsub). Set to false if these are managed externally (e.g., via a project factory)."
  default     = true
}

variable "service_name" {
  type        = string
  description = "The name of the Cloud Run service and prefix for related resources."
  default     = "ces-tracer"
  validation {
    condition     = length(var.service_name) <= 20
    error_message = "The service_name must be 20 characters or less to avoid exceeding service account ID limits."
  }
}
