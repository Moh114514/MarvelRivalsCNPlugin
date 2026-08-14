import json
import logging
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from marvel_rivals_bot.meta.cache import CacheRecord, MetaDiskCache, SCHEMA_VERSION


class TestMetaDiskCache(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.fetched_at = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
        self.now = datetime(2026, 8, 14, 12, 10, tzinfo=timezone.utc)
        self.cache = MetaDiskCache(
            self.root,
            fresh_seconds=600,
            stale_seconds=3600,
            clock=lambda: self.now,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_disk_fresh_hit_and_payload_is_preserved(self):
        payload = {"heroes": [{"hero_id": "1036", "matches": 12}], "extra": {"x": True}}
        self.cache.save("S9.5", payload, "rivalsmeta", 1720000000, self.fetched_at)

        record = self.cache.load("S9.5")

        self.assertIsInstance(record, CacheRecord)
        self.assertEqual(record.payload, payload)
        self.assertEqual(record.source, "rivalsmeta")
        self.assertEqual(record.season, "S9.5")
        self.assertEqual(record.source_timestamp, 1720000000)
        self.assertEqual(record.fetched_at, self.fetched_at)
        self.assertFalse(record.stale)

    def test_stale_hit_and_expired_miss(self):
        self.cache.save("S9", {"value": 1}, "source", fetched_at=self.fetched_at)

        stale = self.cache.load(
            "S9", now=datetime(2026, 8, 14, 12, 20, tzinfo=timezone.utc)
        )
        expired = self.cache.load(
            "S9", now=datetime(2026, 8, 14, 13, 1, tzinfo=timezone.utc)
        )

        self.assertIsNotNone(stale)
        self.assertTrue(stale.stale)
        self.assertIsNone(expired)

    def test_corrupt_json_logs_warning_and_misses(self):
        path = self.cache.cache_dir / "season_S9.json"
        path.parent.mkdir(parents=True)
        path.write_text("{not-json", encoding="utf-8")

        with self.assertLogs("marvel_rivals_bot.meta.cache", level=logging.WARNING) as logs:
            record = self.cache.load("S9")

        self.assertIsNone(record)
        self.assertIn("damaged Meta cache", logs.output[0])

    def test_schema_mismatch_logs_warning_and_misses(self):
        self.cache.save("S9", {"value": 1}, "source", fetched_at=self.fetched_at)
        path = self.cache.cache_dir / "season_S9.json"
        envelope = json.loads(path.read_text(encoding="utf-8"))
        envelope["schema_version"] = SCHEMA_VERSION + 1
        path.write_text(json.dumps(envelope), encoding="utf-8")

        with self.assertLogs("marvel_rivals_bot.meta.cache", level=logging.WARNING) as logs:
            record = self.cache.load("S9")

        self.assertIsNone(record)
        self.assertIn("schema version", logs.output[0])

    def test_save_uses_atomic_replace_and_no_temp_file_remains(self):
        with patch("marvel_rivals_bot.meta.cache.os.replace", wraps=__import__("os").replace) as replace:
            self.cache.save("S9", {"value": 1}, "source", fetched_at=self.fetched_at)

        replace.assert_called_once()
        self.assertTrue((self.cache.cache_dir / "season_S9.json").is_file())
        self.assertEqual(list(self.cache.cache_dir.glob("*.tmp")), [])

    def test_season_key_is_normalized_without_path_traversal(self):
        self.cache.save("../S9/../../escape", {"value": 1}, "source", fetched_at=self.fetched_at)

        files = list(self.cache.cache_dir.glob("season_*.json"))
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].resolve().is_relative_to(self.root.resolve()))
        self.assertIsNotNone(self.cache.load("../S9/../../escape"))


if __name__ == "__main__":
    unittest.main()
