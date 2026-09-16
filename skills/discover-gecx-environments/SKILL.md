---
name: discover-gecx-environments
description: >-
  Discovers available GECX (CCaaS/Dialogflow/CXAS) environments using
  native GECX REST APIs, and initializes or updates
  gecx_environments.yaml from gecx_environments.yaml.sample.
---

# GECX Environment Discovery Skill

This skill discovers available **GECX (Gemini Enterprise for Customer Experience)** environments, extracts product resources using native Google Cloud REST APIs, and maintains the workspace environment configuration in [gecx_environments.yaml](../../gecx_environments.yaml).

For product background and endpoint specifications, see the [GECX Reference Guide](references/gecx_overview.md).

To query or investigate Cloud Logging logs for discovered environments, use the [query-gecx-logs](../query-gecx-logs/SKILL.md) skill.

---

## Initialization Rule (First Run)

Before executing any environment-specific queries, interaction tracing, or dashboard deployments:

1. **Check for configuration file**: Verify if [gecx_environments.yaml](../../gecx_environments.yaml) exists in the repository root.
2. **If missing**:
   - Copy or initialize from the sample template [gecx_environments.yaml.sample](../../gecx_environments.yaml.sample).
   - Run the discovery script against the target project to automatically populate actual resource values.
3. **If present**:
   - Read the configured environments.
   - Run discovery on any new project IDs provided by the user to register additional environments.

---

## Automated Discovery Workflow

Run the automated helper script [discover_environments.py](scripts/discover_environments.py):

```bash
# Preview discovered configuration (dry-run):
python3 skills/discover-gecx-environments/scripts/discover_environments.py \
  --project <GCP_PROJECT_ID> \
  --dry-run

# Discover and save/update gecx_environments.yaml:
python3 skills/discover-gecx-environments/scripts/discover_environments.py \
  --project <GCP_PROJECT_ID> \
  --env-name <ENVIRONMENT_NAME> \
  --set-default
```

### What the Discovery Script Extracts
1. **CCaaS Contact Centers (`contact_centers`)**: Directly queries `https://contactcenteraiplatform.googleapis.com/v1alpha1/projects/<project>/locations/-/contactCenters` using bearer auth to list deployed contact center instances, locations, release versions, and web URIs.
2. **Dialogflow CX Agents (`dialogflow_agents`)**:
   - Discovers available project locations via `https://dialogflow.googleapis.com/v2/projects/<project>/locations`.
   - Queries regional endpoints (e.g. `us-central1-dialogflow.googleapis.com`) and `global` to list deployed CX agents, start flows, and audio export GCS destinations.
3. **Aggregate Logs Project (`aggregate_logs_project_id`)**: Queries Cloud Logging sinks in the infrastructure project to detect sinks (like `ccaas-logs-project`) exporting to dedicated central logging projects.
4. **Components (`components`)**: Identifies enabled GECX products (`ccaas`, `dialogflow`, `cxas`).

---

## Native API Queries

Because GECX products generally lack native `gcloud` subcommands, query REST APIs directly with Google OAuth credentials and `X-goog-user-project` headers:

### 1. Contact Center as a Service (CCaaS)
```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
     -H "Content-Type: application/json" \
     "https://contactcenteraiplatform.googleapis.com/v1alpha1/projects/<PROJECT_ID>/locations/-/contactCenters"
```

### 2. Dialogflow Location & Agent Discovery
**Discover supported locations:**
```bash
curl -s \
  -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" \
  -H "X-goog-user-project: <PROJECT_ID>" \
  "https://dialogflow.googleapis.com/v2/projects/<PROJECT_ID>/locations"
```

**List agents in a regional location (e.g., `us-central1`):**
```bash
curl -s \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "X-goog-user-project: <PROJECT_ID>" \
  "https://<LOCATION>-dialogflow.googleapis.com/v3/projects/<PROJECT_ID>/locations/<LOCATION>/agents"
```

**List agents in `global` location:**
```bash
curl -s \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "X-goog-user-project: <PROJECT_ID>" \
  "https://dialogflow.googleapis.com/v3/projects/<PROJECT_ID>/locations/global/agents"
```

### 3. CX Agent Studio (CXAS)
* **API Service**: `ces.googleapis.com`

**Discover supported locations:**
```bash
curl -s \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "X-goog-user-project: <PROJECT_ID>" \
  "https://ces.googleapis.com/v1/projects/<PROJECT_ID>/locations"
```

**List apps/agents in a location:**
```bash
curl -s \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "X-goog-user-project: <PROJECT_ID>" \
  "https://ces.googleapis.com/v1/projects/<PROJECT_ID>/locations/<LOCATION>/apps"
```

---

## Environment Schema

Each environment in `gecx_environments.yaml` adheres to the following structure:

```yaml
default_environment: probing

environments:
  <env_name>:
    description: "<Description of environment>"
    default_project_id: "<GCP_PROJECT_ID>" # Default GCP project for environment resources
    aggregate_logs_project_id: "<LOGS_PROJECT_ID>" # Optional: Central aggregate logging project (if configured)
    components:                           # Enabled GECX products
      - ccaas
      - dialogflow
      - cxas
    contact_centers:                      # Discovered CCaaS contact center instances
      - id: "customer-service"
        location: "us-central1"
        display_name: "Customer Service Instance"
        domain_prefix: "customer-service"
        root_uri: "https://customer-service.uc1.ccaiplatform.com"
    dialogflow_agents:                    # Discovered Dialogflow CX agents
      - id: "00000000-0000-0000-0000-000000000000"
        location: "us-central1"
        display_name: "CustomerServiceAgent"
        default_language_code: "en"
        time_zone: "America/Los_Angeles"
        audio_export_gcs: "gs://my-gecx-artifacts-bucket/recordings"
    cxas_apps:                            # Discovered CX Agent Studio apps
      - id: "00000000-0000-0000-0000-000000000000"
        location: "us"
        display_name: "Customer Support Assistant"
```
