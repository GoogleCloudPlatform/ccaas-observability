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
