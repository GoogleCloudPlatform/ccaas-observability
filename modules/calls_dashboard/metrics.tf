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

resource "google_logging_metric" "calls_failed" {
  name = "ccaas_calls_failed"

  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of failed calls in the last minute."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    textPayload:"[Call] Call failed due to an error."
  EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  project = var.project_id
}

resource "google_logging_metric" "calls_established" {
  name = "ccaas_calls_established"

  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of established calls in the last minute."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    textPayload:"[Call] Call connected successfully."
  EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  project = var.project_id
}

resource "google_logging_metric" "calls_successful" {
  name = "ccaas_calls_successful"

  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of successful calls in the last minute."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    textPayload:"[Call] Call finished successfully."
  EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  project = var.project_id
}

resource "google_logging_metric" "voice_platform_errors" {
  name = "ccaas_va_errors"

  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of voice platform errors in the last minute."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    textPayload:"error in voice platform"
  EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "resource_id"
      value_type  = "STRING"
      description = "The Contact Center instance ID"
    }
    labels {
      key         = "location"
      value_type  = "STRING"
      description = "The GCP region of the Contact Center"
    }
    labels {
      key         = "error_type"
      value_type  = "STRING"
      description = "The gRPC error code name"
    }
  }

  label_extractors = {
    "resource_id" = "EXTRACT(resource.labels.resource_id)"
    "location"    = "EXTRACT(resource.labels.location)"
    "error_type"  = "REGEXP_EXTRACT(textPayload, \"message : \\\\d+ ([A-Z_]+):\")"
  }

  project = var.project_id
}

resource "google_logging_metric" "stream_errors" {
  name = "ccaas_stream_errors"

  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of stream errors in the last minute."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    textPayload:"An error occurred in stream"
  EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  project = var.project_id
}

resource "google_logging_metric" "streaming_errors_v2" {
  name = "ccaas_streaming_errors_v2"

  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of stream errors in the last minute (v2)."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    textPayload:"An error occurred in stream"
  EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "resource_id"
      value_type  = "STRING"
      description = "The Contact Center instance ID"
    }
    labels {
      key         = "location"
      value_type  = "STRING"
      description = "The GCP region of the Contact Center"
    }
    labels {
      key         = "error_type"
      value_type  = "STRING"
      description = "The gRPC error code name"
    }
  }

  label_extractors = {
    "resource_id" = "EXTRACT(resource.labels.resource_id)"
    "location"    = "EXTRACT(resource.labels.location)"
    "error_type"  = "REGEXP_EXTRACT(textPayload, \"message : \\\\d+ ([A-Z_]+):\")"
  }

  project = var.project_id
}

resource "google_logging_metric" "call_participant_join_errors" {
  name        = "ccaas_call_participant_join_errors"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Call-specific participant join failures."
  filter      = "resource.type=\"contactcenteraiplatform.googleapis.com/ContactCenter\" jsonPayload.event.name=\"session_participant_join_failed\" jsonPayload.event.payload.participant.channel=\"call\""
  project     = var.project_id
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "chat_participant_join_errors" {
  name        = "ccaas_chat_participant_join_errors"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Chat-specific participant join failures."
  filter      = "resource.type=\"contactcenteraiplatform.googleapis.com/ContactCenter\" jsonPayload.event.name=\"session_participant_join_failed\" jsonPayload.event.payload.participant.channel=\"chat\""
  project     = var.project_id
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "call_human_join_errors" {
  name        = "ccaas_call_human_join_errors"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Call-specific human join failures."
  filter      = "resource.type=\"contactcenteraiplatform.googleapis.com/ContactCenter\" jsonPayload.event.name=\"session_participant_join_failed\" jsonPayload.event.payload.participant.id=\"end_user\" jsonPayload.event.payload.participant.channel=\"call\""
  project     = var.project_id
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "chat_human_join_errors" {
  name        = "ccaas_chat_human_join_errors"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Chat-specific human join failures."
  filter      = "resource.type=\"contactcenteraiplatform.googleapis.com/ContactCenter\" jsonPayload.event.name=\"session_participant_join_failed\" jsonPayload.event.payload.participant.id=\"end_user\" jsonPayload.event.payload.participant.channel=\"chat\""
  project     = var.project_id
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "call_virtual_join_errors" {
  name        = "ccaas_call_virtual_join_errors"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Call-specific virtual/internal join failures."
  filter      = "resource.type=\"contactcenteraiplatform.googleapis.com/ContactCenter\" jsonPayload.event.name=\"session_participant_join_failed\" jsonPayload.event.payload.participant.id!=\"end_user\" jsonPayload.event.payload.participant.type!=\"campaign_contact\" jsonPayload.event.payload.participant.channel=\"call\""
  project     = var.project_id
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "chat_virtual_join_errors" {
  name        = "ccaas_chat_virtual_join_errors"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Chat-specific virtual/internal join failures."
  filter      = "resource.type=\"contactcenteraiplatform.googleapis.com/ContactCenter\" jsonPayload.event.name=\"session_participant_join_failed\" jsonPayload.event.payload.participant.id!=\"end_user\" jsonPayload.event.payload.participant.type!=\"campaign_contact\" jsonPayload.event.payload.participant.channel=\"chat\""
  project     = var.project_id
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "call_virtual_join_errors_v2" {
  name        = "ccaas_call_virtual_join_errors_v2"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Call-specific virtual/internal join failures (v2 with logName and agent ID)."
  filter      = "resource.type=\"contactcenteraiplatform.googleapis.com/ContactCenter\" logName:\"/logs/contactcenteraiplatform.googleapis.com%2Fevents\" jsonPayload.event.name=\"session_participant_join_failed\" jsonPayload.event.payload.participant.id!=\"end_user\" jsonPayload.event.payload.participant.type!=\"campaign_contact\" jsonPayload.event.payload.participant.channel=\"call\""
  project     = var.project_id
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "resource_id"
      value_type  = "STRING"
      description = "The Contact Center instance ID"
    }
    labels {
      key         = "location"
      value_type  = "STRING"
      description = "The GCP region of the Contact Center"
    }
    labels {
      key         = "virtual_agent_id"
      value_type  = "STRING"
      description = "The ID of the virtual agent"
    }
  }
  label_extractors = {
    "resource_id"      = "EXTRACT(resource.labels.resource_id)"
    "location"         = "EXTRACT(resource.labels.location)"
    "virtual_agent_id" = "EXTRACT(jsonPayload.event.payload.participant.id)"
  }
}

resource "google_logging_metric" "chat_virtual_join_errors_v2" {
  name        = "ccaas_chat_virtual_join_errors_v2"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Chat-specific virtual/internal join failures (v2 with logName and agent ID)."
  filter      = "resource.type=\"contactcenteraiplatform.googleapis.com/ContactCenter\" logName:\"/logs/contactcenteraiplatform.googleapis.com%2Fevents\" jsonPayload.event.name=\"session_participant_join_failed\" jsonPayload.event.payload.participant.id!=\"end_user\" jsonPayload.event.payload.participant.type!=\"campaign_contact\" jsonPayload.event.payload.participant.channel=\"chat\""
  project     = var.project_id
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "resource_id"
      value_type  = "STRING"
      description = "The Contact Center instance ID"
    }
    labels {
      key         = "location"
      value_type  = "STRING"
      description = "The GCP region of the Contact Center"
    }
    labels {
      key         = "virtual_agent_id"
      value_type  = "STRING"
      description = "The ID of the virtual agent"
    }
  }
  label_extractors = {
    "resource_id"      = "EXTRACT(resource.labels.resource_id)"
    "location"         = "EXTRACT(resource.labels.location)"
    "virtual_agent_id" = "EXTRACT(jsonPayload.event.payload.participant.id)"
  }
}

resource "google_logging_metric" "calls_established_v2" {
  name = "ccaas_calls_established_v2"

  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of established calls with type and answer type."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    textPayload:"[Call] Call connected successfully."
  EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "resource_id"
      value_type  = "STRING"
      description = "The Contact Center instance ID"
    }
    labels {
      key         = "location"
      value_type  = "STRING"
      description = "The GCP region of the Contact Center"
    }
    labels {
      key         = "call_type"
      value_type  = "STRING"
      description = "The type of call (e.g., IvrCall, DirectCall)"
    }
    labels {
      key         = "answer_type"
      value_type  = "STRING"
      description = "How the call was answered (e.g., manual, auto)"
    }
  }

  label_extractors = {
    "resource_id"     = "EXTRACT(resource.labels.resource_id)"
    "location"        = "EXTRACT(resource.labels.location)"
    "call_type"       = "REGEXP_EXTRACT(textPayload, \"Call type \\\\(([^)]+)\\\\)\")"
    "answer_type"     = "REGEXP_EXTRACT(textPayload, \"Answer type \\\\(([^)]+)\\\\)\")"
  }

  project = var.project_id
}

resource "google_logging_metric" "ccaas_calls_failed_v2" {
  name = "ccaas_calls_failed_v2"

  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of failed calls with type, answer type, and deflection type."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    textPayload:"[Call] Call failed due to an error."
  EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "resource_id"
      value_type  = "STRING"
      description = "The Contact Center instance ID"
    }
    labels {
      key         = "location"
      value_type  = "STRING"
      description = "The GCP region of the Contact Center"
    }
    labels {
      key         = "call_type"
      value_type  = "STRING"
      description = "The type of call (e.g., IvrCall, DirectCall)"
    }
    labels {
      key         = "answer_type"
      value_type  = "STRING"
      description = "How the call was answered (e.g., manual, auto)"
    }
    labels {
      key         = "deflection_type"
      value_type  = "STRING"
      description = "The type of deflection"
    }
  }

  label_extractors = {
    "resource_id"     = "EXTRACT(resource.labels.resource_id)"
    "location"        = "EXTRACT(resource.labels.location)"
    "call_type"       = "REGEXP_EXTRACT(textPayload, \"Call type \\\\(([^)]+)\\\\)\")"
    "answer_type"     = "REGEXP_EXTRACT(textPayload, \"Answer type \\\\(([^)]+)\\\\)\")"
    "deflection_type" = "REGEXP_EXTRACT(textPayload, \"Deflection \\\\(([^)]+)\\\\)\")"
  }

  project = var.project_id
}

resource "google_logging_metric" "calls_deflected_v2" {
  name = "ccaas_calls_deflected_v2"

  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of deflected calls with type, answer type, and deflection type."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    textPayload:"[Call] Call deflected"
  EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    labels {
      key         = "resource_id"
      value_type  = "STRING"
      description = "The Contact Center instance ID"
    }
    labels {
      key         = "location"
      value_type  = "STRING"
      description = "The GCP region of the Contact Center"
    }
    labels {
      key         = "call_type"
      value_type  = "STRING"
      description = "The type of call (e.g., IvrCall, DirectCall)"
    }
    labels {
      key         = "answer_type"
      value_type  = "STRING"
      description = "How the call was answered (e.g., manual, auto)"
    }
    labels {
      key         = "deflection_type"
      value_type  = "STRING"
      description = "The type of deflection"
    }
  }

  label_extractors = {
    "resource_id"     = "EXTRACT(resource.labels.resource_id)"
    "location"        = "EXTRACT(resource.labels.location)"
    "call_type"       = "REGEXP_EXTRACT(textPayload, \"Call type \\\\(([^)]+)\\\\)\")"
    "answer_type"     = "REGEXP_EXTRACT(textPayload, \"Answer type \\\\(([^)]+)\\\\)\")"
    "deflection_type" = "REGEXP_EXTRACT(textPayload, \"Deflection \\\\(([^)]+)\\\\)\")"
  }

  project = var.project_id
}
