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

resource "google_logging_metric" "ccaas_version_updates" {
  name        = "ccaas_version_updates"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Count of CCaaS platform update completions labeled by target version and instance."

  filter = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    jsonPayload.message:"Contact Center as a Service update finished. Updated to version"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"

    labels {
      key         = "version"
      value_type  = "STRING"
      description = "CCaaS version updated to (e.g. 6.9.14, 6.7.8)."
    }

    labels {
      key         = "domain_prefix"
      value_type  = "STRING"
      description = "CCaaS tenant domain prefix (e.g. yt-biztech, yt-delorean-uat)."
    }
  }

  label_extractors = {
    "version"       = "EXTRACT(jsonPayload.event.payload.version)"
    "domain_prefix" = "EXTRACT(jsonPayload.event.payload.domain_prefix)"
  }

  project = var.project_id
}
