/**
 * Copyright 2026 Google LLC
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
  type        = string
  description = "The project ID to deploy the dashboard to."
}

variable "escalated_chat_rate_upper_bound" {
  type        = number
  description = "The upper bound for the Current Escalated Chat Rate gauge."
  default     = 110
}

variable "custom_log_name" {
  type        = string
  description = "The log name for CCaaS metadata logs."
  default     = "contactcenteraiplatform.googleapis.com%2Fmetadata"
}

variable "log_bucket" {
  type = object({
    location = string
    name     = string
  })
  description = "The log bucket to use for the metrics, with location and name attributes."
  default = {
    location = "global"
    name     = "_Default"
  }
}
