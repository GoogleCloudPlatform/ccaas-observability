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
  value       = google_cloud_run_v2_service.ces_tracer.uri
  description = "The endpoint URL of the deployed CXAS Tracer Cloud Run service."
}

output "runtime_service_account_email" {
  value       = google_service_account.ces_tracer_sa.email
  description = "The email of the Cloud Run runtime service account."
}

output "trigger_service_account_email" {
  value       = google_service_account.push_invoker_sa.email
  description = "The email of the Pub/Sub push invoker service account."
}

output "pubsub_topic" {
  value       = google_pubsub_topic.complete_conversation.id
  description = "The Pub/Sub topic receiving Dialogflow CompleteConversation audit log entries."
}

output "pubsub_subscription" {
  value       = google_pubsub_subscription.complete_conversation.id
  description = "The Pub/Sub push subscription delivering events to the CXAS Tracer service."
}

output "log_sink_writer_identity" {
  value       = google_logging_project_sink.complete_conversation.writer_identity
  description = "The writer identity of the Log Router sink (needs roles/pubsub.publisher on the topic when grant_project_iam_roles = false)."
}
