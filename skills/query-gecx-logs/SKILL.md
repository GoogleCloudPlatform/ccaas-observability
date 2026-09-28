---
name: query-gecx-logs
description: >-
  Queries, filters, and analyzes Google Cloud Logging for GECX products (CCaaS / CCAIP,
  Dialogflow CX/ES, CES / CX Agent Studio, and Contact Center Insights). Resolves
  target logs projects, contact center IDs, locations, and agents from gecx_environments.yaml.
---

# Query GECX Cloud Logs Skill

This skill provides step-by-step instructions and query recipes for querying Google Cloud Logging for **GECX (Gemini Enterprise for Customer Experience)** products, including **CCaaS**, **Dialogflow**, **CES / CX Agent Studio**, and **Contact Center Insights**.

For advanced recipes (cross-service correlation, SIP diagnostics, audio URIs, latency/token analytics, Log Analytics SQL), see the [Advanced Logging Queries Cookbook](references/logging_queries.md).

---

## Step 1: Environment Resolution & Automatic Fallback

Before constructing queries, resolve the target environment topology:

1. **Check for [gecx_environments.yaml](../../gecx_environments.yaml)**:
   * **If missing**: You MUST trigger discovery first before querying logs:
     1. Resolve target project ID (from user request, `project.auto.tfvars`, or `gcloud config get-value project`).
     2. Run the automated discovery script to generate the configuration:
        ```bash
        python3 skills/discover-gecx-environments/scripts/discover_environments.py \
          --project <PROJECT_ID> \
          --set-default
        ```
     3. Once created, read the generated [gecx_environments.yaml](../../gecx_environments.yaml).

2. **Project Resolution for Log Queries**:
   To determine the target project (`--project=<PROJECT_ID>`) for `gcloud logging read`:
   * **1st Priority**: `aggregate_logs_project_id` (if configured, logs are aggregated/routed here via sinks).
   * **2nd Priority**: The specific resource's `project_id` (if the contact center or agent specifies an override).
   * **3rd Priority**: Fall back to the environment's `default_project_id`.

3. **Active Resources**:
   * **`contact_centers`**: Discovered CCaaS contact center IDs (e.g. `iva`, `advanced-reporting`) and locations.
   * **`dialogflow_agents`**: Discovered Dialogflow agent IDs and locations.
   * **`conversation_profiles`**: Discovered Dialogflow Conversation Profiles (linking CCaaS to Dialogflow CX agents or CES apps).
   * **`cxas_apps`**: Discovered CX Agent Studio app IDs and locations.
   * **`insights`**: Discovered Contact Center Insights location, conversation TTL, and summarization generators.

---

## Step 2: Querying by Product

### 1. CCaaS Contact Centers (Calls, Chats, Voice)
Filter on the identification triplet (`resource.type`, `location`, `resource_id`):

```bash
gcloud logging read 'resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
resource.labels.location="<LOCATION>"
resource.labels.resource_id="<CONTACT_CENTER_ID>"' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=50 \
  --format=json
```

#### Common Log Streams
* **Activity Logs**: `logName:"contactcenteraiplatform.googleapis.com%2Factivity"` (CRM calls, Virtual Agent transitions, media uploads).
* **Event Logs**: `logName:"contactcenteraiplatform.googleapis.com%2Fevents"` (Lifecycle events, call transfers, `dialogflow_conversation_created`).

#### Tracing a Specific Call or Chat
Filter by `tracker_id`:
```bash
gcloud logging read 'resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
resource.labels.location="<LOCATION>"
resource.labels.resource_id="<CONTACT_CENTER_ID>"
labels.tracker_id="<TRACKER_ID>"' \
  --project="<LOGS_PROJECT_ID>" \
  --format=json
```
*(Where `<TRACKER_ID>` is e.g. `call_12345` or `chat_67890`)*

---

### 2. CES / CX Agent Studio (CXAS)
CX Agent Studio emits three primary categories of logs:

#### A. Audit Logs (Admin Activity)
Captures administrative operations and configuration mutations (e.g., app updates, deployments, tool definitions):
```bash
gcloud logging read 'protoPayload.serviceName="ces.googleapis.com"
logName:"cloudaudit.googleapis.com%2Factivity"' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=50 \
  --format=json
```

* **Useful Refinements**:
  * By resource/location: `protoPayload.resourceName:"locations/<LOCATION>"`
  * By API method: `protoPayload.methodName:"google.cloud.ces."` (e.g. `UpdateApp`, `CreateDeployment`)
  * By caller: `protoPayload.authenticationInfo.principalEmail="<USER_OR_SA>"`

#### B. Data Access Logs
Captures read operations and API data access calls (active only if Data Access audit logging is enabled for `ces.googleapis.com` in IAM audit configuration):
```bash
gcloud logging read 'protoPayload.serviceName="ces.googleapis.com"
logName:"cloudaudit.googleapis.com%2Fdata_access"' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=50 \
  --format=json
```

#### C. Conversation History (Session Responses)
Captures full conversation turns, user/agent transcripts, tool calls and outputs, model execution latencies, token usage, and audio GCS URIs (when conversation history logging is enabled in the CES app):
```bash
gcloud logging read 'logName:"ces.googleapis.com%2Fresponses"' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=50 \
  --format=json
```

* **Useful Refinements**:
  * By Session ID: `labels.session_id="<SESSION_ID>"`
  * By App ID: `labels.app_id="<APP_ID>"`
  * By Deployment ID: `labels.deployment_id="<DEPLOYMENT_ID>"`
  * By Location: `labels.location_id="<LOCATION>"`

---

### 3. Dialogflow (CX / ES)
Dialogflow follows the same 3-tier logging structure:

#### A. Audit Logs (Admin Activity)
Captures administrative operations and agent management (e.g., agent creation, flow updates, intents):
```bash
gcloud logging read 'protoPayload.serviceName="dialogflow.googleapis.com"
logName:"cloudaudit.googleapis.com%2Factivity"' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=50 \
  --format=json
```

* **Useful Refinements**:
  * By Agent resource: `protoPayload.resourceName:"agents/<AGENT_ID>"`
  * By Location: `resourceLocation.currentLocations="<LOCATION>"`
  * By API method: `protoPayload.methodName:"google.cloud.dialogflow."` (e.g. `Agents.CreateAgent`, `Intents.UpdateIntent`)
  * By caller: `protoPayload.authenticationInfo.principalEmail="<USER_OR_SA>"`

#### B. Data Access Logs
Captures read operations and API data access calls (active only if Data Access audit logging is enabled for `dialogflow.googleapis.com` in IAM audit configuration):
```bash
gcloud logging read 'protoPayload.serviceName="dialogflow.googleapis.com"
logName:"cloudaudit.googleapis.com%2Fdata_access"' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=50 \
  --format=json
```

* **Useful Refinements**:
  * By API method: `protoPayload.methodName:"google.cloud.dialogflow."` (e.g. `KnowledgeBases.ListKnowledgeBases`, `Agents.GetAgent`)

#### C. Conversation History & Runtime Requests (Session Interactions)
Captures runtime conversation turns, user transcripts, matched intents, page transitions, execution sequence, and virtual agent responses (when Cloud Logging is enabled in Dialogflow Agent settings):
```bash
gcloud logging read 'logName:"dialogflow-runtime.googleapis.com%2Frequests"' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=50 \
  --format=json
```

* **Useful Refinements**:
  * By Session ID: `labels.session_id="<SESSION_ID>"`
  * By Agent ID: `labels.agent_id="<AGENT_ID>"`
  * By Environment ID: `labels.environment_id="<ENVIRONMENT_ID>"`
  * By Location: `labels.location_id="<LOCATION>"`

*(Note: Telephony integrations may also log call lifecycle events to `logName:"dialogflow.googleapis.com%2Fincoming_call"`)*

---

### 4. Contact Center Insights (CCAI Insights)
Contact Center Insights processes call/chat recordings, runs transcription, generates AI summaries, and evaluates QA scorecards.

> [!TIP]
> **Two Ingestion Paths & Multi-Location Topology**:
> Environments often have **multiple active Insights locations** (`insights.locations` in `gecx_environments.yaml`) because each producer writes to its own configured location:
> 1. **Direct Dialogflow CX / CES Runtime Export** (created in the **same `<LOCATION>` as the DF agent or CES app**, e.g., `us` or `eu`, via `loggingSettings.conversationLoggingSettings`): The Insights `<CONVERSATION_ID>` **matches the Dialogflow Conversation ID / CES `labels.session_id` 1:1** (e.g., `locations/us/conversations/119DaI5v0mCR1ywyTMSEjg0gw`), and `agentId` matches the CES `labels.app_id`.
> 2. **CCaaS Post-Interaction Upload** (uploaded to the **CCaaS Insights target location**, e.g., `us-central1`): CCaaS uploads completed interactions via `UploadConversation` as `call-<ID>` or `chat-<ID>` (hyphenated CCaaS `labels.tracker_id="call_<ID>"` / `"chat_<ID>"`) and attaches structured correlation labels on the Insights Conversation resource:
>    * `labels.id`: Numeric CCaaS interaction ID (e.g. `"5580"`)
>    * `labels.dialogflow_conversation_id_1`: Linked Dialogflow / CES session ID (e.g. `"119DaI5v0mCR1ywyTMSEjg0gw"`, which links directly to the Path 1 Insights conversation in the agent/app's location!)
>    * `labels.out_ticket_id`: External CRM / Salesforce ticket ID (e.g. `"500DF00000PTvCiYAL"`)

#### A. Audit Logs (Data Access & Admin Activity)
Captures conversation uploads, metadata updates, retrieval, deletion, and analysis operations:
```bash
gcloud logging read 'protoPayload.serviceName="contactcenterinsights.googleapis.com"
logName:"cloudaudit.googleapis.com%2Fdata_access"' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=50 \
  --format=json
```

* **Useful Refinements**:
  * By API method: `protoPayload.methodName:"google.cloud.contactcenterinsights.v1.ContactCenterInsights."`
    * `UploadConversation` (conversation audio & metadata ingestion)
    * `UpdateConversation` (metadataJson patches, label updates)
    * `GetConversation` (conversation reads by console or services)
    * `CreateAnalysis` / `BatchAnalyzeConversations` (annotator execution)
  * By Conversation ID:
    * For `UploadConversation`, `protoPayload.resourceName` is the **parent location** (`projects/<PROJECT>/locations/<LOCATION>`), so filter by **`protoPayload.request.conversationId="<CONVERSATION_ID>"`** (e.g. `call-12345` or `chat-5580`).
    * For `GetConversation` / `UpdateConversation`, filter by **`protoPayload.resourceName:"conversations/<CONVERSATION_ID>"`**.
  * By Caller / Service Account: `protoPayload.authenticationInfo.principalEmail="<SERVICE_ACCOUNT>"`
  * By Status: `protoPayload.status.code != 0` (non-zero gRPC error codes)

#### B. Direct REST API Access (CLI Workaround)
Since `gcloud` does not provide a native `gcloud contact-center-insights` command group, query the regional/multi-regional REST API (`<LOCATION>-contactcenterinsights.googleapis.com`) directly with OAuth bearer tokens:

```bash
# 1. Fetch conversation details, correlation labels, quality metadata, and summaries
#    (<CONVERSATION_ID> is either `call-<ID>` / `chat-<ID>` for CCaaS uploads, or `<SESSION_ID>` for direct DF/CES ingestion):
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "X-goog-user-project: <PROJECT_ID>" \
  "https://<LOCATION>-contactcenterinsights.googleapis.com/v1/projects/<PROJECT_ID>/locations/<LOCATION>/conversations/<CONVERSATION_ID>"

# 2. List/filter CCaaS-uploaded conversations by numeric Call/Chat ID, Dialogflow/CES Session ID, or CRM Ticket ID:
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "X-goog-user-project: <PROJECT_ID>" \
  "https://<LOCATION>-contactcenterinsights.googleapis.com/v1/projects/<PROJECT_ID>/locations/<LOCATION>/conversations?pageSize=20&filter=labels.dialogflow_conversation_id_1=\"<DF_OR_CES_SESSION_ID>\""

# 3. Fetch conversation analyses, runtime annotations, and LLM summaries:
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "X-goog-user-project: <PROJECT_ID>" \
  "https://<LOCATION>-contactcenterinsights.googleapis.com/v1/projects/<PROJECT_ID>/locations/<LOCATION>/conversations/<CONVERSATION_ID>/analyses"
```

---

## Step 3: Error Investigation & Triage

> [!WARNING]
> **Severity Pitfall in GECX / CCaaS**:
> Many GECX services—especially CCaaS—do **not** log operational failures or customer-impacting errors at `ERROR` severity. Dropped interactions, webhook timeouts, failed agent transfers, and CRM sync errors are frequently logged at `INFO` or `DEFAULT` severity with details embedded in the JSON payload or text body.
> Filtering solely with `severity>=ERROR` will miss the majority of actual issues and give a false impression of health.

### 1. CCaaS Error & Failure Hunting

#### A. Keyword Search Across Payloads (Regardless of Severity)
Query all severities for common failure keywords:
```bash
gcloud logging read 'resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
resource.labels.location="<LOCATION>"
("error" OR "fail" OR "failed" OR "failure" OR "exception" OR "timeout" OR "rejected")' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=50 \
  --format=json
```

#### B. Milestone Metadata Failures
Inspect milestone events for explicit failure reasons (e.g. `client_error`, `agent_no_answer`, `transfer_failed`):
```bash
gcloud logging read 'resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
jsonPayload.event.payload.details.fail_reason:*' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=20 \
  --format=json
```

#### C. Full Lifecycle Tracing by `tracker_id`
Once an issue or session identifier is spotted, read the entire session timeline without severity filtering to uncover root cause:
```bash
gcloud logging read 'resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
labels.tracker_id="<TRACKER_ID>"' \
  --project="<LOGS_PROJECT_ID>" \
  --format=json
```

---

### 2. Dialogflow & CES Anomaly Hunting

#### A. Dialogflow CX Fallbacks and Webhook Errors
Find unhandled user utterances or webhook failures (usually logged under `INFO`):
```bash
# Find no-match / fallback responses
gcloud logging read 'logName:"dialogflow-runtime.googleapis.com%2Frequests"
(jsonPayload.queryResult.match.matchType="NO_MATCH" OR jsonPayload.queryResult.match.event:"sys.no-match")' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=20 \
  --format=json

# Find failed webhook executions
gcloud logging read 'logName:"dialogflow-runtime.googleapis.com%2Frequests"
jsonPayload.queryResult.webhookStatuses.code != 0' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=20 \
  --format=json
```

#### B. CES / CX Agent Studio Supervisor & Tool Failures
Find safety/quality violations and tool execution errors:
```bash
# Find supervisor detections and policy flags
gcloud logging read 'logName:"ces.googleapis.com%2Fresponses"
jsonPayload.supervisor.detections:*' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=20 \
  --format=json

# Search session responses for tool or model errors
gcloud logging read 'logName:"ces.googleapis.com%2Fresponses"
("error" OR "failed" OR "exception")' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=20 \
  --format=json
```

---

### 3. Contact Center Insights Ingestion & Update Failures

#### A. Segmented Metadata Copy Failure (Code 9 - FAILED_PRECONDITION)
When CCAIP uploads calls with segmented audio, `UpdateConversation` patches `metadataJson`. If the segment audio filename does not match `file::Basename(audio_uri)`, or if the call ended without an assigned agent/virtual agent (`agent_id` empty), Insights rejects the update with `"Failed to copy segmented metadata."`:
```bash
gcloud logging read 'protoPayload.serviceName="contactcenterinsights.googleapis.com"
protoPayload.methodName="google.cloud.contactcenterinsights.v1.ContactCenterInsights.UpdateConversation"
protoPayload.status.code=9' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=25 \
  --format="table(timestamp,protoPayload.resourceName,protoPayload.status.message)"
```

#### B. Conversation Not Found Race Condition (Code 5 - NOT_FOUND)
CCAI Platform may invoke `UpdateConversation` before the asynchronous `UploadConversation` call finishes creating the conversation resource in Insights:
```bash
gcloud logging read 'protoPayload.serviceName="contactcenterinsights.googleapis.com"
protoPayload.methodName="google.cloud.contactcenterinsights.v1.ContactCenterInsights.UpdateConversation"
protoPayload.status.code=5' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=25 \
  --format="table(timestamp,protoPayload.resourceName,protoPayload.status.message)"
```

#### C. General Insights Ingestion Failures
Find all failing operations across Contact Center Insights:
```bash
gcloud logging read 'protoPayload.serviceName="contactcenterinsights.googleapis.com"
severity>=ERROR' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=50 \
  --format="table(timestamp,protoPayload.methodName,protoPayload.status.code,protoPayload.status.message,protoPayload.resourceName)"
```

---

### 4. Platform & Infrastructure Errors (Severity Filter)
Use `severity>=ERROR` strictly as a quick first pass for unhandled platform crashes or infrastructure-level alerts:
```bash
gcloud logging read 'resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
resource.labels.location="<LOCATION>"
severity>=ERROR' \
  --project="<LOGS_PROJECT_ID>" \
  --limit=20 \
  --format=json
```
