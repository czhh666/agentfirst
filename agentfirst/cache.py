import hashlib
import json
import sqlite3
import time
from pathlib import Path


def cache_key(api_id: str, method: str, path: str, query: dict | None) -> str:
    q = {k: v for k, v in sorted((query or {}).items()) if v is not None and v != ""}
    raw = json.dumps([api_id, method.upper(), path, q], separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class Cache:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value BLOB, expires_at REAL)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at)")
        self._conn.commit()

    def get(self, key: str) -> bytes | None:
        row = self._conn.execute(
            "SELECT value FROM cache WHERE key=? AND expires_at > ?", (key, time.time())
        ).fetchone()
        return row[0] if row else None

    def set(self, key: str, value: bytes, ttl: int) -> None:
        if ttl <= 0:
            return
        self._conn.execute(
            "INSERT INTO cache (key, value, expires_at) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, expires_at=excluded.expires_at",
            (key, value, time.time() + ttl),
        )
        self._conn.commit()

    def clear(self) -> None:
        self._conn.execute("DELETE FROM cache")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


class Idempotency:
    def __init__(self, db_path: str, ttl: int = 86400):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.ttl = ttl
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS idem ("
            "key TEXT PRIMARY KEY, status INTEGER, body BLOB, content_type TEXT, expires_at REAL)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_idem_expires ON idem(expires_at)")
        self._conn.commit()

    def get(self, key: str):
        row = self._conn.execute(
            "SELECT status, body, content_type FROM idem WHERE key=? AND expires_at > ?",
            (key, time.time()),
        ).fetchone()
        if not row:
            return None
        return {"status": row[0], "body": row[1], "content_type": row[2]}

    def set(self, key: str, status: int, body: bytes, content_type: str | None) -> None:
        self._conn.execute(
            "INSERT INTO idem (key, status, body, content_type, expires_at) VALUES (?,?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET status=excluded.status, body=excluded.body, "
            "content_type=excluded.content_type, expires_at=excluded.expires_at",
            (key, status, body, content_type, time.time() + self.ttl),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def idempotency_key(user: str, api_id: str, idem_key: str) -> str:
    raw = json.dumps([user, api_id, idem_key], separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
