# CES Tracing Service

This folder contains the source code, build scripts, and unit test suites for the **CES Tracer** service. The service runs as a lightweight Cloud Run container triggered by Dialogflow `CompleteConversation` Cloud Audit Logs delivered by a Log Router sink and Pub/Sub push subscription (or direct HTTP invocation). When a conversation finishes, the service:

1. Resolves the target **CX Agent Studio (CES)** app either dynamically from the Dialogflow `ConversationProfile` (`automatedAgentConfig.agent`) or via static configuration overrides (`APP_CONFIGS`). Non-CES conversations (e.g., standard Dialogflow CX agents) are automatically skipped.
2. Fetches the completed CES conversation turns and nested spans from the CES v1 REST API (`ces.googleapis.com`).
3. Fetches correlated Cloud Logging entries for the session:
   * Dialogflow Cloud Audit Logs (`cloudaudit.googleapis.com%2Fdata_access`), grouping streaming operations (`BidiStreamingAnalyzeContent`) into operation spans and point events (`CreateConversation`, `CompleteConversation`) into short spans.
   * Dialogflow Telephony incoming call events (`dialogflow.googleapis.com%2Fincoming_call`, such as `connectCall` and `disconnectCall`).
   * CES response logs (`ces.googleapis.com%2Fresponses`) to enrich turn spans with `turn_completed` status and supervisor issue detections (`supervisor.has_issue`, `supervisor.detection[i].issue_type`, `supervisor.detection[i].details`).
4. Exports the reconstructed hierarchical trace to **Google Cloud Trace** (`cloudtrace.googleapis.com` v2 `BatchWriteSpans`).

---

## W3C `traceparent` Correlation with Downstream CES Tools

To enable end-to-end distributed tracing across CES Python tools and downstream HTTP services (such as Cloud Run microservices), `ces-tracer` uses deterministic hashing:

* **Trace ID (128-bit / 32 hex chars):** `MD5(session_id)`
* **Span ID (64-bit / 16 hex chars):** `SHA256(identifier)[:16]`
* **Tool Call Span ID:** When a CES tool span contains the attribute `"tool call id"`, its span ID is computed as `SHA256(tool_call_id)[:16]`. When CES Python tools inject the W3C header `traceparent: 00-{MD5(session_id)}-{SHA256(function_call_id)[:16]}-01` on outbound HTTP requests, Google Cloud Trace automatically parents the downstream Cloud Run HTTP spans directly under the corresponding CES Tool span.

---

## Directory Structure

* `src/`: The Python Flask application (`main.py`), transformation and correlation engine (`transform.py`), `Dockerfile`, and `requirements.txt`.
* `tests/`: Unit test suites for trace span transformation (`test_transform.py`) and event handling / ConversationProfile resolution / idempotency guard (`test_main.py`).
* `build_and_push.sh`: Build automation script to containerize and publish the service to Artifact Registry.

---

## How to Build and Push the Container Image

The Cloud Run service requires the container image to be hosted in an Artifact Registry repository. Use the provided [build_and_push.sh](./build_and_push.sh) script to build and push the container:

```bash
# Give execution permission to the script if not already done
chmod +x ces_tracing/build_and_push.sh

# Run the build script (uses Google Cloud Build by default)
./ces_tracing/build_and_push.sh <REGION> <PROJECT_ID> <REPOSITORY_NAME> <TAG>
```

To build locally using Docker instead of Cloud Build, append `--local`:

```bash
./ces_tracing/build_and_push.sh <REGION> <PROJECT_ID> <REPOSITORY_NAME> <TAG> --local
```

---

## Running Unit Tests

No external cloud dependencies are required to run the test suite locally. Run the tests from the repository root directory:

```bash
python3 -m unittest discover -s ces_tracing/tests -v
```

---

## Manual / On-Demand Invocation

In addition to handling Pub/Sub push envelopes (and Eventarc CloudEvents), the service also accepts direct JSON `POST` requests to trace or backfill a specific conversation session on demand:

```bash
curl -X POST "${CLOUD_RUN_URL}/" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "<SESSION_ID>",
    "project_id": "<CES_PROJECT_ID>",
    "location": "eu",
    "app_id": "<CES_APP_ID>"
  }'
```

By default (`SKIP_IF_TRACE_EXISTS=true`), the service skips conversations whose root span already exists in Cloud Trace. Add `"force": true` to the request body to re-trace a conversation anyway.

---

## Deploying the Service

To provision the Cloud Run service, Log Router sink, Pub/Sub topic and push subscription, service accounts, and IAM bindings, use the Terraform module in [`modules/ces_tracer/`](../modules/ces_tracer/README.md).
