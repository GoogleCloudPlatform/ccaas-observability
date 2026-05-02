# GECX Monitoring Dashboards

This repository contains a set of Cloud Monitoring dashboards that can be used
to observe the status of Google CCaaS (calls and chats) and Dialogflow (Flow,
Playbooks & Sentiment) metrics.

The dashboards and the underlying logs-based metrics are managed via
[Terraform](https://registry.terraform.io/providers/hashorp/google/latest).

**Note:** These modules will create new logs-based metrics in the specified
project.

## Prerequisites

*   [Terraform](https://learn.hashicorp.com/tutorials/terraform/install-cli)
    installed.
*   [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed.
*   Authenticated to GCP with an account having necessary permissions. Run
    `gcloud auth application-default login`.

## Modules

*   `analytics_dashboard`: Creates a dashboard with log analytics queries to trace
    interactions across CCaaS and Dialogflow.
*   `calls_dashboard`: Creates logs-based metrics and a dashboard to monitor
    metrics related to CCaaS voice calls.
*   `chats_dashboard`: Creates logs-based metrics and a dashboard to monitor
    metrics related to CCaaS chat sessions.
*   `df_dashboard`: Creates logs-based metrics and a dashboard to monitor
    Dialogflow-specific metrics, including Flow execution, Playbook usage, and
    Sentiment Analysis.

## Creating the Dashboards and Metrics

1.  **Initialize Terraform:** `terraform init`

2.  **Prepare Variables:** The modules require the following variables to be
    set:

    *   `project_id`: (string) The project ID where the logs exist and to host
        the dashboards and metrics.
    *   `established_call_rate_upper_bound`: (number) The upper bound for the
        "Current Established Call Rate" gauge in the Calls dashboard.
    *   `escalated_chat_rate_upper_bound`: (number) The upper bound for the
        "Current Escalated Chat Rate" gauge in the Chats dashboard.


    Optional variables:

    *   `log_bucket`: (object) The log bucket to use for the metrics. This
        object has the following attributes:
        *   `location`: (string) The location of the log bucket. Defaults to
            `"global"`.
        *   `name`: (string) The name of the log bucket. Defaults to `"_Default"`.

    The easiest way to pass these variables is via a `project.auto.tfvars` file.
    Create a file named `project.auto.tfvars` in this directory with the
    following content, replacing the placeholder values:

    ```
    project_id = "<YOUR_GCP_PROJECT_ID>"
    established_call_rate_upper_bound = 100
    escalated_chat_rate_upper_bound = 100
    # Optional log_bucket example:
    # log_bucket = {
    #   location = "global"
    #   name     = "_Default"
    # }
    ```

    *Example:* `project_id = "ccaip-probing-logs-zk0hwo"
    established_call_rate_upper_bound = 50 escalated_chat_rate_upper_bound = 20`

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
3.  The new dashboards will be listed under the following names:
    *   "Calls Monitoring"
    *   "Chats Monitoring"
    *   "DialogFlow Playbook Monitoring"
    *   "DialogFlow CX Monitoring"
    *   "CCaaS Log Analytics"

## Destroying the Dashboards and Metrics

To remove the dashboards and the logs-based metrics managed by Terraform:

```
terraform destroy
```

## Modifying Dashboards or Metrics

1.  Edit the `*.tf` files within the `modules/` subdirectories to change
    metrics, widgets, or layouts.
2.  Run `terraform plan` to see the proposed changes.
\
3.  Run `terraform apply` to apply the changes.

## Interaction Tracing Scripts

Beyond the Terraform-managed dashboards, this repository also includes a set of Python scripts in the `interaction_tracing/` directory. These scripts are designed to help developers and support engineers fetch, correlate, and visualize logs from Contact Center as a Service (CCaaS) and Dialogflow CX.

**Key features:**

*   Fetch logs from CCaaS and Dialogflow based on interaction IDs (calls or chats).
*   Automatically map CCaaS interaction IDs to Dialogflow Conversation IDs.
*   Generate Mermaid Gantt charts to visualize the timeline of interaction events, making it easier to troubleshoot and understand interaction flows.
*   Analyze logs at scale using standalone BigQuery SQL scripts (see [BQ README](interaction_tracing/bq/README.md)).

For detailed usage and examples, please refer to the `README.md` within the `interaction_tracing/` directory.

**Typical Workflow:**

1.  Use `interaction_tracing/get_all_interaction_logs.py` to gather combined logs for a specific interaction.
2.  Use `interaction_tracing/generate_interaction_timeline.py` to create a visual timeline from the logs.

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