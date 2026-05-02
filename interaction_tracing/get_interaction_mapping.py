import argparse
import json
from script_utils import run_gcloud_command, get_time_filter, get_dialogflow_conversation_id

def get_quad_from_conversation(project_id, conversation_id, lookback_minutes):
    """Finds the CCAIP Quad for a given Dialogflow Conversation ID."""
    time_filter = get_time_filter(lookback_minutes)
    
    print(f"--- Finding CCAIP Quad for Conversation ID {conversation_id} ---")
    query_filter = f'''
    logName:"contactcenteraiplatform.googleapis.com%2Fevents"
    AND jsonPayload.event.name="dialogflow_conversation_created"
    AND jsonPayload.event.payload.participant.df_conversation_id="{conversation_id}"
    AND {time_filter}
    '''
    query_filter = " ".join(query_filter.split())
    
    gcloud_command = f"gcloud logging read '{query_filter}' --project {project_id} --format json --limit 1"
    logs = run_gcloud_command(gcloud_command)
    
    if logs and len(logs) > 0:
        log = logs[0]
        quad = {
            "project_id": log.get("resource", {}).get("labels", {}).get("resource_container"),
            "location": log.get("resource", {}).get("labels", {}).get("location"),
            "resource_id": log.get("resource", {}).get("labels", {}).get("resource_id"),
            "interaction_id": log.get("labels", {}).get("tracker_id")
        }
        return quad
    return None

def get_df_quad_from_audit(project_id, conversation_id, lookback_minutes):
    """Finds the DF Quad for a given Dialogflow Conversation ID from Audit Logs."""
    time_filter = get_time_filter(lookback_minutes)
    
    print(f"--- Finding DF Quad for Conversation ID {conversation_id} ---")
    query_filter = f'''
    logName:"cloudaudit.googleapis.com%2Fdata_access"
    AND protoPayload.serviceName="dialogflow.googleapis.com"
    AND (
      (protoPayload.methodName="google.cloud.dialogflow.v2beta1.Conversations.CreateConversation" AND protoPayload.response.name:"{conversation_id}") OR
      (protoPayload.methodName!="google.cloud.dialogflow.v2beta1.Conversations.CreateConversation" AND protoPayload.resourceName:"{conversation_id}")
    )
    AND {time_filter}
    '''
    query_filter = " ".join(query_filter.split())
    
    gcloud_command = f"gcloud logging read '{query_filter}' --project {project_id} --format json --limit 1"
    logs = run_gcloud_command(gcloud_command)
    
    if logs and len(logs) > 0:
        log = logs[0]
        protoPayload = log.get("protoPayload", {})
        resource_name = protoPayload.get("resourceName") or protoPayload.get("response", {}).get("name", "")
        
        if resource_name:
            parts = resource_name.split('/')
            if len(parts) >= 6:
                return {
                    "project_id": parts[1],
                    "location": parts[3],
                    "conversation_id": parts[5]
                }
    return None

def main():
    parser = argparse.ArgumentParser(description='Map CCAIP Quad to Dialogflow Quad and vice versa.')
    parser.add_argument('--project_id', required=True, help='Centralized Project ID to query logs from')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--interaction_id', help='Interaction ID (tracker_id, e.g., call_123 or chat_456)')
    group.add_argument('--conversation_id', help='Dialogflow Conversation ID')
    parser.add_argument('--contact_center_id', help='Optional Resource ID to narrow down CCAIP Quad search')
    parser.add_argument('--location', help='Optional Location to narrow down CCAIP Quad search')
    parser.add_argument('--lookback', type=int, default=1440, help='Lookback period in minutes (default: 1440 / 1 day)')
    args = parser.parse_args()

    ccaip_quad = None
    df_quads = []
    conversation_ids = []

    if args.interaction_id:
        conversation_ids = get_dialogflow_conversation_id(args.project_id, args.interaction_id, args.lookback, contact_center_id=args.contact_center_id, location=args.location)
        if not conversation_ids:
            print("Could not find any Conversation IDs for the given Interaction ID.")
            return
        
        # We assume the interaction ID belongs to one CCAIP Quad
        # Let's find it from the first conversation ID
        ccaip_quad = get_quad_from_conversation(args.project_id, conversation_ids[0], args.lookback)

    elif args.conversation_id:
        conversation_ids = [args.conversation_id]
        ccaip_quad = get_quad_from_conversation(args.project_id, args.conversation_id, args.lookback)

    for conv_id in conversation_ids:
        df_quad = get_df_quad_from_audit(args.project_id, conv_id, args.lookback)
        if df_quad:
            df_quads.append(df_quad)

    print("\n========================================")
    print("            QUAD MAPPING RESULT         ")
    print("========================================")
    if ccaip_quad:
        print("\n--- CCAIP Quad ---")
        for k, v in ccaip_quad.items():
            print(f"  {k.replace('_', ' ').title()}: {v}")
    else:
        print("\n--- CCAIP Quad: NOT FOUND in events logs ---")

    if df_quads:
        print("\n--- Dialogflow Quad(s) ---")
        for i, dq in enumerate(df_quads):
            print(f"  [Conversation {i+1}]")
            for k, v in dq.items():
                print(f"    {k.replace('_', ' ').title()}: {v}")
    else:
        print("\n--- Dialogflow Quad: NOT FOUND in audit logs ---")
    print("========================================\n")

if __name__ == '__main__':
    main()
