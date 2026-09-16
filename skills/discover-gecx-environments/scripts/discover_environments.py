#!/usr/bin/env python3
"""
GECX Environment Discovery Script
Discovers GECX (CCaaS, Dialogflow, CXAS) environment resources using
native Google Cloud REST APIs and Logging sinks, and populates or updates
gecx_environments.yaml based on gecx_environments.yaml.sample.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
import yaml


def run_gcloud(cmd_list):
    """Executes a gcloud command and returns parsed JSON or None."""
    try:
        res = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            check=True
        )
        if not res.stdout.strip():
            return []
        return json.loads(res.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Warning: gcloud command failed: {' '.join(cmd_list)}", file=sys.stderr)
        print(f"Stderr: {e.stderr.strip()}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print(f"Warning: could not parse JSON from gcloud output: {res.stdout[:200]}", file=sys.stderr)
        return None


def get_gcloud_token():
    """Retrieves an access token using gcloud auth print-access-token."""
    try:
        res = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        try:
            res = subprocess.run(
                ["gcloud", "auth", "application-default", "print-access-token"],
                capture_output=True,
                text=True,
                check=True
            )
            return res.stdout.strip()
        except Exception as e:
            print(f"Warning: could not retrieve gcloud access token: {e}", file=sys.stderr)
            return None


def fetch_api(url, token, user_project=None):
    """Fetches JSON from a Google Cloud REST API endpoint using an OAuth token."""
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    if user_project:
        req.add_header("X-goog-user-project", user_project)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except urllib.error.HTTPError as e:
        # Don't spam warnings for 404 or empty location resources
        if e.code not in (404, 403):
            print(f"Warning: API request to {url} returned code {e.code}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Warning: API request error for {url}: {e}", file=sys.stderr)
        return None


def discover_logging_sinks(project_id):
    """Discovers Cloud Logging sinks using native gcloud logging."""
    cmd = [
        "gcloud", "logging", "sinks", "list",
        f"--project={project_id}",
        "--format=json"
    ]
    return run_gcloud(cmd) or []


def deduce_environment_name(project_id):
    """Deduces a readable environment name from project ID."""
    match = re.search(r'(?:ccaip|gecx)-([a-zA-Z0-9]+)-(?:infra|logs)', project_id)
    if match:
        return match.group(1)
    for kw in ["probing", "staging", "prod", "production", "dev", "test", "demo"]:
        if kw in project_id.lower():
            return kw
    return project_id


def discover_ccaas_contact_centers(project_id, token):
    """Queries CCaaS API for Contact Centers across all locations."""
    if not token:
        return []
    url = f"https://contactcenteraiplatform.googleapis.com/v1alpha1/projects/{project_id}/locations/-/contactCenters"
    data = fetch_api(url, token, user_project=project_id)
    if not data or "contactCenters" not in data:
        return []

    contact_centers = []
    for cc in data["contactCenters"]:
        full_name = cc.get("name", "")
        parts = full_name.split("/")
        loc = parts[3] if len(parts) >= 4 else "unknown"
        cc_id = parts[5] if len(parts) >= 6 else full_name

        # Only track deployed contact centers
        if cc.get("state") and cc.get("state") != "STATE_DEPLOYED":
            continue

        info = {
            "id": cc_id,
            "location": loc,
            "display_name": cc.get("displayName", ""),
            "domain_prefix": cc.get("customerDomainPrefix", ""),
        }
        if "uris" in cc and "rootUri" in cc["uris"]:
            info["root_uri"] = cc["uris"]["rootUri"]
        contact_centers.append(info)
    return contact_centers


def discover_dialogflow_resources(project_id, token, target_locations):
    """Discovers available Dialogflow locations and agents."""
    if not token:
        return [], []

    # 1. Discover available Dialogflow locations
    loc_url = f"https://dialogflow.googleapis.com/v2/projects/{project_id}/locations"
    loc_data = fetch_api(loc_url, token, user_project=project_id)
    available_locs = []
    cx_supported_locs = set()

    if loc_data and "locations" in loc_data:
        for loc_obj in loc_data["locations"]:
            loc_id = loc_obj.get("locationId")
            available_locs.append(loc_id)
            labels = loc_obj.get("labels", {})
            if labels.get("dialogflow.googleapis.com/dialogflowCxSupported") == "true":
                cx_supported_locs.add(loc_id)

    # 2. Query agents for target locations (must include global and locations of interest)
    locations_to_scan = {"global", "us-central1"}
    for loc in target_locations:
        if loc in cx_supported_locs:
            locations_to_scan.add(loc)

    agents = []
    for loc in sorted(list(locations_to_scan)):
        if loc == "global":
            agent_url = f"https://dialogflow.googleapis.com/v3/projects/{project_id}/locations/global/agents"
        else:
            agent_url = f"https://{loc}-dialogflow.googleapis.com/v3/projects/{project_id}/locations/{loc}/agents"

        res = fetch_api(agent_url, token, user_project=project_id)
        if res and "agents" in res:
            for ag in res["agents"]:
                name = ag.get("name", "")
                agent_id = name.split("/")[-1]
                agent_info = {
                    "id": agent_id,
                    "location": loc,
                    "display_name": ag.get("displayName", ""),
                    "default_language_code": ag.get("defaultLanguageCode", "en"),
                    "time_zone": ag.get("timeZone", "")
                }
                adv = ag.get("advancedSettings", {})
                if "audioExportGcsDestination" in adv and "uri" in adv["audioExportGcsDestination"]:
                    agent_info["audio_export_gcs"] = adv["audioExportGcsDestination"]["uri"]
                agents.append(agent_info)

    return available_locs, agents


def discover_cxas_resources(project_id, token, target_locations):
    """Discovers CX Agent Studio (ces.googleapis.com) apps across target locations."""
    if not token:
        return [], []

    loc_url = f"https://ces.googleapis.com/v1/projects/{project_id}/locations"
    loc_data = fetch_api(loc_url, token, user_project=project_id)
    available_locs = []
    if loc_data and "locations" in loc_data:
        for loc_obj in loc_data["locations"]:
            loc_id = loc_obj.get("locationId")
            if loc_id:
                available_locs.append(loc_id)

    locations_to_scan = set(target_locations)
    locations_to_scan.update(available_locs)
    locations_to_scan.add("global")

    apps = []
    for loc in sorted(locations_to_scan):
        if not loc:
            continue
        apps_url = f"https://ces.googleapis.com/v1/projects/{project_id}/locations/{loc}/apps"
        apps_data = fetch_api(apps_url, token, user_project=project_id)
        if apps_data and "apps" in apps_data:
            for app in apps_data["apps"]:
                full_name = app.get("name", "")
                parts = full_name.split("/")
                app_id = parts[-1] if parts else full_name
                apps.append({
                    "id": app_id,
                    "location": loc,
                    "display_name": app.get("displayName", ""),
                })
    return available_locs, apps


def discover_conversation_profiles(project_id, token, target_locations):
    """Discovers Dialogflow v2 Conversation Profiles across target locations."""
    if not token:
        return []

    locations_to_scan = set(target_locations)
    locations_to_scan.add("global")

    profiles = []
    for loc in sorted(list(locations_to_scan)):
        if not loc:
            continue
        if loc == "global":
            cp_url = f"https://dialogflow.googleapis.com/v2beta1/projects/{project_id}/locations/global/conversationProfiles"
        else:
            cp_url = f"https://{loc}-dialogflow.googleapis.com/v2beta1/projects/{project_id}/locations/{loc}/conversationProfiles"

        res = fetch_api(cp_url, token, user_project=project_id)
        if res and "conversationProfiles" in res:
            for cp in res["conversationProfiles"]:
                name = cp.get("name", "")
                profile_id = name.split("/")[-1]
                profile_info = {
                    "id": profile_id,
                    "location": loc,
                    "display_name": cp.get("displayName", ""),
                }
                auto_agent = cp.get("automatedAgentConfig", {})
                if "agent" in auto_agent:
                    profile_info["target_agent"] = auto_agent["agent"]
                profiles.append(profile_info)

    return profiles


def discover_environment(project_id, env_name=None):
    """Discovers environment configuration for a given GCP project."""
    if not env_name:
        env_name = deduce_environment_name(project_id)

    print(f"[*] Discovering resources in project '{project_id}' for environment '{env_name}'...")
    token = get_gcloud_token()

    # 1. Discover CCaaS Contact Centers via native API
    print(f"[*] Querying CCaaS API (contactcenteraiplatform.googleapis.com)...")
    contact_centers = discover_ccaas_contact_centers(project_id, token)
    if contact_centers:
        print(f"    Found {len(contact_centers)} CCaaS contact center instances.")

    # 2. Discover Log Sinks -> aggregate_logs_project_id
    print(f"[*] Discovering Log Sinks via Cloud Logging API...")
    aggregate_logs_project_id = None
    sinks = discover_logging_sinks(project_id)
    for sink in sinks:
        sink_name = sink.get("name", "")
        if "ccaas-logs-project" in sink_name or sink_name not in ("_Default", "_Required"):
            dest = sink.get("destination", "")
            dest_match = re.search(r'projects/([a-zA-Z0-9-]+)', dest)
            if dest_match and dest_match.group(1) != project_id:
                aggregate_logs_project_id = dest_match.group(1)
                print(f"    Found aggregate logs destination via sink '{sink_name}': {aggregate_logs_project_id}")
                break

    components = set()
    candidate_locations = {"us-central1", "global"}

    if contact_centers:
        components.add("ccaas")
        for cc in contact_centers:
            candidate_locations.add(cc["location"])

    # 3. Discover Dialogflow Locations & Agents
    print(f"[*] Querying Dialogflow API (dialogflow.googleapis.com)...")
    df_locations, df_agents = discover_dialogflow_resources(project_id, token, candidate_locations)
    if df_agents:
        components.add("dialogflow")
        print(f"    Found {len(df_agents)} Dialogflow CX agent(s).")
    for loc in df_locations:
        candidate_locations.add(loc)

    # 4. Discover Dialogflow Conversation Profiles
    print(f"[*] Querying Dialogflow Conversation Profiles (v2beta1 API)...")
    conversation_profiles = discover_conversation_profiles(project_id, token, candidate_locations)
    if conversation_profiles:
        components.add("dialogflow")
        print(f"    Found {len(conversation_profiles)} Conversation Profile(s).")

    # 5. Discover CX Agent Studio (CXAS) Apps
    print(f"[*] Querying CXAS API (ces.googleapis.com)...")
    cxas_locations, cxas_apps = discover_cxas_resources(project_id, token, candidate_locations)
    if cxas_apps:
        components.add("cxas")
        print(f"    Found {len(cxas_apps)} CXAS app(s).")

    env_config = {
        "description": f"{env_name.capitalize()} environment (discovered)",
        "default_project_id": project_id,
    }

    if aggregate_logs_project_id:
        env_config["aggregate_logs_project_id"] = aggregate_logs_project_id

    if components:
        env_config["components"] = sorted(list(components))

    if contact_centers:
        env_config["contact_centers"] = contact_centers

    if df_agents:
        env_config["dialogflow_agents"] = df_agents

    if conversation_profiles:
        env_config["conversation_profiles"] = conversation_profiles

    if cxas_apps:
        env_config["cxas_apps"] = cxas_apps

    return env_name, env_config


def update_config_file(config_path, sample_path, env_name, env_config, set_default=False):
    """Updates or creates the YAML configuration file."""
    config_data = {}

    if os.path.exists(config_path):
        print(f"[*] Reading existing config from '{config_path}'...")
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f) or {}
    elif os.path.exists(sample_path):
        print(f"[*] Initializing '{config_path}' from sample template '{sample_path}'...")
        with open(sample_path, "r") as f:
            config_data = yaml.safe_load(f) or {}

    if "environments" not in config_data:
        config_data["environments"] = {}

    config_data["environments"][env_name] = env_config

    if set_default or "default_environment" not in config_data:
        config_data["default_environment"] = env_name

    header = (
        "# GECX Observability Environment Configuration\n"
        "# This file is read by GECX skills and helper scripts to resolve environment-specific\n"
        "# project IDs, locations, and resource identifiers without hardcoding them in skills.\n\n"
    )

    with open(config_path, "w") as f:
        f.write(header)
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

    print(f"[+] Successfully wrote configuration for environment '{env_name}' to '{config_path}'.")


def main():
    parser = argparse.ArgumentParser(description="Discover GECX environment resources via native Google Cloud REST APIs.")
    parser.add_argument("--project", required=True, help="GCP Project ID to inspect (e.g., ccaip-probing-infra-u8xi7u).")
    parser.add_argument("--env-name", help="Environment key name (e.g., probing). Defaults to auto-deduced name.")
    parser.add_argument("--config-path", default="gecx_environments.yaml", help="Path to gecx_environments.yaml.")
    parser.add_argument("--sample-path", default="gecx_environments.yaml.sample", help="Path to sample file.")
    parser.add_argument("--set-default", action="store_true", help="Set this environment as default_environment.")
    parser.add_argument("--dry-run", action="store_true", help="Print discovered YAML without modifying config.")

    args = parser.parse_args()

    env_name, env_config = discover_environment(args.project, args.env_name)

    if args.dry_run:
        print("\n--- Discovered Environment (Dry Run) ---")
        output = {
            "environments": {
                env_name: env_config
            }
        }
        print(yaml.dump(output, default_flow_style=False, sort_keys=False))
        return

    update_config_file(
        config_path=args.config_path,
        sample_path=args.sample_path,
        env_name=env_name,
        env_config=env_config,
        set_default=args.set_default
    )


if __name__ == "__main__":
    main()
