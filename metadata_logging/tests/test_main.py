import os
import sys
import json
import base64
import unittest
from unittest.mock import patch, MagicMock

# Add src/ to python path
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Set env vars before importing main to avoid errors
os.environ["CUSTOM_LOG_NAME"] = "test-log"
os.environ["PATH_CONFIGS"] = json.dumps([
    {
        "bucket": "test-bucket",
        "path_pattern": "metadata/",
        "ccaas_project_id": "test-project",
        "ccaas_resource_location": "us-central1",
        "ccaas_resource_id": "iva-test"
    }
])

try:
    import flask
    import google.cloud.storage
    import google.cloud.logging
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    DEPENDENCIES_AVAILABLE = False

if DEPENDENCIES_AVAILABLE:
    with patch("google.cloud.storage.Client"):
        import main
else:
    main = None

@unittest.skipUnless(DEPENDENCIES_AVAILABLE, "flask and google-cloud dependencies not installed in local python environment")
class TestMetadataLoggerApp(unittest.TestCase):
    def setUp(self):
        if not DEPENDENCIES_AVAILABLE:
            return
        self.app = main.app.test_client()
        self.app.testing = True

    @patch("main.storage_client")
    @patch("main.get_logging_client")
    @patch("main.extract_milestones")
    @patch("main.format_as_log_entry")
    def test_handle_event_eventarc(self, mock_format, mock_extract, mock_get_logging, mock_storage):
        # Setup mocks
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.download_as_text.return_value = '{"id": 123}'
        mock_bucket.blob.return_value = mock_blob
        mock_storage.bucket.return_value = mock_bucket

        mock_logging_client = MagicMock()
        mock_logger = MagicMock()
        mock_batch = MagicMock()
        mock_logger.batch.return_value.__enter__.return_value = mock_batch
        mock_logging_client.logger.return_value = mock_logger
        mock_get_logging.return_value = mock_logging_client

        mock_extract.return_value = [{"event": "test"}]
        mock_format.return_value = {
            "timestamp": "2026-07-22T12:00:00Z",
            "jsonPayload": {"event": "test"},
            "severity": "INFO",
            "insertId": "1",
            "resource": {"type": "global", "labels": {}}
        }

        # Eventarc payload
        payload = {
            "bucket": "test-bucket",
            "name": "metadata/call-123.json"
        }

        response = self.app.post("/", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Successfully processed", response.data)
        mock_storage.bucket.assert_called_with("test-bucket")
        mock_bucket.blob.assert_called_with("metadata/call-123.json")
        mock_extract.assert_called_once()
        mock_batch.log_struct.assert_called_once()

    @patch("main.storage_client")
    @patch("main.get_logging_client")
    @patch("main.extract_milestones")
    @patch("main.format_as_log_entry")
    def test_handle_event_pubsub(self, mock_format, mock_extract, mock_get_logging, mock_storage):
        # Setup mocks
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.download_as_text.return_value = '{"id": 123}'
        mock_bucket.blob.return_value = mock_blob
        mock_storage.bucket.return_value = mock_bucket

        mock_logging_client = MagicMock()
        mock_logger = MagicMock()
        mock_batch = MagicMock()
        mock_logger.batch.return_value.__enter__.return_value = mock_batch
        mock_logging_client.logger.return_value = mock_logger
        mock_get_logging.return_value = mock_logging_client

        mock_extract.return_value = [{"event": "test"}]
        mock_format.return_value = {
            "timestamp": "2026-07-22T12:00:00Z",
            "jsonPayload": {"event": "test"},
            "severity": "INFO",
            "insertId": "1",
            "resource": {"type": "global", "labels": {}}
        }

        # Inner GCS payload
        gcs_payload = {
            "bucket": "test-bucket",
            "name": "metadata/call-123.json"
        }
        encoded_data = base64.b64encode(json.dumps(gcs_payload).encode("utf-8")).decode("utf-8")

        # Pub/Sub envelope
        payload = {
            "message": {
                "data": encoded_data,
                "messageId": "12345"
            }
        }

        response = self.app.post("/", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Successfully processed", response.data)
        mock_storage.bucket.assert_called_with("test-bucket")
        mock_bucket.blob.assert_called_with("metadata/call-123.json")

    @patch("main.storage_client")
    @patch("main.get_logging_client")
    @patch("main.extract_milestones")
    @patch("main.format_as_log_entry")
    def test_handle_event_pubsub_attributes(self, mock_format, mock_extract, mock_get_logging, mock_storage):
        # Setup mocks
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.download_as_text.return_value = '{"id": 123}'
        mock_bucket.blob.return_value = mock_blob
        mock_storage.bucket.return_value = mock_bucket

        mock_logging_client = MagicMock()
        mock_logger = MagicMock()
        mock_batch = MagicMock()
        mock_logger.batch.return_value.__enter__.return_value = mock_batch
        mock_logging_client.logger.return_value = mock_logger
        mock_get_logging.return_value = mock_logging_client

        mock_extract.return_value = [{"event": "test"}]
        mock_format.return_value = {
            "timestamp": "2026-07-22T12:00:00Z",
            "jsonPayload": {"event": "test"},
            "severity": "INFO",
            "insertId": "1",
            "resource": {"type": "global", "labels": {}}
        }

        # Pub/Sub payload where bucket/object are in attributes (empty or non-dict data payload)
        encoded_data = base64.b64encode(json.dumps({}).encode("utf-8")).decode("utf-8")
        payload = {
            "message": {
                "data": encoded_data,
                "attributes": {
                    "bucketId": "test-bucket",
                    "objectId": "metadata/call-123.json"
                },
                "messageId": "12345"
            }
        }

        response = self.app.post("/", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Successfully processed", response.data)
        mock_storage.bucket.assert_called_with("test-bucket")
        mock_bucket.blob.assert_called_with("metadata/call-123.json")

    def test_handle_event_skip_non_json(self):
        payload = {
            "bucket": "test-bucket",
            "name": "metadata/recording.mp3"
        }
        response = self.app.post("/", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Ignored non-JSON file upload", response.data)

    def test_handle_event_skip_no_match(self):
        payload = {
            "bucket": "other-bucket",
            "name": "metadata/call-123.json"
        }
        response = self.app.post("/", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Ignored GCS file upload", response.data)

if __name__ == "__main__":
    unittest.main()
