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
import json
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# Add src/ to python path
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Set environment variables before importing main
os.environ["PROJECT_ID"] = "default-df-proj"
os.environ["INITIAL_DELAY_SECONDS"] = "0"
os.environ["APP_CONFIGS"] = json.dumps(
    [
        {
            "conversation_profile": "projects/default-df-proj/locations/eu/conversationProfiles/static-prof-1",
            "ces_project_id": "static-ces-proj",
            "ces_location": "eu",
            "ces_app_id": "static-app-eu",
            "trace_project_id": "static-trace-proj",
        }
    ]
)


def _install_fallback_stubs_if_needed():
    """Installs lightweight module stubs if Flask or Google Cloud libraries are not installed locally."""
    try:
        import flask  # noqa: F401
    except ImportError:
        flask_mod = types.ModuleType("flask")
        flask_mod.request = MagicMock()

        class DummyFlask:
            def __init__(self, name):
                self.name = name

            def route(self, *args, **kwargs):
                def decorator(fn):
                    return fn

                return decorator

            def test_client(self):
                return None

        flask_mod.Flask = DummyFlask
        sys.modules["flask"] = flask_mod

    try:
        import google.auth  # noqa: F401
        import google.auth.transport.requests  # noqa: F401
    except ImportError:
        google_mod = sys.modules.setdefault("google", types.ModuleType("google"))
        auth_mod = types.ModuleType("google.auth")
        auth_mod.default = MagicMock(return_value=(MagicMock(), "default-df-proj"))
        transport_mod = types.ModuleType("google.auth.transport")
        requests_mod = types.ModuleType("google.auth.transport.requests")
        requests_mod.AuthorizedSession = MagicMock()
        google_mod.auth = auth_mod
        sys.modules["google.auth"] = auth_mod
        sys.modules["google.auth.transport"] = transport_mod
        sys.modules["google.auth.transport.requests"] = requests_mod

    try:
        import google.api_core.exceptions  # noqa: F401
    except ImportError:
        google_mod = sys.modules.setdefault("google", types.ModuleType("google"))
        api_core_mod = sys.modules.setdefault("google.api_core", types.ModuleType("google.api_core"))
        exc_mod = types.ModuleType("google.api_core.exceptions")

        class GoogleAPICallError(Exception):
            pass

        class BadRequest(GoogleAPICallError):
            pass

        class InvalidArgument(BadRequest):
            pass

        class TooManyRequests(GoogleAPICallError):
            pass

        exc_mod.GoogleAPICallError = GoogleAPICallError
        exc_mod.BadRequest = BadRequest
        exc_mod.InvalidArgument = InvalidArgument
        exc_mod.TooManyRequests = TooManyRequests
        api_core_mod.exceptions = exc_mod
        google_mod.api_core = api_core_mod
        sys.modules["google.api_core.exceptions"] = exc_mod

    try:
        from google.cloud import trace_v2  # noqa: F401
    except ImportError:
        google_mod = sys.modules.setdefault("google", types.ModuleType("google"))
        cloud_mod = sys.modules.setdefault("google.cloud", types.ModuleType("google.cloud"))
        trace_v2_mod = types.ModuleType("google.cloud.trace_v2")
        trace_v2_mod.TraceServiceClient = MagicMock()
        trace_v2_mod.types = MagicMock()
        cloud_mod.trace_v2 = trace_v2_mod
        google_mod.cloud = cloud_mod
        sys.modules["google.cloud.trace_v2"] = trace_v2_mod

    try:
        from google.protobuf import timestamp_pb2  # noqa: F401
    except ImportError:
        google_mod = sys.modules.setdefault("google", types.ModuleType("google"))
        pb_mod = sys.modules.setdefault("google.protobuf", types.ModuleType("google.protobuf"))
        ts_mod = types.ModuleType("google.protobuf.timestamp_pb2")
        ts_mod.Timestamp = MagicMock()
        pb_mod.timestamp_pb2 = ts_mod
        google_mod.protobuf = pb_mod
        sys.modules["google.protobuf.timestamp_pb2"] = ts_mod


_install_fallback_stubs_if_needed()
import main  # noqa: E402
from google.api_core.exceptions import InvalidArgument, TooManyRequests  # noqa: E402


class TestCESTracerMain(unittest.TestCase):
    def setUp(self):
        main._profile_cache.clear()

    def _invoke_endpoint(self, payload):
        client = main.app.test_client()
        if client is not None:
            resp = client.post("/", json=payload)
            return resp.data.decode("utf-8"), resp.status_code
        with patch.object(main.request, "get_json", return_value=payload):
            result = main.handle_event()
            if isinstance(result, tuple):
                return str(result[0]), result[1]
            return str(result), 200

    @patch("main.write_trace_spans")
    @patch("main.fetch_ces_response_logs")
    @patch("main.fetch_incoming_call_logs")
    @patch("main.fetch_ces_conversation")
    @patch("main.fetch_conversation_profile")
    @patch("main.fetch_dialogflow_logs")
    @patch("main.get_authorized_session")
    def test_handle_event_dynamic_conversation_profile_resolution(
        self,
        mock_auth_session,
        mock_df_logs,
        mock_fetch_profile,
        mock_fetch_conv,
        mock_inc_logs,
        mock_ces_logs,
        mock_write_spans,
    ):
        mock_auth_session.return_value = (MagicMock(), "default-df-proj")
        mock_df_logs.return_value = []
        mock_inc_logs.return_value = []
        mock_ces_logs.return_value = []
        mock_write_spans.return_value = True

        # ConversationProfile dynamically points to a CES App
        mock_fetch_profile.return_value = {
            "name": "projects/my-df-proj/locations/eu/conversationProfiles/dynamic-prof-1",
            "automatedAgentConfig": {
                "agent": "projects/my-ces-proj/locations/eu/apps/weather-eu"
            },
        }

        mock_fetch_conv.return_value = {
            "name": "projects/my-ces-proj/locations/eu/apps/weather-eu/conversations/sess-101",
            "turnCount": 1,
            "turns": [
                {
                    "messages": [{"role": "user", "chunks": [{"text": "Hello"}]}],
                    "rootSpan": {
                        "name": "TurnRoot",
                        "startTime": "2026-10-02T12:00:01Z",
                        "endTime": "2026-10-02T12:00:03Z",
                        "childSpans": [],
                    },
                }
            ],
        }

        payload = {
            "insertId": "evt-1",
            "timestamp": "2026-10-02T12:00:05Z",
            "severity": "INFO",
            "protoPayload": {
                "serviceName": "dialogflow.googleapis.com",
                "methodName": "google.cloud.dialogflow.v2beta1.Conversations.CompleteConversation",
                "resourceName": "projects/my-df-proj/locations/eu/conversations/sess-101",
                "response": {
                    "name": "projects/my-df-proj/locations/eu/conversations/sess-101",
                    "conversationProfile": "projects/my-df-proj/locations/eu/conversationProfiles/dynamic-prof-1",
                    "endTime": "2026-10-02T12:00:05Z",
                },
            },
        }

        body, status = self._invoke_endpoint(payload)
        self.assertEqual(status, 200)
        resp_json = json.loads(body)
        self.assertEqual(resp_json["status"], "ok")
        self.assertEqual(resp_json["session_id"], "sess-101")
        self.assertEqual(resp_json["trace_project_id"], "my-ces-proj")

        mock_fetch_conv.assert_called_once()
        mock_write_spans.assert_called_once()

    @patch("main.fetch_conversation_profile")
    @patch("main.fetch_dialogflow_logs")
    @patch("main.get_authorized_session")
    def test_handle_event_skips_non_ces_dialogflow_cx_agent(
        self,
        mock_auth_session,
        mock_df_logs,
        mock_fetch_profile,
    ):
        mock_auth_session.return_value = (MagicMock(), "default-df-proj")
        mock_df_logs.return_value = []

        # ConversationProfile points to a standard Dialogflow CX agent (/agents/), not a CES app (/apps/)
        mock_fetch_profile.return_value = {
            "name": "projects/my-df-proj/locations/eu/conversationProfiles/dfcx-prof-1",
            "automatedAgentConfig": {
                "agent": "projects/my-df-proj/locations/eu/agents/dfcx-agent-uuid"
            },
        }

        payload = {
            "insertId": "evt-dfcx",
            "timestamp": "2026-10-02T12:00:05Z",
            "protoPayload": {
                "serviceName": "dialogflow.googleapis.com",
                "methodName": "google.cloud.dialogflow.v2beta1.Conversations.CompleteConversation",
                "resourceName": "projects/my-df-proj/locations/eu/conversations/sess-dfcx-1",
                "response": {
                    "conversationProfile": "projects/my-df-proj/locations/eu/conversationProfiles/dfcx-prof-1"
                },
            },
        }

        body, status = self._invoke_endpoint(payload)
        self.assertEqual(status, 200)
        self.assertIn("Skipped non-CES conversation", body)

    @patch("main.write_trace_spans")
    @patch("main.fetch_ces_response_logs")
    @patch("main.fetch_incoming_call_logs")
    @patch("main.fetch_ces_conversation")
    @patch("main.fetch_dialogflow_logs")
    @patch("main.get_authorized_session")
    def test_handle_event_static_app_config_override(
        self,
        mock_auth_session,
        mock_df_logs,
        mock_fetch_conv,
        mock_inc_logs,
        mock_ces_logs,
        mock_write_spans,
    ):
        mock_auth_session.return_value = (MagicMock(), "default-df-proj")
        mock_df_logs.return_value = []
        mock_inc_logs.return_value = []
        mock_ces_logs.return_value = []
        mock_write_spans.return_value = True

        mock_fetch_conv.return_value = {
            "turnCount": 1,
            "turns": [
                {
                    "messages": [],
                    "rootSpan": {
                        "name": "TurnRoot",
                        "startTime": "2026-10-02T12:00:01Z",
                        "endTime": "2026-10-02T12:00:02Z",
                        "childSpans": [],
                    },
                }
            ],
        }

        # Matches static-prof-1 in APP_CONFIGS
        inner_event = {
            "insertId": "evt-static",
            "timestamp": "2026-10-02T12:00:05Z",
            "protoPayload": {
                "serviceName": "dialogflow.googleapis.com",
                "methodName": "google.cloud.dialogflow.v2beta1.Conversations.CompleteConversation",
                "resourceName": "projects/default-df-proj/locations/eu/conversations/sess-static-1",
                "response": {
                    "conversationProfile": "projects/default-df-proj/locations/eu/conversationProfiles/static-prof-1"
                },
            },
        }
        encoded = base64.b64encode(json.dumps(inner_event).encode("utf-8")).decode("utf-8")
        pubsub_payload = {"message": {"data": encoded}}

        body, status = self._invoke_endpoint(pubsub_payload)
        self.assertEqual(status, 200)
        resp_json = json.loads(body)
        self.assertEqual(resp_json["trace_project_id"], "static-trace-proj")
        mock_fetch_conv.assert_called_once_with(
            unittest.mock.ANY,
            project_id="static-ces-proj",
            location="eu",
            app_id="static-app-eu",
            session_id="sess-static-1",
        )


class TestIdempotencyGuard(unittest.TestCase):
    """Tests for the best-effort Cloud Trace idempotency guard."""

    def setUp(self):
        main._profile_cache.clear()

    _invoke_endpoint = TestCESTracerMain._invoke_endpoint

    @staticmethod
    def _audit_event(session_id):
        return {
            "insertId": f"evt-{session_id}",
            "timestamp": "2026-10-02T12:00:05Z",
            "protoPayload": {
                "serviceName": "dialogflow.googleapis.com",
                "methodName": "google.cloud.dialogflow.v2beta1.Conversations.CompleteConversation",
                "resourceName": f"projects/default-df-proj/locations/eu/conversations/{session_id}",
                "response": {
                    "conversationProfile": "projects/default-df-proj/locations/eu/conversationProfiles/static-prof-1"
                },
            },
        }

    @staticmethod
    def _conv():
        return {
            "turns": [
                {
                    "messages": [],
                    "rootSpan": {
                        "name": "TurnRoot",
                        "startTime": "2026-10-02T12:00:01Z",
                        "endTime": "2026-10-02T12:00:02Z",
                        "childSpans": [],
                    },
                }
            ]
        }

    @staticmethod
    def _resp(status_code, body=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = body or {}
        resp.text = json.dumps(body or {})
        return resp

    def test_trace_exists_true_when_root_span_present(self):
        session = MagicMock()
        session.get.return_value = self._resp(
            200, {"spans": [{"name": "Turn 1: hi"}, {"name": "Conversation: sess-1"}]}
        )
        self.assertTrue(main.trace_exists(session, "proj", "abc", "sess-1"))

    def test_trace_exists_false_when_root_span_missing(self):
        session = MagicMock()
        session.get.return_value = self._resp(200, {"spans": [{"name": "Turn 1: hi"}]})
        self.assertFalse(main.trace_exists(session, "proj", "abc", "sess-1"))

    def test_trace_exists_false_on_404(self):
        session = MagicMock()
        session.get.return_value = self._resp(404)
        self.assertFalse(main.trace_exists(session, "proj", "abc", "sess-1"))

    def test_trace_exists_fails_open_on_error_status_and_exception(self):
        session = MagicMock()
        session.get.return_value = self._resp(403, {"error": "denied"})
        self.assertFalse(main.trace_exists(session, "proj", "abc", "sess-1"))
        session.get.side_effect = RuntimeError("boom")
        self.assertFalse(main.trace_exists(session, "proj", "abc", "sess-1"))

    @patch("main.write_trace_spans")
    @patch("main.fetch_ces_conversation")
    @patch("main.trace_exists", return_value=True)
    @patch("main.fetch_dialogflow_logs", return_value=[])
    @patch("main.get_authorized_session")
    def test_skips_when_trace_already_exists(
        self, mock_auth, _mock_df_logs, mock_exists, mock_fetch_conv, mock_write
    ):
        mock_auth.return_value = (MagicMock(), "default-df-proj")
        body, status = self._invoke_endpoint(self._audit_event("sess-dup"))
        self.assertEqual(status, 200)
        self.assertIn("already exists", body)
        mock_exists.assert_called_once()
        mock_fetch_conv.assert_not_called()
        mock_write.assert_not_called()

    @patch("main.write_trace_spans", return_value=True)
    @patch("main.fetch_ces_response_logs", return_value=[])
    @patch("main.fetch_incoming_call_logs", return_value=[])
    @patch("main.fetch_ces_conversation")
    @patch("main.trace_exists", return_value=False)
    @patch("main.fetch_dialogflow_logs", return_value=[])
    @patch("main.get_authorized_session")
    def test_writes_when_trace_missing(
        self, mock_auth, _mock_df_logs, mock_exists, mock_fetch_conv, _inc, _ces, mock_write
    ):
        mock_auth.return_value = (MagicMock(), "default-df-proj")
        mock_fetch_conv.return_value = self._conv()
        body, status = self._invoke_endpoint(self._audit_event("sess-new"))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ok")
        mock_exists.assert_called_once()
        mock_write.assert_called_once()

    @patch("main.write_trace_spans", return_value=True)
    @patch("main.fetch_ces_response_logs", return_value=[])
    @patch("main.fetch_incoming_call_logs", return_value=[])
    @patch("main.fetch_ces_conversation")
    @patch("main.trace_exists", return_value=True)
    @patch("main.fetch_dialogflow_logs", return_value=[])
    @patch("main.get_authorized_session")
    def test_force_direct_invocation_bypasses_guard(
        self, mock_auth, _mock_df_logs, mock_exists, mock_fetch_conv, _inc, _ces, mock_write
    ):
        mock_auth.return_value = (MagicMock(), "default-df-proj")
        mock_fetch_conv.return_value = self._conv()
        payload = {
            "session_id": "sess-force",
            "project_id": "static-ces-proj",
            "location": "eu",
            "app_id": "static-app-eu",
            "force": True,
        }
        body, status = self._invoke_endpoint(payload)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ok")
        mock_exists.assert_not_called()
        mock_write.assert_called_once()


class TestTraceWriteErrorHandling(unittest.TestCase):
    """Non-retryable 400s are acknowledged (200); other errors stay retryable (500)."""

    def setUp(self):
        main._profile_cache.clear()

    _invoke_endpoint = TestCESTracerMain._invoke_endpoint
    _audit_event = staticmethod(TestIdempotencyGuard._audit_event)
    _conv = staticmethod(TestIdempotencyGuard._conv)

    def _run_with_write_error(self, error):
        with patch("main.get_authorized_session", return_value=(MagicMock(), "default-df-proj")), \
                patch("main.fetch_dialogflow_logs", return_value=[]), \
                patch("main.trace_exists", return_value=False), \
                patch("main.fetch_ces_conversation", return_value=self._conv()), \
                patch("main.fetch_incoming_call_logs", return_value=[]), \
                patch("main.fetch_ces_response_logs", return_value=[]), \
                patch("main.write_trace_spans", side_effect=error) as mock_write:
            body, status = self._invoke_endpoint(self._audit_event("sess-err"))
            mock_write.assert_called_once()
            return body, status

    def test_invalid_argument_400_is_acknowledged(self):
        body, status = self._run_with_write_error(InvalidArgument("400 Invalid project id in name!"))
        self.assertEqual(status, 200)
        self.assertIn("Non-retryable error writing to Cloud Trace API", body)

    def test_retryable_429_returns_500(self):
        body, status = self._run_with_write_error(TooManyRequests("429 Quota exceeded"))
        self.assertEqual(status, 500)
        self.assertIn("Failed writing to Cloud Trace API", body)

    def test_unexpected_exception_returns_500(self):
        body, status = self._run_with_write_error(RuntimeError("connection reset"))
        self.assertEqual(status, 500)
        self.assertIn("Failed writing to Cloud Trace API", body)


class TestProjectNumberNormalization(unittest.TestCase):
    """CES agent references may use project numbers; Logging and Trace need project IDs."""

    def setUp(self):
        main._profile_cache.clear()
        main._project_id_cache.clear()

    _invoke_endpoint = TestCESTracerMain._invoke_endpoint
    _conv = staticmethod(TestIdempotencyGuard._conv)
    _resp = staticmethod(TestIdempotencyGuard._resp)

    def test_project_id_is_returned_unchanged_without_lookup(self):
        session = MagicMock()
        self.assertEqual(main.normalize_project_id(session, "my-proj"), "my-proj")
        session.get.assert_not_called()

    def test_project_number_is_resolved_and_cached(self):
        session = MagicMock()
        session.get.return_value = self._resp(200, {"name": "projects/123", "projectId": "my-proj"})
        self.assertEqual(main.normalize_project_id(session, "123"), "my-proj")
        self.assertEqual(main.normalize_project_id(session, "123"), "my-proj")
        session.get.assert_called_once()
        self.assertIn("/v3/projects/123", session.get.call_args[0][0])

    def test_permanent_lookup_failure_returns_none(self):
        for code in (403, 404):
            main._project_id_cache.clear()
            session = MagicMock()
            session.get.return_value = self._resp(code, {"error": "nope"})
            self.assertIsNone(main.normalize_project_id(session, "123"))

    def test_transient_lookup_failure_raises(self):
        session = MagicMock()
        session.get.return_value = self._resp(503, {"error": "unavailable"})
        with self.assertRaises(main.TransientLookupError):
            main.normalize_project_id(session, "123")
        session.get.side_effect = RuntimeError("timeout")
        with self.assertRaises(main.TransientLookupError):
            main.normalize_project_id(session, "123")

    @staticmethod
    def _numeric_agent_event():
        return {
            "insertId": "evt-num",
            "timestamp": "2026-10-26T16:02:19Z",
            "protoPayload": {
                "serviceName": "dialogflow.googleapis.com",
                "methodName": "google.cloud.dialogflow.v2beta1.Conversations.CompleteConversation",
                "resourceName": "projects/my-proj/locations/us/conversations/sess-num",
                "response": {
                    "conversationProfile": "projects/my-proj/locations/us/conversationProfiles/chat-prof"
                },
            },
        }

    def _numeric_profile(self):
        return {
            "name": "projects/my-proj/locations/us/conversationProfiles/chat-prof",
            "automatedAgentConfig": {
                "agent": "projects/123456789012/locations/us/apps/chat-app/deployments/d1"
            },
        }

    def test_handler_uses_resolved_project_id_for_logs_and_trace(self):
        with patch("main.get_authorized_session", return_value=(MagicMock(), "my-proj")), \
                patch("main.fetch_dialogflow_logs", return_value=[]), \
                patch("main.fetch_conversation_profile", return_value=self._numeric_profile()), \
                patch("main.normalize_project_id", side_effect=lambda s, p: "my-proj" if p == "123456789012" else p), \
                patch("main.trace_exists", return_value=False) as mock_exists, \
                patch("main.fetch_ces_conversation", return_value=self._conv()) as mock_conv, \
                patch("main.fetch_incoming_call_logs", return_value=[]), \
                patch("main.fetch_ces_response_logs", return_value=[]) as mock_ces_logs, \
                patch("main.write_trace_spans", return_value=True) as mock_write:
            body, status = self._invoke_endpoint(self._numeric_agent_event())
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["trace_project_id"], "my-proj")
        self.assertEqual(mock_conv.call_args.kwargs["project_id"], "my-proj")
        self.assertEqual(mock_ces_logs.call_args[0][1], "my-proj")
        self.assertEqual(mock_exists.call_args[0][1], "my-proj")
        self.assertEqual(mock_write.call_args[0][0], "my-proj")

    def test_handler_acks_when_project_number_unresolvable(self):
        with patch("main.get_authorized_session", return_value=(MagicMock(), "my-proj")), \
                patch("main.fetch_dialogflow_logs", return_value=[]), \
                patch("main.fetch_conversation_profile", return_value=self._numeric_profile()), \
                patch("main.normalize_project_id", return_value=None), \
                patch("main.write_trace_spans") as mock_write:
            body, status = self._invoke_endpoint(self._numeric_agent_event())
        self.assertEqual(status, 200)
        self.assertIn("Unresolvable project number", body)
        mock_write.assert_not_called()

    def test_handler_retries_on_transient_lookup_error(self):
        with patch("main.get_authorized_session", return_value=(MagicMock(), "my-proj")), \
                patch("main.fetch_dialogflow_logs", return_value=[]), \
                patch("main.fetch_conversation_profile", return_value=self._numeric_profile()), \
                patch("main.normalize_project_id", side_effect=main.TransientLookupError("503")), \
                patch("main.write_trace_spans") as mock_write:
            body, status = self._invoke_endpoint(self._numeric_agent_event())
        self.assertEqual(status, 500)
        mock_write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
