"""SQLite tracker to avoid sending duplicate posts."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "seen_posts.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS seen (urn TEXT PRIMARY KEY, seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
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


def cleanup_old(days: int = 30) -> None:
    """Remove entries older than `days` days to keep DB small."""
    with _conn() as conn:
        conn.execute("DELETE FROM seen WHERE seen_at < datetime('now', ?)", (f"-{days} days",))
        conn.commit()
