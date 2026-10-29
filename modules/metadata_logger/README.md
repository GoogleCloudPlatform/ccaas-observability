# Metadata Logger Terraform Module

This module deploys a lightweight, secure Cloud Run service (written in Python) and either Eventarc GCS direct triggers or Pub/Sub GCS notifications inside a source GCS bucket project. It listens for file creations in your storage buckets, filters for metadata JSON objects matching custom path patterns, downloads the files, and logs parsed milestones back to Google Cloud Logging in a single, high-performance batch call.

---

## Architecture Design

This module supports two types of ingestion triggers for GCS events:

*   **Direct Eventarc GCS Triggers (Default):** Listens to GCS `object.v1.finalized` events directly within the storage project scope. This is the simplest configuration, avoiding manual Pub/Sub topic and transport layer overhead.
*   **Pub/Sub Triggers:** Uses GCS Bucket Notifications to publish events to a Pub/Sub topic, which triggers the Cloud Run service via a Push Subscription.

### Choosing a Trigger Type

While Eventarc is simpler to set up, you should prefer the **Pub/Sub trigger** in the following scenarios:

1.  **Dual-Region Buckets (e.g., Canada):** Eventarc GCS triggers currently do not support GCS buckets located in dual-regions (such as the Canada dual-region setup using `northamerica-northeast1` and `northamerica-northeast2`). Pub/Sub notifications must be used for these configurations.
2.  **Disaster Recovery & Cross-Region Routing:** Pub/Sub is a global service, allowing you to easily route events across different regions or consolidate events from multiple regional buckets into a single topic for DR failover scenarios.
3.  **Advanced Reliability & Replay:** Pub/Sub allows you to configure a **Dead Letter Queue (DLQ)** on the subscription to isolate failing events, and customize retry backoff and message retention (up to 7 days) for replaying events after service recovery.

### Key Features (Common to both)

*   **Customizable Path Patterns (Per-Bucket):** Filters events at the application layer using user-configured GCS subfolder patterns (e.g. `"/metadata/"`) to only process files of interest and ignore other GCS uploads (like voice recordings).
*   **Flexible Logging Target:** By default, writes logs to the local project. Alternatively, can write directly to a central Observability project via a single parameter update and cross-project IAM assignment.

---

## Prerequisites

Before deploying the Terraform resources, you **must build and push the Cloud Run container image** to Artifact Registry. 

For step-by-step instructions on compiling and uploading the container, please see the [Metadata Logging Service README](../../metadata_logging/README.md).

---

## Quick Start Guide

### 1. Configure Terraform Inputs
Add the following variable block configuration in your root `terraform.tfvars` or `project.auto.tfvars`:

```hcl
metadata_logger = {
  storage_project_id = "my-gcs-storage-project"
  region             = "us-central1"
  image_url          = "us-central1-docker.pkg.dev/my-gcs-storage-project/my-repo/metadata-logger:latest"

  path_configs = {
    "gs://ccaip-iva-artifact-9a/metadata/" = {
      ccaas_project_id        = "my-gcs-storage-project"
      ccaas_resource_location = "us-central1"
      ccaas_resource_id       = "iva"
    },
    "gs://another-records-bucket/call-metadata/" = {
      ccaas_project_id        = "my-central-observability-project" # Cross-project logging example
      ccaas_resource_location = "us-central1"
      ccaas_resource_id       = "iva-main"
    }
  }
}
```

### 2. Apply the Terraform Layout
Initialize and apply your Terraform configuration to create the resources:
```bash
terraform init
terraform apply
```

### 3. (Optional) Configure Cross-Project Logging
If any of your `path_configs` targets a different `ccaas_project_id` (that is, the CCaaS instance and GCS buckets are not in the same project), you must grant the Cloud Run runtime service account permission to write to that project:
```bash
gcloud projects add-iam-policy-binding <CENTRAL_OBSERVABILITY_PROJECT_ID> \
  --member="serviceAccount:<RUNTIME_SERVICE_ACCOUNT_EMAIL>" \
  --role="roles/logging.logWriter"
```
*(The runtime service account email is available in your Terraform outputs)*


---

## Inputs

| Name | Type | Description | Default | Required |
| :--- | :--- | :--- | :--- | :--- |
| **storage_project_id** | `string` | The Google Cloud project ID hosting GCS, Eventarc, and Cloud Run. | n/a | **yes** |
| **region** | `string` | The region to deploy the Cloud Run service. | `"us-central1"` | no |
| **gcs_path_configs** | `map(object)` | A map of GCS path URIs (e.g. 'gs://bucket/path/') to their target logging configurations. | n/a | **yes** |
| **image_url** | `string` | The container image path in Artifact Registry. | n/a | **yes** |
| **custom_log_name** | `string` | The identifier for custom logs. | `"contactcenteraiplatform.googleapis.com%2Fmetadata"` | no |
| **redact_pii** | `bool` | Whether to redact PII in extracted milestone logs: `phone_number` wherever it appears, and `first_name`, `last_name`, `name`, and `email` in person objects (objects containing `first_name`, `last_name`, or `email`; other `name` fields such as queue names are kept). | `true` | no |
| **grant_project_iam_roles** | `bool` | Whether to let the module automatically create project-level IAM role bindings. | `true` | no |
| **enable_apis** | `bool` | Whether to let the module automatically enable necessary Google Cloud service APIs (run, eventarc, logging, storage, pubsub). | `true` | no |
| **trigger_type** | `string` | The trigger type to use for GCS events. Supported values: `eventarc`, `pubsub`. | `"eventarc"` | no |
| **service_name** | `string` | The name of the Cloud Run service and prefix for related resources. | `"metadata-logger"` | no |

## Outputs

| Name | Description |
| :--- | :--- |
| **cloud_run_url** | The HTTP endpoint URL of the deployed Cloud Run service. |
| **runtime_service_account_email** | The email of the Cloud Run runtime service account. |

---

## Project-Level IAM Roles Management (Project Factory Compatibility)

In many production environments (especially enterprise landing zones or environments managed by a **Project Factory**), project-level IAM role assignments are strictly controlled and must not be managed inside application-level submodules.

If you set `grant_project_iam_roles = false`, the module will skip provisioning project-level bindings. You must manually assign:

1. **Cloud Run Log Writer (Required for both triggers):**
   * **Role:** `roles/logging.logWriter` on the target logging project.
   * **Member:** Cloud Run Runtime Service Account `${service_name}-run-sa@<STORAGE_PROJECT_ID>.iam.gserviceaccount.com`.

2. **GCS Service Agent Pub/Sub Publisher (Only for Eventarc trigger):**
   * **Role:** `roles/pubsub.publisher` on the GCS project.
   * **Member:** GCS Service Account `service-STORAGE_PROJECT_NUMBER@gs-project-accounts.iam.gserviceaccount.com`.

3. **Eventarc Receiver Role (Only for Eventarc trigger):**
   * **Role:** `roles/eventarc.eventReceiver` on the GCS project.
   * **Member:** Eventarc Trigger Service Account `${service_name}-trigger-sa@<STORAGE_PROJECT_ID>.iam.gserviceaccount.com`.

---

## Service API Enablement (Project Factory Compatibility)

If you set `enable_apis = false`, the module will not perform automatic resource actions to enable APIs in the storage project. You must ensure the following 5 APIs are enabled beforehand in the storage project (`storage_project_id`):

*   **Cloud Run API:** `run.googleapis.com`
*   **Eventarc API:** `eventarc.googleapis.com`
*   **Cloud Storage API:** `storage.googleapis.com`
*   **Cloud Logging API:** `logging.googleapis.com`
*   **Pub/Sub API:** `pubsub.googleapis.com`


