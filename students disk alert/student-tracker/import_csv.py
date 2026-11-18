"""
CSV Importer for Student Attendance Tracking System.
Loads student roster and attendance records from CSV into SQLite database.
"""

import os
import sys
import csv
from pathlib import Path
from typing import Optional, Tuple
from werkzeug.security import generate_password_hash
from db import get_db, init_db, DEFAULT_DB_PATH

DEFAULT_PASSWORD = "pass123"


def import_attendance_csv(
    csv_file_path: str,
    db_path: Optional[str] = None,
    default_password: str = DEFAULT_PASSWORD,
) -> Tuple[int, int, int]:
    """
    Imports student attendance CSV into the database.
    Returns (students_count, records_count, skipped_count).
    """
    path = Path(csv_file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    init_db(db_path)
    conn = get_db(db_path)

    skipped_count = 0
    records_count = 0

    # Cache existing or created student ids: username -> id
    username_to_student = {}
    name_to_username = {}

    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = None
        for row in reader:
            if not row or all(c.strip() == "" for c in row):
                continue
            header = [c.strip().lower() for c in row]
            break

        if not header:
            conn.close()
            return 0, 0, 0

        required_cols = ["name", "week", "days_present", "excused", "unexcused"]
        for col in required_cols:
            if col not in header:
                conn.close()
                raise ValueError(f"Missing required CSV column '{col}'. Required: {required_cols}")

        idx_name = header.index("name")
        idx_week = header.index("week")
        idx_present = header.index("days_present")
        idx_excused = header.index("excused")
        idx_unexcused = header.index("unexcused")
        idx_consec = header.index("consecutive_absent") if "consecutive_absent" in header else None

        # Preload existing students
        cur = conn.cursor()
        cur.execute("SELECT id, name, username FROM students")
        for row in cur.fetchall():
            username_to_student[row["username"]] = row["id"]
            name_to_username[row["name"]] = row["username"]

        for row_num, row in enumerate(reader, start=2):
            if not row or all(c.strip() == "" for c in row):
                skipped_count += 1
                continue

            if len(row) <= max(idx_name, idx_week, idx_present, idx_excused, idx_unexcused):
                skipped_count += 1
                continue

            full_name = row[idx_name].strip()
            if not full_name:
                skipped_count += 1
                continue

            try:
                week = int(row[idx_week].strip())
                present = int(row[idx_present].strip())
                excused = int(row[idx_excused].strip())
                unexcused = int(row[idx_unexcused].strip())

                consec = 0
                if idx_consec is not None and idx_consec < len(row):
                    raw_c = row[idx_consec].strip()
                    if raw_c:
                        consec = int(raw_c)

                if week < 0 or present < 0 or excused < 0 or unexcused < 0 or consec < 0:
                    skipped_count += 1
                    continue

                if present + excused + unexcused <= 0:
                    skipped_count += 1
                    continue

            except ValueError:
                skipped_count += 1
                continue

            # Resolve student record
            if full_name not in name_to_username:
                first_name = full_name.split()[0].strip()
                base_username = first_name.lower()
                candidate_username = base_username
                suffix = 2
                while candidate_username in username_to_student:
                    candidate_username = f"{base_username}{suffix}"
                    suffix += 1

                pwd_hash = generate_password_hash(default_password)
                cur.execute(
                    """
                    INSERT INTO students (name, first_name, username, password_hash)
                    VALUES (?, ?, ?, ?)
                    """,
                    (full_name, first_name, candidate_username, pwd_hash),
                )
                student_id = cur.lastrowid
                conn.commit()

                username_to_student[candidate_username] = student_id
                name_to_username[full_name] = candidate_username
            else:
                student_id = username_to_student[name_to_username[full_name]]

            # Insert or replace attendance record
            cur.execute(
                """
                INSERT INTO attendance_records (student_id, week, days_present, excused, unexcused, consecutive_absent)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(student_id, week) DO UPDATE SET
                    days_present = excluded.days_present,
                    excused = excluded.excused,
                    unexcused = excluded.unexcused,
                    consecutive_absent = excluded.consecutive_absent
                """,
                (student_id, week, present, excused, unexcused, consec),
            )
            records_count += 1

    conn.commit()
    conn.close()

    return len(name_to_username), records_count, skipped_count


if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "sample_attendance.csv")
    print(f"Importing attendance data from: {csv_file}")
    students_n, records_n, skipped_n = import_attendance_csv(csv_file)
    print(f"Import complete: {students_n} students, {records_n} attendance records imported.")
    if skipped_n > 0:
        print(f"Notice: Skipped {skipped_n} blank or malformed row(s).")
    else:
        print("Skipped rows: 0 (clean dataset).")
