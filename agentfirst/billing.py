import sqlite3
import time
from pathlib import Path


class Billing:
    def __init__(self, db_path: str, pricing: dict):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.pricing = pricing
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS usage ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, user_id TEXT, api_id TEXT, "
            "cache_hit INTEGER, cost REAL)"
        )
        conn.commit()
        conn.close()

    @staticmethod
    def _conn(db_path: str):
        return sqlite3.connect(db_path, check_same_thread=False)

    def charge(self, user_id: str, api_id: str, cache_hit: bool) -> float:
        cost = self.pricing.get("hit", 0.00025) if cache_hit else self.pricing.get("miss", 0.0005)
        conn = self._conn(self.db_path)
        conn.execute(
            "INSERT INTO usage (ts, user_id, api_id, cache_hit, cost) VALUES (?,?,?,?,?)",
            (time.time(), user_id, api_id, int(cache_hit), cost),
        )
        conn.commit()
        conn.close()
        return cost

    def usage(self, user_id: str) -> dict:
        conn = self._conn(self.db_path)
        rows = conn.execute(
            "SELECT date(ts, 'unixepoch', 'localtime'), COUNT(*), "
            "COALESCE(SUM(CASE WHEN cache_hit=1 THEN 1 ELSE 0 END),0), "
            "COALESCE(SUM(cost),0) FROM usage WHERE user_id=? GROUP BY 1 ORDER BY 1",
            (user_id,),
        ).fetchall()
        conn.close()
        return {
            "user_id": user_id,
            "daily": [{"date": r[0], "calls": r[1], "cache_hits": r[2], "cost_usd": round(r[3], 6)} for r in rows],
            "total_calls": sum(r[1] for r in rows),
            "total_cost_usd": round(sum(r[3] for r in rows), 6),
        }
