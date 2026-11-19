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

"""Builds the golden-file fixtures used by test_fixtures.py.

A fixture is a pair of files in fixtures/:
  conversation_<name>.json    a scrubbed CES GetConversation response (the input)
  expected_trace_<name>.json  the spans convert_to_trace_spans() produces for it (the output)

Create a fixture from a raw GetConversation response (scrubs it, then writes both files):
  python3 ces_tracing/tests/make_fixture.py <name> --raw /path/to/raw_conversation.json

Regenerate the expected trace after an intended change to transform.py:
  python3 ces_tracing/tests/make_fixture.py <name>

Review the diff of the expected trace before committing it: the file records what the
transform does, not what it should do.
"""

import argparse
import ipaddress
import json
import os
import re
import sys
from typing import Any, Dict, List, Set

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(TESTS_DIR, "fixtures")
sys.path.insert(0, os.path.abspath(os.path.join(TESTS_DIR, "..", "src")))

from transform import (  # noqa: E402
    CONVERSATION_RESOURCE_RE,
    convert_to_trace_spans,
    format_span_for_cloud_trace_json,
)

# Project the expected trace is written to (the 'project_id' argument of convert_to_trace_spans).
TRACE_PROJECT_ID = "example-ces-project"

EXAMPLE_PROJECT_ID = "example-ces-project"
EXAMPLE_PROJECT_NUMBER = "123456789012"
EXAMPLE_PHONE = "+15550100100"
EXAMPLE_URL_ORIGIN = "https://api.example.com"
EXAMPLE_VISITOR_ID = "00000000-0000-4000-8000-000000000001"
SCRUBBED = "<scrubbed>"

APP_CONVERSATION_RE = re.compile(
    r"^projects/(?P<project>[^/]+)/locations/(?P<location>[^/]+)/apps/(?P<app>[^/]+)"
    r"/conversations/(?P<session>[^/]+)$"
)
PROJECT_NUMBER_RE = re.compile(r"projects/(\d{6,})(?=/)")
E164_RE = re.compile(r"\+\d{8,15}")
IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
URL_ORIGIN_RE = re.compile(r"https?://[A-Za-z0-9.-]+(?::\d+)?")
VISITOR_ID_KEYS = {"visitor_id", "visitor id"}
# Telephony / SIP headers: keep the keys (shape), drop every value.
HEADER_DICT_KEYS = {"x-headers"}


def fixture_paths(name: str) -> Dict[str, str]:
    return {
        "conversation": os.path.join(FIXTURES_DIR, f"conversation_{name}.json"),
        "expected": os.path.join(FIXTURES_DIR, f"expected_trace_{name}.json"),
    }


def session_id_of(conv: Dict[str, Any]) -> str:
    """Returns the session ID from the conversation's resource name."""
    name = str(conv.get("name", ""))
    match = APP_CONVERSATION_RE.match(name) or CONVERSATION_RESOURCE_RE.match(name)
    if not match:
        raise ValueError(f"Cannot parse a session ID from conversation name {name!r}")
    return match.groupdict().get("session") or match.group("session_id")


def _collect(value: Any, keys: Set[str], found: Set[str]) -> None:
    """Collects the string values stored under any of the given keys."""
    if isinstance(value, dict):
        for k, v in value.items():
            if k in keys and isinstance(v, str) and v:
                found.add(v)
            _collect(v, keys, found)
    elif isinstance(value, list):
        for v in value:
            _collect(v, keys, found)


def _is_state_update(text: str) -> bool:
    # Same rule as transform.is_state_update, so scrubbing keeps a chunk's classification.
    return len(text) > 0 and text.startswith("<") and text.endswith(">")


def scrub_conversation(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Returns a copy of a GetConversation response with identifying values replaced.

    Replaced: project ID and number, phone numbers, IP addresses, telephony header values,
    visitor IDs, URL origins, and all dialogue text.
    Kept: the session ID (a random identifier), and with it the MD5-derived trace ID in
    propagated traceparents; tool names, tool arguments and responses, timings, tool call IDs.
    """
    match = APP_CONVERSATION_RE.match(str(raw.get("name", "")))
    if not match:
        raise ValueError(f"Unexpected conversation name: {raw.get('name')!r}")
    old_project = match.group("project")

    visitor_ids: Set[str] = set()
    _collect(raw, VISITOR_ID_KEYS, visitor_ids)
    blob = json.dumps(raw)
    project_numbers = set(PROJECT_NUMBER_RE.findall(blob))
    phones = set(E164_RE.findall(blob))
    ips = sorted(ip for ip in set(IPV4_RE.findall(blob)) if _is_ip(ip))
    origins = set(URL_ORIGIN_RE.findall(blob))
    ip_map = {ip: f"192.0.2.{i + 1}" for i, ip in enumerate(ips)}

    def scrub_str(s: str) -> str:
        s = URL_ORIGIN_RE.sub(EXAMPLE_URL_ORIGIN, s)
        s = s.replace(old_project, EXAMPLE_PROJECT_ID)
        s = PROJECT_NUMBER_RE.sub(f"projects/{EXAMPLE_PROJECT_NUMBER}", s)
        s = E164_RE.sub(EXAMPLE_PHONE, s)
        s = IPV4_RE.sub(lambda m: ip_map.get(m.group(0), m.group(0)), s)
        for vid in visitor_ids:
            s = s.replace(vid, EXAMPLE_VISITOR_ID)
        return s

    def walk(value: Any) -> Any:
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                if k in HEADER_DICT_KEYS and isinstance(v, dict):
                    out[k] = {hk: SCRUBBED for hk in v}
                else:
                    out[k] = walk(v)
            return out
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, str):
            return scrub_str(value)
        return value

    scrubbed = walk(raw)

    # Dialogue: replace what was said, keep who said it and whether it was a state update.
    for turn in scrubbed.get("turns") or []:
        for msg in turn.get("messages") or []:
            role = msg.get("role", "unknown")
            for chunk in msg.get("chunks") or []:
                if isinstance(chunk.get("text"), str):
                    chunk["text"] = SCRUBBED if _is_state_update(chunk["text"]) else f"[{role} text]"
                if isinstance(chunk.get("transcript"), str):
                    chunk["transcript"] = f"[{role} transcript]"

    # Refuse to write a fixture that still contains any of the original identifying values.
    out_blob = json.dumps(scrubbed)
    forbidden = (
        {old_project}
        | project_numbers | phones | set(ips) | origins | visitor_ids
    ) - {EXAMPLE_PROJECT_ID, EXAMPLE_PROJECT_NUMBER, EXAMPLE_PHONE, EXAMPLE_URL_ORIGIN, EXAMPLE_VISITOR_ID}
    leftovers = sorted(v for v in forbidden if v and v in out_blob)
    if leftovers:
        raise ValueError(f"Scrubbing left {len(leftovers)} original value(s) in the output: {leftovers}")
    return scrubbed


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def build_expected_trace(conv: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Runs the tracer transform on a conversation, exactly as test_fixtures.py does."""
    spans = convert_to_trace_spans(
        conv=conv,
        log_entries=[],
        incoming_call_entries=[],
        ces_response_entries=[],
        project_id=TRACE_PROJECT_ID,
        session_id=session_id_of(conv),
        redact_pii=True,
    )
    return [format_span_for_cloud_trace_json(s) for s in spans]


def _write_json(path: str, data: Any) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", help="fixture name, e.g. callback_openapi")
    parser.add_argument("--raw", help="raw GetConversation response to scrub into a new fixture")
    args = parser.parse_args()

    paths = fixture_paths(args.name)
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    if args.raw:
        with open(args.raw) as f:
            conv = scrub_conversation(json.load(f))
        _write_json(paths["conversation"], conv)
        print(f"wrote {paths['conversation']}")
    else:
        with open(paths["conversation"]) as f:
            conv = json.load(f)

    expected = build_expected_trace(conv)
    _write_json(paths["expected"], expected)
    print(f"wrote {paths['expected']} ({len(expected)} spans)")


if __name__ == "__main__":
    main()
