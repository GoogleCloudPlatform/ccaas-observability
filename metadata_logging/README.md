# Metadata Logging Service

This folder contains the source code, build scripts, and test suites for the Metadata Logger service. The service is designed to run in a Cloud Run container, receiving Google Cloud Storage (GCS) upload events via Eventarc or Pub/Sub, extracting contact center milestones from metadata JSONs, and writing formatted milestone log entries back to Google Cloud Logging.

---

## Directory Structure

*   `src/`: The Python Flask app (`main.py`) and log transformation logic (`transform.py`).
*   `tests/`: Regression test suites (`test_milestones.py`) and test fixtures/expected logs (`fixtures/`).
*   `build_and_push.sh`: Build automation script to containerize and publish the service to Artifact Registry.

---

## How to Build and Push the Container Image

The Cloud Run service requires the container image to be hosted in an Artifact Registry repository. Use the provided [build_and_push.sh](./build_and_push.sh) script to build and push the container:

```bash
# Give execution permission to the script if not already done
chmod +x metadata_logging/build_and_push.sh

# Run the build script
./metadata_logging/build_and_push.sh <REGION> <PROJECT_ID> <REPOSITORY_NAME> <TAG>
```

By default, Google Cloud Build is used to build the image remotely. To build locally using Docker instead, append `--local`:
```bash
./metadata_logging/build_and_push.sh <REGION> <PROJECT_ID> <REPOSITORY_NAME> <TAG> --local
```

---

## Running Regression Tests

The project includes a regression test suite to ensure milestone extraction works correctly and does not break on future metadata structure updates. The tests compare generated log payloads against pre-approved expected log JSONs.

No extra dependencies are required. Run the tests from the project root directory:

```bash
python3 metadata_logging/tests/test_milestones.py
```

Or using standard Python test discovery:
```bash
python3 -m unittest discover -s metadata_logging/tests
```

---

## Deploying the Service

To automate the GCS buckets, Eventarc triggers, Cloud Run service, and IAM policies, use the provided Terraform module.

For detailed instructions and parameter guides, see the [Metadata Logger Terraform Module README](../modules/metadata_logger/README.md).

---

## Telemetry Milestone Reference (Schemas and Docs)

The logger processes raw metadata JSON into structured, discrete telemetry milestones. Below is a complete index of all event milestone schemas and reference docs:

| Event Name | Call Telemetry Links | Chat Telemetry Links |
| :--- | :--- | :--- |
| `agent_handle_completed` | [Schema](./schema/call/agent_handle_completed_log_schema.json) / [Docs](./docs/call/agent_handle_completed_log_schema.md) | [Schema](./schema/chat/agent_handle_completed_log_schema.json) / [Docs](./docs/chat/agent_handle_completed_log_schema.md) |
| `agent_handle_started` | [Schema](./schema/call/agent_handle_started_log_schema.json) / [Docs](./docs/call/agent_handle_started_log_schema.md) | [Schema](./schema/chat/agent_handle_started_log_schema.json) / [Docs](./docs/chat/agent_handle_started_log_schema.md) |
| `call_assigned` | [Schema](./schema/call/call_assigned_log_schema.json) / [Docs](./docs/call/call_assigned_log_schema.md) | N/A |
| `call_connected` | [Schema](./schema/call/call_connected_log_schema.json) / [Docs](./docs/call/call_connected_log_schema.md) | N/A |
| `call_created` | [Schema](./schema/call/call_created_log_schema.json) / [Docs](./docs/call/call_created_log_schema.md) | N/A |
| `call_ended` | [Schema](./schema/call/call_ended_log_schema.json) / [Docs](./docs/call/call_ended_log_schema.md) | N/A |
| `call_queued` | [Schema](./schema/call/call_queued_log_schema.json) / [Docs](./docs/call/call_queued_log_schema.md) | N/A |
| `call_scheduled` | [Schema](./schema/call/call_scheduled_log_schema.json) / [Docs](./docs/call/call_scheduled_log_schema.md) | N/A |
| `call_updated` | [Schema](./schema/call/call_updated_log_schema.json) / [Docs](./docs/call/call_updated_log_schema.md) | N/A |
| `chat_assigned` | N/A | [Schema](./schema/chat/chat_assigned_log_schema.json) / [Docs](./docs/chat/chat_assigned_log_schema.md) |
| `chat_created` | N/A | [Schema](./schema/chat/chat_created_log_schema.json) / [Docs](./docs/chat/chat_created_log_schema.md) |
| `chat_ended` | N/A | [Schema](./schema/chat/chat_ended_log_schema.json) / [Docs](./docs/chat/chat_ended_log_schema.md) |
| `chat_updated` | N/A | [Schema](./schema/chat/chat_updated_log_schema.json) / [Docs](./docs/chat/chat_updated_log_schema.md) |
| `consumer_handle_ended` | [Schema](./schema/call/consumer_handle_ended_log_schema.json) / [Docs](./docs/call/consumer_handle_ended_log_schema.md) | [Schema](./schema/chat/consumer_handle_ended_log_schema.json) / [Docs](./docs/chat/consumer_handle_ended_log_schema.md) |
| `consumer_handle_started` | [Schema](./schema/call/consumer_handle_started_log_schema.json) / [Docs](./docs/call/consumer_handle_started_log_schema.md) | [Schema](./schema/chat/consumer_handle_started_log_schema.json) / [Docs](./docs/chat/consumer_handle_started_log_schema.md) |
| `consumer_in_menu_ended` | [Schema](./schema/call/consumer_in_menu_ended_log_schema.json) / [Docs](./docs/call/consumer_in_menu_ended_log_schema.md) | N/A |
| `consumer_in_menu_started` | [Schema](./schema/call/consumer_in_menu_started_log_schema.json) / [Docs](./docs/call/consumer_in_menu_started_log_schema.md) | N/A |
| `csat_session_completed` | [Schema](./schema/call/csat_session_completed_log_schema.json) / [Docs](./docs/call/csat_session_completed_log_schema.md) | [Schema](./schema/chat/csat_session_completed_log_schema.json) / [Docs](./docs/chat/csat_session_completed_log_schema.md) |
| `csat_session_started` | [Schema](./schema/call/csat_session_started_log_schema.json) / [Docs](./docs/call/csat_session_started_log_schema.md) | [Schema](./schema/chat/csat_session_started_log_schema.json) / [Docs](./docs/chat/csat_session_started_log_schema.md) |
| `participant_connected` | [Schema](./schema/call/participant_connected_log_schema.json) / [Docs](./docs/call/participant_connected_log_schema.md) | [Schema](./schema/chat/participant_connected_log_schema.json) / [Docs](./docs/chat/participant_connected_log_schema.md) |
| `participant_left` | [Schema](./schema/call/participant_left_log_schema.json) / [Docs](./docs/call/participant_left_log_schema.md) | N/A |
| `queue_entry_completed` | [Schema](./schema/call/queue_entry_completed_log_schema.json) / [Docs](./docs/call/queue_entry_completed_log_schema.md) | [Schema](./schema/chat/queue_entry_completed_log_schema.json) / [Docs](./docs/chat/queue_entry_completed_log_schema.md) |
| `queue_entry_started` | [Schema](./schema/call/queue_entry_started_log_schema.json) / [Docs](./docs/call/queue_entry_started_log_schema.md) | [Schema](./schema/chat/queue_entry_started_log_schema.json) / [Docs](./docs/chat/queue_entry_started_log_schema.md) |
| `recording_started` | [Schema](./schema/call/recording_started_log_schema.json) / [Docs](./docs/call/recording_started_log_schema.md) | N/A |
| `session_transfer_connected` | [Schema](./schema/call/session_transfer_connected_log_schema.json) / [Docs](./docs/call/session_transfer_connected_log_schema.md) | [Schema](./schema/chat/session_transfer_connected_log_schema.json) / [Docs](./docs/chat/session_transfer_connected_log_schema.md) |
| `session_transfer_started` | [Schema](./schema/call/session_transfer_started_log_schema.json) / [Docs](./docs/call/session_transfer_started_log_schema.md) | [Schema](./schema/chat/session_transfer_started_log_schema.json) / [Docs](./docs/chat/session_transfer_started_log_schema.md) |
| `virtual_agent_escalation_deflected` | [Schema](./schema/call/virtual_agent_escalation_deflected_log_schema.json) / [Docs](./docs/call/virtual_agent_escalation_deflected_log_schema.md) | [Schema](./schema/chat/virtual_agent_escalation_deflected_log_schema.json) / [Docs](./docs/chat/virtual_agent_escalation_deflected_log_schema.md) |
| `virtual_agent_session_ended` | [Schema](./schema/call/virtual_agent_session_ended_log_schema.json) / [Docs](./docs/call/virtual_agent_session_ended_log_schema.md) | [Schema](./schema/chat/virtual_agent_session_ended_log_schema.json) / [Docs](./docs/chat/virtual_agent_session_ended_log_schema.md) |
| `virtual_agent_session_started` | [Schema](./schema/call/virtual_agent_session_started_log_schema.json) / [Docs](./docs/call/virtual_agent_session_started_log_schema.md) | [Schema](./schema/chat/virtual_agent_session_started_log_schema.json) / [Docs](./docs/chat/virtual_agent_session_started_log_schema.md) |
