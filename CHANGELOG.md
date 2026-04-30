## Pending Changes

**📈 Metric Enhancements (`modules/calls_dashboard/metrics.tf`)**
*   **Virtual Join Errors v2:** Added `ccaas_call_virtual_join_errors_v2` and `ccaas_chat_virtual_join_errors_v2` metrics to extract `virtual_agent_id` from logs.

**🖥 Dashboard Updates (`modules/errors_dashboard/main.tf`)**
*   **Virtual Join Errors by Agent ID:** Added two new widgets (13 and 14) to display call and chat virtual join errors grouped by `virtual_agent_id`.
*   **Documentation:** Updated the dashboard documentation to include the new charts.

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
