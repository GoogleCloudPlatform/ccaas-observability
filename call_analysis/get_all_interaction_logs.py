import argparse
import json
from script_utils import save_json_to_file
from get_contact_center_logs import fetch_contact_center_logs
from get_conversation_logs import fetch_dialogflow_logs

def main():
    parser = argparse.ArgumentParser(description='Get all logs for a call from Contact Center and Dialogflow.')
    parser.add_argument('--contact_center_project_id', required=True, help='GCP Project ID for Contact Center logs')
    parser.add_argument('--contact_center_id', required=True, help='Contact Center ID (resource.labels.resource_id)')
    parser.add_argument('--virtual_agent_project_id', help='GCP Project ID for Dialogflow logs (defaults to Contact Center project ID)')
    parser.add_argument('--call_id', required=True, help='Call ID to trace')
    parser.add_argument('--lookback', type=int, default=60, help='Lookback period in minutes (default: 60)')
    parser.add_argument('--call_id_parameter', default='call_id', help='The session parameter name for the Call ID in Dialogflow (default: call_id)')
    parser.add_argument('--insights_project_id', help='GCP Project ID for CCAI Insights API (defaults to virtual_agent_project_id if not set)')
    parser.add_argument('--location', help='GCP location of the Contact Center resource')
    parser.add_argument('--out_file', help='Output file name for combined logs')
    parser.add_argument('--include_activity', action='store_true', help='Include activity logs in the Contact Center query')
    args = parser.parse_args()

    cc_project_id = args.contact_center_project_id
    va_project_id = args.virtual_agent_project_id if args.virtual_agent_project_id else cc_project_id
    call_id = args.call_id
    lookback = args.lookback
    call_id_param = args.call_id_parameter
    insights_project_id = args.insights_project_id

    # Step 1: Get Contact Center Logs
    print("--- Fetching Contact Center Logs ---")
    cc_logs = fetch_contact_center_logs(cc_project_id, args.contact_center_id, call_id, lookback, include_activity=args.include_activity)

    # Step 2: Get Dialogflow Conversation ID and Logs
    print("--- Fetching Dialogflow Logs ---")
    df_logs = fetch_dialogflow_logs(va_project_id, lookback, call_id=call_id, call_id_parameter=call_id_param, insights_project_id=insights_project_id, contact_center_id=args.contact_center_id, location=args.location)

    # Step 3: Combine Logs
    all_logs = (cc_logs or []) + (df_logs or [])

    if not all_logs:
        print("No logs found to combine.")
        return

    all_logs.sort(key=lambda x: x.get('timestamp', ''))

    # Step 4: Save Combined Logs
    output_filename = args.out_file if args.out_file else f"call_{call_id}_all_logs.json"
    save_json_to_file(all_logs, output_filename)

    print("\n--- Combined Log Summary ---")
    print(f"Call ID: {call_id}")
    print(f"Total Logs: {len(all_logs)}")
    if all_logs:
        print(f"Oldest Log: {all_logs[0]['timestamp']}")
        print(f"Newest Log: {all_logs[-1]['timestamp']}")

if __name__ == '__main__':
    main()
