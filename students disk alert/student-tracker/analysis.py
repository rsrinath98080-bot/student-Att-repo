"""
Attendance Risk Analysis Module
Pure functions for calculating attendance metrics, risk tiers,
trends, streaks, alert reasons, and guardian communications.
"""

from typing import List, Dict, Tuple, Any, Optional

# Configurable Threshold Constants
CRITICAL_THRESHOLD: float = 80.0
RISK_THRESHOLD: float = 90.0
WATCH_THRESHOLD: float = 95.0
CONSECUTIVE_THRESHOLD: int = 3
TREND_DECLINING_DELTA: float = -5.0
TREND_IMPROVING_DELTA: float = 2.0

DEFAULT_CONTACT_LINE: str = (
    "Please reach out to our Attendance Support Team at (555) 014-2840 "
    "or attendance@lincolnhigh.edu so we can partner together."
)


def calculate_overall_attendance_pct(present: int, excused: int, unexcused: int) -> float:
    """
    Calculate actual overall attendance percentage:
    present / (present + excused + unexcused) * 100
    """
    total = present + excused + unexcused
    if total <= 0:
        return 0.0
    return round((present / total) * 100.0, 1)


def calculate_tier_attendance_pct(present: int, excused: int, unexcused: int) -> float:
    """
    Calculate tier percentage where excused absences are treated as present:
    (present + excused) / (present + excused + unexcused) * 100
    """
    total = present + excused + unexcused
    if total <= 0:
        return 0.0
    return round(((present + excused) / total) * 100.0, 1)


def determine_tier(
    tier_pct: float,
    critical_th: float = CRITICAL_THRESHOLD,
    risk_th: float = RISK_THRESHOLD,
    watch_th: float = WATCH_THRESHOLD,
) -> str:
    """
    Determine the attendance tier:
    - Critical: < critical_th (default 80)
    - At risk: critical_th to < risk_th (default 80 to <90)
    - Watch: risk_th to < watch_th (default 90 to <95)
    - On track: >= watch_th (default >= 95)
    """
    if tier_pct < critical_th:
        return "Critical"
    elif tier_pct < risk_th:
        return "At risk"
    elif tier_pct < watch_th:
        return "Watch"
    else:
        return "On track"


def check_consecutive_streak(
    weekly_records: List[Dict[str, Any]],
    threshold: int = CONSECUTIVE_THRESHOLD,
) -> Tuple[bool, int]:
    """
    Check if student has any week with consecutive_absent >= threshold.
    Returns (has_streak, max_streak).
    """
    if not weekly_records:
        return False, 0
    max_streak = max((r.get("consecutive_absent", 0) for r in weekly_records), default=0)
    return max_streak >= threshold, max_streak


def calculate_trend(
    weekly_records: List[Dict[str, Any]],
    declining_delta: float = TREND_DECLINING_DELTA,
    improving_delta: float = TREND_IMPROVING_DELTA,
) -> Tuple[str, str, float]:
    """
    Compare average weekly rate of the last 2 weeks with the average of earlier weeks.
    Returns (trend_label, arrow_symbol, delta).
    Trend labels: 'Declining', 'Improving', 'Steady'.
    """
    if len(weekly_records) < 3:
        return "Steady", "→", 0.0

    sorted_records = sorted(weekly_records, key=lambda r: r.get("week", 0))

    weekly_rates = []
    for r in sorted_records:
        total = r.get("days_present", 0) + r.get("excused", 0) + r.get("unexcused", 0)
        rate = (r.get("days_present", 0) / total * 100.0) if total > 0 else 0.0
        weekly_rates.append(rate)

    recent_avg = sum(weekly_rates[-2:]) / 2.0
    earlier_avg = sum(weekly_rates[:-2]) / float(len(weekly_rates) - 2)
    delta = round(recent_avg - earlier_avg, 1)

    if delta <= declining_delta:
        return "Declining", "↓", delta
    elif delta >= improving_delta:
        return "Improving", "↑", delta
    else:
        return "Steady", "→", delta


def is_student_flagged(tier: str, has_streak: bool, trend: str) -> bool:
    """
    A student is flagged if tier is not 'On track', OR streak flag, OR trend is 'Declining'.
    """
    return (tier != "On track") or has_streak or (trend == "Declining")


def generate_alert_reasons(
    tier: str,
    tier_pct: float,
    has_streak: bool,
    max_streak: int,
    trend: str,
    trend_delta: float,
    critical_th: float = CRITICAL_THRESHOLD,
    risk_th: float = RISK_THRESHOLD,
    watch_th: float = WATCH_THRESHOLD,
    consecutive_th: int = CONSECUTIVE_THRESHOLD,
) -> List[Dict[str, str]]:
    """
    Generate list of structured alert reasons with severity styling.
    """
    reasons = []

    if tier == "Critical":
        reasons.append({
            "type": "tier",
            "severity": "critical",
            "title": "Critical Attendance Level",
            "description": f"Tier attendance rate is {tier_pct:.1f}%, which is below the {critical_th:.0f}% critical threshold."
        })
    elif tier == "At risk":
        reasons.append({
            "type": "tier",
            "severity": "risk",
            "title": "At-Risk Attendance Level",
            "description": f"Tier attendance rate is {tier_pct:.1f}%, which is below the {risk_th:.0f}% threshold."
        })
    elif tier == "Watch":
        reasons.append({
            "type": "tier",
            "severity": "watch",
            "title": "Attendance Watch Notice",
            "description": f"Tier attendance rate is {tier_pct:.1f}%, placing attendance under monitoring."
        })

    if has_streak:
        reasons.append({
            "type": "streak",
            "severity": "warning",
            "title": "Consecutive Absence Streak",
            "description": f"Logged a streak of {max_streak} consecutive absent days in a single week (threshold: {consecutive_th}+ days)."
        })

    if trend == "Declining":
        reasons.append({
            "type": "trend",
            "severity": "warning",
            "title": "Declining Weekly Trend",
            "description": f"Attendance over the past 2 weeks dropped by {abs(trend_delta):.1f} percentage points compared to earlier weeks."
        })

    return reasons


def generate_guardian_message(
    first_name: str,
    total_missed: int,
    unexcused: int,
    excused: int,
    overall_pct: float,
    tier: str,
    has_streak: bool,
    max_streak: int,
    trend: str,
    contact_line: str = DEFAULT_CONTACT_LINE,
) -> str:
    """
    Generate warm, supportive, non-accusatory guardian alert message.
    Uses typographic apostrophes (’ / \\u2019) throughout.
    """
    if total_missed == 0:
        missed_str = "no school days (0 unexcused, 0 excused)"
    elif total_missed == 1:
        missed_str = f"1 day of school ({unexcused} unexcused, {excused} excused)"
    else:
        missed_str = f"{total_missed} days of school ({unexcused} unexcused, {excused} excused)"

    flag_paragraphs = []
    if has_streak:
        flag_paragraphs.append(
            f"We also noticed a recent streak of {max_streak} consecutive days away from class, "
            f"and we wanted to check in to make sure everything is okay and that {first_name} feels supported in getting caught up."
        )

    if trend == "Declining":
        flag_paragraphs.append(
            f"Additionally, {first_name}’s attendance has dipped over the past two weeks compared to earlier in the term, "
            f"and we’d love to work together to turn that trend around before it creates learning hurdles."
        )

    if tier == "Critical":
        tier_body = (
            f"Because missing this amount of classroom time places {first_name} at critical academic risk, "
            f"we would like to schedule a brief meeting or phone conversation this week. "
            f"Our goal is to understand any obstacles your family may be facing and build a positive, realistic plan forward."
        )
    elif tier == "At risk":
        tier_body = (
            f"We are reaching out early because consistent attendance is closely linked with feeling confident and connected in school. "
            f"These absences are beginning to place {first_name} at risk of falling behind, and we want to partner with you to help ensure regular attendance."
        )
    elif tier == "Watch":
        tier_body = (
            f"We are sharing this gentle update so we can stay ahead of any emerging patterns together. "
            f"Keeping attendance strong now helps {first_name} stay engaged, comfortable, and on track with daily learning."
        )
    else:
        tier_body = (
            f"While {first_name}’s cumulative attendance remains strong overall, "
            f"we wanted to share the specific observation noted above so we can keep communication open and support your family."
        )

    flags_text = ("\n\n" + "\n\n".join(flag_paragraphs)) if flag_paragraphs else ""

    message = (
        f"Dear Family of {first_name},\n\n"
        f"We’re reaching out from school to partner with you regarding {first_name}’s attendance. "
        f"Every day in the classroom brings valuable moments for learning, connection, and growth.\n\n"
        f"So far this term, {first_name} has missed {missed_str}, and their overall attendance rate is currently {overall_pct:.1f}%.{flags_text}\n\n"
        f"{tier_body}\n\n"
        f"{contact_line}\n\n"
        f"Thank you for your ongoing care and partnership in {first_name}’s education.\n\n"
        f"Warmly,\n"
        f"Student Attendance Support Team"
    )

    return message


def analyze_student_records(
    weekly_records: List[Dict[str, Any]],
    first_name: str = "Student",
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Comprehensive analysis combining all pure functions.
    """
    th = thresholds or {}
    crit_th = th.get("critical", CRITICAL_THRESHOLD)
    risk_th = th.get("risk", RISK_THRESHOLD)
    watch_th = th.get("watch", WATCH_THRESHOLD)
    consec_th = th.get("consecutive", CONSECUTIVE_THRESHOLD)
    contact_line = th.get("contact", DEFAULT_CONTACT_LINE)

    sorted_records = sorted(weekly_records, key=lambda r: r.get("week", 0))

    total_present = sum(r.get("days_present", 0) for r in sorted_records)
    total_excused = sum(r.get("excused", 0) for r in sorted_records)
    total_unexcused = sum(r.get("unexcused", 0) for r in sorted_records)
    total_enrolled = total_present + total_excused + total_unexcused
    total_missed = total_excused + total_unexcused

    overall_pct = calculate_overall_attendance_pct(total_present, total_excused, total_unexcused)
    tier_pct = calculate_tier_attendance_pct(total_present, total_excused, total_unexcused)
    tier = determine_tier(tier_pct, crit_th, risk_th, watch_th)

    has_streak, max_streak = check_consecutive_streak(sorted_records, consec_th)
    trend, trend_arrow, trend_delta = calculate_trend(sorted_records)

    flagged = is_student_flagged(tier, has_streak, trend)

    alert_title = "Attendance alert" if tier == "Critical" else "Attendance notice"
    reasons = generate_alert_reasons(
        tier=tier,
        tier_pct=tier_pct,
        has_streak=has_streak,
        max_streak=max_streak,
        trend=trend,
        trend_delta=trend_delta,
        critical_th=crit_th,
        risk_th=risk_th,
        watch_th=watch_th,
        consecutive_th=consec_th,
    )

    guardian_message = generate_guardian_message(
        first_name=first_name,
        total_missed=total_missed,
        unexcused=total_unexcused,
        excused=total_excused,
        overall_pct=overall_pct,
        tier=tier,
        has_streak=has_streak,
        max_streak=max_streak,
        trend=trend,
        contact_line=contact_line,
    )

    # Process weekly breakdown for UI and SVG chart
    weekly_chart_data = []
    for r in sorted_records:
        w = r.get("week", 0)
        p = r.get("days_present", 0)
        e = r.get("excused", 0)
        u = r.get("unexcused", 0)
        tot = p + e + u
        pct = round((p / tot * 100.0), 1) if tot > 0 else 0.0
        weekly_chart_data.append({
            "week": w,
            "days_present": p,
            "excused": e,
            "unexcused": u,
            "total_days": tot,
            "attendance_pct": pct,
            "consecutive_absent": r.get("consecutive_absent", 0),
        })

    return {
        "first_name": first_name,
        "total_present": total_present,
        "total_excused": total_excused,
        "total_unexcused": total_unexcused,
        "total_enrolled": total_enrolled,
        "total_missed": total_missed,
        "overall_pct": overall_pct,
        "tier_pct": tier_pct,
        "tier": tier,
        "has_streak": has_streak,
        "max_streak": max_streak,
        "trend": trend,
        "trend_arrow": trend_arrow,
        "trend_delta": trend_delta,
        "flagged": flagged,
        "alert_title": alert_title,
        "reasons": reasons,
        "guardian_message": guardian_message,
        "weekly_records": weekly_chart_data,
    }
