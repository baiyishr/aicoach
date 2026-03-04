"""SQLite session history storage."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config import DB_PATH


@dataclass
class Session:
    """A saved coaching session."""
    id: int | None
    timestamp: str
    video_path: str
    stroke_type: str
    sport: str
    comparison_report: str
    coaching_feedback: str
    metadata: dict

    def to_row(self) -> tuple:
        return (
            self.timestamp,
            self.video_path,
            self.stroke_type,
            self.sport,
            self.comparison_report,
            self.coaching_feedback,
            json.dumps(self.metadata),
        )

    @classmethod
    def from_row(cls, row: tuple) -> "Session":
        return cls(
            id=row[0],
            timestamp=row[1],
            video_path=row[2],
            stroke_type=row[3],
            sport=row[4],
            comparison_report=row[5],
            coaching_feedback=row[6],
            metadata=json.loads(row[7]) if row[7] else {},
        )


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            video_path TEXT NOT NULL,
            stroke_type TEXT NOT NULL,
            sport TEXT NOT NULL DEFAULT 'tennis',
            comparison_report TEXT NOT NULL,
            coaching_feedback TEXT NOT NULL,
            metadata TEXT DEFAULT '{}'
        )
    """)
    conn.commit()
    return conn


def save_session(
    video_path: str,
    stroke_type: str,
    comparison_report: str,
    coaching_feedback: str,
    sport: str = "tennis",
    metadata: dict | None = None,
) -> int:
    """Save a coaching session.

    Returns:
        The session ID.
    """
    conn = _get_connection()
    session = Session(
        id=None,
        timestamp=datetime.now().isoformat(),
        video_path=video_path,
        stroke_type=stroke_type,
        sport=sport,
        comparison_report=comparison_report,
        coaching_feedback=coaching_feedback,
        metadata=metadata or {},
    )
    cursor = conn.execute(
        "INSERT INTO sessions (timestamp, video_path, stroke_type, sport, "
        "comparison_report, coaching_feedback, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
        session.to_row(),
    )
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return session_id


def get_sessions(limit: int = 50) -> list[Session]:
    """Get recent sessions."""
    conn = _get_connection()
    cursor = conn.execute(
        "SELECT * FROM sessions ORDER BY timestamp DESC LIMIT ?", (limit,)
    )
    sessions = [Session.from_row(row) for row in cursor.fetchall()]
    conn.close()
    return sessions


def get_session(session_id: int) -> Session | None:
    """Get a specific session by ID."""
    conn = _get_connection()
    cursor = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    return Session.from_row(row) if row else None


def delete_session(session_id: int) -> bool:
    """Delete a session."""
    conn = _get_connection()
    cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted
