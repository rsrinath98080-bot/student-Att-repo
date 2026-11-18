"""
Database module for Student Attendance Tracking System.
Handles schema initialization, student records, attendance data,
alert persistence, and login security rate-limiting with SQLite.
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "student_tracker.db")


def get_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Connect to SQLite database with Row factory enabled."""
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables and indexes."""
    conn = get_db(db_path)
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                first_name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS attendance_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                week INTEGER NOT NULL,
                days_present INTEGER NOT NULL,
                excused INTEGER NOT NULL,
                unexcused INTEGER NOT NULL,
                consecutive_absent INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                UNIQUE (student_id, week)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tier TEXT NOT NULL,
                reasons TEXT NOT NULL,
                message TEXT NOT NULL,
                acknowledged_at TIMESTAMP NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                username TEXT NOT NULL,
                attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_students_username ON students(username);
            CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance_records(student_id);
            CREATE INDEX IF NOT EXISTS idx_alerts_student ON alerts(student_id);
            CREATE INDEX IF NOT EXISTS idx_login_attempts ON login_attempts(ip_address, username, attempted_at);
        """)
    conn.close()


def get_student_by_username(username: str, db_path: Optional[str] = None) -> Optional[sqlite3.Row]:
    """Retrieve student record by lowercase username."""
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM students WHERE username = ?", (username.strip().lower(),))
    row = cur.fetchone()
    conn.close()
    return row


def get_student_by_id(student_id: int, db_path: Optional[str] = None) -> Optional[sqlite3.Row]:
    """Retrieve student record by student ID."""
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_student_attendance(student_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all weekly attendance records for a student sorted by week."""
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT week, days_present, excused, unexcused, consecutive_absent
        FROM attendance_records
        WHERE student_id = ?
        ORDER BY week ASC
        """,
        (student_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_or_create_alert(
    student_id: int,
    tier: str,
    reasons: List[Dict[str, Any]],
    message: str,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get existing active alert or create a new alert record if none exists or if data changed.
    Prevents creating duplicate alerts on every login.
    """
    conn = get_db(db_path)
    cur = conn.cursor()

    reasons_json = json.dumps(reasons, sort_keys=True)

    # Check the most recent alert for this student
    cur.execute(
        """
        SELECT id, student_id, created_at, tier, reasons, message, acknowledged_at
        FROM alerts
        WHERE student_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (student_id,),
    )
    latest = cur.fetchone()

    if latest:
        # Check if tier and reasons match exactly
        if latest["tier"] == tier and latest["reasons"] == reasons_json and latest["message"] == message:
            result = dict(latest)
            conn.close()
            return result

    # Insert new alert record
    cur.execute(
        """
        INSERT INTO alerts (student_id, tier, reasons, message, created_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (student_id, tier, reasons_json, message),
    )
    alert_id = cur.lastrowid
    conn.commit()

    cur.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
    new_alert = dict(cur.fetchone())
    conn.close()
    return new_alert


def acknowledge_alert(alert_id: int, student_id: int, db_path: Optional[str] = None) -> bool:
    """Record timestamp when student acknowledges an alert."""
    conn = get_db(db_path)
    cur = conn.cursor()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        """
        UPDATE alerts
        SET acknowledged_at = ?
        WHERE id = ? AND student_id = ?
        """,
        (now_str, alert_id, student_id),
    )
    updated = cur.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def get_latest_alert(student_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent alert for a student."""
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, student_id, created_at, tier, reasons, message, acknowledged_at
        FROM alerts
        WHERE student_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (student_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# Rate Limiting Functions
def record_login_attempt(ip_address: str, username: str, success: bool, db_path: Optional[str] = None) -> None:
    """Record a login attempt timestamp."""
    conn = get_db(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO login_attempts (ip_address, username, success, attempted_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (ip_address, username.strip().lower(), 1 if success else 0),
        )
    conn.close()


def is_rate_limited(
    ip_address: str,
    username: str,
    max_attempts: int = 5,
    window_seconds: int = 60,
    db_path: Optional[str] = None,
) -> Tuple[bool, int]:
    """
    Check if login attempts exceed threshold in the recent time window.
    Returns (is_locked, seconds_remaining).
    """
    conn = get_db(db_path)
    cur = conn.cursor()

    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=window_seconds)).strftime("%Y-%m-%d %H:%M:%S")

    # Count recent failures for this IP and username
    cur.execute(
        """
        SELECT COUNT(*), MAX(attempted_at)
        FROM login_attempts
        WHERE (ip_address = ? OR username = ?)
          AND success = 0
          AND attempted_at >= ?
        """,
        (ip_address, username.strip().lower(), cutoff),
    )
    row = cur.fetchone()
    fail_count = row[0] if row else 0
    conn.close()

    if fail_count >= max_attempts:
        return True, window_seconds
    return False, 0


def clear_failed_attempts(ip_address: str, username: str, db_path: Optional[str] = None) -> None:
    """Clear failed login attempts upon successful authentication."""
    conn = get_db(db_path)
    with conn:
        conn.execute(
            """
            DELETE FROM login_attempts
            WHERE (ip_address = ? OR username = ?)
            """,
            (ip_address, username.strip().lower()),
        )
    conn.close()
