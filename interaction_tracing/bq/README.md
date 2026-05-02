# BigQuery Log Analysis Scripts

This directory contains a set of BigQuery SQL scripts designed to fetch and analyze logs for Google CCaaS (Contact Center AI Platform) and Dialogflow CX from a centralized logging bucket.

These scripts are intended for working purposes and are **not committed** to the repository (ignored via `.gitignore`). They are designed to be customized as needed.

## Column Reference

To ensure consistency across scripts, the column names have been standardized:

| Column Name | Description |
| :--- | :--- |
| `timestamp` | The UTC timestamp when the log entry was recorded (includes sub-second details if available). |
| `source` | The source of the log entry (`CCAAS_ACTIVITY`, `CCAAS_EVENT`, `DF_AUDIT`, `DF_RUNTIME`). |
| `ccaas_project_id` | The GCP project ID where the Contact Center resources reside (source). |
| `ccaas_location` | The GCP region where the Contact Center resource resides. |
| `ccaas_id` | The unique identifier for the specific Contact Center instance. |
| `interaction_id` | The identifier for the individual call or chat attempt (e.g., `call_123` or `chat_456`). |
| `df_project_id` | The GCP project ID where the Dialogflow conversation resides. |
| `df_location` | The GCP region where the Dialogflow conversation resides. |
| `df_conversation_id` | The globally unique identifier for the Dialogflow conversation. |
| `core_message` | A synthesized string representing the most valuable content of the log (e.g., event name, user text, intent, or error). |

## Prerequisites

*   Access to the BigQuery dataset containing the routed logs (e.g., `default_bucket_linked`).
*   The `bq` command-line tool installed and authenticated.

## Usage

Replace the `<PROJECT_ID>.<DATASET>._AllLogs` placeholder in the scripts with your actual BigQuery project and dataset path.

Example execution:
```bash
bq query --use_legacy_sql=false < ccaip_events.sql
```

---

## Core Scripts

### 1. `ccaip_activity.sql`

*   **Purpose:** Fetches CCAIP activity logs (e.g., CRM interactions, session creation).
*   **Timeframe:** Last 14 days.
*   **Sorting:** Old to New (chronological).

#### Sample Output

| Timestamp | CCAAS Project ID | CCAAS Location | CCAAS ID | Interaction ID | Core Message |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-03-31 16:09:51.123 | ccaas-test-u9wi5z | europe-west4 | iva | call_325294 | [CRM-Server] REST call finished... |

---

### 2. `ccaip_events.sql`

*   **Purpose:** Fetches CCAIP event logs (e.g., participants joining/leaving).
*   **Features:** Robust extraction of `interaction_id` using `COALESCE` across multiple fields to avoid missing IDs.

#### Sample Output

| Timestamp | CCAAS Project ID | CCAAS Location | CCAAS ID | Interaction ID | Core Message |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-03-31 19:11:53.789 | ccaas-test-u9wi5z | europe-west4 | iva | *None* | IVR greeting started |

---

### 3. `df_audit.sql`

*   **Purpose:** Fetches Dialogflow Audit logs (Data Access).
*   **Features:** Extracts structured Conversation Project, Location, and Conversation ID using regular expressions, handling special cases like `CreateConversation`.

#### Sample Output

| Timestamp | DF Project ID | DF Location | DF Conversation ID | Core Message |
| :--- | :--- | :--- | :--- | :--- |
| 2026-03-31 19:16:56.234 | ccaas-test-u9wi5z | global | 065DzGr3F_PRXGs7uviF02ElA | ...Participants.AnalyzeContent |

---

### 4. `df_runtime.sql`

*   **Purpose:** Fetches Dialogflow Runtime logs (conversation turns).
*   **Features:** Generates a composite `core_message` indicating Direction (`REQ`, `RESP`, `ERR`), Audio flags, Text, Events, DTMF, and Intent names. Extracts location from labels.

#### Sample Output

| Timestamp | DF Project ID | DF Location | DF Conversation ID | Core Message |
| :--- | :--- | :--- | :--- | :--- |
| 2026-04-30 19:24:03.345 | ccaas-test-u9wi5z | global | 081MY1NXXJ5QZezND8Ow3M4pQ | ERR: Error="No handler is defined..." |

---

### 5. `interaction_mapping.sql`

*   **Purpose:** Maps between CCAAS identifiers and Dialogflow identifiers bidirectionally.
*   **Timeframe:** Last 14 days.
*   **Features:** Joins CCAIP events with Dialogflow Audit logs to reconstruct the complete mapping. Returns no timestamp.

#### Sample Output

| CCAAS Project ID | CCAAS Location | CCAAS ID | Interaction ID | DF Project ID | DF Location | DF Conversation ID |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| ccaas-test-u9wi5z | ca | iva | call_342296 | ccaas-test-u9wi5z | global | 103e7wn06tFSfapsJcP0Pkqkg |

---

### 6. `aggregate_events.sql`

*   **Purpose:** Combines logs from all 4 sources (Activity, Events, Audit, Runtime) into a single chronological timeline.
*   **Timeframe:** Last 14 days.
*   **Features:** Enriches Dialogflow logs with CCAAS identifiers by joining with the mapping from Script 5.

#### Sample Output

| Timestamp | Source | CCAAS Project ID | CCAAS Location | CCAAS ID | Interaction ID | DF Project ID | DF Location | DF Conversation ID | Core Message |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-03-31 16:09:51.123 | CCAAS_ACTIVITY | ccaas-test-u9wi5z | europe-west4 | iva | call_325294 | *None* | *None* | *None* | [CRM-Server] REST call finished... |
| 2026-03-31 19:11:53.789 | CCAAS_EVENT | ccaas-test-u9wi5z | europe-west4 | iva | *None* | *None* | *None* | *None* | IVR greeting started |
| 2026-03-31 19:16:56.234 | DF_AUDIT | ccaas-test-u9wi5z | ca | iva | call_342296 | ccaas-test-u9wi5z | global | 065DzGr3F_PRXGs7uviF02ElA | ...Participants.AnalyzeContent |
| 2026-04-30 19:24:03.345 | DF_RUNTIME | ccaas-test-u9wi5z | ca | iva | call_342296 | ccaas-test-u9wi5z | global | 081MY1NXXJ5QZezND8Ow3M4pQ | ERR: Error="No handler is defined..." |
