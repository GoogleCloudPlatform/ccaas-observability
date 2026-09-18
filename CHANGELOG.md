## Upcoming / Unreleased

**New Features & Modules**
*   **GECX Observability Skills:** Added skills and automation tools for interacting with GECX environments.
    *   **Environment Discovery Skill (`skills/discover-gecx-environments`):** Automatically discovers CCaaS contact centers, Dialogflow CX agents, CX Agent Studio apps, and central log destinations across GCP projects via REST APIs, generating structured environment configurations (`gecx_environments.yaml`).
    *   **Log Query Skill (`skills/query-gecx-logs`):** Curated query templates and diagnostic workflows for analyzing CCaaS session lifecycles, virtual agent interactions, and error logs across Cloud Logging and BigQuery Log Analytics.
    *   **Environment Configuration Template:** Added `gecx_environments.yaml.sample` template for multi-environment deployments.

*   **CCaaS Platform Dashboard Module (`modules/platform_dashboard`):** Added a dedicated module and dashboard for monitoring CCaaS platform-level events.
    *   **CCaaS Version Updates Metric (`ccaas_version_updates`):** Added a log-based metric extracting target version and instance domain prefix from platform upgrade completion events.
    *   **Platform Updates Widgets:** Features a daily update count scorecard, a stacked bar chart of platform updates over time broken down by target version and instance domain prefix, and a Log Analytics (SQL) table widget for querying upgrade event details.

*   **Metadata Log-Based Dashboards & Metrics (`modules/metadata_calls_dashboard`, `modules/metadata_chats_dashboard`):** Added Cloud Monitoring dashboards and log-based metrics extracted directly from CCaaS metadata milestone logs.
    *   **Calls Monitoring (Metadata Logs):** Visualizes call volume over time (established, successful, transferred, abandoned, failed), queue wait durations (p50 and p95), current established call rate gauge, and virtual agent session completion breakdown (by finish reason and virtual agent).
    *   **Chats Monitoring (Metadata Logs):** Visualizes chat session volume over time (successful, escalated, abandoned, failed), transfer wait durations, current escalated chat rate gauge, and virtual agent session completion breakdown (by finish reason and virtual agent).
    *   **Abandonment & Failure Metrics Refinements:** Refined `ccaas_metadata_calls_abandoned` and `ccaas_metadata_chats_abandoned` metrics to capture abandonments via failure reasons (`eu_abandoned`, `eu_in_menu_abandoned`) and chat customer timeouts (`no_response`). Scoped failed call/chat dashboard widgets to exclude abandonments while retaining genuine end-user errors (such as `eu_no_answer`, `eu_busy`, `eu_wrong_number`).
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
