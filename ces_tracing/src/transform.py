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

"""Transformation logic for converting CES conversations and logs into Cloud Trace spans."""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ces_tracer_transform")

# Cloud Trace API string byte truncation limits
MAX_DISPLAY_NAME_BYTES = 128
MAX_ATTRIBUTE_STRING_BYTES = 256

# Sensitive attribute keys redacted when redact_pii=True
PII_ATTRIBUTE_KEYS = {
    "user_input",
    "input",
    "output",
    "text",
    "transcript",
    "utterance",
    "phone_number",
    "first_name",
    "last_name",
    "name",
    "email",
    "request_body",
    "response_body",
}

CONVERSATION_RESOURCE_RE = re.compile(
    r"^projects/(?P<project_id>[^/]+)(?:/locations/(?P<location>[^/]+))?/conversations/(?P<session_id>[^/]+)$"
)

CES_APP_RESOURCE_RE = re.compile(
    r"^projects/(?P<project_id>[^/]+)/locations/(?P<location>[^/]+)/apps/(?P<app_id>[^/]+)(?:/.*)?$"
)


def hash_to_trace_id(session_id: str) -> str:
    """Computes a 32-character hex Cloud Trace ID from the session ID using MD5.

    Must use MD5 to maintain W3C traceparent compatibility with downstream CES tools.
    """
    return hashlib.md5(session_id.encode("utf-8")).hexdigest()


def hash_to_span_id(value: str) -> str:
    """Computes a 16-character hex Cloud Trace Span ID (64-bit) using SHA-256."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def get_span_id(ces_span: Dict[str, Any], parent_span_id: str) -> str:
    """Determines the deterministic 16-hex-char Span ID for a CES span.

    Priority:
    1. If attributes['tool call id'] is a non-empty string, hash it directly with SHA-256[:16].
       This matches the W3C traceparent parent-id emitted by CES Python tools when invoking
       downstream HTTP services.
    2. If span name is 'Tool' and attributes['name'] is a non-empty string, hash
       '{parent_span_id}/{tool_name}'.
    3. Fallback to hashing '{parent_span_id}/{span.name}/{span.startTime}'.
    """
    attrs = ces_span.get("attributes")
    if isinstance(attrs, dict):
        tool_call_id = attrs.get("tool call id")
        if isinstance(tool_call_id, str) and tool_call_id:
            return hash_to_span_id(tool_call_id)

        if ces_span.get("name") == "Tool":
            tool_name = attrs.get("name")
            if isinstance(tool_name, str) and tool_name:
                return hash_to_span_id(f"{parent_span_id}/{tool_name}")

    span_name = ces_span.get("name", "")
    start_time = ces_span.get("startTime", "")
    return hash_to_span_id(f"{parent_span_id}/{span_name}/{start_time}")


def parse_conversation_resource(resource_name: str) -> Optional[Dict[str, str]]:
    """Parses a Dialogflow Conversation resource name into project_id, location, and session_id."""
    if not resource_name or not isinstance(resource_name, str):
        return None
    match = CONVERSATION_RESOURCE_RE.match(resource_name.strip())
    if not match:
        return None
    return {
        "project_id": match.group("project_id"),
        "location": match.group("location") or "global",
        "session_id": match.group("session_id"),
    }


def parse_ces_agent_resource(agent_resource: str) -> Optional[Dict[str, str]]:
    """Parses a CES App resource URI from a Dialogflow ConversationProfile automatedAgentConfig.agent.

    Returns a dict with project_id, location, and app_id if the resource points to a CES app
    (projects/*/locations/*/apps/*), or None if it points to a non-CES agent (e.g. Dialogflow CX).
    """
    if not agent_resource or not isinstance(agent_resource, str):
        return None
    match = CES_APP_RESOURCE_RE.match(agent_resource.strip())
    if not match:
        return None
    return {
        "project_id": match.group("project_id"),
        "location": match.group("location"),
        "app_id": match.group("app_id"),
    }


def extract_complete_conversation_event(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extracts conversation and audit metadata from an Eventarc CloudEvent, Pub/Sub push message, or direct JSON request."""
    if not isinstance(payload, dict) or not payload:
        return None

    event_data = payload

    # 1. Unwrap Pub/Sub push message envelope if present
    if "message" in payload and isinstance(payload["message"], dict) and "data" in payload["message"]:
        raw_data = payload["message"]["data"]
        if isinstance(raw_data, str):
            try:
                decoded = base64.b64decode(raw_data).decode("utf-8")
                event_data = json.loads(decoded)
            except Exception as e:
                logger.error(f"Failed to decode Pub/Sub message data: {e}")
                return None

    # 2. Unwrap CloudEvent structured data wrapper if present
    if "protoPayload" not in event_data and isinstance(event_data.get("data"), dict):
        event_data = event_data["data"]

    # 3. Direct manual invocation format (e.g., {"session_id": "...", "ces_app_id": "..."})
    if "session_id" in event_data and "protoPayload" not in event_data:
        session_id = str(event_data["session_id"]).strip()
        if not session_id:
            return None
        return {
            "session_id": session_id,
            "df_project_id": event_data.get("df_project_id") or event_data.get("project_id"),
            "df_location": event_data.get("df_location") or event_data.get("location") or "global",
            "conversation_profile": event_data.get("conversation_profile"),
            "ces_project_id": event_data.get("ces_project_id") or event_data.get("project_id"),
            "ces_location": event_data.get("ces_location") or event_data.get("location"),
            "ces_app_id": event_data.get("ces_app_id") or event_data.get("app_id"),
            "trace_project_id": event_data.get("trace_project_id"),
            "method_name": "direct_invocation",
            "audit_log_entry": None,
        }

    # 4. Cloud Audit Log entry format
    proto = event_data.get("protoPayload")
    if not isinstance(proto, dict):
        return None

    method_name = proto.get("methodName", "")
    response_obj = proto.get("response") if isinstance(proto.get("response"), dict) else {}
    request_obj = proto.get("request") if isinstance(proto.get("request"), dict) else {}

    resource_name = (
        proto.get("resourceName")
        or response_obj.get("name")
        or request_obj.get("name")
        or ""
    )

    parsed_conv = parse_conversation_resource(resource_name)
    if not parsed_conv:
        # Try response.name if resourceName was not a full conversation path
        parsed_conv = parse_conversation_resource(response_obj.get("name", ""))
    if not parsed_conv:
        return None

    resource_labels = (
        event_data.get("resource", {}).get("labels", {})
        if isinstance(event_data.get("resource"), dict)
        else {}
    )
    df_project_id = parsed_conv["project_id"] or resource_labels.get("project_id")
    df_location = parsed_conv["location"]
    session_id = parsed_conv["session_id"]

    conversation_profile = response_obj.get("conversationProfile")
    if not conversation_profile and isinstance(request_obj.get("conversation"), dict):
        conversation_profile = request_obj["conversation"].get("conversationProfile")

    return {
        "session_id": session_id,
        "df_project_id": df_project_id,
        "df_location": df_location,
        "conversation_profile": conversation_profile,
        "ces_project_id": None,
        "ces_location": None,
        "ces_app_id": None,
        "trace_project_id": None,
        "method_name": method_name,
        "audit_log_entry": event_data,
    }


def parse_time(ts_str: Optional[str]) -> Optional[datetime]:
    """Parses an ISO-8601 / RFC3339 timestamp string into a timezone-aware UTC datetime."""
    if not ts_str or not isinstance(ts_str, str):
        return None
    try:
        normalized = ts_str.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        # Handle nanosecond precision (more than 6 fractional digits) in Python < 3.11 or edge formats
        if "." in normalized:
            plus_idx = normalized.find("+", normalized.find("."))
            minus_idx = normalized.find("-", normalized.find("."))
            tz_idx = plus_idx if plus_idx != -1 else minus_idx
            if tz_idx != -1:
                frac = normalized[normalized.find(".") + 1 : tz_idx]
                if len(frac) > 6:
                    normalized = (
                        normalized[: normalized.find(".") + 1]
                        + frac[:6]
                        + normalized[tz_idx:]
                    )
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception as e:
        logger.warning(f"Failed to parse timestamp '{ts_str}': {e}")
        return None


def truncate_str(value: str, max_len: int) -> str:
    """Truncates a string to max_len characters, appending '...' if truncated."""
    if len(value) > max_len:
        return value[: max_len - 3] + "..."
    return value


def truncate_display_name(value: str) -> str:
    """Truncates a span display name to Cloud Trace's 128-character limit."""
    return truncate_str(value, MAX_DISPLAY_NAME_BYTES)


def convert_attribute_value(
    val: Any, key: str = "", redact_pii: bool = False
) -> Optional[Any]:
    """Converts an arbitrary attribute value into a primitive supported by Cloud Trace (str, int, bool)."""
    if val is None:
        return None

    if redact_pii and key and key.lower() in PII_ATTRIBUTE_KEYS:
        return "<REDACTED>"

    # Note: in Python, bool is a subclass of int, so check bool first!
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return truncate_str(f"{val:f}", MAX_ATTRIBUTE_STRING_BYTES)
    if isinstance(val, str):
        return truncate_str(val, MAX_ATTRIBUTE_STRING_BYTES)

    try:
        if redact_pii and isinstance(val, dict):
            redacted_dict = {
                k: ("<REDACTED>" if k.lower() in PII_ATTRIBUTE_KEYS else v)
                for k, v in val.items()
            }
            json_str = json.dumps(redacted_dict, separators=(",", ":"))
        else:
            json_str = json.dumps(val, separators=(",", ":"))
        return truncate_str(json_str, MAX_ATTRIBUTE_STRING_BYTES)
    except Exception:
        return None


def is_state_update(text: str) -> bool:
    """Returns True if a user message chunk is an internal XML-like state update (<...>)."""
    return len(text) > 0 and text.startswith("<") and text.endswith(">")


def get_user_utterance(turn: Dict[str, Any]) -> str:
    """Extracts the first non-state-update user text utterance from a CES turn."""
    messages = turn.get("messages")
    if not isinstance(messages, list):
        return ""
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "user":
            chunks = msg.get("chunks")
            if not isinstance(chunks, list):
                continue
            for chunk in chunks:
                if not isinstance(chunk, dict):
                    continue
                text = chunk.get("text", "")
                if isinstance(text, str) and text and not is_state_update(text):
                    return text
    return ""


def _convert_ces_span(
    ces_span: Dict[str, Any],
    project_id: str,
    trace_id: str,
    span_id: str,
    parent_span_id: str,
    fallback_start: datetime,
    redact_pii: bool = False,
) -> Dict[str, Any]:
    """Converts a single CES span dictionary into a normalized Cloud Trace span dictionary."""
    span_name = f"projects/{project_id}/traces/{trace_id}/spans/{span_id}"
    start_time = parse_time(ces_span.get("startTime")) or fallback_start
    end_time = parse_time(ces_span.get("endTime"))
    if end_time is None or end_time < start_time:
        end_time = start_time + timedelta(milliseconds=1)

    attr_map: Dict[str, Any] = {}
    raw_attrs = ces_span.get("attributes")
    if isinstance(raw_attrs, dict):
        for k, v in raw_attrs.items():
            converted = convert_attribute_value(v, key=k, redact_pii=redact_pii)
            if converted is not None:
                attr_map[k] = converted

    return {
        "name": span_name,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "display_name": truncate_display_name(ces_span.get("name") or "CES Span"),
        "start_time": start_time,
        "end_time": end_time,
        "attributes": attr_map,
    }


def _convert_children(
    ces_spans: List[Dict[str, Any]],
    project_id: str,
    trace_id: str,
    parent_span_id: str,
    fallback_start: datetime,
    redact_pii: bool = False,
) -> List[Dict[str, Any]]:
    """Recursively converts child CES spans into normalized Cloud Trace span dictionaries."""
    spans: List[Dict[str, Any]] = []
    if not isinstance(ces_spans, list):
        return spans

    for ces_span in ces_spans:
        if not isinstance(ces_span, dict):
            continue
        span_id = get_span_id(ces_span, parent_span_id)
        pb_span = _convert_ces_span(
            ces_span,
            project_id=project_id,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            fallback_start=fallback_start,
            redact_pii=redact_pii,
        )
        spans.append(pb_span)
        child_spans = ces_span.get("childSpans")
        if isinstance(child_spans, list) and child_spans:
            spans.extend(
                _convert_children(
                    child_spans,
                    project_id=project_id,
                    trace_id=trace_id,
                    parent_span_id=span_id,
                    fallback_start=pb_span["start_time"],
                    redact_pii=redact_pii,
                )
            )
    return spans


def convert_to_trace_spans(
    conv: Dict[str, Any],
    log_entries: Optional[List[Dict[str, Any]]],
    incoming_call_entries: Optional[List[Dict[str, Any]]],
    ces_response_entries: Optional[List[Dict[str, Any]]],
    project_id: str,
    session_id: str,
    redact_pii: bool = False,
    extra_root_attributes: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Converts a CES Conversation and correlated Cloud Logging entries into Cloud Trace spans.

    Mirrors the span hierarchy and W3C traceparent correlation logic of the reference ces-tracer:
    1. Synthetic Conversation Root Span (`hash_to_span_id(session_id)`)
    2. Dialogflow Audit Log Operation Spans & Single Event Spans
    3. Dialogflow Incoming Call Log Spans (`dialogflow.googleapis.com/incoming_call`)
    4. Turn Root Spans (parented under `BidiStreamingAnalyzeContent` operation span if present)
       enriched with `ces.googleapis.com/responses` supervisor detections and turn completion
    5. Recursive CES Child Spans (Tools, Guardrails, LLM calls, etc.) with W3C tool call ID hashing
    """
    log_entries = log_entries or []
    incoming_call_entries = incoming_call_entries or []
    ces_response_entries = ces_response_entries or []
    turns = conv.get("turns") if isinstance(conv.get("turns"), list) else []

    trace_id = hash_to_trace_id(session_id)
    spans: List[Dict[str, Any]] = []

    conv_start: Optional[datetime] = None
    conv_end: Optional[datetime] = None

    # 1. Try to find exact conversation times from incoming call logs
    for entry in incoming_call_entries:
        json_payload = entry.get("jsonPayload")
        if not isinstance(json_payload, dict):
            continue
        t = parse_time(entry.get("timestamp"))
        if t is None:
            continue
        action = json_payload.get("action")
        if action == "connectCall":
            if conv_start is None or t < conv_start:
                conv_start = t
        elif action == "disconnectCall":
            if conv_end is None or t > conv_end:
                conv_end = t

    # 2. Try to find exact conversation times from Dialogflow audit logs
    for entry in log_entries:
        proto = entry.get("protoPayload")
        if not isinstance(proto, dict):
            continue
        method_name = proto.get("methodName", "")
        response_obj = proto.get("response") if isinstance(proto.get("response"), dict) else {}

        if method_name.endswith("Conversations.CreateConversation"):
            start_str = response_obj.get("startTime") or entry.get("timestamp")
            parsed = parse_time(start_str)
            if parsed is not None:
                conv_start = parsed
        elif method_name.endswith("Conversations.CompleteConversation"):
            end_str = response_obj.get("endTime") or entry.get("timestamp")
            parsed = parse_time(end_str)
            if parsed is not None:
                conv_end = parsed

    # 3. Fallback to turn spans if logs didn't contain conversation start/end
    if conv_start is None or conv_end is None:
        for turn in turns:
            if not isinstance(turn, dict):
                continue
            root_span = turn.get("rootSpan")
            if isinstance(root_span, dict):
                st = parse_time(root_span.get("startTime"))
                et = parse_time(root_span.get("endTime"))
                if st is not None and (conv_start is None or st < conv_start):
                    conv_start = st
                if et is not None and (conv_end is None or et > conv_end):
                    conv_end = et

    # 4. Ultimate fallback
    if conv_start is None:
        conv_start = datetime.now(timezone.utc)
        conv_end = conv_start + timedelta(seconds=1)
    elif conv_end is None or conv_end < conv_start:
        conv_end = conv_start + timedelta(minutes=1)

    # Create Synthetic Root Span for the entire Conversation
    root_span_id = hash_to_span_id(session_id)
    root_span_name = f"projects/{project_id}/traces/{trace_id}/spans/{root_span_id}"
    turn_count = conv.get("turnCount") if conv.get("turnCount") is not None else len(turns)

    root_attrs: Dict[str, Any] = {
        "turn_count": int(turn_count),
    }
    if isinstance(extra_root_attributes, dict):
        for k, v in extra_root_attributes.items():
            converted = convert_attribute_value(v, key=k, redact_pii=redact_pii)
            if converted is not None:
                root_attrs[k] = converted

    root_span = {
        "name": root_span_name,
        "span_id": root_span_id,
        "parent_span_id": "",
        "display_name": truncate_display_name(f"Conversation: {session_id}"),
        "start_time": conv_start,
        "end_time": conv_end,
        "attributes": root_attrs,
    }
    spans.append(root_span)

    # Separate Audit Log entries into operations vs single events
    ops: Dict[str, Dict[str, Any]] = {}
    single_entries: List[Dict[str, Any]] = []

    for entry in log_entries:
        proto = entry.get("protoPayload")
        if not isinstance(proto, dict):
            continue

        op_info = entry.get("operation")
        if isinstance(op_info, dict) and op_info.get("id"):
            op_id = str(op_info["id"])
            if op_id not in ops:
                status_obj = proto.get("status") if isinstance(proto.get("status"), dict) else None
                ops[op_id] = {
                    "start_time": None,
                    "end_time": None,
                    "method": proto.get("methodName", ""),
                    "severity": entry.get("severity", ""),
                    "resource": proto.get("resourceName", ""),
                    "status": status_obj,
                }
            op = ops[op_id]
            if isinstance(proto.get("status"), dict):
                op["status"] = proto["status"]
            if entry.get("severity"):
                op["severity"] = entry["severity"]
            t = parse_time(entry.get("timestamp"))
            if op_info.get("first") and t is not None:
                op["start_time"] = t
            if op_info.get("last"):
                end_t = parse_time(entry.get("receiveTimestamp")) or t
                if end_t is not None:
                    op["end_time"] = end_t
        else:
            single_entries.append(entry)

    # Ingest Operation Spans
    for op_id, op in ops.items():
        st: Optional[datetime] = op["start_time"]
        et: Optional[datetime] = op["end_time"]
        if st is None and et is None:
            continue
        if st is None and et is not None:
            st = et - timedelta(milliseconds=10)
        if et is None or (st is not None and et < st):
            et = st + timedelta(milliseconds=10)

        span_id = hash_to_span_id(op_id)
        span_name = f"projects/{project_id}/traces/{trace_id}/spans/{span_id}"
        method = op["method"] or "Operation"
        short_name = method.rsplit(".", 1)[-1] if "." in method else method

        attr_map: Dict[str, Any] = {
            "method": truncate_str(method, MAX_ATTRIBUTE_STRING_BYTES),
            "severity": truncate_str(str(op["severity"] or ""), MAX_ATTRIBUTE_STRING_BYTES),
            "resourceName": truncate_str(str(op["resource"] or ""), MAX_ATTRIBUTE_STRING_BYTES),
            "operation_id": truncate_str(op_id, MAX_ATTRIBUTE_STRING_BYTES),
        }
        if isinstance(op.get("status"), dict):
            attr_map["status_code"] = int(op["status"].get("code", 0))
            attr_map["status_message"] = truncate_str(
                str(op["status"].get("message", "")), MAX_ATTRIBUTE_STRING_BYTES
            )

        spans.append(
            {
                "name": span_name,
                "span_id": span_id,
                "parent_span_id": root_span_id,
                "display_name": truncate_display_name(short_name),
                "start_time": st,
                "end_time": et,
                "attributes": attr_map,
            }
        )

    # Ingest Single (non-operation) audit log events as 10ms spans
    for idx, entry in enumerate(single_entries):
        proto = entry.get("protoPayload", {})
        event_time = parse_time(entry.get("timestamp"))
        if event_time is None:
            continue
        insert_id = entry.get("insertId") or f"{session_id}/audit/{idx}/{entry.get('timestamp')}"
        span_id = hash_to_span_id(str(insert_id))
        span_name = f"projects/{project_id}/traces/{trace_id}/spans/{span_id}"

        method = proto.get("methodName", "") or "AuditEvent"
        short_name = method.rsplit(".", 1)[-1] if "." in method else method

        attr_map = {
            "method": truncate_str(method, MAX_ATTRIBUTE_STRING_BYTES),
            "severity": truncate_str(str(entry.get("severity", "")), MAX_ATTRIBUTE_STRING_BYTES),
            "resourceName": truncate_str(
                str(proto.get("resourceName", "")), MAX_ATTRIBUTE_STRING_BYTES
            ),
        }
        status_obj = proto.get("status")
        if isinstance(status_obj, dict):
            attr_map["status_code"] = int(status_obj.get("code", 0))
            attr_map["status_message"] = truncate_str(
                str(status_obj.get("message", "")), MAX_ATTRIBUTE_STRING_BYTES
            )

        spans.append(
            {
                "name": span_name,
                "span_id": span_id,
                "parent_span_id": root_span_id,
                "display_name": truncate_display_name(short_name),
                "start_time": event_time,
                "end_time": event_time + timedelta(milliseconds=10),
                "attributes": attr_map,
            }
        )

    # Ingest Incoming Call log events (action as span name, other fields as attributes)
    for idx, entry in enumerate(incoming_call_entries):
        json_payload = entry.get("jsonPayload")
        if not isinstance(json_payload, dict):
            continue
        event_time = parse_time(entry.get("timestamp"))
        if event_time is None:
            continue
        insert_id = entry.get("insertId") or f"{session_id}/incoming_call/{idx}/{entry.get('timestamp')}"
        span_id = hash_to_span_id(str(insert_id))
        span_name = f"projects/{project_id}/traces/{trace_id}/spans/{span_id}"

        action = json_payload.get("action")
        if not isinstance(action, str) or not action:
            action = "incoming_call_event"

        attr_map = {
            "log_name": "dialogflow.googleapis.com/incoming_call",
        }
        if entry.get("severity"):
            attr_map["severity"] = truncate_str(
                str(entry["severity"]), MAX_ATTRIBUTE_STRING_BYTES
            )
        for k, v in json_payload.items():
            if k == "action":
                continue
            converted = convert_attribute_value(v, key=k, redact_pii=redact_pii)
            if converted is not None:
                attr_map[k] = converted

        spans.append(
            {
                "name": span_name,
                "span_id": span_id,
                "parent_span_id": root_span_id,
                "display_name": truncate_display_name(action),
                "start_time": event_time,
                "end_time": event_time + timedelta(milliseconds=10),
                "attributes": attr_map,
            }
        )

    # Convert Turn root spans and children
    # Check if BidiStreamingAnalyzeContent is present in ops map and use it as parent for Turns
    bidi_span_id = root_span_id
    for op_id, op in ops.items():
        if str(op.get("method", "")).endswith("BidiStreamingAnalyzeContent"):
            bidi_span_id = hash_to_span_id(op_id)
            break

    # Index CES response logs by turnIndex (1-based)
    ces_turn_logs: Dict[int, Dict[str, Any]] = {}
    for entry in ces_response_entries:
        json_payload = entry.get("jsonPayload")
        if not isinstance(json_payload, dict):
            continue
        t_idx = json_payload.get("turnIndex")
        if isinstance(t_idx, (int, float)) and not isinstance(t_idx, bool):
            ces_turn_logs[int(t_idx)] = entry

    for i, turn in enumerate(turns):
        if not isinstance(turn, dict):
            continue
        turn_root_span = turn.get("rootSpan")
        if not isinstance(turn_root_span, dict):
            continue

        turn_span_id = hash_to_span_id(f"{session_id}/turn/{i}")
        pb_span = _convert_ces_span(
            turn_root_span,
            project_id=project_id,
            trace_id=trace_id,
            span_id=turn_span_id,
            parent_span_id=bidi_span_id,
            fallback_start=conv_start,
            redact_pii=redact_pii,
        )

        # Customize Display Name for the turn root to make it readable in the Cloud Trace UI
        user_utterance = get_user_utterance(turn)
        if user_utterance and not redact_pii:
            pb_span["display_name"] = truncate_display_name(f"Turn {i + 1}: {user_utterance}")
        else:
            pb_span["display_name"] = truncate_display_name(f"Turn {i + 1}")

        # Enrich with CES Response Log metadata (supervisor detections, turnCompleted)
        ces_entry = ces_turn_logs.get(i + 1)
        if ces_entry is not None:
            ces_payload = ces_entry.get("jsonPayload", {})
            turn_completed = ces_payload.get("turnCompleted")
            if isinstance(turn_completed, bool):
                pb_span["attributes"]["turn_completed"] = turn_completed

            supervisor = ces_payload.get("supervisor")
            if isinstance(supervisor, dict):
                detections = supervisor.get("detections")
                if isinstance(detections, list) and len(detections) > 0:
                    pb_span["attributes"]["supervisor.has_issue"] = True
                    pb_span["attributes"]["supervisor.detection_count"] = len(detections)
                    for d_idx, det in enumerate(detections):
                        if isinstance(det, dict):
                            issue_type = det.get("issue_type")
                            if isinstance(issue_type, str):
                                pb_span["attributes"][
                                    f"supervisor.detection[{d_idx}].issue_type"
                                ] = truncate_str(issue_type, MAX_ATTRIBUTE_STRING_BYTES)
                            details = det.get("details")
                            if isinstance(details, str):
                                pb_span["attributes"][
                                    f"supervisor.detection[{d_idx}].details"
                                ] = (
                                    "<REDACTED>"
                                    if redact_pii
                                    else truncate_str(details, MAX_ATTRIBUTE_STRING_BYTES)
                                )

        spans.append(pb_span)

        # Map child spans recursively
        child_spans = turn_root_span.get("childSpans")
        if isinstance(child_spans, list) and child_spans:
            spans.extend(
                _convert_children(
                    child_spans,
                    project_id=project_id,
                    trace_id=trace_id,
                    parent_span_id=turn_span_id,
                    fallback_start=pb_span["start_time"],
                    redact_pii=redact_pii,
                )
            )

    return spans


def format_span_for_cloud_trace_json(span: Dict[str, Any]) -> Dict[str, Any]:
    """Formats a normalized span dictionary into the Cloud Trace v2 REST / Protobuf JSON structure."""
    attr_map_json: Dict[str, Any] = {}
    for k, v in (span.get("attributes") or {}).items():
        if isinstance(v, bool):
            attr_map_json[k] = {"boolValue": v}
        elif isinstance(v, int):
            attr_map_json[k] = {"intValue": str(v)}
        else:
            attr_map_json[k] = {
                "stringValue": {
                    "value": truncate_str(str(v), MAX_ATTRIBUTE_STRING_BYTES)
                }
            }

    start_dt: datetime = span["start_time"]
    end_dt: datetime = span["end_time"]

    result: Dict[str, Any] = {
        "name": span["name"],
        "spanId": span["span_id"],
        "displayName": {
            "value": truncate_display_name(span["display_name"]),
        },
        "startTime": start_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "endTime": end_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if span.get("parent_span_id"):
        result["parentSpanId"] = span["parent_span_id"]
    if attr_map_json:
        result["attributes"] = {"attributeMap": attr_map_json}
    return result
