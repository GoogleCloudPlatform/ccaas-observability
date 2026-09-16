# GECX (Gemini Enterprise for Customer Experience) Overview

**GECX** stands for **Gemini Enterprise for Customer Experience**. It is a comprehensive suite of Google Cloud products designed for end-to-end Customer Experience, Conversational AI, and Contact Center operations.

Because these products generally do not have comprehensive CLI support in `gcloud`, native REST API calls authenticated with Google OAuth tokens (`Authorization: Bearer $(gcloud auth print-access-token)`) are used for querying and discovering resources.

---

## Main Product Suites & APIs

### 1. Contact Center as a Service (CCaaS)
* **Description**: Complete contact center platform for omnichannel customer interactions (voice, chat, SMS, etc.). Formerly known as **Contact Center AI Platform (CCAIP)**.
* **API Service**: `contactcenteraiplatform.googleapis.com`
* **API Version**: `v1alpha1` / `v1`
* **Discovery Endpoint**:
  List contact centers across all locations in a project:
  ```bash
  curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
       -H "Content-Type: application/json" \
       "https://contactcenteraiplatform.googleapis.com/v1alpha1/projects/<PROJECT_ID>/locations/-/contactCenters"
  ```
* **Key Resource Attributes**:
  * `name`: Full resource name (`projects/<project>/locations/<location>/contactCenters/<id>`)
  * `displayName`: Human-readable name
  * `state`: Deployment status (e.g. `STATE_DEPLOYED`)
  * `customerDomainPrefix`: Domain slug (e.g. `b2b`, `b2c`)
  * `instanceConfig`: Sizing configuration (e.g. `DEV_SMALL`)
  * `releaseVersion`: Software release version (e.g. `6.9.14`, `6.12.9`)
  * `uris`:
    * `rootUri`: Web UI URL (management portal)
  * `advancedReportingEnabled`: Flag indicating if advanced reporting is enabled

---

### 2. Dialogflow (CX / ES / Agent Assist)
* **Description**: Conversational AI platform for virtual agents, conversation flows, playbooks, and sentiment analysis.
* **API Service**: `dialogflow.googleapis.com`
* **Discovery Workflow**:
  Dialogflow uses region-specific API endpoints (e.g. `us-central1-dialogflow.googleapis.com`). Therefore, discovery is a two-step process:

  #### Step A: Discover Available Locations
  Query supported locations and capability flags for the project:
  ```bash
  curl -s \
    -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" \
    -H "X-goog-user-project: <PROJECT_ID>" \
    "https://dialogflow.googleapis.com/v2/projects/<PROJECT_ID>/locations"
  ```
  Each returned location provides capability labels:
  * `dialogflow.googleapis.com/dialogflowCxSupported`: Whether Dialogflow CX is supported in this region.
  * `dialogflow.googleapis.com/dialogflowEsSupported`: Whether Dialogflow ES is supported.
  * `dialogflow.googleapis.com/agentAssistSupported`: Whether Agent Assist is supported.

  #### Step B: Discover Agents in Specific Locations
  For regional endpoints (e.g. `us-central1`):
  ```bash
  curl -s \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H "X-goog-user-project: <PROJECT_ID>" \
    "https://<LOCATION>-dialogflow.googleapis.com/v3/projects/<PROJECT_ID>/locations/<LOCATION>/agents"
  ```
  For the `global` region:
  ```bash
  curl -s \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H "X-goog-user-project: <PROJECT_ID>" \
    "https://dialogflow.googleapis.com/v3/projects/<PROJECT_ID>/locations/global/agents"
  ```

  #### Step C: Discover Conversation Profiles (Integration Bridge)
  CCaaS (UJet) does not invoke Dialogflow CX agents directly; it maps internally via a "Virtual Agent Platform" configuration to a **Dialogflow Conversation Profile** (`v2beta1` API). The Conversation Profile then links to either a Dialogflow CX agent/environment or a CES app:
  ```bash
  curl -s \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H "X-goog-user-project: <PROJECT_ID>" \
    "https://dialogflow.googleapis.com/v2beta1/projects/<PROJECT_ID>/locations/global/conversationProfiles"
  ```
  *(For regional locations like `us-central1`, use `https://<LOCATION>-dialogflow.googleapis.com/v2beta1/...`)*

---

### 3. CX Agent Studio (CXAS)
* **Description**: Agent Studio for building, orchestrating, and testing generative customer experience agents.
* **API Service**: `ces.googleapis.com`
* **Discovery Endpoints**:
  ```bash
  # List supported locations:
  curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
       -H "X-goog-user-project: <PROJECT_ID>" \
       "https://ces.googleapis.com/v1/projects/<PROJECT_ID>/locations"

  # List apps (generative agents container) in a location:
  curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
       -H "X-goog-user-project: <PROJECT_ID>" \
       "https://ces.googleapis.com/v1/projects/<PROJECT_ID>/locations/<LOCATION>/apps"
  ```

---

## Authentication & Quota Headers

Native REST calls require:
1. **OAuth Bearer Token**:
   ```bash
   TOKEN=$(gcloud auth print-access-token) # or $(gcloud auth application-default print-access-token)
   ```
2. **`X-goog-user-project`**: Required for billing/quota project attribution on APIs like Dialogflow:
   `-H "X-goog-user-project: <PROJECT_ID>"`
