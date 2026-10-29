## Unreleased

**New Features & Modules**
*   **CXAS Tracer — PREVIEW (`ces_tracing`, `modules/ces_tracer`):** Added a Cloud Run service and Terraform module that rebuild completed **CX Agent Studio (CXAS)** conversations as hierarchical distributed traces in Google Cloud Trace.
    > **PREVIEW:** The CXAS Tracer is a preview feature. Its configuration surface, span structure, attribute names, and trace/span ID derivation may change in backwards-incompatible ways in future releases. Validate it in a non-production environment before relying on it. It is disabled by default (`enable_ces_tracer = false`).
    *   **Audit Log Delivery Pipeline:** A Log Router sink routes Dialogflow `Conversations.CompleteConversation` Data Access audit logs (`v2` and `v2beta1`) to a module-owned Pub/Sub topic and OIDC-authenticated push subscription. The ack deadline is configurable (`ack_deadline_seconds`, default 300s) and is also used as the Cloud Run request timeout. Eventarc audit-log triggers are intentionally not used: their managed subscription has a fixed 10s ack deadline, shorter than trace processing time, which causes endless redeliveries and duplicated spans.
    *   **CXAS App Resolution:** Resolves the target CXAS app dynamically from the Dialogflow ConversationProfile (`automatedAgentConfig.agent`), skipping non-CXAS agents, or from static `app_configs` mappings. Project numbers in agent references are converted to project IDs via Cloud Resource Manager, because Cloud Logging and Cloud Trace require project IDs.
    *   **Trace Reconstruction:** Builds a conversation root span with Dialogflow operation spans (`CreateConversation`, `CreateParticipant`, `BidiStreamingAnalyzeContent`/`AnalyzeContent`, `CompleteConversation`), Dialogflow Telephony `incoming_call` events, and per-turn CXAS spans (LLM, TTS, VAD, tools, callbacks, data store search). Turns are enriched with CXAS response log data (`turn_completed`, supervisor issue detections).
    *   **W3C Trace Context Correlation:** Uses deterministic IDs (Trace ID = `MD5(session_id)`, Span ID = `SHA-256[:16]`, tool spans keyed by `tool call id`) so downstream services called by CXAS Python tools with W3C `traceparent` headers can be correlated with the conversation trace.
    *   **Reliability:** Best-effort idempotency guard that skips writing when the conversation's root span already exists (`skip_if_trace_exists`, bypassable with `"force": true` for direct invocations). Non-retryable `400 InvalidArgument` / `BadRequest` responses from Cloud Trace are acknowledged (`HTTP 200`) to prevent retry loops, while retryable errors still return `HTTP 500`.
    *   **Privacy & Factory Compatibility:** Optional PII redaction of user utterances and sensitive span attributes (`redact_pii`). IAM bindings (including `roles/logging.privateLogViewer` for Data Access audit logs) and API enablement are gated by `grant_project_iam_roles` and `enable_apis`.

**Rollout & Upgrade Instructions**
*   **CXAS Tracer (optional, PREVIEW):** Enable Data Read / Data Write audit logs for `dialogflow.googleapis.com` in the Dialogflow project. Build and push the `ces-tracer` image using `ces_tracing/build_and_push.sh`, then set `enable_ces_tracer = true` and `ces_tracer.image_url`, and run `terraform apply`. See [`modules/ces_tracer/README.md`](modules/ces_tracer/README.md).
*   Existing deployments that do not enable the CXAS Tracer are unaffected.

---

## Release 2026-09.1

**Bug Fixes & Improvements**
*   **Metadata Logger Future Timestamp Handling & Retry Storm Prevention (`metadata_logging`):** Prevented infinite Eventarc/Pub/Sub retry loops (`400 Timestamp is over a day in the future`) when ingesting scheduled interactions or clock-skewed metadata exports.
    *   **Scheduled Milestone Timestamps (`call_scheduled`, `chat_scheduled`):** Updated `call_scheduled` and `chat_scheduled` milestone extraction to use `created_at` (when the interaction was scheduled, falling back to `scheduled_at` if absent) as the Cloud Logging entry timestamp, while preserving the target future appointment time in `details.scheduled_for`.
    *   **Future Timestamp Clamping:** Added defensive validation in `parse_timestamp` to clamp timestamps more than 23 hours in the future to the current UTC ingestion time (with a warning log) to satisfy Cloud Logging API limits.
    *   **Non-Retryable `400 Bad Request` Acknowledgment:** Narrowed Cloud Logging batch write error handling to acknowledge (`HTTP 200`) non-retryable `400 InvalidArgument` / `BadRequest` rejections so malformed payloads do not block the subscription queue, while continuing to return `HTTP 500` for retryable errors (`429 TooManyRequests`, `5xx`).

**Rollout & Upgrade Instructions**
*   Build and push a new `metadata-logger` container image using `metadata_logging/build_and_push.sh`, update `metadata_logger.image_url` in your Terraform configuration (or run `gcloud run services update`), and redeploy the Cloud Run service.

---

## Release 2026-09

**New Features & Modules**
*   **GECX Observability Skills:** Added skills and automation tools for interacting with GECX environments.
    *   **Environment Discovery Skill (`skills/discover-gecx-environments`):** Automatically discovers CCaaS contact centers, Dialogflow CX agents, Dialogflow Conversation Profiles, CX Agent Studio apps, Contact Center Insights (multi-location settings, conversation TTL, and summarization generators), and central log destinations across GCP projects via REST APIs, generating structured environment configurations (`gecx_environments.yaml`).
    *   **Log Query Skill (`skills/query-gecx-logs`):** Curated query templates and diagnostic workflows for analyzing CCaaS session lifecycles, Dialogflow Telephony (Phone Gateway and SIP Telephony Integration `incoming_call`) ingestion logs, virtual agent interactions, Contact Center Insights ingestion/update logs, cross-product correlation (CCaaS, Dialogflow Telephony, Dialogflow CX/CES, and Insights), and error logs across Cloud Logging and BigQuery Log Analytics.
    *   **Environment Configuration Template:** Added `gecx_environments.yaml.sample` template for multi-environment deployments.

*   **CCaaS Platform Dashboard Module (`modules/platform_dashboard`):** Added a dedicated module and dashboard for monitoring CCaaS platform-level events.
    *   **CCaaS Version Updates Metric (`ccaas_version_updates`):** Added a log-based metric extracting target version and instance domain prefix from platform upgrade completion events.
    *   **Platform Updates Widgets:** Features a daily update count scorecard, a stacked bar chart of platform updates over time broken down by target version and instance domain prefix, and a Log Analytics (SQL) table widget for querying upgrade event details.

*   **CCaaS Telemetry Milestone Logger Updates (`metadata_logging`):**
    *   **Virtual Agent Escalation Deflection Milestone (`virtual_agent_escalation_deflected`):** Added milestone extraction for virtual agent escalation deflections across calls and chats. Emits deflection details (e.g. deflection mechanism, target menu path, escalation reason) alongside virtual agent attributes and suppresses duplicate milestone emissions on subsequent metadata updates.
    *   **Chat Duration Extraction on `chat_ended`:** Fixed `chat_ended` milestone extraction to populate `details.chat_duration` from root chat metadata instead of `details.call_duration`, and updated the `chat_ended` log schema and documentation accordingly.
    *   **Agent Handle Indicators on `call_ended` and `chat_ended`:** Added `details.has_virtual_agent_handle` and `details.has_human_agent_handle` boolean flags to `call_ended` and `chat_ended` milestone events based on the presence of virtual agent and human agent handle durations.

*   **Metadata Log-Based Dashboards & Metrics (`modules/metadata_calls_dashboard`, `modules/metadata_chats_dashboard`):** Added Cloud Monitoring dashboards and log-based metrics extracted directly from CCaaS metadata milestone logs.
    *   **Calls Monitoring (Metadata Logs):** Visualizes call volume over time (established, successful, transferred, abandoned, failed), queue wait durations (p50 and p95), current established call rate gauge, and virtual agent session completion breakdown (by finish reason and virtual agent).
    *   **Chats Monitoring (Metadata Logs):** Visualizes chat session volume over time (successful, escalated, abandoned, failed), transfer wait durations, current escalated chat rate gauge, and virtual agent session completion breakdown (by finish reason and virtual agent).
    *   **Abandonment & Failure Metrics Refinements:** Refined `ccaas_metadata_calls_abandoned` and `ccaas_metadata_chats_abandoned` metrics to capture abandonments via failure reasons (`eu_abandoned`, `eu_in_menu_abandoned`) and chat customer timeouts (`no_response`). Scoped failed call/chat dashboard widgets to exclude abandonments while retaining genuine end-user errors (such as `eu_no_answer`, `eu_busy`, `eu_wrong_number`).
    *   **Virtual Agent Escalation Deflection Metrics & Dashboard Widgets:** Added `ccaas_metadata_calls_va_deflected` and `ccaas_metadata_chats_va_deflected` log-based metrics tracking `virtual_agent_escalation_deflected` events with labels for deflection mechanism, target menu path, virtual agent name, escalation reason, and channel type, alongside dashboard widgets visualizing deflection volume over time and breakdown by deflection mechanism.
    *   **Agent Handle Metrics & Dashboard Scorecards:** Added `ccaas_metadata_calls_va_handled`, `ccaas_metadata_calls_human_handled`, `ccaas_metadata_chats_va_handled`, and `ccaas_metadata_chats_human_handled` log-based metrics labeled by channel type (`call_type` / `chat_type`) and final interaction `status`, along with corresponding total volume scorecards on the Calls and Chats Metadata dashboards.
    *   **Configurable Ingestion:** Enabled conditionally via `var.enable_metadata_dashboards` with customizable log bucket, custom log name, and rate gauge upper bounds.

---

## Release 2026-05.1

**Bug Fixes & Improvements**
*   **Metadata Logger Duplicate Suppression:** Prevented duplicate milestone log generation caused by asynchronous CCaaS post-interaction metadata re-exports (e.g. wrap-up completion and CSAT survey submissions).
    *   **GCS State Tracking:** Added state marker tracking (`<bucket>/<object>.marker`) in a dedicated GCS bucket to definitively identify initial exports versus subsequent updates.
    *   **Heuristic Fallback:** Added automatic timestamp differential detection (`updated_at` vs `ends_at`) as a zero-dependency fallback when the state bucket is not configured.
    *   **Milestone Categorization:** Filtered out live-interaction milestones (`INITIAL_ONLY_MILESTONES`) on subsequent updates, preventing double-counting in downstream dashboards and metrics.
    *   **Stable `insertId`:** Excluded transient transport metadata (`gcs_source`) from the `insertId` hash computation to ensure robust log deduplication by Cloud Logging.
    *   **Terraform Module Support:** Added `state_bucket` input variable to `modules/metadata_logger` with automated bucket creation, lifecycle retention rules, and IAM permissions.

**Rollout & Upgrade Instructions**
*   Deploying this fix requires a two-step rollout:
    1. **Phase 1 (Bucket & Build):** Configure `state_bucket` in your Terraform inputs and run `terraform apply` to provision the state tracking bucket and IAM bindings. Next, build and push the new container image to Artifact Registry using `metadata_logging/build_and_push.sh`.
    2. **Phase 2 (Service Update):** Update `metadata_logger.image_url` to the new container image tag built in Phase 1, then run `terraform apply` again to deploy the Cloud Run service revision with the new image and state tracking enabled.

---

## Release 2026-05

**✨ New Features & Modules**
*   **CCaaS Telemetry Milestone Logger:** Added an automated GCS ingestion pipeline (Terraform module, Eventarc trigger, and Cloud Run service) to transform raw session metadata uploads into structured telemetry milestones. This brings call/chat interaction metrics that were previously locked in metadata files directly into Google Cloud Observability (Cloud Logging and Monitoring).
    *   **Consistently Matched Schemas:** The generated logs conform to a strict, well-defined schema (published under `metadata_logging/schema` and `docs`) where fields are consistently mapped to the same path, simplifying log-based metrics extraction.
    *   **Regression Testing & Paths Routing:** Includes a zero-dependency local regression test suite (`test_milestones.py`) using PII-redacted fixtures, and supports dynamic path-to-resource routing (`path_configs`) to handle multi-tenant setups.
    *   **Dashboards & Metrics:** Standardized log-based metrics and dashboards built on top of these milestone logs will be delivered in an upcoming release based on customer feedback.

**🙏 A shoutout to**
*   Our partners who generously provided sample CCaaS session metadata payloads to help us validate, generalize, and refine the milestone schemas!

---

## Release 2026-04

**✨ New Features & Modules**
*   **CCaaS Log Analytics Dashboard (`modules/analytics_dashboard`):** Added a new dashboard with 6 tables using Log Analytics (SQL) to trace interactions across CCaaS and Dialogflow.
    *   Widget 1: Interaction Aggregate Events Timeline.
    *   Widget 2: Interaction Mapping Table.
    *   Widget 3-6: Raw logs for CCaaS Activity, Events, DF Audit, and Runtime.
    *   Fully supports UI time-range selector by removing hardcoded time filters.

**🛠 Directory Restructuring**
*   Renamed `call_analysis` directory to `interaction_tracing` to be channel-neutral (supporting both calls and chats).
*   Created BigQuery versions of the SQL scripts in `interaction_tracing/bq/`.

**🐛 Bug Fixes & Improvements**
*   Fixed prefix bug in SQL scripts (`ccaip_events.sql`, etc.) where `call_` or `chat_` prefixes were duplicated.
*   Refactored `main.tf` in `analytics_dashboard` to use `jsonencode` and Heredoc for SQL queries to fix escaping issues and permanent diffs.

**📈 Metric Enhancements (`modules/calls_dashboard/metrics.tf`)**
*   **Virtual Join Errors v2:** Added `ccaas_call_virtual_join_errors_v2` and `ccaas_chat_virtual_join_errors_v2` metrics to extract `virtual_agent_id` from logs.

**🖥 Dashboard Updates (`modules/errors_dashboard/main.tf`)**
*   **Virtual Join Errors by Agent ID:** Added two new widgets (13 and 14) to display call and chat virtual join errors grouped by `virtual_agent_id`.
*   **Documentation:** Updated the dashboard documentation to include the new charts.

**🙏 A shoutout to**
*   **Bruno and Pranjal:** Thank you for all your support in bringing this toolkit to life!

## Release 2026-03

**✨ New Features & Modules**
*   **CCaaS Errors Dashboard (`modules/errors_dashboard`):** Added a comprehensive, fully managed dashboard dedicated to tracking failures across the platform. It features 13 structured widgets including:
    *   Topline scorecards for Calls Failed, Chats Failed, and Virtual Agent Errors.
    *   Join Error Breakdowns for both Calls and Chats (Total vs. Human vs. Virtual Agent).
    *   Rolling 5m and 60m Failure Ratios for Calls, Chats, and Virtual Agent (Streaming) errors using advanced MQL queries.
    *   A breakdown of Virtual Agent errors grouped by gRPC error type.
    *   A "1d Platform Trend" Prometheus chart tracking global failure ratio drift.
    *   A built-in Markdown widget explaining the entire dashboard layout.

**📈 Metric Enhancements (`modules/calls_dashboard/metrics.tf`)**
*   **`ccaas_streaming_errors_v2`:** Created a new, enriched streaming error metric that extracts `resource_id`, `location`, and `error_type` labels directly from the logs.
*   **`ccaas_va_errors` (Fixed):** Replaced the empty `ccaas_voice_platform_errors` metric with the correct filter (`"error in voice platform"`) and matching label extractors.
*   **Channel-Specific Join Errors:** Added 6 new granular metrics to replace generic join errors. These correctly filter on the `channel` payload field and are mapped to the logging bucket:
    *   `ccaas_call_participant_join_errors` & `ccaas_chat_participant_join_errors`
    *   `ccaas_call_human_join_errors` & `ccaas_chat_human_join_errors`
    *   `ccaas_call_virtual_join_errors` & `ccaas_chat_virtual_join_errors`

**🛠 Dashboard Updates (`modules/calls_dashboard/main.tf`)**
*   **Calls Monitoring:** Migrated the line charts on the primary Calls Dashboard to use the new, labeled `ccaas_streaming_errors_v2` metric.
