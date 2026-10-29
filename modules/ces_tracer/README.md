# CXAS Tracer Terraform Module

This module deploys the **CXAS Tracer** (`ces-tracer`) — a lightweight, secure Cloud Run service (written in Python) and a Log Router sink → Pub/Sub push delivery pipeline inside a Dialogflow / **CX Agent Studio (CXAS)** project. Whenever a conversation finishes and emits a `google.cloud.dialogflow.v2beta1.Conversations.CompleteConversation` audit log, the service automatically resolves the associated CXAS App, retrieves the conversation turns and spans via the Customer Engagement Suite (CES) v1 REST API (`ces.googleapis.com`), correlates Dialogflow audit logs, `incoming_call` logs, and `ces.googleapis.com%2Fresponses` logs, and exports the reconstructed hierarchical trace to **Google Cloud Trace**.

---

## Architecture Design

1. **Log Router Sink → Pub/Sub Push Delivery:** A Log Router sink routes Dialogflow Data Access audit log entries matching `protoPayload.serviceName = "dialogflow.googleapis.com"` and `protoPayload.methodName:"Conversations.CompleteConversation"` (both `v2` and `v2beta1`) to a module-owned Pub/Sub topic. A module-owned push subscription (OIDC-authenticated) delivers each entry to Cloud Run with a configurable ack deadline (`ack_deadline_seconds`, default 300s), which is also used as the Cloud Run request timeout.
   > **Why not Eventarc?** Eventarc audit-log triggers deliver through an Eventarc-managed Pub/Sub subscription with a fixed 10s ack deadline that isn't configurable from Terraform. Building a trace takes longer than 10s (several Logging/CES API calls), so Pub/Sub treats every response, even HTTP 200, as a nack and redelivers the event repeatedly for up to 24 hours, duplicating spans.
   > **Idempotency:** Pub/Sub delivery is at-least-once. With `skip_if_trace_exists = true` (default), the service checks Cloud Trace for the conversation's root span before writing and skips if it's already there. Cloud Trace writes take a few seconds to become readable, so the guard is best-effort: near-simultaneous duplicates can still be written. Direct invocations can pass `"force": true` to re-trace.
2. **Dynamic CXAS App Resolution:** By default, the service inspects `protoPayload.response.conversationProfile` from the `CompleteConversation` audit event, queries the Dialogflow `ConversationProfile` API (`automatedAgentConfig.agent`), and dynamically resolves the CXAS project, location, and app ID (`projects/{project}/locations/{location}/apps/{app}`). If the profile points to a non-CXAS agent (such as a standard Dialogflow CX agent), the service safely skips it. You can also provide static overrides or fallback mappings via `app_configs`.
3. **W3C `traceparent` Correlation:** Uses `MD5(session_id)` for the 128-bit Trace ID and `SHA256(tool_call_id)[:16]` for CXAS Tool spans so that downstream Cloud Run services invoked by CXAS Python tools with W3C `traceparent` headers automatically appear as child spans under the corresponding CXAS Tool span in Cloud Trace.

---

## Prerequisites

1. **Container Image:** Before deploying the Terraform resources, build and push the Cloud Run container image to Artifact Registry. See the [CXAS Tracing Service README](../../ces_tracing/README.md) for instructions.
2. **Dialogflow Data Access Audit Logs:** The `CompleteConversation` delivery pipeline and the Dialogflow operation spans require **Data Read / Data Write** Cloud Audit Logs to be enabled for `dialogflow.googleapis.com` in the target project (`IAM & Admin > Audit Logs > Dialogflow API`). Review the cost and privacy considerations below before enabling them.

---

## Cost & Privacy Considerations

> **Warning:** Review these with the data owner before enabling the CXAS Tracer, even in non-production projects.

* **Audit log volume and cost:** Data Read / Data Write audit logs apply to **all** Dialogflow API calls in the project, not only those of traced conversations. Streaming methods such as `BidiStreamingAnalyzeContent` and `AnalyzeContent` can produce a large number of entries per conversation, which increases Cloud Logging ingestion and storage cost. Consider adding [exclusion filters](https://cloud.google.com/logging/docs/routing/overview#exclusions) on the `_Default` sink for entries the tracer does not need, and estimate the impact on a representative traffic sample first.
* **Conversation content in logs:** Dialogflow Data Access audit logs can contain request/response payloads, including end-user utterances and agent responses. They are retained according to the destination log bucket's retention policy (30 days for `_Default` by default) and are readable by anyone with `roles/logging.privateLogViewer` on the project.
* **Conversation content in Cloud Trace:** By default (`redact_pii = true`), user utterances are omitted from turn span display names, and span attributes with known sensitive keys (e.g. `user_input`, `input`, `output`, `text`, `transcript`, `utterance`, `phone_number`, `email`, `request_body`, `response_body`) and supervisor detection details are replaced with `<REDACTED>`. Redaction is best-effort and key-based: PII inside other fields (for example tool arguments under different key names, or nested more than one level deep in JSON values) may still be written. Setting `redact_pii = false` writes utterances and full attribute values to Cloud Trace, visible to anyone with Cloud Trace read access (e.g. `roles/cloudtrace.user`) on the trace project; only do this if all of them may see conversation content. Cloud Trace retains spans for 30 days.

---

## Quick Start Guide

### 1. Configure Terraform Inputs
Add the following configuration in your root `terraform.tfvars` or `project.auto.tfvars`:

```hcl
enable_ces_tracer = true

ces_tracer = {
  project_id = "my-ces-project"
  region     = "europe-west1"
  image_url  = "europe-west1-docker.pkg.dev/my-ces-project/my-repo/ces-tracer:latest"
}
```

Or with optional static `app_configs` overrides:

```hcl
enable_ces_tracer = true

ces_tracer = {
  project_id = "my-ces-project"
  region     = "europe-west1"
  image_url  = "europe-west1-docker.pkg.dev/my-ces-project/my-repo/ces-tracer:latest"

  app_configs = [
    {
      conversation_profile = "*"
      ces_location         = "eu"
      ces_app_id           = "weather-eu"
    }
  ]
}
```

### 2. Apply the Terraform Configuration
```bash
terraform init
terraform apply
```

---

## Inputs

| Name | Type | Description | Default | Required |
| :--- | :--- | :--- | :--- | :--- |
| **project_id** | `string` | The Google Cloud project ID hosting Dialogflow/CXAS, the Log Router sink, Pub/Sub, and the Cloud Run service. | n/a | **yes** |
| **region** | `string` | The region to deploy the Cloud Run service. | `"us-central1"` | no |
| **image_url** | `string` | The container image path in Artifact Registry. | n/a | **yes** |
| **trace_project_id** | `string` | Optional target Google Cloud project ID where Cloud Trace spans are written. Defaults to the resolved CXAS project ID or `project_id`. | `null` | no |
| **app_configs** | `list(object)` | Optional static mappings from Dialogflow ConversationProfile to target CXAS App configurations (`conversation_profile`, `ces_project_id`, `ces_location`, `ces_app_id`, `trace_project_id`). | `[]` | no |
| **ack_deadline_seconds** | `number` | Ack deadline of the Pub/Sub push subscription (10–600), also used as the Cloud Run request timeout. Must exceed end-to-end trace processing time. | `300` | no |
| **skip_if_trace_exists** | `bool` | Skip writing spans if the conversation's root span already exists in Cloud Trace (best-effort idempotency). | `true` | no |
| **redact_pii** | `bool` | Whether to redact user utterances in turn span display names and sensitive PII fields in span attributes (best-effort, key-based). | `true` | no |
| **initial_delay_seconds** | `number` | Number of seconds to wait before querying Cloud Logging so final conversation log entries are indexed. | `2` | no |
| **grant_project_iam_roles** | `bool` | Whether to let the module automatically create project-level IAM role bindings. | `true` | no |
| **enable_apis** | `bool` | Whether to let the module automatically enable necessary Google Cloud service APIs. | `true` | no |
| **service_name** | `string` | The name of the Cloud Run service and prefix for related resources (max 20 chars). | `"ces-tracer"` | no |

## Outputs

| Name | Description |
| :--- | :--- |
| **cloud_run_url** | The HTTP endpoint URL of the deployed CXAS Tracer Cloud Run service. |
| **runtime_service_account_email** | The email of the Cloud Run runtime service account. |
| **trigger_service_account_email** | The email of the Pub/Sub push invoker service account. |
| **pubsub_topic** | The Pub/Sub topic receiving Dialogflow CompleteConversation audit log entries. |
| **pubsub_subscription** | The Pub/Sub push subscription delivering events to the CXAS Tracer service. |
| **log_sink_writer_identity** | The writer identity of the Log Router sink. |

---

## Project-Level IAM Roles Management (Project Factory Compatibility)

If you set `grant_project_iam_roles = false`, the module will skip provisioning IAM role bindings. You must externally grant:

1. **Cloud Run Runtime Service Account (`${service_name}-run-sa@<PROJECT_ID>.iam.gserviceaccount.com`):**
   * `roles/logging.viewer` on the Dialogflow/CXAS project(s)
   * `roles/logging.privateLogViewer` on the Dialogflow/CXAS project(s) (required to read Data Access audit logs)
   * `roles/dialogflow.reader` on the Dialogflow project
   * `roles/ces.viewer` on the CXAS project(s)
   * `roles/cloudtrace.agent` on the target Trace project(s)
   * `roles/cloudtrace.user` on the target Trace project(s) (idempotency guard reads existing traces)
2. **Pub/Sub Push Invoker Service Account (`${service_name}-trigger-sa@<PROJECT_ID>.iam.gserviceaccount.com`):**
   * `roles/run.invoker` on the Cloud Run service
3. **Log Router Sink Writer Identity (output `log_sink_writer_identity`):**
   * `roles/pubsub.publisher` on the module's Pub/Sub topic

---

## Service API Enablement (Project Factory Compatibility)

If you set `enable_apis = false`, ensure the following APIs are enabled beforehand in `project_id`:

* `run.googleapis.com`
* `cloudresourcemanager.googleapis.com`
* `logging.googleapis.com`
* `cloudtrace.googleapis.com`
* `ces.googleapis.com`
* `dialogflow.googleapis.com`
* `pubsub.googleapis.com`
