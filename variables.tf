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