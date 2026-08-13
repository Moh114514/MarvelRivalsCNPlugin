from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator


class BindingStoreError(RuntimeError):
    """Storage failure without exposing local filesystem details to users."""


class BindingStore:
    def __init__(self, path: str | Path = "data/marvel_rivals.sqlite3"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS bindings (qq_id TEXT PRIMARY KEY, uid TEXT NOT NULL)")

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        try:
            conn.execute("PRAGMA busy_timeout = 5000")
            yield conn
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise BindingStoreError("绑定存储暂时不可用") from exc
        finally:
            conn.close()

    def bind(self, qq_id: str, uid: str) -> None:
        with self._connection() as conn:
            conn.execute("INSERT INTO bindings(qq_id, uid) VALUES (?, ?) ON CONFLICT(qq_id) DO UPDATE SET uid=excluded.uid", (qq_id, uid))

    def get(self, qq_id: str) -> str | None:
        with self._connection() as conn:
            row = conn.execute("SELECT uid FROM bindings WHERE qq_id = ?", (qq_id,)).fetchone()
        return row[0] if row else None

    def unbind(self, qq_id: str) -> bool:
        with self._connection() as conn:
            cursor = conn.execute("DELETE FROM bindings WHERE qq_id = ?", (qq_id,))
        return cursor.rowcount > 0
