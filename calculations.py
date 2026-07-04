"""Working-hours calculations: session duration, and day/week/month rollups.

Target hours per day come from the calendar (see calendar_model.py), not
from a hardcoded weekday check, so holidays are handled correctly.
"""

from datetime import datetime
from collections import defaultdict

from models import WorkEntry

Calendar = dict[str, dict]


def session_hours(start: str, end: str) -> float:
    """Compute the duration of a session in hours.

    Args:
        start: Start time, format HH:MM.
        end: End time, format HH:MM.

    Returns:
        Duration in decimal hours. 0.0 if end is not after start.
    """
    fmt = "%H:%M"
    delta = (datetime.strptime(end, fmt) - datetime.strptime(start, fmt)).total_seconds() / 3600
    return max(delta, 0.0)


def day_target(date: str, calendar: Calendar) -> float:
    """Return the target hours for a date, using the calendar if available.

    Falls back to a plain Mon-Fri check if the date is missing from the
    calendar (should not normally happen once ensure_years has run).
    """
    record = calendar.get(date)
    if record is not None:
        return record["target_hours"]
    return 0.0 if datetime.strptime(date, "%Y-%m-%d").weekday() >= 5 else 3.4


def week_key(date: str) -> str:
    """Return the ISO year-week key for a date, e.g. '2026-W27'."""
    iso = datetime.strptime(date, "%Y-%m-%d").isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def month_key(date: str) -> str:
    """Return the year-month key for a date, e.g. '2026-07'."""
    return date[:7]


def group_by_date(entries: list[WorkEntry]) -> dict[str, list[WorkEntry]]:
    """Group entries by date, preserving insertion order per date."""
    grouped = defaultdict(list)
    for e in entries:
        grouped[e.date].append(e)
    return dict(grouped)


def daily_total(sessions: list[WorkEntry]) -> float:
    """Sum worked hours for a list of sessions on the same day."""
    return sum(session_hours(s.start, s.end) for s in sessions)


def build_day_records(entries: list[WorkEntry], calendar: Calendar) -> list[dict]:
    """Build one record per day (with sessions) worked hours, target, balance.

    Only days with at least one logged session are included.

    Returns:
        List of dicts sorted by date, each with keys:
        date, weekday, sessions, worked, target, balance.
    """
    grouped = group_by_date(entries)
    records = []
    for day in sorted(grouped.keys()):
        sessions = grouped[day]
        worked = daily_total(sessions)
        target = day_target(day, calendar)
        weekday = calendar.get(day, {}).get("weekday", "")
        records.append({
            "date": day,
            "weekday": weekday,
            "sessions": sessions,
            "worked": worked,
            "target": target,
            "balance": worked - target,
        })
    return records


def cumulative_balance(day_records: list[dict]) -> list[dict]:
    """Attach a running cumulative balance to each day record (banco de horas).

    Args:
        day_records: Output of build_day_records, in chronological order.

    Returns:
        Same list, with a 'cumulative' key added to each record.
    """
    running = 0.0
    for record in day_records:
        running += record["balance"]
        record["cumulative"] = running
    return day_records


def group_days_by_week(day_records: list[dict]) -> dict[str, list[dict]]:
    """Group day records by ISO week key."""
    grouped = defaultdict(list)
    for record in day_records:
        grouped[week_key(record["date"])].append(record)
    return dict(grouped)


def group_days_by_month(day_records: list[dict]) -> dict[str, list[dict]]:
    """Group day records by year-month key."""
    grouped = defaultdict(list)
    for record in day_records:
        grouped[month_key(record["date"])].append(record)
    return dict(grouped)


def period_totals(day_records: list[dict]) -> dict:
    """Sum worked, target, and balance across a list of day records."""
    return {
        "worked": sum(r["worked"] for r in day_records),
        "target": sum(r["target"] for r in day_records),
        "balance": sum(r["balance"] for r in day_records),
    }

def build_day_records(entries: list[WorkEntry], calendar: Calendar, months: set[str]) -> list[dict]:
    """Build one record per calendar day within the given months.

    Every day in `months` is included, even with zero sessions, so the
    tree shows the full month (past, today, and future days).

    Args:
        entries: All logged sessions.
        calendar: Calendar dict from CalendarModel.
        months: Year-month keys (e.g. '2026-07') to include.

    Returns:
        List of dicts sorted by date, each with keys:
        date, weekday, sessions, worked, target, balance.
    """
    grouped = group_by_date(entries)
    days = sorted(d for d in calendar if month_key(d) in months)

    records = []
    for day in days:
        sessions = grouped.get(day, [])
        worked = daily_total(sessions)
        target = day_target(day, calendar)
        weekday = calendar.get(day, {}).get("weekday", "")
        records.append({
            "date": day,
            "weekday": weekday,
            "sessions": sessions,
            "worked": worked,
            "target": target,
            "balance": worked - target,
        })
    return records