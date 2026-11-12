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

import base64
import hashlib
import json
import os
import sys
import unittest

# Add src/ to python path
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from transform import (
    convert_to_trace_spans,
    extract_complete_conversation_event,
    format_span_for_cloud_trace_json,
    get_span_id,
     get_user_utterance,
    hash_to_span_id,
    hash_to_trace_id,
    parse_ces_agent_resource,
    parse_conversation_resource,
)


class TestCESTransform(unittest.TestCase):
    def test_w3c_trace_and_span_id_hashing(self):
        session_id = "test-session-12345"
        expected_trace_id = hashlib.md5(session_id.encode("utf-8")).hexdigest()
        self.assertEqual(hash_to_trace_id(session_id), expected_trace_id)
        self.assertEqual(len(hash_to_trace_id(session_id)), 32)

        expected_span_id = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]
        self.assertEqual(hash_to_span_id(session_id), expected_span_id)
        self.assertEqual(len(hash_to_span_id(session_id)), 16)

    def test_get_span_id_w3c_tool_call_correlation(self):
        parent_id = "abcdef0123456789"
        tool_call_id = "adk-function-call-uuid-999"

        # 1. Span with "tool call id" attribute must hash tool_call_id directly
        span_with_tool_call_id = {
            "name": "Tool: get_weather",
            "startTime": "2026-10-02T10:00:01Z",
            "attributes": {
                "tool call id": tool_call_id,
                "name": "get_weather",
            },
        }
        self.assertEqual(
            get_span_id(span_with_tool_call_id, parent_id),
            hash_to_span_id(tool_call_id),
        )

        # 2. Span named "Tool" without "tool call id" hashes "{parent_id}/{tool_name}/{call_number}"
        span_tool_by_name = {
            "name": "Tool",
            "startTime": "2026-10-02T10:00:01Z",
            "attributes": {
                "name": "get_weather",
            },
        }
        self.assertEqual(
            get_span_id(span_tool_by_name, parent_id),
            hash_to_span_id(f"{parent_id}/get_weather/1"),
        )
        self.assertEqual(
            get_span_id(span_tool_by_name, parent_id, 2),
            hash_to_span_id(f"{parent_id}/get_weather/2"),
        )

        # 3. Other spans fall back to "{parent_id}/{name}/{startTime}"
        llm_span = {
            "name": "LLM",
            "startTime": "2026-10-02T10:00:01Z",
            "attributes": {"model": "gemini-2.5-flash"},
        }
        self.assertEqual(
            get_span_id(llm_span, parent_id),
            hash_to_span_id(f"{parent_id}/LLM/2026-10-02T10:00:01Z"),
        )

    def test_parse_conversation_and_ces_agent_resources(self):
        conv_res = parse_conversation_resource(
            "projects/my-df-proj/locations/eu/conversations/sess-abc-123"
        )
        self.assertEqual(
            conv_res,
            {
                "project_id": "my-df-proj",
                "location": "eu",
                "session_id": "sess-abc-123",
            },
        )

        # Global conversation path without explicit /locations/ segment
        conv_global = parse_conversation_resource(
            "projects/my-df-proj/conversations/sess-global-1"
        )
        self.assertEqual(
            conv_global,
            {
                "project_id": "my-df-proj",
                "location": "global",
                "session_id": "sess-global-1",
            },
        )

        # CES App URI
        ces_app = parse_ces_agent_resource(
            "projects/my-ces-proj/locations/eu/apps/weather-eu"
        )
        self.assertEqual(
            ces_app,
            {
                "project_id": "my-ces-proj",
                "location": "eu",
                "app_id": "weather-eu",
            },
        )

        # CES App URI with deployment suffix
        ces_app_dep = parse_ces_agent_resource(
            "projects/my-ces-proj/locations/us/apps/banking-app/deployments/dep-123"
        )
        self.assertEqual(
            ces_app_dep,
            {
                "project_id": "my-ces-proj",
                "location": "us",
                "app_id": "banking-app",
            },
        )

        # Dialogflow CX Agent URI must return None (not a CES app)
        df_cx_agent = parse_ces_agent_resource(
            "projects/my-df-proj/locations/eu/agents/agent-uuid-123"
        )
        self.assertIsNone(df_cx_agent)

    def test_extract_complete_conversation_event_formats(self):
        audit_payload = {
            "insertId": "audit-insert-1",
            "timestamp": "2026-10-02T12:05:00Z",
            "severity": "INFO",
            "protoPayload": {
                "serviceName": "dialogflow.googleapis.com",
                "methodName": "google.cloud.dialogflow.v2beta1.Conversations.CompleteConversation",
                "resourceName": "projects/my-proj/locations/eu/conversations/conv-999",
                "response": {
                    "name": "projects/my-proj/locations/eu/conversations/conv-999",
                    "conversationProfile": "projects/my-proj/locations/eu/conversationProfiles/prof-1",
                    "endTime": "2026-10-02T12:05:00Z",
                },
            },
        }

        # 1. Direct Eventarc Audit Log payload
        info_direct = extract_complete_conversation_event(audit_payload)
        self.assertIsNotNone(info_direct)
        self.assertEqual(info_direct["session_id"], "conv-999")
        self.assertEqual(info_direct["df_project_id"], "my-proj")
        self.assertEqual(info_direct["df_location"], "eu")
        self.assertEqual(
            info_direct["conversation_profile"],
            "projects/my-proj/locations/eu/conversationProfiles/prof-1",
        )

        # 2. Pub/Sub push message envelope
        encoded = base64.b64encode(json.dumps(audit_payload).encode("utf-8")).decode("utf-8")
        pubsub_payload = {"message": {"data": encoded, "messageId": "m-1"}}
        info_pubsub = extract_complete_conversation_event(pubsub_payload)
        self.assertIsNotNone(info_pubsub)
        self.assertEqual(info_pubsub["session_id"], "conv-999")

        # 3. Direct manual invocation JSON
        manual_payload = {
            "session_id": "manual-sess-1",
            "project_id": "my-proj",
            "location": "eu",
            "app_id": "weather-eu",
        }
        info_manual = extract_complete_conversation_event(manual_payload)
        self.assertIsNotNone(info_manual)
        self.assertEqual(info_manual["session_id"], "manual-sess-1")
        self.assertEqual(info_manual["ces_app_id"], "weather-eu")
        self.assertEqual(info_manual["method_name"], "direct_invocation")

    def test_get_user_utterance_ignores_state_updates(self):
        turn = {
            "messages": [
                {
                    "role": "user",
                    "chunks": [
                        {"text": "<session_state_update>"},
                        {"text": "What is the weather in Zurich?"},
                    ],
                },
                {
                    "role": "model",
                    "chunks": [{"text": "It is sunny and 21 degrees."}],
                },
            ]
        }
        self.assertEqual(get_user_utterance(turn), "What is the weather in Zurich?")

    def test_convert_to_trace_spans_full_hierarchy(self):
        session_id = "conv-trace-test-1"
        project_id = "test-trace-proj"

        conv = {
            "name": f"projects/{project_id}/locations/eu/apps/weather-eu/conversations/{session_id}",
            "turnCount": 1,
            "turns": [
                {
                    "messages": [
                        {
                            "role": "user",
                            "chunks": [{"text": "Check weather in Berlin"}],
                        }
                    ],
                    "rootSpan": {
                        "name": "TurnRoot",
                        "startTime": "2026-10-02T12:00:05Z",
                        "endTime": "2026-10-02T12:00:08Z",
                        "attributes": {"turn_number": 1},
                        "childSpans": [
                            {
                                "name": "Tool",
                                "startTime": "2026-10-02T12:00:06Z",
                                "endTime": "2026-10-02T12:00:07Z",
                                "attributes": {
                                    "name": "fetch_weather",
                                    "tool call id": "call-id-xyz-789",
                                    "city": "Berlin",
                                },
                                "childSpans": [],
                            }
                        ],
                    },
                }
            ],
        }

        audit_entries = [
            {
                "insertId": "create-1",
                "timestamp": "2026-10-02T12:00:01Z",
                "severity": "INFO",
                "protoPayload": {
                    "methodName": "google.cloud.dialogflow.v2beta1.Conversations.CreateConversation",
                    "resourceName": f"projects/{project_id}/locations/eu/conversations/{session_id}",
                    "response": {"startTime": "2026-10-02T12:00:01Z"},
                },
            },
            {
                "insertId": "bidi-start",
                "timestamp": "2026-10-02T12:00:02Z",
                "severity": "INFO",
                "operation": {"id": "op-bidi-1", "first": True, "last": False},
                "protoPayload": {
                    "methodName": "google.cloud.dialogflow.v2beta1.Conversations.BidiStreamingAnalyzeContent",
                    "resourceName": f"projects/{project_id}/locations/eu/conversations/{session_id}",
                },
            },
            {
                "insertId": "bidi-end",
                "timestamp": "2026-10-02T12:00:09Z",
                "receiveTimestamp": "2026-10-02T12:00:09.500Z",
                "severity": "INFO",
                "operation": {"id": "op-bidi-1", "first": False, "last": True},
                "protoPayload": {
                    "methodName": "google.cloud.dialogflow.v2beta1.Conversations.BidiStreamingAnalyzeContent",
                    "resourceName": f"projects/{project_id}/locations/eu/conversations/{session_id}",
                    "status": {"code": 0, "message": "OK"},
                },
            },
            {
                "insertId": "complete-1",
                "timestamp": "2026-10-02T12:00:10Z",
                "severity": "INFO",
                "protoPayload": {
                    "methodName": "google.cloud.dialogflow.v2beta1.Conversations.CompleteConversation",
                    "resourceName": f"projects/{project_id}/locations/eu/conversations/{session_id}",
                    "response": {"endTime": "2026-10-02T12:00:10Z"},
                },
            },
        ]

        incoming_call_entries = [
            {
                "insertId": "inc-1",
                "timestamp": "2026-10-02T12:00:00Z",
                "severity": "INFO",
                "jsonPayload": {
                    "action": "connectCall",
                    "conversation": f"projects/{project_id}/locations/eu/conversations/{session_id}",
                    "sipCallId": "sip-123",
                },
            }
        ]

        ces_response_entries = [
            {
                "insertId": "ces-resp-1",
                "timestamp": "2026-10-02T12:00:08Z",
                "jsonPayload": {
                    "turnIndex": 1,
                    "turnCompleted": True,
                    "supervisor": {
                        "detections": [
                            {
                                "issue_type": "HALLUCINATION",
                                "details": "Minor discrepancy detected",
                            }
                        ]
                    },
                },
            }
        ]

        spans = convert_to_trace_spans(
            conv=conv,
            log_entries=audit_entries,
            incoming_call_entries=incoming_call_entries,
            ces_response_entries=ces_response_entries,
            project_id=project_id,
            session_id=session_id,
            redact_pii=False,
            extra_root_attributes={"ces.app_id": "weather-eu"},
        )

        # Expected spans:
        # 1. Conversation root span
        # 2. BidiStreamingAnalyzeContent operation span
        # 3. CreateConversation single span
        # 4. CompleteConversation single span
        # 5. connectCall incoming_call span
        # 6. Turn 1 root span
        # 7. Tool child span
        self.assertEqual(len(spans), 7)

        spans_by_id = {s["span_id"]: s for s in spans}
        root_span_id = hash_to_span_id(session_id)
        bidi_span_id = hash_to_span_id("op-bidi-1")
        turn_span_id = hash_to_span_id(f"{session_id}/turn/0")
        tool_span_id = hash_to_span_id("call-id-xyz-789")

        # Root span checks
        root_span = spans_by_id[root_span_id]
        self.assertEqual(root_span["parent_span_id"], "")
        self.assertEqual(root_span["display_name"], f"Conversation: {session_id}")
        self.assertEqual(root_span["attributes"]["turn_count"], 1)
        self.assertEqual(root_span["attributes"]["ces.app_id"], "weather-eu")

        # Bidi operation span checks
        bidi_span = spans_by_id[bidi_span_id]
        self.assertEqual(bidi_span["parent_span_id"], root_span_id)
        self.assertEqual(bidi_span["display_name"], "BidiStreamingAnalyzeContent")
        self.assertEqual(bidi_span["attributes"]["status_code"], 0)

        # Turn 1 span checks (must be parented under BidiStreamingAnalyzeContent!)
        turn_span = spans_by_id[turn_span_id]
        self.assertEqual(turn_span["parent_span_id"], bidi_span_id)
        self.assertEqual(turn_span["display_name"], "Turn 1: Check weather in Berlin")
        self.assertTrue(turn_span["attributes"]["turn_completed"])
        self.assertTrue(turn_span["attributes"]["supervisor.has_issue"])
        self.assertEqual(turn_span["attributes"]["supervisor.detection_count"], 1)
        self.assertEqual(
            turn_span["attributes"]["supervisor.detection[0].issue_type"],
            "HALLUCINATION",
        )

        # Tool child span checks (must use hash_to_span_id("call-id-xyz-789") and parent under Turn 1)
        tool_span = spans_by_id[tool_span_id]
        self.assertEqual(tool_span["parent_span_id"], turn_span_id)

        # Verify JSON formatting helper
        json_span = format_span_for_cloud_trace_json(turn_span)
        self.assertEqual(json_span["spanId"], turn_span_id)
        self.assertEqual(json_span["parentSpanId"], bidi_span_id)
        self.assertEqual(
            json_span["attributes"]["attributeMap"]["turn_completed"],
            {"boolValue": True},
        )

    def test_redact_pii_masks_utterance_and_sensitive_attributes(self):
        session_id = "conv-pii-test"
        conv = {
            "turnCount": 1,
            "turns": [
                {
                    "messages": [
                        {
                            "role": "user",
                            "chunks": [{"text": "My phone is +15551234567"}],
                        }
                    ],
                    "rootSpan": {
                        "name": "TurnRoot",
                        "startTime": "2026-10-02T12:00:05Z",
                        "endTime": "2026-10-02T12:00:08Z",
                        "attributes": {
                            "user_input": "My phone is +15551234567",
                            "phone_number": "+15551234567",
                            "safe_metric": 42,
                        },
                        "childSpans": [],
                    },
                }
            ],
        }

        spans = convert_to_trace_spans(
            conv=conv,
            log_entries=[],
            incoming_call_entries=[],
            ces_response_entries=[],
            project_id="proj-1",
            session_id=session_id,
            redact_pii=True,
        )
        turn_span_id = hash_to_span_id(f"{session_id}/turn/0")
        turn_span = [s for s in spans if s["span_id"] == turn_span_id][0]

        # Display name should not include raw user utterance when redact_pii=True
        self.assertEqual(turn_span["display_name"], "Turn 1")
        self.assertEqual(turn_span["attributes"]["user_input"], "<REDACTED>")
        self.assertEqual(turn_span["attributes"]["phone_number"], "<REDACTED>")
        self.assertEqual(turn_span["attributes"]["safe_metric"], 42)

    @staticmethod
    def _async_conv(turn1_children, turn2_children=None):
        turns = [
            {
                "rootSpan": {
                    "name": "root",
                    "startTime": "2026-11-12T07:08:43.027Z",
                    "endTime": "2026-11-12T07:08:45.909Z",
                    "childSpans": turn1_children,
                }
            }
        ]
        if turn2_children is not None:
            turns.append(
                {
                    "rootSpan": {
                        "name": "root",
                        "startTime": "2026-11-12T07:08:51.228Z",
                        "endTime": "2026-11-12T07:08:54.821Z",
                        "childSpans": turn2_children,
                    }
                }
            )
        return {"turnCount": len(turns), "turns": turns}

    def test_llm_started_async_tool_has_no_duplicate_ids_and_run_nests_under_schedule(self):
        # LLM-started async tool: CES reports the same tool call id on the
        # scheduled span (Turn 1) and on the completed run (Turn 2).
        tcid = "adk-00000000-0000-4000-8000-000000000001"
        scheduled = {
            "name": "Async Tool",
            "startTime": "2026-11-12T07:08:43.592000Z",
            "endTime": "2026-11-12T07:08:43.592100Z",
            "attributes": {
                "name": "get_active_region_monitoring",
                "type": "PythonFunctionTool",
                "tool call id": tcid,
                "response": {"result": "pending"},
            },
        }
        completed = {
            "name": "Async Tool",
            "startTime": "2026-11-12T07:08:43.592150Z",
            "endTime": "2026-11-12T07:08:44.163000Z",
            "attributes": {
                "name": "get_active_region_monitoring",
                "type": "PythonFunctionTool",
                "tool call id": tcid,
                "response": {"result": {"region": "europe-west1"}},
            },
        }
        conv = self._async_conv([scheduled], [completed])
        spans = convert_to_trace_spans(conv, [], [], [], "p", "sess-async-llm")

        ids = [s["span_id"] for s in spans]
        self.assertEqual(len(ids), len(set(ids)), "span IDs must be unique")

        async_spans = [s for s in spans if s["display_name"] == "Async Tool"]
        sched_span = [s for s in async_spans if s["start_time"].microsecond == 592000][0]
        run_span = [s for s in async_spans if s is not sched_span][0]

        # The run keeps SHA256(tool call id) so downstream calls built from function_call_id attach to it.
        self.assertEqual(run_span["span_id"], hash_to_span_id(tcid))
        self.assertEqual(sched_span["span_id"], hash_to_span_id(f"{tcid}/scheduled"))
        # Turn 1 -> scheduled -> run
        self.assertEqual(sched_span["parent_span_id"], hash_to_span_id("sess-async-llm/turn/0"))
        self.assertEqual(run_span["parent_span_id"], sched_span["span_id"])

    def test_callback_started_async_tool_run_nests_under_schedule(self):
        # Callback-started async tool: a BeforeAgent callback starts it; CES sets no
        # tool call id on the scheduled span and a different one on the completed run.
        scheduled = {
            "name": "Async Tool",
            "startTime": "2026-11-11T05:32:41.489655Z",
            "endTime": "2026-11-11T05:32:41.489731Z",
            "attributes": {
                "name": "load_reference_data",
                "type": "PythonFunctionTool",
                "response": {"result": "pending"},
            },
        }
        callback = {
            "name": "Callback",
            "startTime": "2026-11-11T05:32:41.469405Z",
            "endTime": "2026-11-11T05:32:41.496979Z",
            "attributes": {"stage": "BeforeAgent"},
            "childSpans": [scheduled],
        }
        run_tcid = "parent-span-1111aaaa-tool-execution-2222bbbb"
        completed = {
            "name": "Async Tool",
            "startTime": "2026-11-11T05:32:41.489746Z",
            "endTime": "2026-11-11T05:32:43.238806Z",
            "attributes": {
                "name": "load_reference_data",
                "type": "PythonFunctionTool",
                "tool call id": run_tcid,
                "response": {"result": {"status": "success"}},
            },
        }
        conv = self._async_conv([callback], [completed])
        spans = convert_to_trace_spans(conv, [], [], [], "p", "sess-async-cb")

        ids = [s["span_id"] for s in spans]
        self.assertEqual(len(ids), len(set(ids)))
        by_id = {s["span_id"]: s for s in spans}
        run_span = by_id[hash_to_span_id(run_tcid)]
        sched_span = by_id[run_span["parent_span_id"]]
        self.assertEqual(sched_span["display_name"], "Async Tool")
        self.assertEqual(sched_span["attributes"]["response"], '{"result":"pending"}')
        # Scheduled span keeps its existing ID (it has no tool call id, so nothing collided).
        callback_id = sched_span["parent_span_id"]
        self.assertEqual(
            sched_span["span_id"],
            hash_to_span_id(f"{callback_id}/Async Tool/2026-11-11T05:32:41.489655Z"),
        )

    def test_repeated_child_tool_calls_are_numbered(self):
        # A callback-started
        # Python tool calls two OpenAPI tools twice each (listed out of start-time order here).
        def call(name, start, end, args):
            return {
                "name": "Tool",
                "startTime": start,
                "endTime": end,
                "attributes": {"name": name, "type": "OpenApiTool", "args": args},
            }

        sub, otp = "backend_getSubscriptions", "backend_getPurchases"
        calls = [
            call(sub, "2026-10-30T15:33:21.760965Z", "2026-10-30T15:33:31.481479Z", {"case_id": "C-1"}),
            call(sub, "2026-10-30T15:33:12.376066Z", "2026-10-30T15:33:21.412377Z", {"chat_id": "1001"}),
            call(otp, "2026-10-30T15:33:21.417628Z", "2026-10-30T15:33:21.754667Z", {"chat_id": "1001"}),
            call(otp, "2026-10-30T15:33:31.488508Z", "2026-10-30T15:33:37.040612Z", {"case_id": "C-1"}),
        ]
        wrapper = {
            "name": "Tool",
            "startTime": "2026-10-30T15:33:12.318055Z",
            "endTime": "2026-10-30T15:33:37.067584Z",
            "attributes": {"name": "load_account_data", "type": "PythonFunctionTool"},
            "childSpans": calls,
        }
        conv = self._async_conv([wrapper])
        spans = convert_to_trace_spans(conv, [], [], [], "p", "sess-repeat")

        ids = [s["span_id"] for s in spans]
        self.assertEqual(len(ids), len(set(ids)), "span IDs must be unique")

        wrapper_id = hash_to_span_id(f"{hash_to_span_id('sess-repeat/turn/0')}/load_account_data/1")
        by_start = {s["start_time"].isoformat(): s for s in spans}
        expected = {
            "2026-10-30T15:33:12.376066+00:00": f"{wrapper_id}/{sub}/1",
            "2026-10-30T15:33:21.417628+00:00": f"{wrapper_id}/{otp}/1",
            "2026-10-30T15:33:21.760965+00:00": f"{wrapper_id}/{sub}/2",
            "2026-10-30T15:33:31.488508+00:00": f"{wrapper_id}/{otp}/2",
        }
        for start, key in expected.items():
            self.assertEqual(by_start[start]["span_id"], hash_to_span_id(key))
            self.assertEqual(by_start[start]["parent_span_id"], wrapper_id)

    def test_scheduled_only_async_tool_is_unchanged(self):
        # Async tools fired in the last turn (e.g. at hang-up) never get a completed span recorded.
        tcid = "adk-00000000-0000-4000-8000-000000000002"
        scheduled = {
            "name": "Async Tool",
            "startTime": "2026-11-10T11:30:20.032288Z",
            "endTime": "2026-11-10T11:30:20.032312Z",
            "attributes": {
                "name": "start_verification",
                "tool call id": tcid,
                "response": {"result": "pending"},
            },
        }
        conv = self._async_conv([scheduled])
        spans = convert_to_trace_spans(conv, [], [], [], "p", "sess-async-last")
        sched_span = [s for s in spans if s["display_name"] == "Async Tool"][0]
        self.assertEqual(sched_span["span_id"], hash_to_span_id(tcid))
        self.assertEqual(sched_span["parent_span_id"], hash_to_span_id("sess-async-last/turn/0"))


if __name__ == "__main__":
    unittest.main()
