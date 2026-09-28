"""Focused checks for upload validation, analysis fallback, and Flask pages."""
import io
import tempfile
import unittest
from pathlib import Path

import pandas as pd

import app as web_app
from models.detector import analyze_logs


class DetectorTests(unittest.TestCase):
    def test_empty_dataframe_returns_empty_summary(self):
        result = analyze_logs(pd.DataFrame())
        self.assertEqual(result["total_messages"], 0)
        self.assertEqual(result["sender_summaries"], [])
        self.assertIn("No communication records", result["summary"])

    def test_sample_data_uses_machine_learning_with_enough_senders(self):
        result = analyze_logs(pd.read_csv(web_app.SAMPLE_FILE))
        self.assertEqual(result["total_messages"], 30)
        self.assertTrue(result["ml_available"])

    def test_multiple_receiver_accounts_are_reported_as_a_pattern(self):
        frame = pd.DataFrame([
            {"timestamp": "2025-01-01", "sender_id": "sample_a", "receiver_id": "target_1", "platform": "web", "message_type": "note", "response_status": "unknown"},
            {"timestamp": "2025-01-02", "sender_id": "sample_a", "receiver_id": "target_2", "platform": "web", "message_type": "note", "response_status": "unknown"},
        ])
        profile = analyze_logs(frame)["sender_summaries"][0]
        self.assertEqual(profile["receiver_count"], 2)
        self.assertIn("Multiple-account contact pattern", profile["indicators"])


class FlaskApplicationTests(unittest.TestCase):
    def setUp(self):
        self.original_database = web_app.DATABASE
        self.temporary_directory = tempfile.TemporaryDirectory()
        web_app.DATABASE = Path(self.temporary_directory.name) / "test.db"
        web_app.initialize_database()
        self.client = web_app.app.test_client()

    def tearDown(self):
        web_app.DATABASE = self.original_database
        self.temporary_directory.cleanup()

    def test_main_pages_load(self):
        for path in ("/", "/analysis", "/report"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_missing_columns_are_rejected_without_replacing_data(self):
        before = len(web_app.load_logs())
        response = self.client.post(
            "/upload",
            data={"file": (io.BytesIO(b"timestamp,sender_id\n2025-01-01,a\n"), "invalid.csv")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"Missing required columns", response.data)
        self.assertEqual(len(web_app.load_logs()), before)

    def test_invalid_timestamp_is_rejected(self):
        csv_bytes = (
            b"timestamp,sender_id,receiver_id,platform,message_type,response_status\n"
            b"not-a-date,source,target,forum,note,unanswered\n"
        )
        with self.assertRaisesRegex(ValueError, "valid timestamp"):
            web_app.validate_csv(csv_bytes)

    def test_header_only_csv_clears_dataset_and_pages_remain_available(self):
        headers = b"timestamp,sender_id,receiver_id,platform,message_type,response_status\n"
        response = self.client.post(
            "/upload",
            data={"file": (io.BytesIO(headers), "empty.csv")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"Loaded 0 validated", response.data)
        self.assertEqual(len(web_app.load_logs()), 0)
        self.assertEqual(self.client.get("/").status_code, 200)


if __name__ == "__main__":
    unittest.main()
