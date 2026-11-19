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

"""Golden-file regression tests: recorded CES GetConversation responses -> expected trace spans.

Fixtures are scrubbed recordings of real conversations (see make_fixture.py). The expected
traces cover the conversation-derived spans only; no Cloud Logging entries are supplied.
"""

import ipaddress
import json
import os
import re
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(TESTS_DIR, "..", "src")))
sys.path.insert(0, TESTS_DIR)

from make_fixture import (  # noqa: E402
    FIXTURES_DIR,
    TRACE_PROJECT_ID,
    build_expected_trace,
    fixture_paths,
    session_id_of,
)
from transform import (  # noqa: E402
    TRACEPARENT_RE,
    _iter_spans,
    convert_to_trace_spans,
    hash_to_trace_id,
)

# Fixture name -> number of OpenAPI tool calls made directly by a callback, each carrying a
# propagated 'traceparent' header argument, that the recording is known to contain.
FIXTURES = {
    "callback_openapi": {"callback_openapi_calls": 5},
}

E164_RE = re.compile(r"\+\d{8,15}")
IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
DOCUMENTATION_NET = ipaddress.ip_network("192.0.2.0/24")


def _load(path):
    with open(path) as f:
        return json.load(f)


class TestConversationFixtures(unittest.TestCase):
    maxDiff = None

    def test_trace_matches_golden_output(self):
        for name in FIXTURES:
            with self.subTest(fixture=name):
                paths = fixture_paths(name)
                actual = build_expected_trace(_load(paths["conversation"]))
                expected = _load(paths["expected"])
                self.assertEqual(len(actual), len(expected), f"span count differs for {name}")
                self.assertEqual(actual, expected, f"trace differs from golden output for {name}")

    def test_span_ids_are_unique(self):
        for name in FIXTURES:
            with self.subTest(fixture=name):
                ids = [s["spanId"] for s in build_expected_trace(_load(fixture_paths(name)["conversation"]))]
                self.assertEqual(len(ids), len(set(ids)))

    def test_callback_invoked_openapi_tools_adopt_propagated_span_id(self):
        # A callback that calls an OpenAPI tool directly (no Python tool in between) has no
        # function_call_id, so it sends an arbitrary span ID in the 'traceparent' header. CES
        # records that header in the tool span's args; the tracer must give the tool span that
        # same ID, and keep it parented under the Callback span.
        for name, expect in FIXTURES.items():
            with self.subTest(fixture=name):
                conv = _load(fixture_paths(name)["conversation"])
                session_id = session_id_of(conv)
                trace_id = hash_to_trace_id(session_id)
                spans = convert_to_trace_spans(conv, [], [], [], TRACE_PROJECT_ID, session_id)
                by_id = {s["span_id"]: s for s in spans}

                checked = 0
                for turn in conv["turns"]:
                    for callback in _iter_spans(turn.get("rootSpan")):
                        if callback.get("name") != "Callback":
                            continue
                        for child in callback.get("childSpans") or []:
                            attrs = child.get("attributes") or {}
                            traceparent = (attrs.get("args") or {}).get("traceparent")
                            if attrs.get("type") != "OpenApiTool" or not isinstance(traceparent, str):
                                continue
                            sent = TRACEPARENT_RE.search(traceparent)
                            self.assertIsNotNone(sent, f"unparseable traceparent {traceparent!r}")
                            self.assertEqual(sent.group("trace_id"), trace_id)
                            tool_span = by_id.get(sent.group("span_id"))
                            self.assertIsNotNone(
                                tool_span, f"no span adopted propagated ID {sent.group('span_id')}"
                            )
                            self.assertEqual(tool_span["display_name"], "Tool")
                            self.assertEqual(tool_span["attributes"].get("type"), "OpenApiTool")
                            self.assertEqual(by_id[tool_span["parent_span_id"]]["display_name"], "Callback")
                            checked += 1
                self.assertEqual(checked, expect["callback_openapi_calls"])

    def test_fixtures_contain_no_real_phone_numbers_or_ip_addresses(self):
        # Guard for scrubbing: only reserved example values may appear in fixture files. Every
        # JSON file in fixtures/ is scanned, registered or not, so an unredacted response saved
        # by fetch_conversation.py is caught too. This detects phone numbers and IP addresses
        # only; it does not prove a file was scrubbed.
        paths = sorted(
            os.path.join(FIXTURES_DIR, f) for f in os.listdir(FIXTURES_DIR) if f.endswith(".json")
        )
        self.assertTrue(paths, "no fixture files found")
        for path in paths:
            with self.subTest(file=os.path.basename(path)):
                with open(path) as f:
                    text = f.read()
                phones = [p for p in E164_RE.findall(text) if not p.startswith("+1555")]
                self.assertEqual(phones, [], f"phone number in {path}")
                ips = []
                for candidate in IPV4_RE.findall(text):
                    try:
                        if ipaddress.ip_address(candidate) not in DOCUMENTATION_NET:
                            ips.append(candidate)
                    except ValueError:
                        pass
                self.assertEqual(ips, [], f"IP address in {path}")


if __name__ == "__main__":
    unittest.main()
