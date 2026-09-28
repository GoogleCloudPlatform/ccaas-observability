# GECX Advanced Logging Recipes & Cookbook

This reference provides advanced, deep-dive query recipes for **GECX (CCaaS, Dialogflow CX, and CES / CX Agent Studio)**. For environment discovery and standard product log streams, see [SKILL.md](../SKILL.md).

---

## 1. Cross-Product Interaction Correlation

In end-to-end customer journeys, interactions traverse CCaaS, Dialogflow virtual agents, and generative CES agents. Correlate across these streams using specific link keys:

### A. Correlating CCaaS Interactions to Dialogflow CX / CES via Conversation Profiles

CCaaS (UJet) does not map directly to a Dialogflow CX agent. Instead, CCaaS maps internally to a **Virtual Agent Platform** configuration (represented in CCaaS metadata as `virtual_agent.name` UUID, e.g. `544cf1cb-7351-48e0-8a55-64e6d422b2a1` and ID `1`). That integration targets a Dialogflow `v2beta1` **Conversation Profile** resource, which in turn configures the target Dialogflow CX agent (`automatedAgentConfig.agent`) or CES app.

1. **Find the Dialogflow conversation created event in CCaaS**:
   When CCaaS hands off to a Virtual Agent, it emits an event containing the Dialogflow conversation ID:
   ```bash
   gcloud logging read 'resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
   labels.tracker_id="<TRACKER_ID>"
   logName:"contactcenteraiplatform.googleapis.com%2Fevents"
   jsonPayload.event.name="dialogflow_conversation_created"' \
     --project="<LOGS_PROJECT_ID>" \
     --format="value(jsonPayload.event.payload.participant.df_conversation_id)"
   ```
   *(Or inspect raw metadata JSON in GCS under `participants[].virtual_agent.conversation_id`)*

2. **Correlate with Dialogflow Audit Logs to resolve the Conversation Profile**:
   Dialogflow logs the conversation creation and target conversation profile:
   ```bash
   gcloud logging read 'logName:"cloudaudit.googleapis.com%2Fdata_access"
   protoPayload.methodName="google.cloud.dialogflow.v2beta1.Conversations.CreateConversation"
   "<DF_CONVERSATION_ID>"' \
     --project="<LOGS_PROJECT_ID>" \
     --format="yaml(protoPayload.response.conversationProfile)"
   ```
   Cross-reference the returned profile with `conversation_profiles` in `gecx_environments.yaml` to identify the human-readable profile name and target agent.

3. **Query the corresponding Dialogflow runtime turns**:
   Using the session ID (which matches the conversation ID for single-session interactions) or filtering by agent ID:
   ```bash
   gcloud logging read 'logName:"dialogflow-runtime.googleapis.com%2Frequests"
   labels.session_id="<DF_CONVERSATION_ID>"' \
     --project="<LOGS_PROJECT_ID>" \
     --format=json
   ```

### B. Correlating CCaaS with CRM / Third-Party Webhooks
Extract CRM integration calls and external webhook payloads by `tracker_id`:
```bash
gcloud logging read 'resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
labels.tracker_id="<TRACKER_ID>"
logName:"contactcenteraiplatform.googleapis.com%2Factivity"
jsonPayload.message:"CRM"' \
  --project="<LOGS_PROJECT_ID>" \
  --format=json
```

### C. Correlating CCaaS, Dialogflow CX / CES, and Contact Center Insights

When a customer interaction traverses both a Virtual Agent (Dialogflow CX / CES) and CCaaS, **two separate Insights Conversation resources are created** (often in different Insights locations within the same GCP project). They are **not** merged into a single Insights record; instead, the CCaaS-uploaded conversation references the Virtual Agent conversation via a foreign-key label (`labels.dialogflow_conversation_id_1`):

1. **Virtual Agent Insights Conversation (`conversations/<SESSION_ID>`, e.g. in `locations/us`)**: Created in real time (`21:23:47Z`) directly by the Dialogflow CX agent or CES app in its own location. Captures the automated virtual agent turns and runtime annotations.
2. **CCaaS Insights Conversation (`conversations/call-<ID>` or `chat-<ID>`, e.g. in `locations/us-central1`)**: Created **after** the interaction ends (`21:27:10Z`) when `ccai-insights-sa` calls `UploadConversation` with `conversationId="chat-<ID>"`. Captures the full CCaaS transcript/recording from GCS (`gs://.../chat-<ID>.json`) and stores `labels.dialogflow_conversation_id_1="<SESSION_ID>"` pointing to the Virtual Agent Insights conversation.

#### Path 1: Direct Dialogflow CX / CES Runtime Conversation (Matches Agent/App Location, e.g. `locations/us`) — **1:1 ID Match**
When `loggingSettings.conversationLoggingSettings` is enabled on a CES app (or Insights export is enabled on a Dialogflow agent/Conversation Profile), the agent/app **directly creates its own conversation in Contact Center Insights in its own `<LOCATION>`** (e.g., a CES app in `locations/us` writes to Insights `locations/us`).
* **Insights Location**: Matches the Dialogflow agent or CES app's `location` (e.g., `locations/us`).
* **Insights Conversation ID**: Identical to the Dialogflow Conversation ID / CES `labels.session_id` (`conversations/<SESSION_ID>`).
* **Insights `agentId`**: Matches the CES `labels.app_id` (or Dialogflow `agent_id`).

1. **Find the `session_id` (or `df_conversation_id`) in CES / Dialogflow / CCaaS logs**:
   ```bash
   gcloud logging read 'logName:"ces.googleapis.com%2Fresponses"
   labels.session_id="<SESSION_ID>"' \
     --project="<LOGS_PROJECT_ID>" \
     --limit=5 \
     --format="table(timestamp,labels.app_id,labels.session_id,jsonPayload.diagnosticInfo.rootSpan.attributes.user\ audio\ uri)"
   ```
   *(Note: For voice calls handed off from CCaaS, CES logs also record `ccaasCallId` / `call_id_str` inside `BeforeModel` callback attributes.)*

2. **Inspect the corresponding Insights Conversation directly using `<SESSION_ID>`**:
   ```bash
   curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
     -H "X-goog-user-project: <PROJECT_ID>" \
     "https://<INSIGHTS_LOCATION>-contactcenterinsights.googleapis.com/v1/projects/<PROJECT_ID>/locations/<INSIGHTS_LOCATION>/conversations/<SESSION_ID>" \
     | jq '{name, agentId, medium, dataSource, labels, latestSummary, runtimeAnnotations: (.runtimeAnnotations | length)}'
   ```

#### Path 2: CCaaS Post-Interaction Upload (e.g. `locations/us-central1`) — **Structured Bridge via `conversationId` & `labels`**
When CCaaS (`ccai-insights-sa`, `Ruby` client) uploads completed calls or chats via `UploadConversation`, it converts the CCaaS `labels.tracker_id` from underscore (`call_<ID>` / `chat_<ID>`) to hyphen (`call-<ID>` / `chat-<ID>`) and populates **structured correlation labels** on the Insights Conversation resource that link CCaaS, Dialogflow/CES, and CRM tickets together:

| System / Resource | Structured Correlation Field | Example Value (`chat_5580`) |
| :--- | :--- | :--- |
| **CCaaS Event Logs** (`%2Fevents`) | `labels.tracker_id`<br>`jsonPayload.event.payload.participant.df_conversation_id` | `"chat_5580"`<br>`"119DaI5v0mCR1ywyTMSEjg0gw"` |
| **Insights `UploadConversation` Audit Log** | `protoPayload.request.conversationId`<br>*(Note: `protoPayload.resourceName` is the parent location, NOT the conversation path)* | `"chat-5580"` |
| **Insights `Get`/`UpdateConversation` Audit Log** | `protoPayload.resourceName` | `".../locations/us-central1/conversations/chat-5580"` |
| **Insights Conversation Resource (`labels`)** | `labels.id` (CCaaS numeric ID)<br>`labels.dialogflow_conversation_id_1` (DF / CES Session ID)<br>`labels.out_ticket_id` (CRM / Salesforce Case ID) | `"5580"`<br>`"119DaI5v0mCR1ywyTMSEjg0gw"`<br>`"500DF00000PTvCiYAL"` |

1. **Trace the Insights `UploadConversation` / `UpdateConversation` audit logs by structured `conversationId`**:
   ```bash
   gcloud logging read 'protoPayload.serviceName="contactcenterinsights.googleapis.com"
   (protoPayload.request.conversationId="chat-<ID>" OR protoPayload.resourceName:"conversations/chat-<ID>")' \
     --project="<LOGS_PROJECT_ID>" \
     --limit=20 \
     --format="table(timestamp,protoPayload.methodName,protoPayload.request.conversationId,protoPayload.resourceName,protoPayload.status.code,protoPayload.status.message)"
   ```

2. **Query the Insights Conversation to extract linked Dialogflow/CES session IDs and CRM ticket IDs**:
   ```bash
   curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
     -H "X-goog-user-project: <PROJECT_ID>" \
     "https://<INSIGHTS_LOCATION>-contactcenterinsights.googleapis.com/v1/projects/<PROJECT_ID>/locations/<INSIGHTS_LOCATION>/conversations/chat-<ID>" \
     | jq '{
         name,
         ccaas_id: .labels.id,
         df_or_ces_session_id: .labels.dialogflow_conversation_id_1,
         crm_ticket_id: .labels.out_ticket_id,
         gcs_source: .dataSource.gcsSource,
         latestSummary
       }'
   ```

3. **Search Insights Conversations by Dialogflow/CES Session ID or CRM Ticket ID**:
   ```bash
   curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
     -H "X-goog-user-project: <PROJECT_ID>" \
     "https://<INSIGHTS_LOCATION>-contactcenterinsights.googleapis.com/v1/projects/<PROJECT_ID>/locations/<INSIGHTS_LOCATION>/conversations?filter=labels.dialogflow_conversation_id_1=\"<DF_CONVERSATION_ID>\"" \
     | jq '.conversations[] | {name, labels, dataSource}'
   ```

---

## 2. Telephony & SIP Diagnostics

### A. Telephony Lifecycle & Disconnect Events
For Dialogflow Phone Gateway / CCaaS SIP integrations, inspect call disconnect and lifecycle events:
```bash
gcloud logging read 'logName:"dialogflow.googleapis.com%2Fincoming_call"
jsonPayload.action="disconnectCall"' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=20 \
  --format=json
```

### B. Inspecting Telephony / SIP Headers
Dialogflow CX logs carrier headers, SBC addresses, and SIP call IDs in session parameters:
```bash
gcloud logging read 'logName:"dialogflow-runtime.googleapis.com%2Frequests"
labels.session_id="<SESSION_ID>"' \
  --project="<LOGS_PROJECT_ID>" \
  --format="json(timestamp,jsonPayload.queryResult.parameters.x-headers)"
```
*(Key fields include `google-inbound-carrier-id`, `google-sbc-address`, `google-session-callid`, and `telephony-caller-id`)*

---

## 3. Audio Recordings & Storage URI Retrieval

### A. Retrieving CES Audio Storage URIs
When audio recording is enabled in CES apps, conversation response logs record the Cloud Storage URIs for user and agent audio turns:
```bash
gcloud logging read 'logName:"ces.googleapis.com%2Fresponses"
labels.session_id="<SESSION_ID>"
jsonPayload.diagnosticInfo.rootSpan.attributes."agent audio uri":*' \
  --project="<LOGS_PROJECT_ID>" \
  --format="table(timestamp,labels.session_id,jsonPayload.diagnosticInfo.rootSpan.attributes.agent\ audio\ uri,jsonPayload.diagnosticInfo.rootSpan.attributes.user\ audio\ uri)"
```

### B. Retrieving Dialogflow CX Audio Export URIs
For agents configured with GCS audio export (`audio_export_gcs` in `gecx_environments.yaml`):
```bash
gcloud logging read 'logName:"dialogflow-runtime.googleapis.com%2Frequests"
labels.session_id="<SESSION_ID>"
jsonPayload.queryResult.audioExportUri:*' \
  --project="<LOGS_PROJECT_ID>" \
  --format="value(jsonPayload.queryResult.audioExportUri)"
```

### C. CCaaS Recording Milestones
Track when audio recording started or completed for an interaction:
```bash
gcloud logging read 'resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
labels.tracker_id="<TRACKER_ID>"
jsonPayload.event.name=~"recording_"' \
  --project="<LOGS_PROJECT_ID>" \
  --format="table(timestamp,jsonPayload.event.name,jsonPayload.event.payload.details)"
```

---

## 4. Performance, Latency & Token Analytics

### A. CES LLM Latencies & Token Consumption
Inspect model duration, time-to-first-audio, perceived latency, and token usage for generative agents:
```bash
gcloud logging read 'logName:"ces.googleapis.com%2Fresponses"
labels.app_id="<APP_ID>"' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=25 \
  --format="table(
    timestamp,
    labels.session_id,
    jsonPayload.turnIndex,
    jsonPayload.diagnosticInfo.rootSpan.attributes.perceived\ latency\ (ms),
    jsonPayload.diagnosticInfo.rootSpan.childSpans[1].attributes.model,
    jsonPayload.diagnosticInfo.rootSpan.childSpans[1].attributes.input\ token\ count,
    jsonPayload.diagnosticInfo.rootSpan.childSpans[1].attributes.output\ token\ count
  )"
```

### B. Dialogflow Low-Confidence & Fallback Intent Analysis
Detect user turns where confidence was below threshold or triggered fallback handlers:
```bash
gcloud logging read 'logName:"dialogflow-runtime.googleapis.com%2Frequests"
labels.agent_id="<AGENT_ID>"
jsonPayload.queryResult.intentDetectionConfidence < 0.6' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=50 \
  --format="table(timestamp,labels.session_id,jsonPayload.queryResult.transcript,jsonPayload.queryResult.intent.displayName,jsonPayload.queryResult.intentDetectionConfidence)"
```

---

## 5. Log Analytics (SQL) Queries

When querying BigQuery exports or Log Analytics buckets (`_AllLogs` view):

### A. Aggregating CCaaS Failures by Reason
```sql
SELECT
  JSON_VALUE(jsonPayload.event.payload.details.fail_reason) AS fail_reason,
  COUNT(1) AS failure_count
FROM
  `<PROJECT_ID>.<LOCATION>._AllLogs`
WHERE
  resource.type = 'contactcenteraiplatform.googleapis.com/ContactCenter'
  AND JSON_VALUE(jsonPayload.event.payload.details.fail_reason) IS NOT NULL
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY
  fail_reason
ORDER BY
  failure_count DESC;
```

### B. Top Unmatched Dialogflow CX Utterances
```sql
SELECT
  JSON_VALUE(jsonPayload.queryResult.transcript) AS user_utterance,
  COUNT(1) AS occurrence_count
FROM
  `<PROJECT_ID>.<LOCATION>._AllLogs`
WHERE
  log_name LIKE '%dialogflow-runtime.googleapis.com%2Frequests'
  AND JSON_VALUE(jsonPayload.queryResult.match.matchType) = 'NO_MATCH'
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
GROUP BY
  user_utterance
ORDER BY
  occurrence_count DESC
LIMIT 50;
```

### C. CES Average Latency & Token Usage by Model
```sql
SELECT
  JSON_VALUE(child.attributes.model) AS model_name,
  AVG(CAST(JSON_VALUE(jsonPayload.diagnosticInfo.rootSpan.attributes['perceived latency (ms)']) AS INT64)) AS avg_perceived_latency_ms,
  AVG(CAST(JSON_VALUE(child.attributes['input token count']) AS INT64)) AS avg_input_tokens,
  AVG(CAST(JSON_VALUE(child.attributes['output token count']) AS INT64)) AS avg_output_tokens,
  COUNT(1) AS total_turns
FROM
  `<PROJECT_ID>.<LOCATION>._AllLogs`,
  UNNEST(JSON_QUERY_ARRAY(jsonPayload.diagnosticInfo.rootSpan.childSpans)) AS child
WHERE
  log_name LIKE '%ces.googleapis.com%2Fresponses'
  AND JSON_VALUE(child.name) = 'LLM'
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY
  model_name;
```

### D. Contact Center Insights Ingestion Error Breakdown
```sql
SELECT
  protoPayload.methodName AS api_method,
  protoPayload.status.code AS error_code,
  protoPayload.status.message AS error_message,
  COUNT(1) AS failure_count
FROM
  `<PROJECT_ID>.<LOCATION>._AllLogs`
WHERE
  protoPayload.serviceName = 'contactcenterinsights.googleapis.com'
  AND severity = 'ERROR'
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY
  api_method, error_code, error_message
ORDER BY
  failure_count DESC;
```

### E. Insights Conversation Ingestion vs Update Volume
```sql
SELECT
  TIMESTAMP_TRUNC(timestamp, HOUR) AS hour,
  protoPayload.methodName AS api_method,
  protoPayload.status.code AS status_code,
  COUNT(1) AS call_count
FROM
  `<PROJECT_ID>.<LOCATION>._AllLogs`
WHERE
  protoPayload.serviceName = 'contactcenterinsights.googleapis.com'
  AND protoPayload.methodName IN (
    'google.cloud.contactcenterinsights.v1.ContactCenterInsights.UploadConversation',
    'google.cloud.contactcenterinsights.v1.ContactCenterInsights.UpdateConversation'
  )
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
GROUP BY
  hour, api_method, status_code
ORDER BY
  hour DESC, call_count DESC;
```

---

## 6. Sink & Centralized Logging Verification

To verify that logging sinks from infrastructure source projects are actively routing to `aggregate_logs_project_id`:

```bash
# Check recent ingestion from a specific source project container in the central logs project
gcloud logging read 'logName:*
resource.labels.project_id="<SOURCE_PROJECT_ID>"' \
  --project="<AGGREGATE_LOGS_PROJECT_ID>" \
  --limit=10 \
  --format="table(timestamp,logName,resource.type)"
```
