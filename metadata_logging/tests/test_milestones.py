import os
import re
import sys
import json
import unittest

# Add src/ to python path
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from transform import extract_milestones, format_as_log_entry, is_metadata_update, redact_pii_fields

E164_RE = re.compile(r"\+\d{8,15}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
FIXTURES = ("call-1418", "call-987", "chat-135")

class TestCCaASMilestoneExtraction(unittest.TestCase):
    def setUp(self):
        self.examples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures"))
        self.project_id = "example-ccaas-project"
        self.location = "europe-west1"
        self.resource_id = "iva"

    def build_log_entries(self, fixture_name, gcs_uri, redact_pii_enabled=True):
        with open(os.path.join(self.examples_dir, fixture_name), "r") as f:
            metadata = json.load(f)
        extracted = extract_milestones(metadata, gcs_uri, redact_pii_enabled=redact_pii_enabled)
        return [
            format_as_log_entry(
                m,
                project_id=self.project_id,
                location=self.location,
                resource_id=self.resource_id
            )
            for m in extracted
        ]

    def run_regression_test(self, fixture_name, expected_name, gcs_uri, redact_pii_enabled=True):
        expected_path = os.path.join(self.examples_dir, expected_name)

        # Load expected logs
        with open(expected_path, "r") as f:
            expected_logs = json.load(f)

        # Extract milestones and format them as log entries
        actual_logs = self.build_log_entries(fixture_name, gcs_uri, redact_pii_enabled)

        # Verify exact match
        self.assertEqual(len(actual_logs), len(expected_logs), f"Mismatch in number of log entries for {fixture_name}")
        self.assertEqual(actual_logs, expected_logs, f"Parsed log entries differ from expected golden output for {fixture_name}")

    def test_call_1418_milestones(self):
        gcs_uri = "gs://example-ccaas-artifacts/example-tenant.ew1/metadata/call-1418.json"
        self.run_regression_test("metadata_call-1418.json", "expected_logs_call-1418.json", gcs_uri)

    def test_call_987_milestones(self):
        gcs_uri = "gs://example-ccaas-artifacts/example-tenant.ew1/metadata/call-987.json"
        self.run_regression_test("metadata_call-987.json", "expected_logs_call-987.json", gcs_uri)

    def test_chat_135_milestones(self):
        gcs_uri = "gs://example-ccaas-artifacts/example-tenant.ew1/metadata/chat-135.json"
        self.run_regression_test("metadata_chat-135.json", "expected_logs_chat-135.json", gcs_uri)

    def test_insert_id_stable_across_gcs_uri(self):
        fixture_path = os.path.join(self.examples_dir, "metadata_call-1418.json")
        with open(fixture_path, "r") as f:
            metadata = json.load(f)

        uri1 = "gs://bucket/2026/09/07/call-1418.json"
        uri2 = "gs://bucket/2026/09/08/call-1418.json"

        extracted1 = extract_milestones(metadata, uri1)
        extracted2 = extract_milestones(metadata, uri2)

        logs1 = [format_as_log_entry(m, project_id=self.project_id) for m in extracted1]
        logs2 = [format_as_log_entry(m, project_id=self.project_id) for m in extracted2]

        insert_ids1 = [l["insertId"] for l in logs1]
        insert_ids2 = [l["insertId"] for l in logs2]

        self.assertEqual(insert_ids1, insert_ids2, "insertIds should remain identical across differing GCS URI paths")

    def test_is_metadata_update_initial_exports(self):
        # Existing fixture files represent initial exports (delta <= 12s)
        for fixture_name in ["metadata_call-1418.json", "metadata_call-987.json", "metadata_chat-135.json"]:
            with open(os.path.join(self.examples_dir, fixture_name)) as f:
                data = json.load(f)
            self.assertFalse(is_metadata_update(data), f"{fixture_name} should be recognized as initial export")

    def test_is_metadata_update_delayed_updates(self):
        # When updated_at is 15-20 min after ends_at, classify as update
        metadata = {
            "ends_at": "2026-09-10T10:00:00.000Z",
            "updated_at": "2026-09-10T10:17:30.000Z"
        }
        self.assertTrue(is_metadata_update(metadata))

    def test_is_metadata_update_custom_threshold(self):
        metadata = {
            "ends_at": "2026-09-10T10:00:00.000Z",
            "updated_at": "2026-09-10T10:01:00.000Z" # 60s delta
        }
        self.assertFalse(is_metadata_update(metadata, update_threshold_seconds=120))
        self.assertTrue(is_metadata_update(metadata, update_threshold_seconds=30))

    def test_is_metadata_update_missing_timestamps(self):
        self.assertFalse(is_metadata_update({}))
        self.assertFalse(is_metadata_update(None))
        self.assertFalse(is_metadata_update({"ends_at": "2026-09-10T10:00:00Z"}))
        self.assertFalse(is_metadata_update({"updated_at": "2026-09-10T10:00:00Z"}))

    def test_extract_milestones_suppresses_group1_on_update(self):
        fixture_path = os.path.join(self.examples_dir, "metadata_call-1418.json")
        with open(fixture_path, "r") as f:
            metadata = json.load(f)

        gcs_uri = "gs://bucket/call-1418.json"
        
        # 1. Initial export: all milestones extracted
        initial_milestones = extract_milestones(metadata, gcs_uri)
        initial_names = {m["event_name"] for m in initial_milestones}
        
        # Verify Group 1 milestones are present in initial export
        group1_call_events = {
            "call_created", "call_queued", "call_assigned", "call_connected", "call_ended",
            "consumer_in_menu_started", "consumer_in_menu_ended",
            "virtual_agent_session_started", "virtual_agent_session_ended"
        }
        for ev in group1_call_events:
            self.assertIn(ev, initial_names, f"Initial export should include {ev}")

        # 2. Update export: simulate post-call update (updated_at 17 minutes after ends_at)
        update_metadata = metadata.copy()
        update_metadata["updated_at"] = "2026-03-23T13:33:46.000-07:00" # 17m after ends_at 13:16:46
        self.assertTrue(is_metadata_update(update_metadata))

        update_milestones = extract_milestones(update_metadata, gcs_uri)
        update_names = {m["event_name"] for m in update_milestones}

        # Verify NO Group 1 milestones are present on update
        for ev in group1_call_events:
            self.assertNotIn(ev, update_names, f"Update export must NOT include Group 1 event: {ev}")

        # Verify call_updated is present on update
        self.assertIn("call_updated", update_names, "Update export must include call_updated")

        # Verify other post-interaction / remaining events are still present
        self.assertTrue(any("recording" in ev or "handle" in ev for ev in update_names),
                        "Remaining events should still be parsed on update")

    def test_extract_milestones_suppresses_group1_chat_on_update(self):
        fixture_path = os.path.join(self.examples_dir, "metadata_chat-135.json")
        with open(fixture_path, "r") as f:
            metadata = json.load(f)

        gcs_uri = "gs://bucket/chat-135.json"

        # Simulate update 18 minutes after ends_at
        update_metadata = metadata.copy()
        update_metadata["updated_at"] = "2026-03-23T15:20:00.000Z"
        self.assertTrue(is_metadata_update(update_metadata))

        update_milestones = extract_milestones(update_metadata, gcs_uri)
        update_names = {m["event_name"] for m in update_milestones}

        # Verify chat Group 1 events are suppressed
        for ev in ["chat_created", "chat_assigned", "chat_ended"]:
            self.assertNotIn(ev, update_names, f"Update export must NOT include Group 1 chat event: {ev}")

        self.assertIn("chat_updated", update_names, "Update export must include chat_updated")

    def test_extract_milestones_explicit_is_update_overrides_heuristic(self):
        fixture_path = os.path.join(self.examples_dir, "metadata_call-1418.json")
        with open(fixture_path, "r") as f:
            metadata = json.load(f)

        gcs_uri = "gs://bucket/call-1418.json"

        # Simulate a call where timestamps indicate update (e.g. 27 min callback wait like call-6285)
        delayed_metadata = metadata.copy()
        delayed_metadata["updated_at"] = "2026-03-23T13:45:00.000-07:00"
        self.assertTrue(is_metadata_update(delayed_metadata))

        # But state tracking knows it is an initial export (is_update=False)
        milestones = extract_milestones(delayed_metadata, gcs_uri, is_update=False)
        event_names = {m["event_name"] for m in milestones}

        # Group 1 milestones must be present because is_update=False
        self.assertIn("call_created", event_names)
        self.assertIn("call_queued", event_names)
        self.assertIn("call_ended", event_names)

        # Conversely, if is_update=True explicitly passed even on fresh timestamps
        update_milestones = extract_milestones(metadata, gcs_uri, is_update=True)
        update_names = {m["event_name"] for m in update_milestones}
        self.assertNotIn("call_created", update_names)
        self.assertNotIn("call_queued", update_names)
        self.assertNotIn("call_ended", update_names)
        self.assertIn("call_updated", update_names)

    def test_virtual_agent_escalation_deflected_extraction(self):
        metadata = {
            "id": 12345,
            "call_uuid": "c-uuid-12345",
            "call_type": "Voice Inbound (IVR)",
            "created_at": "2026-09-16T17:22:48.000-07:00",
            "ends_at": "2026-09-16T17:27:50.000-07:00",
            "updated_at": "2026-09-16T17:27:50.000-07:00",
            "status": "canceled",
            "virtual_agent_deflected_escalations": [
                {
                    "id": 101,
                    "deflection": "temp_redirection_queue",
                    "escalation_id": 201,
                    "escalation_reason": "unknown",
                    "escalated_at": "2026-09-16T17:27:11.000-07:00",
                    "menu_path_id": 50,
                    "menu_path": "Main Menu - IVR/Virtual Agent/Reroute to service selection",
                    "lang": "en",
                    "virtual_agent": {
                        "id": 6,
                        "name": "Example Virtual Agent",
                        "va_alias": None,
                        "avatar_url": "https://example.com/avatar.png"
                    }
                }
            ]
        }
        gcs_uri = "gs://bucket/call-12345.json"
        milestones = extract_milestones(metadata, gcs_uri)
        deflected = [m for m in milestones if m["event_name"] == "virtual_agent_escalation_deflected"]
        self.assertEqual(len(deflected), 1)

        event = deflected[0]
        self.assertEqual(event["timestamp"], "2026-09-16T17:27:11.000-07:00")
        inner = event["payload"]["event"]["payload"]
        self.assertEqual(inner["call"]["id"], 12345)
        self.assertEqual(inner["virtual_agent"]["id"], 6)
        self.assertEqual(inner["virtual_agent"]["name"], "Example Virtual Agent")
        vade = inner["virtual_agent_deflected_escalation"]
        self.assertEqual(vade["deflection"], "temp_redirection_queue")
        self.assertEqual(vade["escalation_id"], 201)
        self.assertEqual(vade["menu_path_id"], 50)
        self.assertIn("Reroute to service selection", vade["menu_path"])

        # Formatted log entry check
        log_entry = format_as_log_entry(event, self.project_id, self.location, self.resource_id)
        self.assertEqual(log_entry["severity"], "INFO")
        self.assertEqual(log_entry["timestamp"], "2026-09-17T00:27:11Z")
        self.assertEqual(log_entry["jsonPayload"]["message"], "Milestone: virtual_agent_escalation_deflected (call 12345)")

        # Verify suppressed on metadata update
        update_milestones = extract_milestones(metadata, gcs_uri, is_update=True)
        update_deflected = [m for m in update_milestones if m["event_name"] == "virtual_agent_escalation_deflected"]
        self.assertEqual(len(update_deflected), 0)

    def test_session_ended_handle_boolean_flags(self):
        # 1. Neither VA nor human handle
        meta_neither = {
            "id": 1001,
            "call_type": "Voice Inbound (IVR)",
            "ends_at": "2026-09-16T17:27:50.000-07:00",
            "virtual_agent_handle_durations": [],
            "handle_durations": []
        }
        ended_neither = [m for m in extract_milestones(meta_neither, "gs://b/call-1001.json") if m["event_name"] == "call_ended"][0]
        details_neither = ended_neither["payload"]["event"]["payload"]["details"]
        self.assertFalse(details_neither["has_virtual_agent_handle"])
        self.assertFalse(details_neither["has_human_agent_handle"])

        # 2. VA handle only (chat)
        meta_va_only = {
            "id": 1002,
            "chat_type": "Messaging Inbound (Web Chat)",
            "ends_at": "2026-09-16T17:27:50.000-07:00",
            "chat_duration": 42,
            "virtual_agent_handle_durations": [{"id": 1, "started_at": "2026-09-16T17:27:00.000-07:00"}],
            "handle_durations": []
        }
        ended_va = [m for m in extract_milestones(meta_va_only, "gs://b/chat-1002.json") if m["event_name"] == "chat_ended"][0]
        details_va = ended_va["payload"]["event"]["payload"]["details"]
        self.assertTrue(details_va["has_virtual_agent_handle"])
        self.assertFalse(details_va["has_human_agent_handle"])
        self.assertEqual(details_va["chat_duration"], 42)

        # 3. Both VA and human handle
        meta_both = {
            "id": 1003,
            "call_type": "Voice Inbound (IVR)",
            "ends_at": "2026-09-16T17:27:50.000-07:00",
            "virtual_agent_handle_durations": [{"id": 1}],
            "handle_durations": [{"id": 2}]
        }
        ended_both = [m for m in extract_milestones(meta_both, "gs://b/call-1003.json") if m["event_name"] == "call_ended"][0]
        details_both = ended_both["payload"]["event"]["payload"]["details"]
        self.assertTrue(details_both["has_virtual_agent_handle"])
        self.assertTrue(details_both["has_human_agent_handle"])

    def test_call_scheduled_future_uses_created_at_timestamp(self):
        metadata = {
            "id": 2050,
            "lang": "en",
            "call_type": "Voice Scheduled (API)",
            "created_at": "2026-10-21T10:00:00.000-04:00",
            "scheduled_at": "2026-10-28T15:30:00.000-04:00",
            "updated_at": "2026-10-21T10:00:05.000-04:00"
        }
        gcs_uri = "gs://bucket/call-2050.json"
        milestones = extract_milestones(metadata, gcs_uri, is_update=False)
        scheduled_events = [m for m in milestones if m["event_name"] == "call_scheduled"]
        self.assertEqual(len(scheduled_events), 1)

        log_entry = format_as_log_entry(scheduled_events[0], self.project_id, self.location, self.resource_id)
        # Timestamp must reflect when the scheduling event occurred (created_at = 14:00:00Z),
        # not the future appointment time (>24h in the future on 2026-10-28).
        self.assertEqual(log_entry["timestamp"], "2026-10-21T14:00:00Z")
        self.assertNotIn("2026-10-28", json.dumps(log_entry))

    def test_redact_pii_enabled_and_disabled(self):
        metadata = {
            "id": 9999,
            "call_type": "Voice Inbound (IVR)",
            "participants": [
                {
                    "id": 1,
                    "type": "end_user",
                    "phone_number": "+15551234567",
                    "connected_at": "2026-09-16T17:22:48.000-07:00"
                }
            ],
            "transfers": [
                {
                    "id": 10,
                    "created_at": "2026-09-16T17:23:00.000-07:00",
                    "to_agent": {
                        "id": 42,
                        "first_name": "Alice",
                        "last_name": "Smith",
                        "name": "Alice Smith",
                        "email": "alice@example.com"
                    }
                }
            ]
        }
        gcs_uri = "gs://bucket/call-9999.json"

        # Default (redact_pii_enabled=True)
        redacted_milestones = extract_milestones(metadata, gcs_uri)
        p_redacted = [m for m in redacted_milestones if m["event_name"] == "participant_connected"][0]
        self.assertEqual(p_redacted["payload"]["event"]["payload"]["participant"]["phone_number"], "<REDACTED>")
        t_redacted = [m for m in redacted_milestones if m["event_name"] == "session_transfer_started"][0]
        to_agent_redacted = t_redacted["payload"]["event"]["payload"]["transfer"]["to_agent"]
        self.assertEqual(to_agent_redacted["first_name"], "<REDACTED>")
        self.assertEqual(to_agent_redacted["last_name"], "<REDACTED>")
        self.assertEqual(to_agent_redacted["name"], "<REDACTED>")
        self.assertEqual(to_agent_redacted["email"], "<REDACTED>")

        # Disabled (redact_pii_enabled=False)
        unredacted_milestones = extract_milestones(metadata, gcs_uri, redact_pii_enabled=False)
        p_unredacted = [m for m in unredacted_milestones if m["event_name"] == "participant_connected"][0]
        self.assertEqual(p_unredacted["payload"]["event"]["payload"]["participant"]["phone_number"], "+15551234567")
        t_unredacted = [m for m in unredacted_milestones if m["event_name"] == "session_transfer_started"][0]
        to_agent_unredacted = t_unredacted["payload"]["event"]["payload"]["transfer"]["to_agent"]
        self.assertEqual(to_agent_unredacted["first_name"], "Alice")
        self.assertEqual(to_agent_unredacted["last_name"], "Smith")
        self.assertEqual(to_agent_unredacted["name"], "Alice Smith")
        self.assertEqual(to_agent_unredacted["email"], "alice@example.com")

    def test_call_1418_unredacted_output_is_unchanged(self):
        # Golden output generated before the redaction rules were extended: opting out of
        # redaction must keep producing exactly the same log entries.
        gcs_uri = "gs://example-ccaas-artifacts/example-tenant.ew1/metadata/call-1418.json"
        self.run_regression_test(
            "metadata_call-1418.json", "expected_logs_call-1418_unredacted.json", gcs_uri,
            redact_pii_enabled=False,
        )

    def test_call_1418_redacts_ani_dnis_and_sip_headers(self):
        gcs_uri = "gs://example-ccaas-artifacts/example-tenant.ew1/metadata/call-1418.json"
        participants = [
            e["jsonPayload"]["event"]["payload"]["participant"]
            for e in self.build_log_entries("metadata_call-1418.json", gcs_uri)
            if "participant" in e["jsonPayload"]["event"]["payload"]
        ]
        va_params = [p["virtual_agent_params"] for p in participants if p.get("virtual_agent_params")]
        self.assertTrue(va_params, "fixture should contain virtual_agent_params")
        for params in va_params:
            self.assertEqual(params["ani"], "<REDACTED>")
            self.assertEqual(params["dnis"], "<REDACTED>")
            # Operational VA params are kept
            self.assertEqual(params["escalation_type"], "custom_payload")
        sip_headers = [p["sip_headers"] for p in participants if p.get("sip_headers") is not None]
        self.assertTrue(sip_headers, "fixture should contain sip_headers")
        self.assertTrue(all(h == "<REDACTED>" for h in sip_headers))

        # With redaction disabled the original values are written
        unredacted = [
            e["jsonPayload"]["event"]["payload"]["participant"]
            for e in self.build_log_entries("metadata_call-1418.json", gcs_uri, redact_pii_enabled=False)
            if "participant" in e["jsonPayload"]["event"]["payload"]
        ]
        params = [p["virtual_agent_params"] for p in unredacted if p.get("virtual_agent_params")][0]
        self.assertEqual(params["ani"], "+15550100100")
        self.assertEqual(params["dnis"], "+15550100300")
        headers = [p["sip_headers"] for p in unredacted if p.get("sip_headers") is not None][0]
        self.assertEqual(headers["P-Attestation-Indicator"], "A")

    def test_redact_pii_fields_phone_like_keys(self):
        payload = {
            "participant": {
                "phone_number": "+15550100001",
                "virtual_agent_params": {"ani": "+15550100002", "DNIS": "+15550100003", "lang": "en"},
                "custom": {
                    "callerId": "+15550100004",
                    "caller-id": "+15550100005",
                    "Caller_ID": "+15550100006",
                    "from_number": "+15550100007",
                    "toNumber": "+15550100008",
                    "Phone": "+15550100009",
                    "mobile": "+15550100010",
                    "deep": [{"nested": {"phoneNumber": "+15550100011"}}],
                    "phone_type": "mobile",
                    "missing": {"ani": None},
                },
            }
        }
        redacted = redact_pii_fields(payload)
        participant = redacted["participant"]
        custom = participant["custom"]
        self.assertEqual(participant["phone_number"], "<REDACTED>")
        self.assertEqual(participant["virtual_agent_params"], {"ani": "<REDACTED>", "DNIS": "<REDACTED>", "lang": "en"})
        for key in ("callerId", "caller-id", "Caller_ID", "from_number", "toNumber", "Phone", "mobile"):
            self.assertEqual(custom[key], "<REDACTED>", key)
        self.assertEqual(custom["deep"][0]["nested"]["phoneNumber"], "<REDACTED>")
        # Keys that only contain a phone word are not redacted, and None stays None
        self.assertEqual(custom["phone_type"], "mobile")
        self.assertIsNone(custom["missing"]["ani"])

    def test_redact_pii_fields_person_objects_and_sip_headers(self):
        payload = {
            "to_agent": {"first_name": "Alice", "middle_name": "B", "last_name": "Smith", "name": "Alice B Smith", "email": "alice@example.com", "id": 42},
            "only_middle": {"middle_name": "B", "name": "Alice"},
            "menu": {"name": "Main Menu"},
            "sip_headers": {"P-Origination-ID": "abc", "From": "+15550100012"},
            "no_headers": {"sip_headers": None},
        }
        redacted = redact_pii_fields(payload)
        self.assertEqual(
            redacted["to_agent"],
            {"first_name": "<REDACTED>", "middle_name": "<REDACTED>", "last_name": "<REDACTED>", "name": "<REDACTED>", "email": "<REDACTED>", "id": 42},
        )
        # A dict with middle_name counts as a person object
        self.assertEqual(redacted["only_middle"], {"middle_name": "<REDACTED>", "name": "<REDACTED>"})
        # name outside person objects (e.g. menu or queue names) is kept
        self.assertEqual(redacted["menu"], {"name": "Main Menu"})
        self.assertEqual(redacted["sip_headers"], "<REDACTED>")
        self.assertIsNone(redacted["no_headers"]["sip_headers"])

    def test_redacted_fixture_output_contains_no_phone_numbers_or_emails(self):
        # Guard test: with redaction on, no E.164 phone number or email may appear anywhere
        # in the log entries produced for the repo fixtures.
        for name in FIXTURES:
            gcs_uri = f"gs://example-ccaas-artifacts/example-tenant.ew1/metadata/{name}.json"
            text = json.dumps(self.build_log_entries(f"metadata_{name}.json", gcs_uri))
            self.assertEqual(E164_RE.findall(text), [], f"phone number in redacted output for {name}")
            self.assertEqual(EMAIL_RE.findall(text), [], f"email in redacted output for {name}")

if __name__ == "__main__":
    unittest.main()
