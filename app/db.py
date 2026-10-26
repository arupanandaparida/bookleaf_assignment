"""Thin SQLite wrapper: one shared connection guarded by an RLock, WAL mode, FK enforcement.
SQLite calls are sub-millisecond for this workload, so a single serialized connection is simple and safe."""
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from .config import settings


class Database:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)  # autocommit; explicit BEGIN
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript((Path(__file__).parent / "schema.sql").read_text())

    def one(self, sql: str, params=()):
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def all(self, sql: str, params=()):
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def run(self, sql: str, params=()) -> int:
        """Execute a write; returns lastrowid."""
        with self._lock:
            return self._conn.execute(sql, params).lastrowid

    @contextmanager
    def transaction(self):
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                yield
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    def close(self):
        self._conn.close()


db = Database(settings.db_path)
