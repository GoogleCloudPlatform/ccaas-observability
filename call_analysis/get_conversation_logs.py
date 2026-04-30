import argparse
import json
from script_utils import run_gcloud_command, get_time_filter, save_json_to_file, get_dialogflow_conversation_id

def fetch_dialogflow_logs(project_id, lookback_minutes, call_id=None, conversation_id=None, call_id_parameter='call_id', insights_project_id=None, contact_center_id=None, location=None):
    """Fetches Dialogflow logs for a given call ID or conversation ID."""
    time_filter = get_time_filter(lookback_minutes)

    if call_id and not conversation_id:
        conversation_id = get_dialogflow_conversation_id(project_id, call_id, lookback_minutes, call_id_parameter, insights_project_id, contact_center_id, location)
        if not conversation_id:
            print(f"Could not find Conversation ID for Call ID: {call_id}")
            return []
        # print(f"Found Conversation ID: {conversation_id} for Call ID: {call_id}") # This is printed inside the util function
    elif not conversation_id:
        print("Error: Either call_id or conversation_id must be provided.")
        return []

    print(f"--- DF Logs: Querying Audit Logs for Conversation ID: {conversation_id} in project {project_id} ---")
    query_filter = f'''
    logName:"cloudaudit.googleapis.com%2Fdata_access"
    protoPayload.serviceName="dialogflow.googleapis.com"
    AND (
      (protoPayload.methodName="google.cloud.dialogflow.v2beta1.Conversations.CreateConversation" AND protoPayload.response.name:"{conversation_id}") OR
      (protoPayload.methodName!="google.cloud.dialogflow.v2beta1.Conversations.CreateConversation" AND protoPayload.resourceName:"{conversation_id}")
    )
    AND {time_filter}
    '''
    query_filter = " ".join(query_filter.split())
    gcloud_command = f"gcloud logging read '{query_filter}' --project {project_id} --format json"
    audit_logs = run_gcloud_command(gcloud_command)
    num_audit_logs = len(audit_logs) if audit_logs else 0
    print(f"Found {num_audit_logs} audit log entries.")

    runtime_query_filter = f'''
    logName:"dialogflow-runtime.googleapis.com%2Frequests"
    labels.session_id="{conversation_id}"
    AND {time_filter}
    '''
    runtime_query_filter = " ".join(runtime_query_filter.split())
    gcloud_runtime_command = f"gcloud logging read '{runtime_query_filter}' --project {project_id} --format json"

    print(f"--- DF Logs: Querying for Runtime Logs for Session ID: {conversation_id} ---")
    runtime_logs = run_gcloud_command(gcloud_runtime_command)
    num_runtime_logs = len(runtime_logs) if runtime_logs else 0
    print(f"Found {num_runtime_logs} runtime log entries.")

    all_logs = (audit_logs or []) + (runtime_logs or [])

    if not all_logs:
        print("No DF logs found matching the criteria.")
        return []

    all_logs.sort(key=lambda x: x.get('timestamp', ''))
    print(f"Found {len(all_logs)} total DF log entries.")

    print("\n--- DF Logs Summary ---")
    print(f"Project ID: {project_id}")
    if call_id:
        print(f"Call ID: {call_id}")
    print(f"Conversation ID: {conversation_id}")
    print(f"Audit Logs Found (data access): {num_audit_logs}")
    print(f"Runtime Logs Found (dialogflow runtime): {num_runtime_logs}")
    print(f"Total Logs Found: {len(all_logs)}")
    if all_logs:
        print(f"Oldest Log Timestamp: {all_logs[0]['timestamp']}")
        print(f"Newest Log Timestamp: {all_logs[-1]['timestamp']}")

    return all_logs

def main():
    parser = argparse.ArgumentParser(description='Query Dialogflow logs for a specific conversation.')
    parser.add_argument('--virtual_agent_project_id', required=True, help='GCP Project ID for Dialogflow logs')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--conversation_id', help='Dialogflow Conversation ID')
    group.add_argument('--call_id', help='Call ID to map to Dialogflow Conversation ID')
    parser.add_argument('--call_id_parameter', default='call_id', help='The session parameter name containing the Call ID (default: call_id)')
    parser.add_argument('--insights_project_id', help='GCP Project ID for CCAI Insights API (defaults to virtual_agent_project_id if not set)')
    parser.add_argument('--lookback', type=int, default=180, help='Lookback period in minutes (default: 180)')
    parser.add_argument('--save_logs', action='store_true', help='Save the logs to a JSON file')
    args = parser.parse_args()

    all_logs = fetch_dialogflow_logs(args.virtual_agent_project_id, args.lookback, args.call_id, args.conversation_id, args.call_id_parameter, args.insights_project_id)

    if args.save_logs and all_logs:
        if args.call_id:
            output_filename = f"call_{args.call_id}_df_logs.json"
        else:
            output_filename = f"conversation_{args.conversation_id}_logs.json"
        save_json_to_file(all_logs, output_filename)

if __name__ == '__main__':
    main()
