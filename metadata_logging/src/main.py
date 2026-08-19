# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import json
import base64
import logging
import datetime
from flask import Flask, request
from google.cloud import storage
from google.cloud import logging as cloud_logging
from google.cloud.logging_v2 import LogEntry

# Import shared transformation engine functions
from transform import extract_milestones, format_as_log_entry

# Configure standard stream logging for Cloud Run logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("metadata_logger_app")

app = Flask(__name__)

# Initialize GCS client
storage_client = storage.Client()

# Read environment configurations
CUSTOM_LOG_NAME = os.getenv("CUSTOM_LOG_NAME", "metadata-logger")
PATH_CONFIGS_STR = os.getenv("PATH_CONFIGS", "[]")

# Parse path configs JSON safely
try:
    PATH_CONFIGS = json.loads(PATH_CONFIGS_STR)
    logger.info(f"Loaded GCS path configurations: {PATH_CONFIGS_STR}")
except Exception as e:
    logger.error(f"Failed to parse PATH_CONFIGS environment variable as JSON: {e}")
    PATH_CONFIGS = []

# Cache logging clients dynamically per project ID
logging_clients = {}

def get_logging_client(project_id):
    """Retrieves or initializes a Google Cloud Logging client for the target project."""
    if not project_id:
        return None
    if project_id not in logging_clients:
        try:
            logger.info(f"Initializing Cloud Logging client for project: {project_id}")
            logging_clients[project_id] = cloud_logging.Client(project=project_id)
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud Logging client for project {project_id}: {e}")
            logging_clients[project_id] = None
    return logging_clients[project_id]


def parse_timestamp(ts_str):
    """Parses ISO-8601 string containing UTC offsets safely and normalizes to UTC."""
    if not ts_str:
        return None
    try:
        # Parse standard ISO format (with timezone offset)
        dt = datetime.datetime.fromisoformat(ts_str)
        # Convert explicitly to UTC timezone
        return dt.astimezone(datetime.timezone.utc)
    except Exception as e:
        logger.warning(f"Failed to parse timestamp '{ts_str}': {e}. Using current time.")
        return datetime.datetime.now(datetime.timezone.utc)


@app.route("/", methods=["POST"])
def handle_event():
    """Handles incoming Eventarc GCS object-finalized payloads or Pub/Sub push messages."""
    payload = request.get_json(silent=True) or {}
    
    # Auto-detect Pub/Sub envelope
    if "message" in payload and "data" in payload["message"]:
        logger.info("Received Pub/Sub push message envelope")
        try:
            pubsub_message = payload["message"]
            decoded_data = base64.b64decode(pubsub_message["data"]).decode("utf-8")
            event_data = json.loads(decoded_data)
        except Exception as e:
            logger.error(f"Failed to decode Pub/Sub payload: {e}")
            return f"Failed to decode Pub/Sub payload: {e}", 400
    else:
        # Assume direct Eventarc GCS payload
        event_data = payload
    
    bucket_name = event_data.get("bucket")
    object_name = event_data.get("name")
    
    # Fallback to Pub/Sub message attributes if missing in decoded payload
    if not bucket_name or not object_name:
        attributes = payload.get("message", {}).get("attributes", {}) or event_data.get("attributes", {})
        bucket_name = bucket_name or attributes.get("bucketId")
        object_name = object_name or attributes.get("objectId")
    
    if not bucket_name or not object_name:
        logger.warning(f"Received malformed payload missing 'bucket' or 'name': {payload}")
        return "Missing 'bucket' or 'name' in event request data", 400

    gcs_uri = f"gs://{bucket_name}/{object_name}"

    # Path safety filtering: only process .json files
    if not object_name.endswith(".json"):
        logger.info(f"Skipping non-JSON object: {gcs_uri}")
        return "Ignored non-JSON file upload", 200

    # Dynamic path configuration matching
    matching_config = None
    for config in PATH_CONFIGS:
        if config.get("bucket") == bucket_name:
            pattern = config.get("path_pattern", "").lstrip('/')
            if not pattern or pattern in object_name:
                matching_config = config
                break

    if not matching_config:
        logger.info(f"Skipping object because it does not match any GCS path pattern configurations: {gcs_uri}")
        return "Ignored GCS file upload (no matching path config)", 200

    logger.info(f"Processing metadata GCS upload event for: {gcs_uri}")

    try:
        # Download GCS content
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        file_content = blob.download_as_text()
        metadata = json.loads(file_content)
    except Exception as e:
        logger.error(f"Failed to download or parse GCS object from {gcs_uri}: {e}")
        # Return 200 to prevent eventarc message loop retry in case of a corrupted or missing file
        return f"Failed to download/parse GCS metadata: {e}", 200

    # Extract all milestones
    milestones = extract_milestones(metadata, gcs_uri)
    if not milestones:
        logger.info(f"No milestones parsed from metadata file: {gcs_uri}")
        return "No milestone events found in metadata file", 200

    logger.info(f"Extracted {len(milestones)} milestones from call {metadata.get('id')}. Commencing write operation.")

    # Get dynamic logging target details
    target_project_id = matching_config["ccaas_project_id"]
    ccaip_location = matching_config["ccaas_resource_location"]
    ccaip_resource_id = matching_config["ccaas_resource_id"]

    logging_client = get_logging_client(target_project_id)

    # Write log entries in a single batch
    if not logging_client:
        logger.error(f"Google Cloud Logging client is not initialized for project {target_project_id}. Outputting milestones to stdout instead.")
        for m in milestones:
            logger.info(f"[Stdout Fallback Log] {json.dumps(m)}")
        return "Logs printed to stdout (Logging client uninitialized)", 200

    try:
        # Initialize target logger
        logger_target = logging_client.logger(CUSTOM_LOG_NAME)
        
        # Use the batch context manager to commit entries in a single API call
        with logger_target.batch() as batch:
            for m in milestones:
                # Format milestone using matched config parameters
                entry = format_as_log_entry(
                    m, 
                    project_id=target_project_id, 
                    location=ccaip_location, 
                    resource_id=ccaip_resource_id
                )
                
                parsed_time = parse_timestamp(entry["timestamp"])
                
                batch.log_struct(
                    info=entry["jsonPayload"],
                    timestamp=parsed_time,
                    severity=entry["severity"],
                    labels=entry.get("labels"),
                    insert_id=entry["insertId"],
                    resource=cloud_logging.Resource(
                        type=entry["resource"]["type"],
                        labels=entry["resource"]["labels"]
                    )
                )
                
        logger.info(f"Successfully wrote {len(milestones)} batch log entries to {CUSTOM_LOG_NAME} in project {target_project_id}.")
    except Exception as e:
        logger.error(f"Failed to write batch entries to Cloud Logging API: {e}")
        return f"Failed writing to Cloud Logging API: {e}", 500

    return f"Successfully processed call {metadata.get('id')} with {len(milestones)} events logged.", 200


if __name__ == "__main__":
    # Start app listening on standard default environment port (8080)
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
