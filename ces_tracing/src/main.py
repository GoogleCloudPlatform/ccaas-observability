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

"""Cloud Run service for ingesting CES conversation traces into Google Cloud Trace."""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, request
import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.api_core.exceptions import BadRequest, InvalidArgument
from google.cloud import trace_v2
from google.protobuf import timestamp_pb2

from transform import (
    MAX_ATTRIBUTE_STRING_BYTES,
    MAX_DISPLAY_NAME_BYTES,
    convert_to_trace_spans,
    extract_complete_conversation_event,
    hash_to_trace_id,
    parse_ces_agent_resource,
    truncate_str,
)

# Configure standard stream logging for Cloud Run logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ces_tracer_app")

app = Flask(__name__)

# Read environment configurations
PROJECT_ID = os.getenv("PROJECT_ID", "")
TRACE_PROJECT_ID = os.getenv("TRACE_PROJECT_ID", "")
APP_CONFIGS_STR = os.getenv("APP_CONFIGS", "[]")
REDACT_PII = os.getenv("REDACT_PII", "false").strip().lower() in ("true", "1", "yes")
INITIAL_DELAY_SECONDS = float(os.getenv("INITIAL_DELAY_SECONDS", "2.0"))
SKIP_IF_TRACE_EXISTS = os.getenv("SKIP_IF_TRACE_EXISTS", "true").strip().lower() in ("true", "1", "yes")

try:
    APP_CONFIGS = json.loads(APP_CONFIGS_STR)
    if not isinstance(APP_CONFIGS, list):
        logger.warning("APP_CONFIGS is not a JSON list; resetting to empty list.")
        APP_CONFIGS = []
    else:
        logger.info(f"Loaded CES app configurations: {APP_CONFIGS_STR}")
except Exception as e:
    logger.error(f"Failed to parse APP_CONFIGS environment variable as JSON: {e}")
    APP_CONFIGS = []

logger.info(f"PII redaction enabled: {REDACT_PII}")
logger.info(f"Skip if trace exists: {SKIP_IF_TRACE_EXISTS}")

# In-memory caches for credentials/session, Trace client, and Dialogflow ConversationProfiles
_authorized_session: Optional[AuthorizedSession] = None
_default_project_id: Optional[str] = None
_trace_client: Optional[trace_v2.TraceServiceClient] = None
_profile_cache: Dict[str, Dict[str, Any]] = {}
_project_id_cache: Dict[str, str] = {}

PROFILE_RESOURCE_RE = re.compile(
    r"^projects/(?P<project_id>[^/]+)(?:/locations/(?P<location>[^/]+))?/conversationProfiles/(?P<profile_id>[^/]+)$"
)


def get_authorized_session() -> Tuple[Optional[AuthorizedSession], Optional[str]]:
    """Initializes or returns a cached AuthorizedSession using Application Default Credentials."""
    global _authorized_session, _default_project_id
    if _authorized_session is None:
        try:
            creds, default_proj = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            _authorized_session = AuthorizedSession(creds)
            _default_project_id = default_proj
        except Exception as e:
            logger.error(f"Failed to initialize Application Default Credentials: {e}")
            return None, None
    return _authorized_session, _default_project_id


def get_trace_client() -> Optional[trace_v2.TraceServiceClient]:
    """Initializes or returns a cached Cloud Trace v2 client."""
    global _trace_client
    if _trace_client is None:
        try:
            _trace_client = trace_v2.TraceServiceClient()
        except Exception as e:
            logger.error(f"Failed to initialize Cloud Trace client: {e}")
            return None
    return _trace_client


def fetch_conversation_profile(
    session: AuthorizedSession, conversation_profile_name: str
) -> Optional[Dict[str, Any]]:
    """Fetches a Dialogflow ConversationProfile via REST API (with in-memory caching)."""
    if not conversation_profile_name:
        return None

    if conversation_profile_name in _profile_cache:
        return _profile_cache[conversation_profile_name]

    match = PROFILE_RESOURCE_RE.match(conversation_profile_name.strip())
    location = match.group("location") if match and match.group("location") else "global"

    if location == "global":
        endpoint = "https://dialogflow.googleapis.com"
    else:
        endpoint = f"https://{location}-dialogflow.googleapis.com"

    url = f"{endpoint}/v2beta1/{conversation_profile_name.strip('/')}"
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            logger.warning(
                f"Dialogflow ConversationProfile GET {url} returned {resp.status_code}: {resp.text}"
            )
            return None
        profile_data = resp.json()
        if isinstance(profile_data, dict):
            _profile_cache[conversation_profile_name] = profile_data
            return profile_data
    except Exception as e:
        logger.warning(f"Error fetching ConversationProfile {conversation_profile_name}: {e}")
    return None


def match_static_app_config(
    conversation_profile: Optional[str], df_project_id: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Matches a conversation profile against static APP_CONFIGS overrides."""
    if not APP_CONFIGS:
        return None

    profile_str = (conversation_profile or "").strip()
    short_profile_id = profile_str.rsplit("/", 1)[-1] if "/" in profile_str else profile_str

    # 1. Exact or short ID match on conversation_profile
    if profile_str:
        for cfg in APP_CONFIGS:
            if not isinstance(cfg, dict):
                continue
            cfg_profile = (cfg.get("conversation_profile") or "").strip()
            if cfg_profile and cfg_profile != "*":
                if cfg_profile == profile_str or cfg_profile == short_profile_id:
                    return cfg

    # 2. Wildcard / default config match (where conversation_profile is omitted or '*')
    for cfg in APP_CONFIGS:
        if not isinstance(cfg, dict):
            continue
        cfg_profile = (cfg.get("conversation_profile") or "").strip()
        if not cfg_profile or cfg_profile == "*":
            cfg_df_proj = cfg.get("df_project_id") or cfg.get("ces_project_id")
            if not cfg_df_proj or not df_project_id or cfg_df_proj == df_project_id:
                return cfg

    return None


def resolve_ces_target(
    session: AuthorizedSession,
    event_info: Dict[str, Any],
    audit_entries: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Resolves the target CES project, location, app_id, and trace_project_id for a conversation.

    Resolution order:
    1. Explicit parameters in direct invocation payload (`ces_project_id`, `ces_location`, `ces_app_id`).
    2. Explicit match in `APP_CONFIGS` for the conversation profile.
    3. Dynamic lookup of `conversationProfile` via Dialogflow REST API -> `automatedAgentConfig.agent`.
    4. Fallback wildcard entry in `APP_CONFIGS`.
    """
    df_project_id = event_info.get("df_project_id") or PROJECT_ID
    conversation_profile = event_info.get("conversation_profile")

    # If conversation_profile wasn't on the CompleteConversation event, check fetched audit logs
    if not conversation_profile and audit_entries:
        for entry in audit_entries:
            proto = entry.get("protoPayload") if isinstance(entry, dict) else None
            if not isinstance(proto, dict):
                continue
            resp_obj = proto.get("response") if isinstance(proto.get("response"), dict) else {}
            req_obj = proto.get("request") if isinstance(proto.get("request"), dict) else {}
            profile_candidate = resp_obj.get("conversationProfile") or (
                req_obj.get("conversation", {}).get("conversationProfile")
                if isinstance(req_obj.get("conversation"), dict)
                else None
            )
            if profile_candidate:
                conversation_profile = profile_candidate
                break

    # 1. Explicit parameters in event_info
    if event_info.get("ces_location") and event_info.get("ces_app_id"):
        ces_proj = event_info.get("ces_project_id") or df_project_id
        return {
            "is_ces": True,
            "ces_project_id": ces_proj,
            "ces_location": event_info["ces_location"],
            "ces_app_id": event_info["ces_app_id"],
            "trace_project_id": event_info.get("trace_project_id") or TRACE_PROJECT_ID or ces_proj,
            "conversation_profile": conversation_profile,
        }

    # 2. Check explicit profile match in APP_CONFIGS
    if conversation_profile:
        for cfg in APP_CONFIGS:
            if not isinstance(cfg, dict):
                continue
            cfg_profile = (cfg.get("conversation_profile") or "").strip()
            short_id = conversation_profile.rsplit("/", 1)[-1]
            if cfg_profile and cfg_profile != "*" and cfg_profile in (conversation_profile, short_id):
                ces_proj = cfg.get("ces_project_id") or df_project_id
                return {
                    "is_ces": True,
                    "ces_project_id": ces_proj,
                    "ces_location": cfg.get("ces_location", "global"),
                    "ces_app_id": cfg.get("ces_app_id", ""),
                    "trace_project_id": cfg.get("trace_project_id") or TRACE_PROJECT_ID or ces_proj,
                    "conversation_profile": conversation_profile,
                }

    # 3. Dynamic lookup via Dialogflow ConversationProfile API
    if conversation_profile and session is not None:
        profile_data = fetch_conversation_profile(session, conversation_profile)
        if profile_data is not None:
            auto_cfg = profile_data.get("automatedAgentConfig")
            if not isinstance(auto_cfg, dict) or not auto_cfg.get("agent"):
                return {
                    "is_ces": False,
                    "reason": f"ConversationProfile '{conversation_profile}' has no automatedAgentConfig.agent",
                }
            agent_uri = auto_cfg["agent"]
            ces_info = parse_ces_agent_resource(agent_uri)
            if ces_info is None:
                return {
                    "is_ces": False,
                    "reason": f"ConversationProfile agent '{agent_uri}' is not a CES app",
                }
            ces_proj = ces_info["project_id"]
            return {
                "is_ces": True,
                "ces_project_id": ces_proj,
                "ces_location": ces_info["location"],
                "ces_app_id": ces_info["app_id"],
                "trace_project_id": TRACE_PROJECT_ID or ces_proj,
                "conversation_profile": conversation_profile,
            }

    # 4. Fallback to wildcard/default entry in APP_CONFIGS
    fallback_cfg = match_static_app_config(conversation_profile, df_project_id)
    if fallback_cfg and fallback_cfg.get("ces_app_id"):
        ces_proj = fallback_cfg.get("ces_project_id") or df_project_id
        return {
            "is_ces": True,
            "ces_project_id": ces_proj,
            "ces_location": fallback_cfg.get("ces_location", "global"),
            "ces_app_id": fallback_cfg["ces_app_id"],
            "trace_project_id": fallback_cfg.get("trace_project_id") or TRACE_PROJECT_ID or ces_proj,
            "conversation_profile": conversation_profile,
        }

    return {
        "is_ces": False,
        "reason": (
            f"Could not resolve CES app for session '{event_info.get('session_id')}' "
            f"(conversation_profile={conversation_profile})"
        ),
    }


def fetch_ces_conversation(
    session: AuthorizedSession,
    project_id: str,
    location: str,
    app_id: str,
    session_id: str,
    max_attempts: int = 3,
) -> Optional[Dict[str, Any]]:
    """Fetches a CES Conversation resource via the CES v1 REST API with retry."""
    url = (
        f"https://ces.googleapis.com/v1/projects/{project_id}"
        f"/locations/{location}/apps/{app_id}/conversations/{session_id}"
    )

    for attempt in range(1, max_attempts + 1):
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404 and attempt < max_attempts:
                logger.info(
                    f"CES conversation {session_id} not yet available (404), retrying ({attempt}/{max_attempts})..."
                )
                time.sleep(1.5 * attempt)
                continue
            logger.error(
                f"CES API GET {url} returned status {resp.status_code}: {resp.text}"
            )
            return None
        except Exception as e:
            logger.error(f"Error calling CES API {url} (attempt {attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                time.sleep(1.5 * attempt)
    return None


def _query_logging_entries(
    session: AuthorizedSession,
    project_id: str,
    log_filter: str,
    max_pages: int = 5,
) -> List[Dict[str, Any]]:
    """Queries Cloud Logging v2 entries:list REST API and returns matching log entry dicts."""
    url = "https://logging.googleapis.com/v2/entries:list"
    entries: List[Dict[str, Any]] = []
    page_token = ""

    for _ in range(max_pages):
        req_body: Dict[str, Any] = {
            "resourceNames": [f"projects/{project_id}"],
            "filter": log_filter,
            "orderBy": "timestamp asc",
            "pageSize": 1000,
        }
        if page_token:
            req_body["pageToken"] = page_token

        try:
            resp = session.post(url, json=req_body, timeout=25)
            if resp.status_code != 200:
                logger.warning(
                    f"Cloud Logging API returned status {resp.status_code}: {resp.text}"
                )
                break
            data = resp.json()
            page_entries = data.get("entries")
            if isinstance(page_entries, list) and page_entries:
                entries.extend(page_entries)
            page_token = data.get("nextPageToken", "")
            if not page_token:
                break
        except Exception as e:
            logger.warning(f"Error querying Cloud Logging in project {project_id}: {e}")
            break

    return entries


def fetch_dialogflow_logs(
    session: AuthorizedSession, project_id: str, session_id: str
) -> List[Dict[str, Any]]:
    """Fetches Dialogflow Cloud Audit Logs (data_access) for a conversation session."""
    log_filter = (
        f'logName="projects/{project_id}/logs/cloudaudit.googleapis.com%2Fdata_access" '
        f'AND protoPayload.serviceName="dialogflow.googleapis.com" '
        f'AND (protoPayload.resourceName:"conversations/{session_id}" '
        f'OR protoPayload.response.name:"conversations/{session_id}")'
    )
    return _query_logging_entries(session, project_id, log_filter, max_pages=10)


def fetch_incoming_call_logs(
    session: AuthorizedSession, project_id: str, session_id: str
) -> List[Dict[str, Any]]:
    """Fetches Dialogflow Telephony incoming_call logs for a conversation session."""
    log_filter = (
        f'logName="projects/{project_id}/logs/dialogflow.googleapis.com%2Fincoming_call" '
        f'AND jsonPayload.conversation:"conversations/{session_id}"'
    )
    return _query_logging_entries(session, project_id, log_filter, max_pages=5)


def fetch_ces_response_logs(
    session: AuthorizedSession, project_id: str, session_id: str
) -> List[Dict[str, Any]]:
    """Fetches CES response logs (for supervisor detections and turnCompleted) for a session."""
    log_filter = (
        f'logName="projects/{project_id}/logs/ces.googleapis.com%2Fresponses" '
        f'AND labels.session_id="{session_id}"'
    )
    return _query_logging_entries(session, project_id, log_filter, max_pages=5)


def _to_protobuf_span(span_dict: Dict[str, Any]) -> trace_v2.types.Span:
    """Converts a normalized span dictionary into a google.cloud.trace_v2.types.Span protobuf."""
    start_pb = timestamp_pb2.Timestamp()
    start_pb.FromDatetime(span_dict["start_time"])

    end_pb = timestamp_pb2.Timestamp()
    end_pb.FromDatetime(span_dict["end_time"])

    attr_map: Dict[str, trace_v2.types.AttributeValue] = {}
    for k, v in (span_dict.get("attributes") or {}).items():
        if isinstance(v, bool):
            attr_map[k] = trace_v2.types.AttributeValue(bool_value=v)
        elif isinstance(v, int):
            attr_map[k] = trace_v2.types.AttributeValue(int_value=v)
        else:
            str_val = truncate_str(str(v), MAX_ATTRIBUTE_STRING_BYTES)
            attr_map[k] = trace_v2.types.AttributeValue(
                string_value=trace_v2.types.TruncatableString(value=str_val)
            )

    display_str = truncate_str(span_dict["display_name"], MAX_DISPLAY_NAME_BYTES)

    pb_span = trace_v2.types.Span(
        name=span_dict["name"],
        span_id=span_dict["span_id"],
        parent_span_id=span_dict.get("parent_span_id", ""),
        display_name=trace_v2.types.TruncatableString(value=display_str),
        start_time=start_pb,
        end_time=end_pb,
        attributes=trace_v2.types.Span.Attributes(attribute_map=attr_map),
    )
    return pb_span


class TransientLookupError(Exception):
    """Raised when a project number lookup fails for a reason that may succeed on retry."""


def normalize_project_id(session: AuthorizedSession, project: str) -> Optional[str]:
    """Returns the project ID for a project ID or project number.

    CES app references in a ConversationProfile's automatedAgentConfig.agent may use either
    form (projects/<id>/... or projects/<number>/...). The CES API accepts both, but Cloud
    Logging logName filters and Cloud Trace require the project ID, so numbers are resolved
    via the Cloud Resource Manager API (resourcemanager.projects.get) and cached.

    Returns None when the number can't be resolved permanently (403/404), and raises
    TransientLookupError on errors that may succeed on retry.
    """
    if not project or not project.isdigit():
        return project
    if project in _project_id_cache:
        return _project_id_cache[project]

    url = f"https://cloudresourcemanager.googleapis.com/v3/projects/{project}"
    try:
        resp = session.get(url, timeout=10)
    except Exception as e:
        raise TransientLookupError(f"Error resolving project number {project}: {e}") from e
    if resp.status_code == 200:
        project_id = (resp.json() or {}).get("projectId")
        if project_id:
            _project_id_cache[project] = project_id
            logger.info(f"Resolved project number {project} to project ID {project_id}.")
            return project_id
        logger.error(f"Cloud Resource Manager response for project {project} has no projectId.")
        return None
    if resp.status_code in (403, 404):
        logger.error(
            f"Cannot resolve project number {project} to a project ID "
            f"(Cloud Resource Manager returned {resp.status_code}): {resp.text}"
        )
        return None
    raise TransientLookupError(
        f"Cloud Resource Manager returned status {resp.status_code} resolving project number {project}: {resp.text}"
    )


def trace_exists(
    session: AuthorizedSession, project_id: str, trace_id: str, session_id: str
) -> bool:
    """Returns True if Cloud Trace already holds the root span for this conversation.

    Best-effort idempotency guard against Pub/Sub redeliveries. Cloud Trace writes take a
    few seconds to become readable, so near-simultaneous duplicates can still slip through.
    Fails open (returns False) on lookup errors so that traces are never silently dropped.
    """
    url = f"https://cloudtrace.googleapis.com/v1/projects/{project_id}/traces/{trace_id}"
    try:
        resp = session.get(url, timeout=10)
    except Exception as e:
        logger.warning(f"Error checking for existing trace {trace_id} in project {project_id}: {e}")
        return False
    if resp.status_code == 404:
        return False
    if resp.status_code != 200:
        logger.warning(
            f"Cloud Trace API returned status {resp.status_code} checking trace {trace_id}: {resp.text}"
        )
        return False
    try:
        spans = resp.json().get("spans") or []
    except Exception:
        return False
    root_name = f"Conversation: {session_id}"
    return any(
        isinstance(span, dict) and str(span.get("name", "")).startswith(root_name)
        for span in spans
    )


def write_trace_spans(project_id: str, spans: List[Dict[str, Any]]) -> bool:
    """Writes a batch of spans to Google Cloud Trace v2."""
    # NOTE (OpenTelemetry / OTLP export): this function is the single export seam.
    # Everything upstream (convert_to_trace_spans in transform.py) produces backend-agnostic
    # span dicts; only this function and _to_protobuf_span() are Cloud Trace specific.
    # To push traces to an external OpenTelemetry endpoint, add an OTLP exporter here
    # (e.g. an OTLP/HTTP POST of an ExportTraceServiceRequest to {endpoint}/v1/traces,
    # or an OpenTelemetry Collector that fans out to multiple backends), either alongside
    # or instead of BatchWriteSpans.
    #
    # Span dict fields and their OTLP mapping:
    #   name            "projects/{p}/traces/{trace_id}/spans/{span_id}" -> traceId (32 hex)
    #                   can be parsed from here, or recomputed as hash_to_trace_id(session_id)
    #   span_id         16 hex chars                                      -> spanId
    #   parent_span_id  16 hex chars, "" for the root span                -> parentSpanId
    #   display_name    str                                               -> name
    #   start_time      datetime (UTC)                                    -> startTimeUnixNano
    #   end_time        datetime (UTC)                                    -> endTimeUnixNano
    #   attributes      Dict[str, str | int | bool]                       -> attributes (KeyValue)
    # IDs are deterministic and W3C Trace Context compatible, so no translation is needed.
    #
    # Considerations for an OTLP exporter:
    #   * Truncation to Cloud Trace limits (MAX_DISPLAY_NAME_BYTES / MAX_ATTRIBUTE_STRING_BYTES)
    #     happens in _to_protobuf_span() only; an OTLP exporter can send untruncated values.
    #   * Set resource attributes (e.g. service.name) and span kind/status as needed.
    #   * Endpoint, auth headers (e.g. from Secret Manager) and network egress must be
    #     configured on the Cloud Run service via the ces_tracer module.
    #   * The idempotency guard (trace_exists) reads Cloud Trace only; OTLP backends may
    #     store duplicate spans on Pub/Sub redeliveries.
    #   * handle_event() acknowledges google.api_core InvalidArgument/BadRequest as
    #     non-retryable and returns 500 for other exceptions; an OTLP exporter should raise
    #     equivalent errors (4xx permanent vs 429/5xx retryable) to keep retry semantics.
    trace_client = get_trace_client()
    if trace_client is None:
        logger.error("Cloud Trace client is not initialized.")
        return False

    pb_spans = [_to_protobuf_span(s) for s in spans]
    request_pb = trace_v2.types.BatchWriteSpansRequest(
        name=f"projects/{project_id}",
        spans=pb_spans,
    )
    trace_client.batch_write_spans(request=request_pb)
    return True


@app.route("/", methods=["POST"])
def handle_event():
    """Handles Eventarc Audit Log CloudEvents, Pub/Sub push messages, or direct JSON trace requests."""
    payload = request.get_json(silent=True) or {}

    event_info = extract_complete_conversation_event(payload)
    if not event_info:
        logger.warning(f"Received malformed or unrecognized event payload: {payload}")
        return "Malformed or unrecognized event payload", 400

    method_name = event_info.get("method_name", "")
    if method_name != "direct_invocation" and not method_name.endswith("CompleteConversation"):
        logger.info(f"Skipping non-CompleteConversation audit event: {method_name}")
        return f"Ignored audit event for method {method_name}", 200

    session_id = event_info["session_id"]
    force = method_name == "direct_invocation" and bool(payload.get("force"))
    session, default_proj = get_authorized_session()
    if session is None:
        logger.error("Google Cloud credentials unavailable; cannot query CES or Cloud Logging.")
        return "Internal authentication error", 500

    df_project_id = event_info.get("df_project_id") or PROJECT_ID or default_proj
    if not df_project_id:
        logger.error(f"Project ID could not be determined for session {session_id}")
        return "Missing project_id", 400
    event_info["df_project_id"] = df_project_id

    if INITIAL_DELAY_SECONDS > 0:
        time.sleep(INITIAL_DELAY_SECONDS)

    # Fetch Dialogflow audit logs first (also helps resolve conversationProfile if omitted in event)
    logger.info(f"Fetching Dialogflow audit logs for session {session_id} in project {df_project_id}...")
    audit_entries = fetch_dialogflow_logs(session, df_project_id, session_id)

    # Ensure the triggering CompleteConversation audit log entry is present even if Logging indexing lagged
    trigger_entry = event_info.get("audit_log_entry")
    if isinstance(trigger_entry, dict):
        trigger_insert_id = trigger_entry.get("insertId")
        existing_ids = {e.get("insertId") for e in audit_entries if isinstance(e, dict)}
        if not trigger_insert_id or trigger_insert_id not in existing_ids:
            audit_entries.append(trigger_entry)

    # Resolve target CES App (dynamic ConversationProfile lookup or static APP_CONFIGS)
    target = resolve_ces_target(session, event_info, audit_entries=audit_entries)
    if not target.get("is_ces"):
        reason = target.get("reason", "Not a CES conversation")
        logger.info(f"Skipping session {session_id}: {reason}")
        return f"Skipped non-CES conversation: {reason}", 200

    ces_location = target["ces_location"]
    ces_app_id = target["ces_app_id"]

    # CES app references may use project numbers; Logging and Trace need project IDs.
    try:
        ces_project_id = normalize_project_id(session, target["ces_project_id"])
        trace_project_id = normalize_project_id(session, target["trace_project_id"])
    except TransientLookupError as e:
        logger.error(f"Transient error resolving project IDs for session {session_id}: {e}")
        return f"Transient error resolving project IDs: {e}", 500
    if not ces_project_id or not trace_project_id:
        logger.error(
            f"Could not resolve project IDs for session {session_id} "
            f"(ces_project={target['ces_project_id']}, trace_project={target['trace_project_id']}). "
            f"Acknowledging message to prevent infinite retry loop."
        )
        return f"Unresolvable project number for conversation {session_id}", 200

    logger.info(
        f"Resolved CES App for session {session_id}: "
        f"project={ces_project_id}, location={ces_location}, app={ces_app_id}, trace_project={trace_project_id}"
    )

    trace_id = hash_to_trace_id(session_id)
    if SKIP_IF_TRACE_EXISTS and not force and trace_exists(session, trace_project_id, trace_id, session_id):
        logger.info(
            f"Skipping session {session_id}: trace {trace_id} already exists in project {trace_project_id}."
        )
        return f"Trace {trace_id} already exists for conversation {session_id}", 200

    # Fetch Conversation from CES API
    conv = fetch_ces_conversation(
        session,
        project_id=ces_project_id,
        location=ces_location,
        app_id=ces_app_id,
        session_id=session_id,
    )
    if not conv:
        logger.warning(
            f"Could not fetch CES conversation {session_id} from app {ces_app_id}; skipping."
        )
        return f"CES conversation {session_id} not found", 200

    turns = conv.get("turns")
    if not isinstance(turns, list) or len(turns) == 0:
        logger.info(f"No turns found in CES conversation {session_id}. Nothing to trace.")
        return f"No turns in CES conversation {session_id}", 200

    # Fetch Dialogflow incoming_call logs and CES response logs
    incoming_call_entries = fetch_incoming_call_logs(session, df_project_id, session_id)
    ces_response_entries = fetch_ces_response_logs(session, ces_project_id, session_id)

    logger.info(
        f"Session {session_id}: fetched {len(turns)} turn(s), "
        f"{len(audit_entries)} audit log(s), "
        f"{len(incoming_call_entries)} incoming_call log(s), "
        f"{len(ces_response_entries)} CES response log(s)."
    )

    extra_root_attrs: Dict[str, Any] = {
        "ces.project_id": ces_project_id,
        "ces.location": ces_location,
        "ces.app_id": ces_app_id,
    }
    if target.get("conversation_profile"):
        extra_root_attrs["dialogflow.conversation_profile"] = target["conversation_profile"]

    spans = convert_to_trace_spans(
        conv=conv,
        log_entries=audit_entries,
        incoming_call_entries=incoming_call_entries,
        ces_response_entries=ces_response_entries,
        project_id=trace_project_id,
        session_id=session_id,
        redact_pii=REDACT_PII,
        extra_root_attributes=extra_root_attrs,
    )

    logger.info(
        f"Writing {len(spans)} spans for session {session_id} (trace_id={trace_id}) to project {trace_project_id}..."
    )

    try:
        # Export seam: see write_trace_spans() for where an OpenTelemetry (OTLP) exporter goes.
        ok = write_trace_spans(trace_project_id, spans)
        if not ok:
            return "Failed to initialize Cloud Trace client", 500
    except (InvalidArgument, BadRequest) as e:
        # A 400 from Cloud Trace is permanent for this payload; returning 5xx would make
        # Pub/Sub redeliver the same event until message retention expires.
        logger.error(
            f"Non-retryable 400 Bad Request writing spans to Cloud Trace project {trace_project_id} "
            f"for session {session_id}: {e}. Acknowledging message to prevent infinite retry loop."
        )
        return f"Non-retryable error writing to Cloud Trace API: {e}", 200
    except Exception as e:
        logger.error(f"Failed to write spans to Cloud Trace for session {session_id}: {e}")
        return f"Failed writing to Cloud Trace API: {e}", 500

    logger.info(
        f"Successfully ingested trace {trace_id} ({len(spans)} spans) for conversation {session_id}."
    )
    return (
        json.dumps(
            {
                "status": "ok",
                "session_id": session_id,
                "trace_id": trace_id,
                "trace_project_id": trace_project_id,
                "span_count": len(spans),
            }
        ),
        200,
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
