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

output "cloud_run_url" {
  value       = google_cloud_run_v2_service.metadata_logger.uri
  description = "The endpoint URL of the deployed Cloud Run service."
}

output "runtime_service_account_email" {
  value       = google_service_account.metadata_logger_sa.email
  description = "The email of the Cloud Run runtime service account (needed if setting up cross-project logging/GCS IAM permissions)."
}

output "state_bucket_name" {
  value       = local.state_bucket_name
  description = "The name of the dedicated state tracking bucket (if configured)."
}
