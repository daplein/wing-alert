"""The All days page as a calendar: one month grid per month with a day page (FR-16)."""

import calendar
from collections import Counter
from datetime import date, timedelta
from typing import Any

MONDAY_FIRST = calendar.Calendar(firstweekday=calendar.MONDAY)


def months(
    summaries: dict[str, dict[str, Any]], weeks: list[dict[str, Any]], today: str
) -> list[dict[str, Any]]:
    """Newest month first; only months that have at least one day page (FR-16.1)."""
    reports = {week["start"]: week for week in weeks}
    shown = sorted({(int(day[:4]), int(day[5:7])) for day in summaries}, reverse=True)
    return [_month(year, month, summaries, reports, today) for year, month in shown]


def _month(year: int, month: int, summaries: dict, reports: dict, today: str) -> dict[str, Any]:
    in_month = [day for day in sorted(summaries) if day[:7] == f"{year:04d}-{month:02d}"]
    return {
        "label": f"{date(year, month, 1):%B %Y}",
        **_rideable(in_month, summaries, today),
        "weeks": [
            _week(dates, month, summaries, reports, today)
            for dates in MONDAY_FIRST.monthdatescalendar(year, month)
        ],
    }


def _rideable(days: list[str], summaries: dict, today: str) -> dict[str, Any]:
    """Days up to today with a window, and the spot best most often (FR-16.4)."""
    ridden = [summaries[day] for day in days if day <= today and summaries[day]["peak"]]
    best = Counter(day["spot_name"] for day in ridden).most_common(1)
    return {"rideable": len(ridden), "mostly": best[0][0] if best else None}


def _week(
    dates: list[date], month: int, summaries: dict, reports: dict, today: str
) -> dict[str, Any]:
    cells = [_cell(d, summaries, today) if d.month == month else None for d in dates]
    sunday = dates[-1]
    if sunday.month != month:  # the summary sits on the row with the week's Sunday
        return {"days": cells, "report": None, "pending": False}
    report = reports.get(dates[0].isoformat())
    pending = report is None and dates[0].isoformat() <= today <= sunday.isoformat()
    return {"days": cells, "report": report, "pending": pending}


def _cell(day: date, summaries: dict, today: str) -> dict[str, Any]:
    iso = day.isoformat()
    tomorrow = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
    return {
        "date": iso,
        "number": day.day,
        "summary": summaries.get(iso),
        "today": iso == today,
        "outlook": iso > tomorrow,
    }
