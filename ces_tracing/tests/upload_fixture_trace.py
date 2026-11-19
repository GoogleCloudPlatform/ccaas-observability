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

"""Step 3 of 3: uploads a fixture's trace file to Cloud Trace so it can be viewed.

  1. fetch_conversation.py     CES GetConversation -> fixtures/conversation_<name>.json
  2. make_fixture.py           tracer transform    -> fixtures/expected_trace_<name>.json
  3. upload_fixture_trace.py   upload that trace file to Cloud Trace   (this script)

  python3 ces_tracing/tests/upload_fixture_trace.py <name> --project <trace-project>

This script only reads fixtures/expected_trace_<name>.json and sends it. It does not run the
tracer's transform and applies no redaction of its own: what is uploaded is what step 2 wrote.
Two adjustments are made so repeated uploads stay viewable:
  * all timestamps are shifted by one offset so the trace ends now (durations are unchanged);
  * a new random trace ID is used, so uploads do not pile up on one trace.
Span IDs, parent links and attributes are never changed.

Options:
  --keep-times     upload the recorded timestamps as they are
  --keep-trace-id  upload under the trace ID stored in the file
  --dry-run        print what would be sent; do not call the API
  --adc            authenticate with Application Default Credentials

This writes real spans to the given project. They cannot be deleted; they expire with Cloud
Trace retention. Authentication uses the active gcloud account (gcloud auth print-access-token)
by default, or Application Default Credentials with --adc; the identity used needs
cloudtrace.traces.patch on the project.
"""

import argparse
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
SPAN_NAME_RE = re.compile(r"^projects/(?P<project>[^/]+)/traces/(?P<trace>[0-9a-f]{32})/spans/(?P<span>[0-9a-f]{16})$")
BATCH_SIZE = 200


def trace_path(name: str) -> str:
    return os.path.join(FIXTURES_DIR, f"expected_trace_{name}.json")


def load_spans(name: str) -> List[Dict[str, Any]]:
    path = trace_path(name)
    if not os.path.exists(path):
        raise SystemExit(f"{path} not found; run make_fixture.py {name} first.")
    with open(path) as f:
        return json.load(f)


def _parse_time(value: str) -> datetime:
    """Parses the UTC timestamps written to the trace file (e.g. 2026-11-18T13:10:54.708038Z)."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format_time(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def prepare_spans(
    spans: List[Dict[str, Any]], project: str, keep_times: bool, keep_trace_id: bool
) -> Dict[str, Any]:
    """Returns {'trace_id', 'spans'} with span names retargeted and, by default, times shifted."""
    first = SPAN_NAME_RE.match(spans[0]["name"])
    if not first:
        raise ValueError(f"Unexpected span name: {spans[0]['name']!r}")
    trace_id = first.group("trace") if keep_trace_id else uuid.uuid4().hex

    offset = None
    if not keep_times:
        latest = max(_parse_time(s["endTime"]) for s in spans)
        offset = datetime.now(timezone.utc) - latest

    out = []
    for span in spans:
        m = SPAN_NAME_RE.match(span["name"])
        if not m:
            raise ValueError(f"Unexpected span name: {span['name']!r}")
        new_span = dict(span)
        new_span["name"] = f"projects/{project}/traces/{trace_id}/spans/{m.group('span')}"
        if offset is not None:
            new_span["startTime"] = _format_time(_parse_time(span["startTime"]) + offset)
            new_span["endTime"] = _format_time(_parse_time(span["endTime"]) + offset)
        out.append(new_span)
    return {"trace_id": trace_id, "spans": out}


def access_token(use_adc: bool = False) -> str:
    """Returns an access token for the active gcloud account, or for ADC if use_adc is set."""
    cmd = ["gcloud", "auth"] + (["application-default"] if use_adc else []) + ["print-access-token"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        source = "Application Default Credentials" if use_adc else "the active gcloud account"
        raise SystemExit(f"Could not get an access token for {source}:\n{result.stderr.strip()}")
    return result.stdout.strip()


def batch_write(project: str, spans: List[Dict[str, Any]], token: str) -> None:
    url = f"https://cloudtrace.googleapis.com/v2/projects/{project}/traces:batchWrite"
    for start in range(0, len(spans), BATCH_SIZE):
        batch = spans[start : start + BATCH_SIZE]
        req = urllib.request.Request(url, data=json.dumps({"spans": batch}).encode("utf-8"), method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        req.add_header("x-goog-user-project", project)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                print(f"batchWrite spans {start + 1}-{start + len(batch)}: HTTP {resp.status}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            raise SystemExit(f"batchWrite failed with HTTP {e.code}:\n{body}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", help="fixture name, e.g. callback_openapi")
    parser.add_argument("--project", required=True, help="project ID to write the trace to")
    parser.add_argument("--keep-times", action="store_true")
    parser.add_argument("--keep-trace-id", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--adc", action="store_true", help="authenticate with Application Default Credentials")
    args = parser.parse_args()

    prepared = prepare_spans(load_spans(args.name), args.project, args.keep_times, args.keep_trace_id)
    spans, trace_id = prepared["spans"], prepared["trace_id"]
    starts = [s["startTime"] for s in spans]
    ends = [s["endTime"] for s in spans]
    print(f"trace file: {trace_path(args.name)} ({len(spans)} spans)")
    print(f"project: {args.project}")
    print(f"trace ID: {trace_id}")
    print(f"time range: {min(starts)} -> {max(ends)}")

    if args.dry_run:
        print("dry run: nothing sent. First span that would be written:")
        print(json.dumps(spans[0], indent=2, ensure_ascii=False))
        return

    batch_write(args.project, spans, access_token(args.adc))
    print("Spans can take a few seconds to become visible.")
    print(f"https://console.cloud.google.com/traces/explorer;traceId={trace_id}?project={args.project}")


if __name__ == "__main__":
    main()
