import unittest
from pathlib import Path

from marvel_rivals_bot.storage.bindings import BindingStore


class TestBindingStore(unittest.TestCase):
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
