# GECX Monitoring Dashboards & Observability Toolkit

This repository provides an observability toolkit for **Gemini Enterprise for Customer Experience (GECX)**, including Cloud Monitoring dashboards and logs-based metrics for Google CCaaS (calls, chats, errors, platform updates, and metadata milestones) and Dialogflow (Flow, Playbooks & Sentiment), an automated CCaaS Metadata Logging service, interaction tracing utilities, and agent skills for environment discovery and log analysis.

The dashboards, logs-based metrics, and metadata logging infrastructure are managed via
[Terraform](https://registry.terraform.io/providers/hashicorp/google/latest).

**Note:** These modules will create new logs-based metrics in the specified
project.

## Prerequisites

*   [Terraform](https://learn.hashicorp.com/tutorials/terraform/install-cli)
    installed.
*   [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed.
*   Authenticated to GCP with an account having necessary permissions. Run
    `gcloud auth application-default login`.

## Modules

*   `analytics_dashboard`: Creates a dashboard with Log Analytics (SQL) queries to trace
    interactions across CCaaS and Dialogflow.
*   `calls_dashboard`: Creates logs-based metrics and a dashboard to monitor
    metrics related to CCaaS voice calls.
*   `chats_dashboard`: Creates logs-based metrics and a dashboard to monitor
    metrics related to CCaaS chat sessions.
*   `df_dashboard`: Creates logs-based metrics and a dashboard to monitor
    Dialogflow-specific metrics, including Flow execution, Playbook usage, and
    Sentiment Analysis.
*   `errors_dashboard`: Creates logs-based metrics and a dashboard to track call, chat,
    participant join, and virtual agent streaming errors and failure ratios across the platform.
*   `platform_dashboard`: Creates a logs-based metric (`ccaas_version_updates`) and a dashboard
    to monitor CCaaS platform version upgrades over time.
*   `metadata_logger`: Sets up the Cloud Run service, Eventarc or Pub/Sub trigger, GCS state tracking bucket, GCS permissions, and project IAM roles to ingest and parse session metadata uploads into structured milestone logs. *(Optional, conditionally enabled via `enable_metadata_logger`)*
*   `metadata_calls_dashboard`: Creates logs-based metrics and a dashboard (`Calls Monitoring (Metadata Logs)`) built on structured milestone logs emitted by `metadata_logger`, covering call volumes, VA/human agent handled scorecards, queue wait durations, virtual agent session completions, and escalation deflections. *(Optional, conditionally enabled via `enable_metadata_dashboards`)*
*   `metadata_chats_dashboard`: Creates logs-based metrics and a dashboard (`Chats Monitoring (Metadata Logs)`) built on structured milestone logs emitted by `metadata_logger`, covering chat volumes, VA/human agent handled scorecards, transfer wait durations, virtual agent session completions, and escalation deflections. *(Optional, conditionally enabled via `enable_metadata_dashboards`)*

## Creating the Dashboards and Metrics

1.  **Initialize Terraform:** `terraform init`

2.  **Prepare Variables:** The modules support the following variables:

    *   `project_id`: (string) The project ID where the logs exist and to host
        the dashboards and metrics.
    *   `established_call_rate_upper_bound`: (number, optional) The upper bound for the
        "Current Established Call Rate" gauge in the Calls dashboard. Defaults to `110`.
    *   `escalated_chat_rate_upper_bound`: (number, optional) The upper bound for the
        "Current Escalated Chat Rate" gauge in the Chats dashboard. Defaults to `110`.
    *   `enable_metadata_logger`: (boolean, optional) Whether to deploy the metadata logger. Defaults to `false`.
    *   `metadata_logger`: (object, optional) The configuration object for deploying the
        metadata milestone logger (used when `enable_metadata_logger = true`):
        *   `storage_project_id`: (string) The GCP project ID hosting the central prober GCS buckets, Eventarc/Pub/Sub trigger resources, and Cloud Run service.
        *   `region`: (string, optional) Location for the Cloud Run deployment (defaults to `"us-central1"`).
        *   `image_url`: (string) The Artifact Registry URI of the compiled container image (e.g. `"europe-docker.pkg.dev/.../metadata-logger:latest"`).
        *   `custom_log_name`: (string, optional) Override log name for extracted milestones in Cloud Logging (defaults to `"contactcenteraiplatform.googleapis.com%2Fmetadata"`).
        *   `path_configs`: (map of object) A mapping of source GCS path URIs (e.g., `"gs://bucket/path/"`) to target Contact Center resources (with `ccaas_project_id`, `ccaas_resource_location`, and `ccaas_resource_id`).
        *   `state_bucket`: (object, optional) Configuration for the interaction state tracking GCS bucket used to suppress duplicate milestones on metadata re-exports (`create_bucket`, `name`, `location`, `retention_days`).
        *   `grant_project_iam_roles`: (boolean, optional) Whether to automatically create project-level IAM role bindings. Defaults to `true`.
        *   `enable_apis`: (boolean, optional) Whether to automatically enable required GCP service APIs. Defaults to `true`.
        *   `trigger_type`: (string, optional) The trigger type to use for GCS events (`"eventarc"` or `"pubsub"`). Defaults to `"eventarc"`. Use `"pubsub"` for dual-region buckets (e.g., Canada) or advanced reliability features.
        *   `service_name`: (string, optional) The name of the Cloud Run service. Defaults to `"metadata-logger"`.
    *   `enable_metadata_dashboards`: (boolean, optional) Whether to deploy the metadata log-based calls and chats dashboards and metrics. Defaults to `false`.
    *   `metadata_dashboards`: (object, optional) Configuration settings for the metadata log-based dashboards (used when `enable_metadata_dashboards = true`):
        *   `custom_log_name`: (string, optional) Identifier for custom metadata milestone logs (defaults to `"contactcenteraiplatform.googleapis.com%2Fmetadata"`).
        *   `established_call_rate_upper_bound`: (number, optional) Upper bound for the metadata Calls dashboard rate gauge (defaults to `established_call_rate_upper_bound`).
        *   `escalated_chat_rate_upper_bound`: (number, optional) Upper bound for the metadata Chats dashboard rate gauge (defaults to `escalated_chat_rate_upper_bound`).
        *   `log_bucket`: (object, optional) The log bucket where metadata milestone logs are stored (`location` defaults to `"global"`, `name` defaults to `"_Default"`).

    The easiest way to pass these variables is via a `project.auto.tfvars` file.
    Create a file named `project.auto.tfvars` in this directory with the
    following content, replacing the placeholder values:

    ```hcl
    project_id                        = "<YOUR_GCP_PROJECT_ID>"
    established_call_rate_upper_bound = 100
    escalated_chat_rate_upper_bound   = 100

    # Set to true to deploy the metadata logger (defaults to false)
    enable_metadata_logger = true

    # Metadata Logger configuration (only required if enable_metadata_logger is true)
    metadata_logger = {
      storage_project_id = "<PROBER_GCP_PROJECT_ID>"
      region             = "europe-west1"
      image_url          = "europe-docker.pkg.dev/<PROBER_GCP_PROJECT_ID>/metadata-logger/metadata-logger:latest"
      state_bucket = {
        create_bucket  = true
        location       = "europe-west1"
        retention_days = 30
      }
      path_configs = {
        "gs://ccaip-iva-artifact-9a/iva-prober-gxjs4ra.ew1/metadata/" = {
          ccaas_project_id        = "<TARGET_PROJECT_ID>"
          ccaas_resource_location = "europe-west1"
          ccaas_resource_id       = "iva"
        }
      }
    }

    # Set to true to deploy the metadata log-based Calls and Chats dashboards (defaults to false)
    enable_metadata_dashboards = true
    ```

3.  **Plan and Apply:** `terraform plan` Review the plan to ensure it
    creates the expected logs-based metrics and dashboards.

    ```
    terraform apply
    ```

    Confirm the apply operation when prompted.

## Viewing the Dashboards

Once applied, the dashboards can be found in the Google Cloud Console:

1.  Navigate to the
    [Monitoring > Dashboards](https://console.cloud.google.com/monitoring/dashboards)
    section.
2.  Select the project you specified in the `project_id` variable.
3.  The dashboards will be listed under the following names:
    *   `"Calls Monitoring"`
    *   `"Chats Monitoring"`
    *   `"DialogFlow Playbook Monitoring"`
    *   `"DialogFlow CX Monitoring"`
    *   `"CCaaS Errors Dashboard"`
    *   `"CCaaS Log Analytics"`
    *   `"CCaaS - Platform"`
    *   `"Calls Monitoring (Metadata Logs)"` *(if `enable_metadata_dashboards = true`)*
    *   `"Chats Monitoring (Metadata Logs)"` *(if `enable_metadata_dashboards = true`)*

## Destroying the Dashboards and Metrics

To remove the dashboards and the logs-based metrics managed by Terraform:

```
terraform destroy
```

## Modifying Dashboards or Metrics

1.  Edit the `*.tf` files within the `modules/` subdirectories to change
    metrics, widgets, or layouts.
2.  Run `terraform plan` to see the proposed changes.
3.  Run `terraform apply` to apply the changes.

## GECX Observability Agent Skills

The `skills/` directory contains reusable agent skills and scripts for discovering GECX topologies and querying Cloud Logging across GECX products:

*   **Environment Discovery (`skills/discover-gecx-environments`):** Automatically discovers CCaaS contact centers, Dialogflow CX agents, Dialogflow Conversation Profiles, CX Agent Studio (CES) apps, Contact Center Insights settings and summarization generators, and central log destinations across GCP projects via native REST APIs. Generates and updates a local `gecx_environments.yaml` configuration file based on [gecx_environments.yaml.sample](gecx_environments.yaml.sample).
*   **Log Query & Correlation (`skills/query-gecx-logs`):** Provides diagnostic workflows and ready-to-use Cloud Logging and BigQuery Log Analytics SQL query templates for analyzing CCaaS session lifecycles, Dialogflow Telephony (`incoming_call` via Phone Gateway and SIP Telephony Integration), virtual agent sessions, Contact Center Insights ingestion/update logs, and cross-product interaction correlation.

## Interaction Tracing Scripts

Beyond the Terraform-managed dashboards, this repository also includes a set of Python scripts in the `interaction_tracing/` directory. These scripts are designed to help developers and support engineers fetch, correlate, and visualize logs from Contact Center as a Service (CCaaS) and Dialogflow CX.

**Key features:**

*   Fetch logs from CCaaS and Dialogflow based on interaction IDs (calls or chats).
*   Automatically map CCaaS interaction IDs to Dialogflow Conversation IDs.
*   Generate Mermaid Gantt charts to visualize the timeline of interaction events, making it easier to troubleshoot and understand interaction flows.
*   Analyze logs at scale using standalone BigQuery SQL scripts (see [BQ README](interaction_tracing/bq/README.md)).

For detailed usage and examples, please refer to the [Interaction Tracing README](interaction_tracing/README.md).

**Typical Workflow:**

1.  Use `interaction_tracing/get_all_interaction_logs.py` to gather combined logs for a specific interaction.
2.  Use `interaction_tracing/generate_interaction_timeline.py` to create a visual timeline from the logs.

## Metadata Logging Service

Beyond dashboards, this repository includes the `metadata_logging/` service. It is a Cloud Run-based telemetry ingestion pipeline that extracts structured contact center milestones (such as call creation, queue durations, agent handle events, virtual agent escalation deflections, and transfers) from GCS metadata uploads and logs them as structured entries in Google Cloud Logging.

For detailed usage, local regression testing instructions, build steps, and link directories of all parsed milestones, see the [Metadata Logging Service README](metadata_logging/README.md).

## Permissions


The account used to run Terraform needs sufficient permissions in the target
project, typically including:

*   `logging.metrics.create`
*   `logging.metrics.delete`
*   `logging.metrics.update`
*   `monitoring.dashboards.create`
*   `monitoring.dashboards.delete`
*   `monitoring.dashboards.update`
*   Roles like `logging.admin` and `monitoring.admin` usually suffice.

## Disclaimer

This is not an officially supported Google product. This project is not eligible for the [Google Open Source Software Vulnerability Rewards Program](https://bughunters.google.com/open-source-security).

## Terms of Service

Usage of this toolkit is subject to the following terms:

*   [Google Cloud Platform Terms of Service](https://cloud.google.com/terms/)
*   [Service Specific Terms](https://cloud.google.com/terms/service-terms)
*   [Cloud Observability SLA](https://cloud.google.com/operations/sla)

## Contributing

Contributions are welcome! Please submit a pull request with your desired
changes.