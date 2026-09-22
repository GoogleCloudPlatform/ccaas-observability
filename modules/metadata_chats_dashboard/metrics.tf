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

resource "google_logging_metric" "metadata_chats_created" {
  name        = "ccaas_metadata_chats_created"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of chat sessions created from metadata logs in the last minute labeled by chat type."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name="chat_created"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"

    labels {
      key         = "chat_type"
      value_type  = "STRING"
      description = "Chat channel type (e.g. Messaging Inbound (Web Chat))"
    }
  }

  label_extractors = {
    "chat_type" = "EXTRACT(jsonPayload.event.payload.chat.type)"
  }

  project = var.project_id
}

resource "google_logging_metric" "metadata_chats_successful" {
  name        = "ccaas_metadata_chats_successful"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of successfully finished chats from metadata logs in the last minute."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name="chat_ended"
    jsonPayload.event.payload.chat.status="finished"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  project = var.project_id
}

resource "google_logging_metric" "metadata_chats_escalated" {
  name        = "ccaas_metadata_chats_escalated"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of escalated/transferred chats from metadata logs in the last minute."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name=("session_transfer_started" OR "chat_queued")
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  project = var.project_id
}

resource "google_logging_metric" "metadata_chats_abandoned" {
  name        = "ccaas_metadata_chats_abandoned"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of abandoned chats from metadata logs in the last minute."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name="chat_ended"
    (jsonPayload.event.payload.chat.status="abandoned" OR jsonPayload.event.payload.chat.status="no_response" OR jsonPayload.event.payload.details.fail_reason:"abandoned")
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  project = var.project_id
}

resource "google_logging_metric" "metadata_chats_failed" {
  name        = "ccaas_metadata_chats_failed"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of failed chats from metadata logs in the last minute."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name="chat_ended"
    jsonPayload.event.payload.chat.status="failed"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"

    labels {
      key         = "fail_reason"
      value_type  = "STRING"
      description = "The failure reason assigned by CCaaS (e.g. force_ended, customer_timeout)."
    }

    labels {
      key         = "disconnected_by"
      value_type  = "STRING"
      description = "The entity that disconnected the chat (e.g. disconnected_by_end_user, agent, virtual_agent)."
    }

    labels {
      key         = "chat_type"
      value_type  = "STRING"
      description = "Chat channel type (e.g. Messaging Inbound (Web Chat))."
    }
  }

  label_extractors = {
    "fail_reason"     = "EXTRACT(jsonPayload.event.payload.details.fail_reason)"
    "disconnected_by" = "EXTRACT(jsonPayload.event.payload.details.disconnected_by)"
    "chat_type"       = "EXTRACT(jsonPayload.event.payload.chat.type)"
  }

  project = var.project_id
}

resource "google_logging_metric" "metadata_chat_wait_duration" {
  name        = "ccaas_metadata_chat_wait_duration"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Distribution of chat queue wait durations in seconds before transfer connection."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name="session_transfer_connected"
    jsonPayload.event.payload.transfer.wait_duration:*
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "s"
  }

  value_extractor = "EXTRACT(jsonPayload.event.payload.transfer.wait_duration)"

  bucket_options {
    exponential_buckets {
      num_finite_buckets = 32
      growth_factor      = 2
      scale              = 1
    }
  }

  project = var.project_id
}

resource "google_logging_metric" "metadata_chats_va_sessions_ended" {
  name        = "ccaas_metadata_chats_va_sessions_ended"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of virtual agent sessions ended for chats from metadata logs labeled by finish reason, VA name, escalation reason, and chat type."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name="virtual_agent_session_ended"
    jsonPayload.event.payload.chat:*
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
      description = "Virtual agent name (e.g. Chat Agentic AI)."
    }

    labels {
      key         = "escalation_reason"
      value_type  = "STRING"
      description = "Reason for escalation if applicable."
    }

    labels {
      key         = "chat_type"
      value_type  = "STRING"
      description = "Chat channel type (e.g. Messaging Inbound (Web Chat))."
    }
  }

  label_extractors = {
    "finish_reason"      = "EXTRACT(jsonPayload.event.payload.virtual_agent_session.finish_reason)"
    "virtual_agent_name" = "EXTRACT(jsonPayload.event.payload.virtual_agent.name)"
    "escalation_reason"  = "EXTRACT(jsonPayload.event.payload.virtual_agent_session.escalation_reason)"
    "chat_type"          = "EXTRACT(jsonPayload.event.payload.chat.type)"
  }

  project = var.project_id
}

resource "google_logging_metric" "metadata_chats_va_deflected" {
  name        = "ccaas_metadata_chats_va_deflected"
  bucket_name = "projects/${var.project_id}/locations/${var.log_bucket.location}/buckets/${var.log_bucket.name}"
  description = "Number of virtual agent escalation deflections on chats from metadata logs labeled by deflection type, menu path, VA name, escalation reason, and chat type."
  filter      = <<-EOT
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    logName:"/logs/${var.custom_log_name}"
    jsonPayload.event.name="virtual_agent_escalation_deflected"
    jsonPayload.event.payload.chat:*
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
      description = "Target menu path where the deflection was routed."
    }

    labels {
      key         = "virtual_agent_name"
      value_type  = "STRING"
      description = "Virtual agent name (e.g. Chat Agentic AI)."
    }

    labels {
      key         = "escalation_reason"
      value_type  = "STRING"
      description = "Reason for escalation (e.g. by_virtual_agent, unknown)."
    }

    labels {
      key         = "chat_type"
      value_type  = "STRING"
      description = "Chat channel type (e.g. Messaging Inbound (Web Chat))."
    }
  }

  label_extractors = {
    "deflection"         = "EXTRACT(jsonPayload.event.payload.virtual_agent_deflected_escalation.deflection)"
    "menu_path"          = "EXTRACT(jsonPayload.event.payload.virtual_agent_deflected_escalation.menu_path)"
    "virtual_agent_name" = "EXTRACT(jsonPayload.event.payload.virtual_agent.name)"
    "escalation_reason"  = "EXTRACT(jsonPayload.event.payload.virtual_agent_deflected_escalation.escalation_reason)"
    "chat_type"          = "EXTRACT(jsonPayload.event.payload.chat.type)"
  }

  project = var.project_id
}
