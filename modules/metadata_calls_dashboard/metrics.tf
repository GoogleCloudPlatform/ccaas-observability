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

resource "google_logging_metric" "metadata_calls_created" {
  name        = "ccaas_metadata_calls_created"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of calls created from metadata logs in the last minute labeled by call type."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name="call_created"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"

    labels {
      key         = "call_type"
      value_type  = "STRING"
      description = "Call type (e.g. Voice Inbound (IVR), Voice Outbound)"
    }
  }

  label_extractors = {
    "call_type" = "EXTRACT(jsonPayload.event.payload.call.type)"
  }

  project = var.project_id
}

resource "google_logging_metric" "metadata_calls_established" {
  name        = "ccaas_metadata_calls_established"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of established/connected calls from metadata logs in the last minute."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name="call_connected"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  project = var.project_id
}

resource "google_logging_metric" "metadata_calls_successful" {
  name        = "ccaas_metadata_calls_successful"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of successfully finished calls from metadata logs in the last minute."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name="call_ended"
    jsonPayload.event.payload.call.status="finished"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  project = var.project_id
}

resource "google_logging_metric" "metadata_calls_transferred" {
  name        = "ccaas_metadata_calls_transferred"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of transferred/queued calls from metadata logs in the last minute."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name=("session_transfer_started" OR "call_queued")
  EOT


  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  project = var.project_id
}

resource "google_logging_metric" "metadata_calls_abandoned" {
  name        = "ccaas_metadata_calls_abandoned"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of abandoned calls from metadata logs in the last minute."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name="call_ended"
    (jsonPayload.event.payload.call.status="abandoned" OR jsonPayload.event.payload.details.fail_reason:"abandoned")
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  project = var.project_id
}

resource "google_logging_metric" "metadata_calls_failed" {
  name        = "ccaas_metadata_calls_failed"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of failed calls from metadata logs in the last minute."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name="call_ended"
    jsonPayload.event.payload.call.status="failed"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"

    labels {
      key         = "fail_reason"
      value_type  = "STRING"
      description = "The failure reason assigned by CCaaS (e.g. force_ended, ag_mic_denied, eu_abandoned)."
    }

    labels {
      key         = "disconnected_by"
      value_type  = "STRING"
      description = "The entity that disconnected the call (e.g. disconnected_by_end_user, agent, virtual_agent)."
    }

    labels {
      key         = "call_type"
      value_type  = "STRING"
      description = "Call channel type (e.g. Voice Inbound (IVR), Voice Outbound)."
    }
  }

  label_extractors = {
    "fail_reason"     = "EXTRACT(jsonPayload.event.payload.details.fail_reason)"
    "disconnected_by" = "EXTRACT(jsonPayload.event.payload.details.disconnected_by)"
    "call_type"       = "EXTRACT(jsonPayload.event.payload.call.type)"
  }

  project = var.project_id
}

resource "google_logging_metric" "metadata_call_queue_duration" {
  name        = "ccaas_metadata_call_queue_duration"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Distribution of call queue wait durations in seconds from metadata logs."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name="queue_entry_completed"
    jsonPayload.event.payload.queue_entry.queue_duration:*
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "s"
  }

  value_extractor = "EXTRACT(jsonPayload.event.payload.queue_entry.queue_duration)"

  bucket_options {
    exponential_buckets {
      num_finite_buckets = 32
      growth_factor      = 2
      scale              = 1
    }
  }

  project = var.project_id
}

resource "google_logging_metric" "metadata_calls_va_sessions_ended" {
  name        = "ccaas_metadata_calls_va_sessions_ended"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of virtual agent sessions ended for calls from metadata logs labeled by finish reason, VA name, escalation reason, and call type."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name="virtual_agent_session_ended"
    jsonPayload.event.payload.call:*
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"

    labels {
      key         = "finish_reason"
      value_type  = "STRING"
      description = "Virtual agent session finish reason (e.g. unexpectedly_ended, consumer_ended, escalated, resolved)."
    }

    labels {
      key         = "virtual_agent_name"
      value_type  = "STRING"
      description = "Virtual agent name (e.g. Polysynth Agentic AI)."
    }

    labels {
      key         = "escalation_reason"
      value_type  = "STRING"
      description = "Reason for escalation if applicable."
    }

    labels {
      key         = "call_type"
      value_type  = "STRING"
      description = "Call channel type (e.g. Voice Inbound (IVR))."
    }
  }

  label_extractors = {
    "finish_reason"      = "EXTRACT(jsonPayload.event.payload.virtual_agent_session.finish_reason)"
    "virtual_agent_name" = "EXTRACT(jsonPayload.event.payload.virtual_agent.name)"
    "escalation_reason"  = "EXTRACT(jsonPayload.event.payload.virtual_agent_session.escalation_reason)"
    "call_type"          = "EXTRACT(jsonPayload.event.payload.call.type)"
  }

  project = var.project_id
}

resource "google_logging_metric" "metadata_calls_va_deflected" {
  name        = "ccaas_metadata_calls_va_deflected"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of virtual agent escalation deflections on calls from metadata logs labeled by deflection type, menu path, VA name, escalation reason, and call type."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name="virtual_agent_escalation_deflected"
    jsonPayload.event.payload.call:*
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"

    labels {
      key         = "deflection"
      value_type  = "STRING"
      description = "The deflection mechanism (e.g. temp_redirection_queue, after_hours_message_only)."
    }

    labels {
      key         = "menu_path"
      value_type  = "STRING"
      description = "Target menu path where the deflection was routed (e.g. Reroute to service selection)."
    }

    labels {
      key         = "virtual_agent_name"
      value_type  = "STRING"
      description = "Virtual agent name (e.g. Voice Agentic AI)."
    }

    labels {
      key         = "escalation_reason"
      value_type  = "STRING"
      description = "Reason for escalation (e.g. by_virtual_agent, unknown)."
    }

    labels {
      key         = "call_type"
      value_type  = "STRING"
      description = "Call channel type (e.g. Voice Inbound (IVR))."
    }
  }

  label_extractors = {
    "deflection"         = "EXTRACT(jsonPayload.event.payload.virtual_agent_deflected_escalation.deflection)"
    "menu_path"          = "EXTRACT(jsonPayload.event.payload.virtual_agent_deflected_escalation.menu_path)"
    "virtual_agent_name" = "EXTRACT(jsonPayload.event.payload.virtual_agent.name)"
    "escalation_reason"  = "EXTRACT(jsonPayload.event.payload.virtual_agent_deflected_escalation.escalation_reason)"
    "call_type"          = "EXTRACT(jsonPayload.event.payload.call.type)"
  }

  project = var.project_id
}
