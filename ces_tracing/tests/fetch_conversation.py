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

"""Fetches a CES conversation (GetConversation) and saves it as a fixture input file.

  python3 ces_tracing/tests/fetch_conversation.py <project> <location> <app> <conversation> --name <name>
  python3 ces_tracing/tests/fetch_conversation.py projects/<p>/locations/<l>/apps/<a>/conversations/<c> --name <name>

The response is scrubbed of identifying values (same scrubbing as make_fixture.py --raw) and
written to fixtures/conversation_<name>.json (or to --output <path>).
Run make_fixture.py <name> afterwards to generate the expected trace for it.

Options:
  --no-redact  write the raw API response without scrubbing
  --output     write to this path instead of fixtures/conversation_<name>.json
  --force      replace the output file if it already exists
  --adc        authenticate with Application Default Credentials

Redaction is ON by default. The session ID is kept: it is a random identifier. With
--no-redact the file holds the raw response, including caller phone numbers, IP addresses,
project IDs, and what was said. Do not commit such a
file. test_fixtures.py fails if a JSON file in fixtures/ contains a real phone number or IP
address, but that guard does not detect every raw file.

Authentication uses the active gcloud account (gcloud auth print-access-token) by default, or
Application Default Credentials (gcloud auth application-default print-access-token) with --adc.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any, Dict

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(TESTS_DIR, "..", "src")))
sys.path.insert(0, TESTS_DIR)

from make_fixture import APP_CONVERSATION_RE, fixture_paths, scrub_conversation  # noqa: E402

CES_API = "https://ces.googleapis.com/v1"


def resource_name(parts) -> str:
    """Builds the conversation resource name from 1 (full name) or 4 positional arguments."""
    if len(parts) == 1:
        name = parts[0].strip("/")
    elif len(parts) == 4:
        project, location, app, conversation = parts
        name = f"projects/{project}/locations/{location}/apps/{app}/conversations/{conversation}"
    else:
        raise SystemExit(
            "Pass either <project> <location> <app> <conversation> or one full resource name "
            "(projects/<p>/locations/<l>/apps/<a>/conversations/<c>)."
        )
    if not APP_CONVERSATION_RE.match(name):
        raise SystemExit(f"Not a CES conversation resource name: {name!r}")
    return name


def access_token(use_adc: bool = False) -> str:
    """Returns an access token for the active gcloud account, or for ADC if use_adc is set."""
    cmd = ["gcloud", "auth"] + (["application-default"] if use_adc else []) + ["print-access-token"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        source = "Application Default Credentials" if use_adc else "the active gcloud account"
        raise SystemExit(f"Could not get an access token for {source}:\n{result.stderr.strip()}")
    return result.stdout.strip()


def fetch_conversation(name: str, token: str) -> Dict[str, Any]:
    project = APP_CONVERSATION_RE.match(name).group("project")
    req = urllib.request.Request(f"{CES_API}/{name}", method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("x-goog-user-project", project)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise SystemExit(f"GetConversation failed with HTTP {e.code}:\n{body}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("resource", nargs="+", help="<project> <location> <app> <conversation>, or the full resource name")
    parser.add_argument("--name", help="fixture name, e.g. callback_openapi")
    parser.add_argument("--output", help="output path (default: fixtures/conversation_<name>.json)")
    parser.add_argument(
        "--redact",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="scrub identifying values before writing (default: on; --no-redact writes the raw response)",
    )
    parser.add_argument("--force", action="store_true", help="replace an existing output file")
    parser.add_argument("--adc", action="store_true", help="authenticate with Application Default Credentials")
    args = parser.parse_args()

    name = resource_name(args.resource)
    if not args.name and not args.output:
        raise SystemExit("Pass --name <fixture_name> or --output <path>.")
    output = args.output or fixture_paths(args.name)["conversation"]
    if os.path.exists(output) and not args.force:
        raise SystemExit(f"{output} already exists; pass --force to replace it.")

    conv = fetch_conversation(name, access_token(args.adc))
    turns = conv.get("turns") or []
    if args.redact:
        conv = scrub_conversation(conv)

    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(output, "w") as f:
        json.dump(conv, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"wrote {output} ({len(turns)} turns, {'redacted' if args.redact else 'NOT redacted'})")
    if not args.redact:
        print(
            "WARNING: this file is the raw API response. It can contain phone numbers, IP addresses,\n"
            "project IDs, and what was said. Do not commit it; re-run without --no-redact first.",
            file=sys.stderr,
        )
    if args.name and not args.output:
        print(f"next: python3 ces_tracing/tests/make_fixture.py {args.name}")


if __name__ == "__main__":
    main()
