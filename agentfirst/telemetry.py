import sqlite3
import statistics
import time
from pathlib import Path


class Telemetry:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS request_log ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, user_id TEXT, api_id TEXT, "
            "endpoint TEXT, cache_hit INTEGER, response_bytes INTEGER, tokens_estimate INTEGER, "
            "cost REAL, upstream_status INTEGER)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS field_usage ("
            "api_id TEXT, endpoint TEXT, field TEXT, cnt INTEGER DEFAULT 0, "
            "bytes INTEGER DEFAULT 0, PRIMARY KEY (api_id, endpoint, field))"
        )
        conn.commit()
        conn.close()

    @staticmethod
    def _conn(db_path: str):
        return sqlite3.connect(db_path, check_same_thread=False)

    def log_request(self, user_id, api_id, endpoint, cache_hit, response_bytes,
                    tokens_estimate, cost, upstream_status):
        conn = self._conn(self.db_path)
        conn.execute(
            "INSERT INTO request_log (ts, user_id, api_id, endpoint, cache_hit, "
            "response_bytes, tokens_estimate, cost, upstream_status) VALUES (?,?,?,?,?,?,?,?,?)",
            (time.time(), user_id, api_id, endpoint, int(cache_hit), int(response_bytes),
             int(tokens_estimate), cost, int(upstream_status or 0)),
        )
        conn.commit()
        conn.close()

    def record_fields(self, api_id: str, endpoint: str, data: dict):
        conn = self._conn(self.db_path)
        conn.executemany(
            "INSERT INTO field_usage (api_id, endpoint, field, cnt, bytes) VALUES (?,?,?,1,?) "
            "ON CONFLICT(api_id, endpoint, field) DO UPDATE SET "
            "cnt = cnt + 1, bytes = bytes + excluded.bytes",
            [(api_id, endpoint, str(k), len(str(v))) for k, v in data.items()],
        )
        conn.commit()
        conn.close()

    def generate_profile(self, api_id: str, top_k: int = 20) -> list:
        conn = self._conn(self.db_path)
        rows = conn.execute(
            "SELECT field FROM field_usage WHERE api_id=? ORDER BY cnt DESC, bytes DESC LIMIT ?",
            (api_id, top_k),
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]

    def size_stats(self, api_id: str, endpoint: str) -> int | None:
        conn = self._conn(self.db_path)
        rows = conn.execute(
            "SELECT response_bytes FROM request_log WHERE api_id=? AND endpoint=? AND cache_hit=0",
            (api_id, endpoint),
        ).fetchall()
        conn.close()
        if not rows:
            return None
        return int(statistics.median(r[0] for r in rows))

    def report(self, api_id: str) -> dict:
        conn = self._conn(self.db_path)
        total = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(response_bytes),0), COALESCE(SUM(cost),0) "
            "FROM request_log WHERE api_id=?", (api_id,)
        ).fetchone()
        hits = conn.execute(
            "SELECT COUNT(*) FROM request_log WHERE api_id=? AND cache_hit=1", (api_id,)
        ).fetchone()[0]
        endpoints = conn.execute(
            "SELECT endpoint, COUNT(*), COALESCE(SUM(response_bytes),0) FROM request_log "
            "WHERE api_id=? GROUP BY endpoint ORDER BY 3 DESC", (api_id,)
        ).fetchall()
        conn.close()
        total_calls = total[0] or 0
        return {
            "api_id": api_id,
            "calls": total_calls,
            "cache_hit_rate": round(hits / total_calls, 3) if total_calls else 0.0,
            "total_bytes": total[1],
            "total_cost_usd": round(total[2], 6),
            "endpoints": [{"endpoint": e[0], "calls": e[1], "bytes": e[2]} for e in endpoints],
        }
