import sys
import json
from datetime import datetime, timezone
import hashlib
import os
import argparse

OUTCOME_ONLY_FIELDS = {
    "virtual_agent_handle_durations": {
        "started_at", "ended_at", "call_duration", "chat_duration", "escalation_reason", 
        "finish_reason", "sentiment", "response_count", "fallback_response_count", 
        "transfer_id"
    },
    "consumer_handle_durations": {
        "started_at", "ended_at", "call_duration", "hold_duration", "chat_duration", 
        "message_count", "response_count", "response_time_total", 
        "response_time_max", "response_time_avg"
    },
    "consumer_in_menu_durations": {
        "started_at", "ended_at", "duration", "event"
    },
    "participants": {
        "connected_at", "ended_at", "finished_at", "call_duration", "chat_duration", 
        "fail_reason", "adapter_fail_code", "adapter_fail_message", "status"
    },
    "recordings": {
        "started_at", "ended_at", "duration"
    },
    "queue_durations": {
        "started_at", "ended_at", "queue_duration", "transfer_id", "transfer_cold", 
        "transfer", "service_level_event", "agent_id"
    },
    "transfers": {
        "started_at", "connected_at", "updated_at", "created_at", "assigned_at", "call_duration", "wait_duration", 
        "transfer_status", "status", "fail_reason"
    },
    "handle_durations": {
        "started_at", "ended_at", "call_duration", "hold_duration", "acw_duration", "bcw_duration"
    },
    "consumer_event_durations": {
        "started_at", "ended_at", "duration", "event"
    },
    "virtual_agent_deflected_escalations": {
        "escalated_at"
    }
}

MILESTONE_TIMESTAMP_FIELDS = {
    "virtual_agent_handle_durations": {"started_at", "ended_at"},
    "consumer_handle_durations": {"started_at", "ended_at"},
    "consumer_in_menu_durations": {"started_at", "ended_at"},
    "participants": {"connected_at", "ended_at", "finished_at"},
    "recordings": {"started_at", "ended_at"},
    "queue_durations": {"started_at", "ended_at"},
    "transfers": {"created_at", "assigned_at", "connected_at", "updated_at", "started_at"},
    "handle_durations": {"started_at", "ended_at"},
    "consumer_event_durations": {"started_at", "ended_at"},
    "virtual_agent_deflected_escalations": {"escalated_at"},
}

def filter_timestamp_fields(item, parent_key):
    if not isinstance(item, dict):
        return item
    
    filtered_item = item.copy()
    ts_fields = MILESTONE_TIMESTAMP_FIELDS.get(parent_key, set())
    
    for field in ts_fields:
        if field in filtered_item:
            del filtered_item[field]
            
    return filtered_item

EVENT_PAYLOAD_KEY_MAPPING = {
    # Virtual Agent Session
    "virtual_agent_session_started": "virtual_agent_session",
    "virtual_agent_session_ended": "virtual_agent_session",
    
    # Consumer Handle
    "consumer_handle_started": "consumer_handle",
    "consumer_handle_ended": "consumer_handle",
    
    # Consumer in Menu
    "consumer_in_menu_started": "consumer_in_menu",
    "consumer_in_menu_ended": "consumer_in_menu",
    
    # Participants
    "participant_connected": "participant",
    "participant_left": "participant",
    
    # Recordings
    "recording_started": "recording",
    "recording_completed": "recording",
    
    # Queue durations
    "queue_entry_started": "queue_entry",
    "queue_entry_completed": "queue_entry",
    
    # Transfers
    "session_transfer_started": "transfer",
    "session_transfer_connected": "transfer",
    
    # Agent Handle
    "agent_handle_started": "agent_handle",
    "agent_handle_completed": "agent_handle",
    
    # Consumer Events (CSAT / etc)
    "csat_session_started": "csat_session",
    "csat_session_completed": "csat_session",
    "consumer_event_started": "consumer_event",
    "consumer_event_completed": "consumer_event",

    # Escalation Deflection
    "virtual_agent_escalation_deflected": "virtual_agent_deflected_escalation",
}

def filter_outcome_fields(item, parent_key):
    if not isinstance(item, dict):
        return item
    
    filtered_item = item.copy()
    outcome_fields = OUTCOME_ONLY_FIELDS.get(parent_key, set())
    
    for field in outcome_fields:
        if field in filtered_item:
            del filtered_item[field]
            
    return filtered_item

def to_utc_z_str(val):
    if not isinstance(val, str):
        return val
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(val)
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return val

def normalize_timestamps(obj):
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                new_dict[k] = normalize_timestamps(v)
            elif isinstance(v, str) and (k.endswith("_at") or k in ["start", "end", "timestamp"]):
                new_dict[k] = to_utc_z_str(v)
            else:
                new_dict[k] = v
        return new_dict
    elif isinstance(obj, list):
        return [normalize_timestamps(item) for item in obj]
    return obj

def redact_pii_fields(val):
    if isinstance(val, dict):
        is_person = "first_name" in val or "last_name" in val or "email" in val
        new_dict = {}
        for k, v in val.items():
            if is_person and k in ["first_name", "last_name", "name", "email"]:
                new_dict[k] = "<REDACTED>" if v is not None else v
            elif k == "phone_number":
                new_dict[k] = "<REDACTED>" if v is not None else v
            else:
                new_dict[k] = redact_pii_fields(v)
        return new_dict
    elif isinstance(val, list):
        return [redact_pii_fields(item) for item in val]
    return val


# Group 1: Milestones that occur strictly during the live interaction (Initial Export).
# These must never be parsed or emitted on subsequent post-processing updates.
INITIAL_ONLY_MILESTONES = {
    # Session lifecycle initiation & termination
    "call_created",
    "chat_created",
    "call_scheduled",
    "chat_scheduled",
    "call_ended",
    "chat_ended",

    # Routing, queueing, and connectivity
    "call_connected",
    "chat_connected",
    "call_queued",
    "chat_queued",
    "call_assigned",
    "chat_assigned",

    # IVR & Virtual Agent (concluded prior to session termination)
    "consumer_in_menu_started",
    "consumer_in_menu_ended",
    "virtual_agent_session_started",
    "virtual_agent_session_ended",
    "virtual_agent_escalation_deflected",
}


def is_metadata_update(metadata, update_threshold_seconds=120):
    """
    Determines whether a metadata JSON payload represents a subsequent update
    to an already concluded interaction (e.g. post-call processing, wrap-up,
    CSAT submission) versus the initial session termination export.

    Heuristic Strategy:
    1. Check 'ends_at' (or 'ended_at') vs 'updated_at':
       - In CCaaS/UJET, the initial export occurs immediately upon disconnect,
         with updated_at typically within 0-15 seconds of ends_at.
       - Asynchronous post-call updates occur significantly later (typically 15-20 minutes
         later when wrap-up finishes or survey windows expire).
       - If (updated_at - ends_at) exceeds update_threshold_seconds (default 120s),
         this payload is classified as an update.
    2. Fallback: If ends_at is not present, check created_at vs updated_at. If
       updated_at is significantly later than created_at and the interaction is
       finished, classify accordingly.
    3. Returns False (initial creation) by default if timestamps cannot be reliably parsed.

    Args:
        metadata (dict): The parsed CCaaS metadata JSON object.
        update_threshold_seconds (int): Minimum difference in seconds between
            updated_at and ends_at to consider the file an update. Default: 120.

    Returns:
        bool: True if classified as a subsequent update event; False otherwise.
    """
    if not isinstance(metadata, dict):
        return False

    session = metadata
    if isinstance(metadata.get("call"), dict):
        session = metadata["call"]
    elif isinstance(metadata.get("chat"), dict):
        session = metadata["chat"]

    ends_at_str = session.get("ends_at") or session.get("ended_at")
    updated_at_str = session.get("updated_at")

    if not updated_at_str:
        return False

    try:
        updated_dt = datetime.fromisoformat(updated_at_str).astimezone(timezone.utc)
    except Exception:
        return False

    if ends_at_str:
        try:
            ends_dt = datetime.fromisoformat(ends_at_str).astimezone(timezone.utc)
            delta_sec = (updated_dt - ends_dt).total_seconds()
            return delta_sec >= update_threshold_seconds
        except Exception:
            pass

    # Fallback when ends_at is missing: compare created_at vs updated_at
    created_at_str = session.get("created_at")
    if created_at_str:
        try:
            created_dt = datetime.fromisoformat(created_at_str).astimezone(timezone.utc)
            duration = session.get("call_duration") or session.get("chat_duration") or 0
            effective_end = created_dt.timestamp() + duration
            delta_sec = updated_dt.timestamp() - effective_end
            return delta_sec >= update_threshold_seconds
        except Exception:
            pass

    return False

def extract_milestones(metadata, gcs_uri, redact_pii_enabled=True, is_update=None):
    if is_update is None:
        is_update = is_metadata_update(metadata)

    events = []
    
    is_chat = "chat_type" in metadata or "chat_uuid" in metadata or "chat-" in os.path.basename(gcs_uri)
    
    call_id = metadata.get("id")
    call_uuid = metadata.get("chat_uuid") if is_chat else metadata.get("call_uuid")
    call_type = metadata.get("chat_type", "") if is_chat else metadata.get("call_type", "")
    status = metadata.get("status", "")
    
    base_labels = {}
    
    rating = metadata.get("rating")
    fail_reason = metadata.get("fail_reason")
        
    lang = metadata.get("lang")

    root_timestamps = [
        ("created_at", "call_created"),
        ("queued_at", "call_queued"),
        ("assigned_at", "call_assigned"),
        ("connected_at", "call_connected"),
        ("ends_at", "call_ended"),
        ("scheduled_at", "call_scheduled"),
        ("updated_at", "call_updated")
    ]
    
    for field_name, event_name in root_timestamps:
        ts_val = metadata.get(field_name)
        if ts_val:
            actual_event_name = event_name.replace("call_", "chat_") if is_chat else event_name
            
            # Group 1 live-interaction milestones must never be re-parsed or re-emitted on updates
            if is_update and actual_event_name in INITIAL_ONLY_MILESTONES:
                continue

            payload_details = {}
            if event_name == "call_ended":
                payload_details.update({
                    "rating": rating,
                    "feedback": metadata.get("feedback"),
                    "fail_reason": fail_reason,
                    "fail_details": metadata.get("fail_details"),
                    "sub_status": metadata.get("sub_status"),
                    "disconnected_by": metadata.get("disconnected_by"),
                    "wait_duration": metadata.get("wait_duration"),
                    "call_duration": metadata.get("call_duration"),
                    "hold_duration": metadata.get("hold_duration"),
                    "in_queue_wait_time_va": metadata.get("in_queue_wait_time_va"),
                    "automation_redirection": metadata.get("automation_redirection")
                })
                
            payload = {
                "event": actual_event_name,
                "call_id": call_id,
                "call_uuid": call_uuid
            }
            if payload_details:
                payload["details"] = payload_details
                
            events.append({
                "timestamp": ts_val,
                "event_name": actual_event_name,
                "payload": payload,
                "labels": base_labels.copy()
            })
            
    # Virtual agent sessions conclude during the live interaction; skip on updates
    if not is_update:
        for item in metadata.get("virtual_agent_handle_durations", []):
            va_info = item.get("virtual_agent", {})
            start_va_labels = base_labels.copy()
            start_va_labels.update({
                "virtual_agent_id": str(va_info.get("id", "")),
                "virtual_agent_name": str(va_info.get("name", ""))
            })
            
            end_va_labels = start_va_labels.copy()
            if item.get("finish_reason"):
                end_va_labels["va_finish_reason"] = str(item.get("finish_reason"))
            if item.get("escalation_reason"):
                end_va_labels["va_escalation_reason"] = str(item.get("escalation_reason"))
                
            start = item.get("started_at")
            if start:
                events.append({
                    "timestamp": start,
                    "event_name": "virtual_agent_session_started",
                    "payload": {
                        "event": "virtual_agent_session_started",
                        "call_id": call_id,
                        "virtual_agent": va_info,
                        "details": filter_outcome_fields(item, "virtual_agent_handle_durations")
                    },
                    "labels": start_va_labels.copy()
                })
                
            end = item.get("ended_at")
            if end:
                events.append({
                    "timestamp": end,
                    "event_name": "virtual_agent_session_ended",
                    "payload": {
                        "event": "virtual_agent_session_ended",
                        "call_id": call_id,
                        "virtual_agent": va_info,
                        "details": filter_timestamp_fields(item, "virtual_agent_handle_durations")
                    },
                    "labels": end_va_labels.copy()
                })

        for item in metadata.get("virtual_agent_deflected_escalations", []):
            esc_at = item.get("escalated_at")
            if esc_at:
                va_info = item.get("virtual_agent", {})
                vade_details = filter_timestamp_fields(item, "virtual_agent_deflected_escalations")
                if "virtual_agent" in vade_details:
                    del vade_details["virtual_agent"]

                vade_payload = {
                    "event": "virtual_agent_escalation_deflected",
                    "call_id": call_id,
                    "details": vade_details
                }
                if va_info:
                    vade_payload["virtual_agent"] = va_info

                events.append({
                    "timestamp": esc_at,
                    "event_name": "virtual_agent_escalation_deflected",
                    "payload": vade_payload,
                    "labels": {}
                })
 
    for item in metadata.get("consumer_handle_durations", []):
        start = item.get("started_at")
        if start:
            events.append({
                "timestamp": start,
                "event_name": "consumer_handle_started",
                "payload": {
                    "event": "consumer_handle_started",
                    "call_id": call_id,
                    "details": filter_outcome_fields(item, "consumer_handle_durations")
                },
                "labels": base_labels.copy()
            })
            
        end = item.get("ended_at")
        if end:
            events.append({
                "timestamp": end,
                "event_name": "consumer_handle_ended",
                "payload": {
                    "event": "consumer_handle_ended",
                    "call_id": call_id,
                    "details": filter_timestamp_fields(item, "consumer_handle_durations")
                },
                "labels": base_labels.copy()
            })
 
    # IVR menu navigation occurs during initial greeting; skip on updates
    if not is_update:
        for item in metadata.get("consumer_in_menu_durations", []):
            start = item.get("started_at")
            if start:
                events.append({
                    "timestamp": start,
                    "event_name": "consumer_in_menu_started",
                    "payload": {
                        "event": "consumer_in_menu_started",
                        "call_id": call_id,
                        "details": filter_outcome_fields(item, "consumer_in_menu_durations")
                    },
                    "labels": {}
                })
                
            end = item.get("ended_at")
            if end:
                events.append({
                    "timestamp": end,
                    "event_name": "consumer_in_menu_ended",
                    "payload": {
                        "event": "consumer_in_menu_ended",
                        "call_id": call_id,
                        "details": filter_timestamp_fields(item, "consumer_in_menu_durations")
                    },
                    "labels": {}
                })
 
    for item in metadata.get("participants", []):
        p_labels = base_labels.copy()
        p_labels.update({
            "participant_type": str(item.get("type", "")),
            "participant_id": str(item.get("id", ""))
        })
        
        conn = item.get("connected_at")
        if conn:
            events.append({
                "timestamp": conn,
                "event_name": "participant_connected",
                "payload": {
                    "event": "participant_connected",
                    "call_id": call_id,
                    "participant": {
                        "id": item.get("id"),
                        "type": item.get("type"),
                        "phone_number": item.get("phone_number")
                    },
                    "details": filter_outcome_fields(item, "participants")
                },
                "labels": p_labels
            })
            
        end = item.get("ended_at")
        if end:
            events.append({
                "timestamp": end,
                "event_name": "participant_left",
                "payload": {
                    "event": "participant_left",
                    "call_id": call_id,
                    "participant": {
                        "id": item.get("id"),
                        "type": item.get("type")
                    },
                    "details": filter_timestamp_fields(item, "participants")
                },
                "labels": p_labels
            })
 
    for item in metadata.get("recordings", []):
        start = item.get("started_at")
        if start:
            events.append({
                "timestamp": start,
                "event_name": "recording_started",
                "payload": {
                    "event": "recording_started",
                    "call_id": call_id,
                    "recording_id": item.get("id"),
                    "recording_type": item.get("recording_type"),
                    "details": filter_outcome_fields(item, "recordings")
                },
                "labels": base_labels.copy()
            })
            
        end = item.get("ended_at")
        if end:
            events.append({
                "timestamp": end,
                "event_name": "recording_completed",
                "payload": {
                    "event": "recording_completed",
                    "call_id": call_id,
                    "recording_id": item.get("id"),
                    "recording_type": item.get("recording_type"),
                    "details": filter_timestamp_fields(item, "recordings")
                },
                "labels": base_labels.copy()
            })
            
    for item in metadata.get("queue_durations", []):
        q_labels = {
            "queue_id": str(item.get("id", "")),
            "queue_name": str(item.get("menu_path", ""))
        }
        if item.get("service_level_event"):
            q_labels["sla_status"] = str(item.get("service_level_event"))
            
        if item.get("agent_id") is not None:
            q_labels["answering_agent_id"] = str(item.get("agent_id"))
            
        start = item.get("started_at")
        if start:
            events.append({
                "timestamp": start,
                "event_name": "queue_entry_started",
                "payload": {
                    "event": "queue_entry_started",
                    "call_id": call_id,
                    "details": filter_outcome_fields(item, "queue_durations")
                },
                "labels": {}
            })
            
        end = item.get("ended_at")
        if end:
            events.append({
                "timestamp": end,
                "event_name": "queue_entry_completed",
                "payload": {
                    "event": "queue_entry_completed",
                    "call_id": call_id,
                    "details": filter_timestamp_fields(item, "queue_durations")
                },
                "labels": q_labels.copy()
            })
            
    for item in metadata.get("transfers", []):
        from_agent = item.get("from_agent") or {}
        to_agent = item.get("to_agent") or {}
        from_va = item.get("from_virtual_agent") or {}
        to_va = item.get("to_virtual_agent") or {}
        
        start_t_labels = base_labels.copy()
        start_t_labels.update({
            "transfer_id": str(item.get("id", ""))
        })
        
        if from_agent.get("email"):
            start_t_labels["from_agent_email"] = str(from_agent.get("email"))
        elif from_va.get("name"):
            start_t_labels["from_agent_email"] = f"bot:{from_va.get('name')}"
            
        if to_agent.get("email"):
            start_t_labels["to_agent_email"] = str(to_agent.get("email"))
        elif to_va.get("name"):
            start_t_labels["to_agent_email"] = f"bot:{to_va.get('name')}"
            
        end_t_labels = start_t_labels.copy()
        end_t_labels.update({
            "transfer_status": str(item.get("status", ""))
        })
        
        start = item.get("created_at")
        if start:
            events.append({
                "timestamp": start,
                "event_name": "session_transfer_started",
                "payload": {
                    "event": "session_transfer_started",
                    "call_id": call_id,
                    "details": filter_outcome_fields(item, "transfers")
                },
                "labels": start_t_labels.copy()
            })
            
        conn = item.get("connected_at")
        if conn:
            events.append({
                "timestamp": conn,
                "event_name": "session_transfer_connected",
                "payload": {
                    "event": "session_transfer_connected",
                    "call_id": call_id,
                    "details": filter_timestamp_fields(item, "transfers")
                },
                "labels": end_t_labels.copy()
            })
            
    for item in metadata.get("handle_durations", []):
        h_labels = base_labels.copy()
        h_labels.update({
            "agent_id": str(item.get("agent_id", "")),
            "handle_id": str(item.get("id", ""))
        })
        
        start = item.get("started_at")
        if start:
            events.append({
                "timestamp": start,
                "event_name": "agent_handle_started",
                "payload": {
                    "event": "agent_handle_started",
                    "call_id": call_id,
                    "details": filter_outcome_fields(item, "handle_durations")
                },
                "labels": h_labels.copy()
            })
            
        end = item.get("ended_at")
        if end:
            events.append({
                "timestamp": end,
                "event_name": "agent_handle_completed",
                "payload": {
                    "event": "agent_handle_completed",
                    "call_id": call_id,
                    "details": filter_timestamp_fields(item, "handle_durations")
                },
                "labels": h_labels.copy()
            })
            
    for item in metadata.get("consumer_event_durations", []):
        ev_labels = base_labels.copy()
        ev_labels.update({
            "event_type_name": str(item.get("type", "")),
            "event_id": str(item.get("id", ""))
        })
        
        is_csat = item.get("type") == "csat"
        
        start = item.get("started_at")
        if start:
            events.append({
                "timestamp": start,
                "event_name": "csat_session_started" if is_csat else "consumer_event_started",
                "payload": {
                    "event": "csat_session_started" if is_csat else "consumer_event_started",
                    "call_id": call_id,
                    "details": filter_outcome_fields(item, "consumer_event_durations")
                },
                "labels": ev_labels.copy()
            })
            
        end = item.get("ended_at")
        if end:
            details = filter_timestamp_fields(item, "consumer_event_durations")
            if is_csat and rating is not None:
                details["rating"] = rating
                
            events.append({
                "timestamp": end,
                "event_name": "csat_session_completed" if is_csat else "consumer_event_completed",
                "payload": {
                    "event": "csat_session_completed" if is_csat else "consumer_event_completed",
                    "call_id": call_id,
                    "details": details
                },
                "labels": ev_labels.copy()
            })
            
    session_key = "chat" if is_chat else "call"
    
    formatted_events = []
    for event in events:
        event_name = event.get("event_name")
        event["labels"] = {}
                
        # Format the nested payload structure
        old_payload = event["payload"]
        
        # Build the session sub-object (call or chat)
        session_obj = {}
        if call_id is not None:
            session_obj["id"] = call_id
        if call_uuid is not None:
            session_obj["uuid"] = call_uuid
        if call_type is not None and call_type != "":
            session_obj["type"] = call_type
        if lang is not None:
            session_obj["lang"] = str(lang)
            
        if event_name in ["call_ended", "chat_ended"]:
            if status is not None and status != "":
                session_obj["status"] = str(status)
            
        inner_payload = {
            session_key: session_obj
        }
        
        for k, v in old_payload.items():
            if k not in ["event", "call_id", "call_uuid", "chat_id", "chat_uuid", "lang"]:
                inner_payload[k] = v
                
        # Sanitize and rename details payload
        if "details" in inner_payload:
            details = inner_payload["details"]
            if isinstance(details, dict):
                details = details.copy()
                if "menu_path" in details:
                    val = details["menu_path"]
                    if val is None or val == "":
                        details["menu_path"] = "/"
                
                # Rename to specific milestone key if mapped
                mapped_key = EVENT_PAYLOAD_KEY_MAPPING.get(event_name)
                if mapped_key:
                    inner_payload[mapped_key] = details
                    del inner_payload["details"]
                else:
                    inner_payload["details"] = details
                
        # Normalize all timestamps inside inner_payload to UTC Z format
        inner_payload = normalize_timestamps(inner_payload)
        
        if redact_pii_enabled:
            inner_payload = redact_pii_fields(inner_payload)
        
        new_payload = {
            "event": {
                "name": event_name,
                "gcs_source": gcs_uri,
                "payload": inner_payload
            }
        }
        
        event["payload"] = new_payload
        formatted_events.append(event)
        
    return formatted_events

def format_as_log_entry(milestone, project_id, location="asia-southeast1", resource_id="iva"):
    # Convert timestamp to UTC Z format if possible
    ts = milestone["timestamp"]
    try:
        dt = datetime.fromisoformat(ts)
        dt_utc = dt.astimezone(timezone.utc)
        timestamp_str = dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        timestamp_str = ts
        
    labels = milestone["labels"].copy()
    
    # Copy payload and synthesize a user-friendly message field for Logs Explorer
    payload = milestone["payload"].copy()
    event = payload.get("event", {})
    event_name = event.get("name", "unknown")
    inner_payload = event.get("payload", {})
    
    session_id = None
    session_type = "session"
    if "call" in inner_payload:
        session_id = inner_payload["call"].get("id")
        session_type = "call"
    elif "chat" in inner_payload:
        session_id = inner_payload["chat"].get("id")
        session_type = "chat"
        
    if session_id:
        payload["message"] = f"Milestone: {event_name} ({session_type} {session_id})"
    else:
        payload["message"] = f"Milestone: {event_name}"

    # Generate a stable unique insertId by hashing the business payload (excluding transient transport details like gcs_source)
    hash_payload = payload.copy()
    if "event" in hash_payload and isinstance(hash_payload["event"], dict):
        hash_event = hash_payload["event"].copy()
        hash_event.pop("gcs_source", None)
        hash_payload["event"] = hash_event

    payload_str = json.dumps(hash_payload, sort_keys=True)
    insert_id = hashlib.md5(payload_str.encode('utf-8')).hexdigest()
        
    res = {
        "insertId": insert_id,
        "jsonPayload": payload,
        "resource": {
            "type": "contactcenteraiplatform.googleapis.com/ContactCenter",
            "labels": {
                "location": location,
                "resource_container": project_id,
                "resource_id": resource_id
            }
        },
        "timestamp": timestamp_str,
        "severity": "INFO",
        "logName": f"projects/{project_id}/logs/contactcenteraiplatform.googleapis.com%2Fmetadata"
    }
    if labels:
        res["labels"] = labels
    return res

def main():
    parser = argparse.ArgumentParser(description="Transform CCAIP metadata JSON into milestone events.")
    parser.add_argument("file_path", help="Path to local metadata JSON file.")
    parser.add_argument("gcs_uri", nargs="?", help="Fallback GCS URI for metadata file.")
    parser.add_argument("--log-format", action="store_true", help="Format output as GCP Cloud Logging LogEntry.")
    parser.add_argument("--location", default="asia-southeast1", help="GCP location label for ContactCenter resource.")
    parser.add_argument("--resource-container", help="GCP resource container (project ID) for ContactCenter resource.")
    parser.add_argument("--resource-id", default="iva", help="CCAIP resource ID for ContactCenter resource.")
    parser.add_argument("--no-redact-pii", action="store_true", help="Disable PII redaction (redaction is enabled by default).")
    
    args = parser.parse_args()
    
    file_path = args.file_path
    gcs_uri = args.gcs_uri or f"gs://fallback-bucket/{file_path}"
    
    try:
        with open(file_path, 'r') as f:
            metadata = json.load(f)
    except Exception as e:
        print(f"Error reading or parsing JSON file '{file_path}': {e}", file=sys.stderr)
        sys.exit(1)
        
    milestones = extract_milestones(metadata, gcs_uri, redact_pii_enabled=not args.no_redact_pii)
    
    if args.log_format:
        project_id = args.resource_container or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            print("Error: Target GCP project ID must be specified via --resource-container or the GOOGLE_CLOUD_PROJECT environment variable.", file=sys.stderr)
            sys.exit(1)

        milestones = [
            format_as_log_entry(
                m, 
                project_id=project_id, 
                location=args.location, 
                resource_id=args.resource_id
            ) 
            for m in milestones
        ]
        
    print(json.dumps(milestones, indent=2))

if __name__ == "__main__":
    main()
