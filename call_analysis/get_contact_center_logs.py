import argparse
import json
from script_utils import run_gcloud_command, get_time_filter, save_json_to_file

def get_session_id(log):
    payload = log.get("jsonPayload", {}).get("event", {}).get("payload", {})
    if "session" in payload and "id" in payload["session"]:
        return payload["session"]["id"]
    return None

def has_call_id(log, call_id):
    call_id_str = str(call_id)
    if call_id_str.startswith("call_") or call_id_str.startswith("chat_"):
        call_id_full = call_id_str
    else:
        call_id_full = f"call_{call_id}"
    payload = log.get("jsonPayload", {}).get("event", {}).get("payload", {})
    labels = log.get("labels", {})

    if payload.get("call", {}).get("id") == call_id:
        return True
    if payload.get("chat", {}).get("id") == call_id_str:
        return True
    if payload.get("participant", {}).get("call_id") == call_id_full:
        return True
    if labels.get("tracker_id") == call_id_full:
        return True
    return False

def fetch_contact_center_logs(project_id, contact_center_id, call_id, lookback_minutes, include_activity=False):
    '''Fetches contact center logs related to a call ID and session ID.'''
    time_filter = get_time_filter(lookback_minutes)

    call_id_str = str(call_id)
    if call_id_str.startswith("call_") or call_id_str.startswith("chat_"):
        call_id_full = call_id_str
    else:
        call_id_full = f"call_{call_id}"

    log_name_filter = "" if include_activity else f'AND -logName="projects/{project_id}/logs/contactcenteraiplatform.googleapis.com%2Factivity"'

    # Pass 1: Find Session ID(s) from logs matching Call ID
    print(f"--- CC Logs: Pass 1: Querying for Call ID: {call_id} to find Session ID ---")
    
    filter_conditions = []
    if call_id_str.isdigit():
        filter_conditions.append(f'jsonPayload.event.payload.call.id={call_id_str}')
    
    filter_conditions.extend([
        f'jsonPayload.event.payload.chat.id="{call_id_str}"',
        f'jsonPayload.event.payload.participant.call_id="{call_id_full}"',
        f'labels.tracker_id="{call_id_full}"'
    ])
    
    or_conditions = " OR ".join(filter_conditions)

    call_query_filter = f'''
    resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
    AND resource.labels.resource_id="{contact_center_id}"
    AND (
        {or_conditions}
    )
    {log_name_filter}
    AND {time_filter}
    '''
    call_query_filter = " ".join(call_query_filter.split())
    gcloud_call_command = f"gcloud logging read '{call_query_filter}' --project {project_id} --format json"
    call_id_logs = run_gcloud_command(gcloud_call_command)

    session_id = None
    found_session_ids = set()
    if call_id_logs:
        for entry in call_id_logs:
            s_id = get_session_id(entry)
            if s_id:
                found_session_ids.add(s_id)
        print(f"Found {len(call_id_logs)} logs in Pass 1.")
    else:
        print("No logs found matching Call ID in Pass 1.")
        call_id_logs = []

    if not found_session_ids:
        print(f"Could not deduce Session ID from logs for Call ID: {call_id}")
    else:
        if len(found_session_ids) > 1:
            print(f"Warning: Found multiple Session IDs: {sorted(list(found_session_ids))}. Using the first one.")
        session_id = sorted(list(found_session_ids))[0]
        print(f"Deduced Session ID: {session_id}")

    # Pass 2: Get all logs for the deduced Session ID
    session_logs = []
    if session_id:
        print(f"--- CC Logs: Pass 2: Querying all logs for Session ID: {session_id} ---")
        session_query_filter = f'''
        resource.type="contactcenteraiplatform.googleapis.com/ContactCenter"
        AND resource.labels.resource_id="{contact_center_id}"
        AND jsonPayload.event.payload.session.id="{session_id}"
        {log_name_filter}
        AND {time_filter}
        '''
        session_query_filter = " ".join(session_query_filter.split())
        gcloud_session_command = f"gcloud logging read '{session_query_filter}' --project {project_id} --format json"
        session_logs = run_gcloud_command(gcloud_session_command)
        if session_logs:
            print(f"Found {len(session_logs)} logs in Pass 2.")
        else:
            print("No additional logs found for the deduced Session ID.")
            session_logs = []
    else:
         session_logs = []

    # Combine and Analyze
    all_logs_dict = {}
    for log in call_id_logs:
        all_logs_dict[log['insertId']] = log
    for log in session_logs:
        all_logs_dict[log['insertId']] = log

    combined_logs = list(all_logs_dict.values())

    # Sort logs by timestamp ascending
    combined_logs.sort(key=lambda x: x['timestamp'])

    call_id_only_count = 0
    session_id_only_count = 0
    both_count = 0

    for log in combined_logs:
        log_has_call = has_call_id(log, call_id)
        log_session = get_session_id(log)
        log_has_session = log_session is not None and log_session == session_id

        if log_has_call and log_has_session:
            both_count += 1
        elif log_has_call:
            call_id_only_count += 1
        elif log_has_session:
            session_id_only_count += 1

    print("\n--- CC Logs Summary ---")
    print(f"Call ID: {call_id}")
    print(f"Deduced Session ID: {session_id if session_id else 'Not Found'}")
    print(f"Total Unique Logs Analyzed: {len(combined_logs)}")
    print(f"Logs matching Call ID {call_id} only: {call_id_only_count}")
    print(f"Logs matching Session ID {session_id} only: {session_id_only_count}")
    print(f"Logs matching Both Call ID {call_id} AND Session ID {session_id}: {both_count}")

    return combined_logs

def main():
    parser = argparse.ArgumentParser(description='Query Contact Center logs for call and session information.')
    parser.add_argument('--contact_center_project_id', required=True, help='GCP Project ID')
    parser.add_argument('--contact_center_id', required=True, help='Contact Center ID (resource.labels.resource_id)')
    parser.add_argument('--call_id', required=True, type=int, help='Call ID (number only)')
    parser.add_argument('--lookback', type=int, default=180, help='Lookback period in minutes (default: 180)')
    parser.add_argument('--save_logs', action='store_true', help='Save the combined logs to a JSON file')
    parser.add_argument('--include_activity', action='store_true', help='Include activity logs in the query')
    args = parser.parse_args()

    combined_logs = fetch_contact_center_logs(args.contact_center_project_id, args.contact_center_id, args.call_id, args.lookback, args.include_activity)

    if args.save_logs:
        output_filename = f"call_{args.call_id}_cc_logs.json"
        save_json_to_file(combined_logs, output_filename)

if __name__ == '__main__':
    main()