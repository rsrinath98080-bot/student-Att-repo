"""
Unit and Integration Tests for Student Attendance Tracking System
Tests pure analysis functions, tier boundary conditions, streak flags,
trend algorithms, alert generation, and Flask authentication/authorization routes.
"""

import os
import sys
import pytest
from pathlib import Path

# Ensure student-tracker directory is on path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CURRENT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import analysis
import db
import import_csv
from app import app


# ============================================================================
# Pure Analysis Function Tests
# ============================================================================

class TestPercentageFormulas:
    """Test both attendance percentage formulas."""

    def test_overall_attendance_pct(self):
        # 20 present, 2 excused, 3 unexcused -> 20 / 25 = 80.0%
        assert analysis.calculate_overall_attendance_pct(20, 2, 3) == 80.0
        # Perfect attendance
        assert analysis.calculate_overall_attendance_pct(30, 0, 0) == 100.0
        # Zero days enrolled
        assert analysis.calculate_overall_attendance_pct(0, 0, 0) == 0.0

    def test_tier_attendance_pct_excused_counted_as_present(self):
        # Rule 2: (present + excused) / (present + excused + unexcused) * 100
        # 21 present, 5 excused, 4 unexcused = (21 + 5) / 30 = 26 / 30 = 86.7%
        pct = analysis.calculate_tier_attendance_pct(21, 5, 4)
        assert pct == 86.7

        # Excused absences preserve tier percentage
        assert analysis.calculate_tier_attendance_pct(20, 10, 0) == 100.0


class TestTierBoundaries:
    """Test each required tier boundary condition."""

    def test_critical_boundary(self):
        # Critical < 80
        assert analysis.determine_tier(79.9) == "Critical"
        assert analysis.determine_tier(0.0) == "Critical"

    def test_at_risk_boundary(self):
        # At risk 80 to < 90
        assert analysis.determine_tier(80.0) == "At risk"
        assert analysis.determine_tier(85.0) == "At risk"
        assert analysis.determine_tier(89.9) == "At risk"

    def test_watch_boundary(self):
        # Watch 90 to < 95
        assert analysis.determine_tier(90.0) == "Watch"
        assert analysis.determine_tier(92.5) == "Watch"
        assert analysis.determine_tier(94.9) == "Watch"

    def test_on_track_boundary(self):
        # On track >= 95
        assert analysis.determine_tier(95.0) == "On track"
        assert analysis.determine_tier(99.0) == "On track"
        assert analysis.determine_tier(100.0) == "On track"


class TestStreakFlag:
    """Test consecutive absence streak detection."""

    def test_streak_below_threshold(self):
        records = [
            {"week": 1, "consecutive_absent": 1},
            {"week": 2, "consecutive_absent": 2},
        ]
        has_streak, max_streak = analysis.check_consecutive_streak(records, threshold=3)
        assert not has_streak
        assert max_streak == 2

    def test_streak_exactly_threshold(self):
        records = [
            {"week": 1, "consecutive_absent": 0},
            {"week": 2, "consecutive_absent": 3},
            {"week": 3, "consecutive_absent": 1},
        ]
        has_streak, max_streak = analysis.check_consecutive_streak(records, threshold=3)
        assert has_streak
        assert max_streak == 3

    def test_streak_above_threshold(self):
        records = [
            {"week": 1, "consecutive_absent": 4},
        ]
        has_streak, max_streak = analysis.check_consecutive_streak(records, threshold=3)
        assert has_streak
        assert max_streak == 4

    def test_empty_records_streak(self):
        has_streak, max_streak = analysis.check_consecutive_streak([], threshold=3)
        assert not has_streak
        assert max_streak == 0


class TestTrendCalculations:
    """Test Declining, Improving, and Steady trend cases."""

    def test_declining_trend(self):
        # Earlier 4 weeks = 100%, last 2 weeks = 80% -> delta = -20.0 (<= -5.0)
        records = [
            {"week": 1, "days_present": 5, "excused": 0, "unexcused": 0},
            {"week": 2, "days_present": 5, "excused": 0, "unexcused": 0},
            {"week": 3, "days_present": 5, "excused": 0, "unexcused": 0},
            {"week": 4, "days_present": 5, "excused": 0, "unexcused": 0},
            {"week": 5, "days_present": 4, "excused": 0, "unexcused": 1},
            {"week": 6, "days_present": 4, "excused": 0, "unexcused": 1},
        ]
        label, arrow, delta = analysis.calculate_trend(records)
        assert label == "Declining"
        assert arrow == "↓"
        assert delta <= -5.0

    def test_improving_trend(self):
        # Earlier 4 weeks = 60%, last 2 weeks = 100% -> delta = +40.0 (>= +2.0)
        records = [
            {"week": 1, "days_present": 3, "excused": 0, "unexcused": 2},
            {"week": 2, "days_present": 3, "excused": 0, "unexcused": 2},
            {"week": 3, "days_present": 3, "excused": 0, "unexcused": 2},
            {"week": 4, "days_present": 3, "excused": 0, "unexcused": 2},
            {"week": 5, "days_present": 5, "excused": 0, "unexcused": 0},
            {"week": 6, "days_present": 5, "excused": 0, "unexcused": 0},
        ]
        label, arrow, delta = analysis.calculate_trend(records)
        assert label == "Improving"
        assert arrow == "↑"
        assert delta >= 2.0

    def test_steady_trend(self):
        # Consistent 80% across all 6 weeks -> delta = 0.0
        records = [
            {"week": 1, "days_present": 4, "excused": 0, "unexcused": 1},
            {"week": 2, "days_present": 4, "excused": 0, "unexcused": 1},
            {"week": 3, "days_present": 4, "excused": 0, "unexcused": 1},
            {"week": 4, "days_present": 4, "excused": 0, "unexcused": 1},
            {"week": 5, "days_present": 4, "excused": 0, "unexcused": 1},
            {"week": 6, "days_present": 4, "excused": 0, "unexcused": 1},
        ]
        label, arrow, delta = analysis.calculate_trend(records)
        assert label == "Steady"
        assert arrow == "→"
        assert delta == 0.0


class TestFlaggedLogic:
    """Test flagging conditions."""

    def test_tier_flagged(self):
        # Any tier other than On track is flagged
        assert analysis.is_student_flagged("Critical", False, "Steady") is True
        assert analysis.is_student_flagged("At risk", False, "Steady") is True
        assert analysis.is_student_flagged("Watch", False, "Steady") is True

    def test_streak_flagged_when_on_track(self):
        # On track student with streak is flagged
        assert analysis.is_student_flagged("On track", True, "Steady") is True

    def test_declining_flagged_when_on_track(self):
        # On track student with declining trend is flagged
        assert analysis.is_student_flagged("On track", False, "Declining") is True

    def test_unflagged_on_track(self):
        # On track student with no streak and steady/improving trend is NOT flagged
        assert analysis.is_student_flagged("On track", False, "Steady") is False
        assert analysis.is_student_flagged("On track", False, "Improving") is False


class TestGuardianMessage:
    """Test guardian message formatting and typographic apostrophes."""

    def test_typographic_apostrophes(self):
        msg = analysis.generate_guardian_message(
            first_name="Noah",
            total_missed=14,
            unexcused=14,
            excused=0,
            overall_pct=53.3,
            tier="Critical",
            has_streak=True,
            max_streak=4,
            trend="Declining",
        )
        # Must contain typographic apostrophes (’ / \u2019)
        assert "We’re" in msg
        assert "Noah’s" in msg
        assert "we’d" in msg
        # Must not contain ASCII contractions
        assert "We're" not in msg
        assert "we'd" not in msg


# ============================================================================
# Flask Route and Security Tests
# ============================================================================

@pytest.fixture
def client(tmp_path):
    """Set up test Flask client with an isolated temporary database."""
    test_db = str(tmp_path / "test_tracker.db")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    
    # Initialize DB and import sample CSV
    csv_path = str(PROJECT_DIR / "sample_attendance.csv")
    import_csv.import_attendance_csv(csv_path, test_db)
    
    # Monkeypatch db path in app module
    import app as flask_app_module
    old_db_path = flask_app_module.DB_PATH
    flask_app_module.DB_PATH = test_db

    with app.test_client() as client:
        yield client

    flask_app_module.DB_PATH = old_db_path


class TestRouteSecurity:
    """Test authentication, authorization, and route security."""

    def test_login_wrong_password_fails(self, client):
        # Attempt login with invalid password
        client.get("/login")
        with client.session_transaction() as sess:
            token = sess.get("_csrf_token", "")

        res = client.post(
            "/login",
            data={"username": "noah", "password": "wrongpassword", "csrf_token": token},
            follow_redirects=True,
        )
        assert res.status_code == 401
        assert b"Invalid username or password" in res.data

    def test_login_correct_password_succeeds(self, client):
        # Noah login
        client.get("/login")
        with client.session_transaction() as sess:
            token = sess.get("_csrf_token", "")

        res = client.post(
            "/login",
            data={"username": "noah", "password": "pass123", "csrf_token": token},
            follow_redirects=True,
        )
        assert res.status_code == 200
        assert b"Welcome back, Noah Williams" in res.data

    def test_unauthorized_dashboard_access_redirects(self, client):
        # Accessing dashboard without session redirects to /login
        res = client.get("/dashboard", follow_redirects=False)
        assert res.status_code == 302
        assert "/login" in res.headers["Location"]

    def test_cannot_access_another_student_api(self, client):
        # Log in as Noah
        client.get("/login")
        with client.session_transaction() as sess:
            token = sess.get("_csrf_token", "")
        client.post(
            "/login",
            data={"username": "noah", "password": "pass123", "csrf_token": token},
            follow_redirects=True,
        )

        with client.session_transaction() as sess:
            my_id = sess["user_id"]
            other_id = my_id + 1 if my_id == 1 else my_id - 1

        # Accessing own data succeeds
        res_own = client.get(f"/api/student/{my_id}")
        assert res_own.status_code == 200

        # Accessing someone else's id returns 403 Forbidden!
        res_other = client.get(f"/api/student/{other_id}")
        assert res_other.status_code == 403
        assert b"Forbidden" in res_other.data

    def test_flagged_student_shows_alert(self, client):
        # Noah is Critical + Streak + Declining -> Flagged
        client.get("/login")
        with client.session_transaction() as sess:
            token = sess.get("_csrf_token", "")
        res = client.post(
            "/login",
            data={"username": "noah", "password": "pass123", "csrf_token": token},
            follow_redirects=True,
        )
        assert res.status_code == 200
        # Alert dialog should be in HTML
        assert b'role="alertdialog"' in res.data
        assert b'data-show-on-load="true"' in res.data

    def test_unflagged_student_shows_no_alert_popup(self, client):
        # Emma is On track (100% attendance, no flags) -> Not flagged
        client.get("/login")
        with client.session_transaction() as sess:
            token = sess.get("_csrf_token", "")
        res = client.post(
            "/login",
            data={"username": "emma", "password": "pass123", "csrf_token": token},
            follow_redirects=True,
        )
        assert res.status_code == 200
        # Alert dialog should NOT be shown
        assert b'role="alertdialog"' not in res.data
        assert b"All Good" in res.data
