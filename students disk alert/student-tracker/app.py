"""
Student Attendance Tracking System - Flask Application
Full-stack attendance tracking with role-based dashboard,
session authentication, rate limiting, CSRF protection, and alert popups.
"""

import os
import secrets
from functools import wraps
from typing import Optional, Dict, Any

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    abort,
    flash,
)
from werkzeug.security import check_password_hash

import db
import analysis
import import_csv

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), "student_tracker.db")
SAMPLE_CSV_PATH = os.path.join(os.path.dirname(__file__), "sample_attendance.csv")


def ensure_db_initialized():
    """Ensure database exists and is populated with sample data."""
    if not os.path.exists(DB_PATH):
        db.init_db(DB_PATH)
        if os.path.exists(SAMPLE_CSV_PATH):
            import_csv.import_attendance_csv(SAMPLE_CSV_PATH, DB_PATH)


@app.before_request
def setup_csrf():
    """Ensure session has a CSRF token."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)


@app.context_processor
def inject_csrf_token():
    """Inject csrf_token into all Jinja templates."""
    return {"csrf_token": session.get("_csrf_token", "")}


def login_required(f):
    """Decorator to enforce student session authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def get_client_ip() -> str:
    """Retrieve client IP address safely."""
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


@app.route("/")
def index():
    """Root route redirecting to dashboard or login."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Student login with CSRF protection, rate limiting, and password verification."""
    ensure_db_initialized()

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    error = None
    ip_addr = get_client_ip()

    if request.method == "POST":
        # CSRF check
        token = request.form.get("csrf_token")
        if not token or token != session.get("_csrf_token"):
            abort(400, description="Invalid CSRF token")

        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        # Rate limiting check
        is_locked, remaining = db.is_rate_limited(ip_addr, username, max_attempts=5, window_seconds=60, db_path=DB_PATH)
        if is_locked:
            error = f"Too many failed login attempts. Please wait {remaining} seconds before trying again."
            return render_template("login.html", error=error), 429

        # User lookup & authentication
        student = db.get_student_by_username(username, db_path=DB_PATH)

        if student and check_password_hash(student["password_hash"], password):
            # Success: clear failed attempts
            db.clear_failed_attempts(ip_addr, username, db_path=DB_PATH)
            db.record_login_attempt(ip_addr, username, success=True, db_path=DB_PATH)

            # Establish session
            session["user_id"] = student["id"]
            session["username"] = student["username"]
            session["first_name"] = student["first_name"]
            session["full_name"] = student["name"]
            session["just_logged_in"] = True

            return redirect(url_for("dashboard"))
        else:
            # Failure: record attempt and return generic inline error
            db.record_login_attempt(ip_addr, username, success=False, db_path=DB_PATH)
            error = "Invalid username or password. Please try again."
            return render_template("login.html", error=error), 401

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    """Log out student and clear session."""
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    """Student attendance dashboard displaying individual attendance data and alert popup."""
    ensure_db_initialized()
    student_id = session["user_id"]

    student = db.get_student_by_id(student_id, db_path=DB_PATH)
    if not student:
        session.clear()
        return redirect(url_for("login"))

    # Fetch attendance and run analysis
    raw_records = db.get_student_attendance(student_id, db_path=DB_PATH)
    analysis_data = analysis.analyze_student_records(
        raw_records,
        first_name=student["first_name"],
    )

    # Manage alert persistence
    alert_record = None
    if analysis_data["flagged"]:
        alert_record = db.get_or_create_alert(
            student_id=student_id,
            tier=analysis_data["tier"],
            reasons=analysis_data["reasons"],
            message=analysis_data["guardian_message"],
            db_path=DB_PATH,
        )

    # Determine whether popup should trigger on page load
    show_popup_on_load = False
    if session.pop("just_logged_in", False):
        if analysis_data["flagged"]:
            show_popup_on_load = True

    return render_template(
        "dashboard.html",
        student=student,
        data=analysis_data,
        alert=alert_record,
        show_popup_on_load=show_popup_on_load,
    )


@app.route("/api/student/<int:student_id>")
@login_required
def api_student(student_id: int):
    """
    API endpoint to retrieve student data.
    Enforces authorization: students can only fetch their own attendance data.
    """
    if session.get("user_id") != student_id:
        return jsonify({"error": "Forbidden: You may only access your own attendance data."}), 403

    student = db.get_student_by_id(student_id, db_path=DB_PATH)
    if not student:
        return jsonify({"error": "Student not found"}), 404

    raw_records = db.get_student_attendance(student_id, db_path=DB_PATH)
    data = analysis.analyze_student_records(raw_records, first_name=student["first_name"])
    return jsonify({
        "id": student["id"],
        "name": student["name"],
        "username": student["username"],
        "analysis": data,
    })


@app.route("/api/alert/acknowledge", methods=["POST"])
@login_required
def api_acknowledge_alert():
    """
    API endpoint for student to acknowledge an active alert.
    """
    student_id = session.get("user_id")
    data = request.get_json(silent=True) or request.form

    alert_id = data.get("alert_id")
    if not alert_id:
        # Fallback to latest alert
        latest = db.get_latest_alert(student_id, db_path=DB_PATH)
        if latest:
            alert_id = latest["id"]

    if alert_id:
        try:
            alert_id = int(alert_id)
            db.acknowledge_alert(alert_id, student_id, db_path=DB_PATH)
            return jsonify({"status": "ok", "alert_id": alert_id})
        except ValueError:
            return jsonify({"error": "Invalid alert_id"}), 400

    return jsonify({"status": "no_active_alert"})


if __name__ == "__main__":
    ensure_db_initialized()
    # Run locally on port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)
