import unittest
from pathlib import Path

from marvel_rivals_bot.storage.bindings import BindingStore


class TestBindingStore(unittest.TestCase):
    def test_existing_bindings_survive_schema_bootstrap(self):
        import sqlite3

        path = Path.cwd() / "test-bindings-legacy.sqlite3"
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(f"{path}{suffix}")
            if candidate.exists():
                candidate.unlink()
        try:
            conn = sqlite3.connect(path)
            try:
                conn.execute("CREATE TABLE bindings (qq_id TEXT PRIMARY KEY, uid TEXT NOT NULL)")
                conn.execute("INSERT INTO bindings (qq_id, uid) VALUES ('qq', '123')")
                conn.commit()
            finally:
                conn.close()
            store = BindingStore(path)
            self.assertEqual(store.get("qq"), "123")
        finally:
            for suffix in ("", "-wal", "-shm"):
                candidate = Path(f"{path}{suffix}")
                if candidate.exists():
                    candidate.unlink()

    def test_new_database_records_schema_version(self):
        path = Path.cwd() / "test-bindings-schema.sqlite3"
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(f"{path}{suffix}")
            if candidate.exists():
                candidate.unlink()
        try:
            BindingStore(path)
            import sqlite3

            conn = sqlite3.connect(path)
            try:
                version = conn.execute(
                    "SELECT schema_version FROM schema_meta WHERE id = 1"
                ).fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(version, 1)
        finally:
            for suffix in ("", "-wal", "-shm"):
                candidate = Path(f"{path}{suffix}")
                if candidate.exists():
                    candidate.unlink()

    def test_bind_update_and_unbind(self):
        path = Path.cwd() / "test-bindings.sqlite3"
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(f"{path}{suffix}")
            if candidate.exists():
                candidate.unlink()
        try:
            store = BindingStore(path)
            self.assertIsNone(store.get("qq"))
            store.bind("qq", "123")
            self.assertEqual(store.get("qq"), "123")
            store.bind("qq", "456")
            self.assertEqual(store.get("qq"), "456")
            self.assertTrue(store.unbind("qq"))
            self.assertFalse(store.unbind("qq"))
        finally:
            for suffix in ("", "-wal", "-shm"):
                candidate = Path(f"{path}{suffix}")
                if candidate.exists():
                    candidate.unlink()
