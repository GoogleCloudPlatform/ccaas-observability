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

variable "storage_project_id" {
  type        = string
  description = "The Google Cloud project ID hosting GCS, Eventarc, and Cloud Run."
}

variable "region" {
  type        = string
  description = "The region to deploy the Cloud Run service."
  default     = "us-central1"
}

variable "gcs_path_configs" {
  type = map(object({
    ccaas_project_id        = string
    ccaas_resource_location = string
    ccaas_resource_id       = string
  }))
  description = "A map of GCS path URIs (e.g., 'gs://bucket/path/') to their target logging configurations."
}

variable "image_url" {
  type        = string
  description = "The container image path in Artifact Registry (e.g., us-central1-docker.pkg.dev/my-project/my-repo/metadata-logger:latest)."
}

variable "custom_log_name" {
  type        = string
  description = "The identifier for custom logs."
  default     = "contactcenteraiplatform.googleapis.com%2Fmetadata"
}

variable "grant_project_iam_roles" {
  type        = bool
  description = "Whether to let the module automatically create the project-level IAM role bindings for GCS, Eventarc, and logging. Set to false if these are managed externally (e.g., via a project factory)."
  default     = true
}

variable "enable_apis" {
  type        = bool
  description = "Whether to let the module automatically enable necessary Google Cloud service APIs (run, eventarc, logging, storage, pubsub). Set to false if these are managed externally (e.g., via a project factory)."
  default     = true
}

variable "trigger_type" {
  type        = string
  description = "The trigger type to use for GCS events. Supported values: 'eventarc', 'pubsub'."
  default     = "eventarc"
  validation {
    condition     = contains(["eventarc", "pubsub"], var.trigger_type)
    error_message = "The trigger_type must be either 'eventarc' or 'pubsub'."
  }
}

variable "service_name" {
  type        = string
  description = "The name of the Cloud Run service and prefix for related resources."
  default     = "metadata-logger"
  validation {
    condition     = length(var.service_name) <= 20
    error_message = "The service_name must be 20 characters or less to avoid exceeding SA name limits."
  }
}

variable "state_bucket" {
  type = object({
    create_bucket  = optional(bool, true)
    name           = optional(string)
    location       = optional(string)
    retention_days = optional(number, 30)
  })
  default     = null
  description = "Configuration for the interaction state tracking GCS bucket. If create_bucket is false, a pre-existing bucket name must be passed. If create_bucket is true, location must be specified, and name is optional (defaults to '<storage_project_id>-<service_name>-state')."
  validation {
    condition = var.state_bucket == null || (
      try(var.state_bucket.create_bucket, true) == false ? (
        try(var.state_bucket.name != null && var.state_bucket.name != "", false)
      ) : (
        try(var.state_bucket.location != null && var.state_bucket.location != "", false)
      )
    )
    error_message = "When state_bucket.create_bucket is false, a pre-existing state_bucket.name must be provided. When create_bucket is true, state_bucket.location must be specified."
  }
}
