import subprocess
import json
import shlex
from datetime import datetime, timedelta, timezone

def run_gcloud_command(command, raw_output=False):
    """Runs a gcloud command and returns the parsed JSON output or raw output."""
    try:
        # print(f"Running command: {command}")
        process = subprocess.run(shlex.split(command), capture_output=True, text=True, check=True)
        if raw_output:
            return process.stdout.strip()
        try:
            return json.loads(process.stdout)
        except json.JSONDecodeError:
            print(f"Warning: gcloud output for '{command}' was not valid JSON.")
            return process.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running gcloud command: {command}")
        print(f"Stderr: {e.stderr}")
        return None

def get_time_filter(lookback_minutes):
    """Generates a log filter string for the given lookback minutes."""
    if lookback_minutes > 0:
        start_time = (datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)).strftime('%Y-%m-%dT%H:%M:%SZ')
        return f'timestamp >= "{start_time}"'
    return "timestamp > 0"

def save_json_to_file(data, filename):
    """Saves data to a JSON file."""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Successfully saved {len(data)} items to {filename}")
        return True
    except Exception as e:
        print(f"Error saving to file {filename}: {e}")
        return False

def get_dialogflow_conversation_id(virtual_agent_project_id, call_id, lookback_minutes, call_id_parameter='call_id', insights_project_id=None, contact_center_id=None, location=None):
    """Gets the Dialogflow Conversation IDs for a given Call ID by searching for the
       'dialogflow_conversation_created' event in CCAIP logs.
       Adheres to the 'Identification Quad' by using contact_center_id and location if provided.
       Returns a list of unique Conversation IDs.
    """
    time_filter = get_time_filter(lookback_minutes)
    
    print(f"--- Finding DF Conv IDs for Call ID {call_id} in CCAIP logs ---")
    call_id_str = str(call_id)
    if call_id_str.startswith("call_") or call_id_str.startswith("chat_"):
        call_id_full = call_id_str
    else:
        call_id_full = f"call_{call_id}"
    
    # Use a loose filter for logName to support routed logs
    query_filter = f'''
    logName:"contactcenteraiplatform.googleapis.com%2Fevents"
    AND jsonPayload.event.name="dialogflow_conversation_created"
    AND labels.tracker_id="{call_id_full}"
    AND {time_filter}
    '''
    
    if contact_center_id:
        query_filter += f'\n    AND resource.labels.resource_id="{contact_center_id}"'
    if location:
        query_filter += f'\n    AND resource.labels.location="{location}"'
        
    query_filter = " ".join(query_filter.split())
    
    gcloud_command = f"gcloud logging read '{query_filter}' --project {virtual_agent_project_id} --format json"
    logs = run_gcloud_command(gcloud_command)
    
    conv_ids = []
    if logs and len(logs) > 0:
        for log in logs:
            try:
                c_id = log['jsonPayload']['event']['payload']['participant']['df_conversation_id']
                if c_id not in conv_ids:
                    conv_ids.append(c_id)
            except KeyError as e:
                continue
        
    if conv_ids:
        print(f"Found Conversation IDs via CCAIP logs: {conv_ids}")
        return conv_ids
    
    print(f"Could not find dialogflow_conversation_created event for Call ID: {call_id} in project {virtual_agent_project_id}")
    return []
