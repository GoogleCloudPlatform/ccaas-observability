import argparse
import json
from datetime import datetime

def format_timestamp(ts_str):
    # Converts ISO format to Mermaid compatible format
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + 'Z'
    except ValueError:
        return ts_str

def generate_mermaid_gantt(logs, call_id):
    gantt_lines = [
        "gantt",
        "    dateFormat  YYYY-MM-DD HH:mm:ss.SSSZ",
        "    axisFormat %H:%M:%S",
        f"    title Call {call_id} Event Timeline",
        ""
    ]

    ccaip_events = []
    ccaip_activity_events = []
    df_runtime_events = []
    df_audit_events = []
    va_active = False
    first_no_input = None
    last_no_input = None

    # Sort logs by timestamp to ensure chronological order for va_active flag
    logs.sort(key=lambda x: (x.get('timestamp', ''), not x.get('operation', {}).get('first', False)))

    for i, log in enumerate(logs):
        ts = log.get('timestamp')
        if not ts: continue
        formatted_ts = format_timestamp(ts)
        log_name = log.get('logName', '')
        task_id = f"task{i}"

        if "contactcenteraiplatform.googleapis.com%2Factivity" in log_name:
            text_payload = log.get("textPayload", "N/A")
            if text_payload.startswith("[CRM-Server]") or \
               text_payload.startswith("[External-Storage]") or \
               ("GCS upload done, key" in text_payload and "metadata" in text_payload):
                continue
            # Sanitize text_payload to avoid breaking Mermaid syntax
            text_payload = text_payload.replace(":", "").replace(",", "")
            ccaip_activity_events.append(f"{text_payload} :milestone, {task_id}, {formatted_ts}, 0s")
        elif "contactcenteraiplatform.googleapis.com%2Fevents" in log_name:
            event_data = log.get("jsonPayload", {}).get("event", {})
            event_name = event_data.get("name")
            payload = event_data.get("payload", {})
            participant = payload.get("participant", {})
            participant_type = participant.get("type")
            participant_id = participant.get("id", "")
            session = payload.get("session", {})
            session_id = session.get('id', "").replace('session_', '')

            if event_name == "session_started":
                ccaip_events.append(f"session_started ({session_id}) :milestone, {task_id}, {formatted_ts}, 0s")
            elif event_name == "session_ended":
                ccaip_events.append(f"session_ended ({session_id}) :milestone, {task_id}, {formatted_ts}, 0s")
            elif event_name == "session_participant_joined":
                p_type = participant_type or "unknown"
                if p_type == "end_user":
                    ccaip_events.append(f"end_user_joined :milestone, {task_id}, {formatted_ts}, 0s")
                elif p_type == "virtual_agent":
                    va_id = participant_id.replace('virtual_agent_', '')
                    ccaip_events.append(f"virtual_agent_joined ({va_id}) :milestone, {task_id}, {formatted_ts}, 0s")
                    va_active = True
                elif p_type == "agent":
                    agent_id = participant_id.replace('user_', '')
                    ccaip_events.append(f"human_agent_joined ({agent_id}) :milestone, {task_id}, {formatted_ts}, 0s")
                else:
                    ccaip_events.append(f"{p_type.capitalize()} Joined ({participant_id}) :{task_id}, {formatted_ts}, 0s")
            elif event_name == "session_participant_left":
                p_type = participant_type or "unknown"
                if p_type == "end_user":
                    ccaip_events.append(f"end_user_left :milestone, {task_id}, {formatted_ts}, 0s")
                elif p_type == "virtual_agent":
                    va_id = participant_id.replace('virtual_agent_', '')
                    ccaip_events.append(f"virtual_agent_left ({va_id}) :milestone, {task_id}, {formatted_ts}, 0s")
                    va_active = False
                elif p_type == "agent":
                    agent_id = participant_id.replace('user_', '')
                    ccaip_events.append(f"human_agent_left ({agent_id}) :milestone, {task_id}, {formatted_ts}, 0s")
                else:
                    ccaip_events.append(f"{p_type.capitalize()} Left ({participant_id}) :{task_id}, {formatted_ts}, 0s")

        if "cloudaudit.googleapis.com%2Fdata_access" in log_name:
            protoPayload = log.get("protoPayload", {})
            if protoPayload.get("serviceName") == "dialogflow.googleapis.com":
                methodName = protoPayload.get("methodName", "").split('.')[-1]
                task_id = f"dfa{len(df_audit_events)}"
                if methodName == "CreateConversation":
                    conv_name = protoPayload.get("response", {}).get("name", "")
                    conv_id = conv_name.split('/')[-1] if '/' in conv_name else conv_name
                    df_audit_events.append(f"CreateConversation ({conv_id}) :milestone, {task_id}, {formatted_ts}, 0s")
                elif methodName == "CreateParticipant":
                    role = protoPayload.get("request", {}).get("participant", {}).get("role", "UNKNOWN")
                    df_audit_events.append(f"CreateParticipant ({role}) :milestone, {task_id}, {formatted_ts}, 0s")
                elif methodName == "StreamingAnalyzeContent":
                    if log.get("operation", {}).get("first"):
                        df_audit_events.append(f"StreamingAnalyzeContent (request) :milestone, {task_id}, {formatted_ts}, 0s")
                    elif log.get("operation", {}).get("last"):
                        df_audit_events.append(f"StreamingAnalyzeContent (response) :milestone, {task_id}, {formatted_ts}, 0s")
                elif methodName == "CompleteConversation":
                    state = protoPayload.get("response", {}).get("lifecycleState", "UNKNOWN")
                    df_audit_events.append(f"CompleteConversation ({state}) :milestone, {task_id}, {formatted_ts}, 0s")
                else:
                    df_audit_events.append(f"{methodName} :milestone, {task_id}, {formatted_ts}, 0s")

        if "dialogflow-runtime.googleapis.com%2Frequests" in log_name:
            query_input = log.get("jsonPayload", {}).get("queryInput")
            query_result = log.get("jsonPayload", {}).get("queryResult")
            task_id = f"dfr{len(df_runtime_events)}"

            if query_input and not query_result:
                input_type = "UNKNOWN"
                input_details = ""
                if query_input.get("audio"): input_type = "AUDIO"
                elif query_input.get("text"):
                    input_type = "TEXT"
                    text = query_input.get("text", {}).get("text", "")
                    input_details = f", {text}"
                elif query_input.get("event"):
                    input_type = "EVENT"
                    input_details = f", {query_input.get("event", {}).get("event")}"
                elif query_input.get("dtmf"): input_type = "DTMF"
                elif query_input.get("intent"): input_type = "INTENT"
                df_runtime_events.append(f"INPUT ({input_type}{input_details}) :milestone, {task_id}, {formatted_ts}, 0s")
            elif query_result and va_active:
                match = query_result.get("match", {})
                match_type = match.get("matchType")
                page = query_result.get("currentPage", {}).get("displayName", "N/A")
                intent = query_result.get("intent", {}).get("displayName", "N/A")
                agent_responses = query_result.get("responseMessages", [])
                task_id = f"dfr{len(df_runtime_events)}"
                
                if match_type == "INTENT" or match_type == "DIRECT_INTENT":
                    event_desc = f"{match_type}_MATCH ({intent})"
                    df_runtime_events.append(f"{event_desc} :milestone, {task_id}, {formatted_ts}, 0s")
                    # VA Responses
                    has_end_interaction = any(resp.get("endInteraction") is not None for resp in agent_responses)
                    for resp in agent_responses:
                        if resp.get("text", {}).get("text"):
                             text = resp["text"]["text"][0]
                             short_text = " ".join(text.split()[:2])
                             end_note = " endInteraction" if has_end_interaction else ""
                             df_runtime_events.append(f"INTENT_HANDLE ({intent}, {short_text}...{end_note}) :milestone, {task_id}_h, {formatted_ts}, 0s")
                             break
                elif match_type == "NO_INPUT":
                    if not first_no_input:
                        first_no_input = f"NO_INPUT Start :crit, {task_id}, {formatted_ts}, 0s"
                    last_no_input = f"NO_INPUT End :crit, {task_id}, {formatted_ts}, 0s"
                elif match_type == "NO_MATCH":
                     df_runtime_events.append(f"NO_MATCH on {page} :{task_id}, {formatted_ts}, 0s")
                elif match_type == "EVENT":
                     df_runtime_events.append(f"Event: {match.get('event')} -> {page} :{task_id}, {formatted_ts}, 0s")

    if first_no_input:
        df_runtime_events.append(first_no_input)
    if last_no_input and last_no_input != first_no_input:
        df_runtime_events.append(last_no_input)

    if ccaip_events:
        gantt_lines.append("    section CCAIP Events")
        gantt_lines.extend([f"    {e}" for e in ccaip_events])
    if ccaip_activity_events:
        gantt_lines.append("")
        gantt_lines.append("    section CCAIP Activity")
        gantt_lines.extend([f"    {e}" for e in ccaip_activity_events])
    if df_audit_events:
        gantt_lines.append("")
        gantt_lines.append("    section Dialogflow Audit")
        gantt_lines.extend([f"    {e}" for e in df_audit_events])
    if df_runtime_events:
        gantt_lines.append("")
        gantt_lines.append("    section Dialogflow Runtime")
        gantt_lines.extend([f"    {e}" for e in df_runtime_events])

    return "\n".join(gantt_lines)

def main():
    parser = argparse.ArgumentParser(description='Generate a Mermaid Gantt chart from combined call logs.')
    parser.add_argument('--in_file', required=True, help='Input JSON file containing combined logs')
    parser.add_argument('--call_id', required=True, help='Call ID for the title')
    parser.add_argument('--out_file', help='Output file name for Mermaid Gantt chart markdown')
    args = parser.parse_args()

    try:
        with open(args.in_file, 'r') as f:
            all_logs = json.load(f)
    except Exception as e:
        print(f"Error reading input file {args.in_file}: {e}")
        return

    gantt_chart = generate_mermaid_gantt(all_logs, args.call_id)
    gantt_filename = args.out_file if args.out_file else f"call_{args.call_id}_gantt.md"

    try:
        with open(gantt_filename, 'w') as f:
            f.write("```mermaid\n")
            f.write(gantt_chart)
            f.write("\n```")
        print(f"Successfully saved Gantt chart to {gantt_filename}")
    except Exception as e:
        print(f"Error saving Gantt chart: {e}")

if __name__ == '__main__':
    main()
