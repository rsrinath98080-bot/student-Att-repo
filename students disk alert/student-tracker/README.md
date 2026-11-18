# Student Attendance Tracking System

A full-stack, single-student attendance tracking web application built with **Python 3.10+**, **Flask**, **SQLite**, and **vanilla HTML/CSS/JavaScript** (zero build step).

Each student logs in to an individual attendance portal that calculates their overall attendance and unexcused risk tier, visualizes weekly performance with a pure SVG attendance chart, and triggers an accessible notification popup dialog (`role="alertdialog"`) whenever their attendance is flagged for intervention.

---

## Quick Start & Setup

### 1. Requirements
- Python 3.10+
- SQLite3 (included with Python standard library)

### 2. Installation & Launch
```bash
# Navigate to the project directory
cd student-tracker

# Install minimal dependencies (Flask, pytest, Werkzeug)
pip install -r requirements.txt

# Run the Flask web application
python app.py
```
Open **[http://localhost:5000](http://localhost:5000)** in your web browser. The database is initialized automatically with sample attendance records on startup.

### 3. Run Automated Tests
```bash
# Run unit and integration tests with pytest
python -m pytest tests/test_analysis.py -v
```

---

## Demo Student Accounts

Every demo account is seeded with the initial password: **`pass123`**.

| Student Name | Username | Risk Tier | Special Flags & Behaviors | Expected Login Experience |
|---|---|---|---|---|
| **Noah Williams** | `noah` | **Critical** (53.3%) | • Streak (4 days)<br>• Declining (-50.0 pts) | Immediate **"Attendance alert"** popup dialog with Critical, streak, and declining reasons + urgent meeting request. |
| **Jordan Miller** | `jordan` | **On track** (100.0%) | • Streak (3 days) | Immediate **"Attendance notice"** popup dialog highlighting the consecutive absence streak. |
| **Aaliyah Patel** | `aaliyah` | **On track** (96.7%) | • Declining (-20.0 pts) | Immediate **"Attendance notice"** popup dialog addressing the sharp drop in weeks 5–6. |
| **Isabella Kim** | `isabella` | **At risk** (86.7%) | • 5 Excused absences | Shows excused vs. unexcused distinction (70.0% actual vs. 86.7% tier). Alert popup for At risk tier. |
| **Marcus Vance** | `marcus` | **Critical** (60.0%) | • Steady trend | "Attendance alert" popup for Critical attendance rate. |
| **Sophia Chen** | `sophia` | **At risk** (80.0%) | • Steady trend | "Attendance notice" popup for At risk tier. |
| **Olivia Martinez** | `olivia` | **Watch** (90.0%) | • Improving (+15.0 pts) | "Attendance notice" popup with gentle check-in guidance. |
| **Liam Rodriguez** | `liam` | **Watch** (93.3%) | • Steady trend | "Attendance notice" popup for Watch tier. |
| **Ethan Davis** | `ethan` | **On track** (100.0%) | • None | Direct to dashboard. No popup. Notification bell shows 0 active flags. |
| **Emma Johnson** | `emma` | **On track** (100.0%) | • None (100% perfect) | Direct to dashboard. No popup. Notification shows **"✅ All Good"**. |

---

## Business & Attendance Rules (`analysis.py`)

All attendance intelligence rules are implemented as pure, deterministic functions in `analysis.py`:

| Rule | Formula / Logic | Explanation |
|---|---|---|
| **1. Overall Attendance %** | $\frac{\text{present}}{\text{present} + \text{excused} + \text{unexcused}} \times 100$ | Measures true classroom instructional time attended across all enrolled days. |
| **2. Tier Attendance %** | $\frac{\text{present} + \text{excused}}{\text{present} + \text{excused} + \text{unexcused}} \times 100$ | Evaluates disciplinary/intervention risk using **unexcused absences only**. Excused absences are treated as present for tier classification. |
| **3. Risk Tiers** | • **Critical**: $< 80.0\%$<br>• **At risk**: $80.0\%$ to $< 90.0\%$<br>• **Watch**: $90.0\%$ to $< 95.0\%$<br>• **On track**: $\ge 95.0\%$ | Configurable constants in `analysis.py`. Displayed as high-contrast badges with icon and text. |
| **4. Consecutive Streak** | $\max(\text{consecutive\_absent}) \ge 3$ | Triggers a **`⚡ 3+ days in a row`** badge on any student missing $\ge 3$ consecutive days in any single week. |
| **5. Weekly Trend** | $\Delta = \text{Avg}(\text{last 2 weeks}) - \text{Avg}(\text{earlier weeks})$<br>• $\Delta \le -5.0\% \to$ **Declining** (`↓`)<br>• $\Delta \ge +2.0\% \to$ **Improving** (`↑`)<br>• Otherwise $\to$ **Steady** (`→`) | Identifies sudden drops in engagement early, even if the student's cumulative tier is still high. |
| **6. Flagged Status** | $\text{Tier} \neq \text{"On track"} \lor \text{Streak} \lor \text{Declining}$ | When flagged, student triggers the modal alert dialog on login and active badge counts on the notification bell. |

---

## Security & Architecture Highlights

1. **Authentication & Session Isolation**:
   - Passwords stored using `werkzeug.security.generate_password_hash` (`scrypt`/`pbkdf2`).
   - Server-side signed cookie sessions with `session['user_id']`.
   - Every route and API checks session authentication.
   - Strict ID authorization: calling `/api/student/<id>` for any account other than the authenticated student immediately returns **`403 Forbidden`**.

2. **Login Brute-Force Rate Limiting**:
   - Tracks failed authentication attempts by IP address and username in the `login_attempts` SQLite table.
   - Automatically locks further attempts for **60 seconds** after 5 consecutive failures.
   - Returns generic error message (*"Invalid username or password. Please try again."*) to prevent user enumeration.

3. **CSRF Protection**:
   - Session-backed CSRF tokens injected into login forms and verified on POST submissions.

4. **Alert Persistence & De-duplication**:
   - The `alerts` table records `(student_id, created_at, tier, reasons, message, acknowledged_at)`.
   - `get_or_create_alert()` checks existing records so alerts are not duplicated on repeated logins if attendance data has not changed.
   - Clicking *"I understand"* records the acknowledgment timestamp via `/api/alert/acknowledge`.

5. **Accessibility (WCAG 2.1 Compliant)**:
   - Alert modal implements `role="alertdialog"`, `aria-modal="true"`, and traps keyboard Tab navigation inside the dialog while open.
   - Closes via `Escape` key or the *"I understand"* button.
   - Minimum 44px touch targets on buttons.
   - Badges use distinctive icons and text labels, never relying on color alone.
   - Theme toggle supporting **Light**, **Dark**, and **Auto** (synced to OS `prefers-color-scheme`).

---

## How to Import Your Own Attendance CSV

You can import any custom attendance CSV file into the SQLite database at any time using `import_csv.py`:

```bash
python import_csv.py /path/to/your_attendance.csv
```

### Required CSV Schema
The CSV must include a header row with the following column headers (case-insensitive):

```csv
name,week,days_present,excused,unexcused,consecutive_absent
Maya Lin,1,5,0,0,0
Maya Lin,2,4,1,0,1
Carlos Gomez,1,3,0,2,2
```

- **`name`**: Student full name (usernames are auto-generated from lowercase first names, handling duplicates with numerical suffixes).
- **`week`**: Week number ($\ge 1$).
- **`days_present`**: Days present that week ($\ge 0$).
- **`excused`**: Excused absences ($\ge 0$).
- **`unexcused`**: Unexcused absences ($\ge 0$).
- **`consecutive_absent`** *(optional)*: Longest absence streak in that week ($\ge 0$, defaults to 0).

*Malformed or blank rows are safely skipped, and a summary of imported records and skipped lines is printed to the terminal.*

---

## Verification & Screenshots

Browser integration testing verified the end-to-end user flows in headless Microsoft Edge across light and dark themes. The screenshots are saved in `screenshots/`:

1. `01_login_light.png` & `02_login_dark.png`: Login screen with demo account quick-fill buttons.
2. `03_noah_popup_light.png` & `04_noah_popup_dark.png`: Noah Williams's Critical popup alert displaying 3 active reasons and guardian message.
3. `05_noah_dashboard_light.png`: Noah Williams's dashboard with SVG chart and stat cards.
4. `06_jordan_popup_light.png`: Jordan Miller's streak notice popup dialog.
5. `08_aaliyah_popup_light.png`: Aaliyah Patel's declining trend notice popup dialog.
6. `10_emma_dashboard_light.png` & `11_emma_dashboard_dark.png`: Emma Johnson's dashboard showing no popup and the "All Good" confirmation.

---

## Next Steps & Roadmap

If taking this system into a full district or school-wide deployment, recommended next steps include:

1. **Staff & Administration Portal**:
   - Multi-role authorization (Student, Teacher, Attendance Counselor, Principal).
   - District-wide filtered tables, bulk export, and cohort intervention queues.
2. **Automated Guardian Delivery (Email / SMS)**:
   - Direct integration with school communication APIs (SendGrid, Twilio, or SIS hooks like PowerSchool/Canvas).
   - Delivery logging, read receipts, and multi-language guardian translations.
3. **Production Deployment Checklist**:
   - Replace Flask development server with an ASGI/WSGI production server (e.g. `gunicorn -w 4 -b 0.0.0.0:5000 app:app`).
   - Move from SQLite to PostgreSQL or MySQL for high concurrent write volumes.
   - Store session secrets in external secret managers (AWS Secrets Manager, GCP Secret Manager).
   - Set up reverse proxy SSL/TLS termination with NGINX or Caddy (`Strict-Transport-Security`, `X-Content-Type-Options: nosniff`).
