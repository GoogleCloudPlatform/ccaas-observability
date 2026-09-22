import os
import sys
import json
import unittest

# Add src/ to python path
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from transform import extract_milestones, format_as_log_entry, is_metadata_update

class TestCCaASMilestoneExtraction(unittest.TestCase):
    def setUp(self):
        self.examples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures"))
        self.project_id = "ccaip-probing-infra-u8xi7u"
        self.location = "europe-west1"
        self.resource_id = "iva"

    def run_regression_test(self, fixture_name, expected_name, gcs_uri):
        fixture_path = os.path.join(self.examples_dir, fixture_name)
        expected_path = os.path.join(self.examples_dir, expected_name)

        # Load fixture metadata
        with open(fixture_path, "r") as f:
            metadata = json.load(f)

        # Load expected logs
        with open(expected_path, "r") as f:
            expected_logs = json.load(f)

        # Extract milestones
        extracted = extract_milestones(metadata, gcs_uri)
        
        # Format milestones as log entries
        actual_logs = [
            format_as_log_entry(
                m,
                project_id=self.project_id,
                location=self.location,
                resource_id=self.resource_id
            )
            for m in extracted
        ]

        # Verify exact match
        self.assertEqual(len(actual_logs), len(expected_logs), f"Mismatch in number of log entries for {fixture_name}")
        self.assertEqual(actual_logs, expected_logs, f"Parsed log entries differ from expected golden output for {fixture_name}")

    def test_call_1418_milestones(self):
        gcs_uri = "gs://ccaip-iva-artifact-9a/iva-prober-gxjs4ra.ew1/metadata/call-1418.json"
        self.run_regression_test("metadata_call-1418.json", "expected_logs_call-1418.json", gcs_uri)

    def test_call_987_milestones(self):
        gcs_uri = "gs://ccaip-iva-artifact-9a/iva-prober-gxjs4ra.ew1/metadata/call-987.json"
        self.run_regression_test("metadata_call-987.json", "expected_logs_call-987.json", gcs_uri)

    def test_chat_135_milestones(self):
        gcs_uri = "gs://ccaip-iva-artifact-9a/iva-prober-gxjs4ra.ew1/metadata/chat-135.json"
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

if __name__ == "__main__":
    unittest.main()
