"""SQLite tracker: avoids duplicate posts and stores run history."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "seen_posts.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS seen "
        "(urn TEXT PRIMARY KEY, seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS run_history "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, ran_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, posts_found INTEGER)"
    )
    conn.commit()
    return conn


def is_new(urn: str) -> bool:
    with _conn() as conn:
        return conn.execute("SELECT 1 FROM seen WHERE urn=?", (urn,)).fetchone() is None


def mark_seen(urns: list[str]) -> None:
    if not urns:
        return
    with _conn() as conn:
        conn.executemany("INSERT OR IGNORE INTO seen (urn) VALUES (?)", [(u,) for u in urns])
        conn.commit()


def log_run(posts_found: int) -> None:
    with _conn() as conn:
        conn.execute("INSERT INTO run_history (posts_found) VALUES (?)", (posts_found,))
        conn.commit()


def get_run_history(limit: int = 10) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT ran_at, posts_found FROM run_history ORDER BY ran_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [{"ran_at": r[0], "posts_found": r[1]} for r in rows]


def cleanup_old(days: int = 30) -> None:
    with _conn() as conn:
        conn.execute(
            "DELETE FROM seen WHERE seen_at < datetime('now', ?)", (f"-{days} days",)
        )
        conn.execute(
            "DELETE FROM run_history WHERE ran_at < datetime('now', ?)", (f"-{days} days",)
        )
        conn.commit()
