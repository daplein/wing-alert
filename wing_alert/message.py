"""Short WhatsApp alert text (FR-1.6)."""

from datetime import date
from itertools import groupby

from wing_alert.scoring import Window


def format_alert(ranked: list[Window], link: str | None = None) -> str:
    """Group by day (earliest first), keeping the ranked order inside each day.
    The link to the day page goes last (FR-2.5)."""
    lines = ["🪁 Wing alert"]
    by_day = sorted(ranked, key=lambda window: window.date)
    for day, windows in groupby(by_day, key=lambda window: window.date):
        lines.append(day_label(day))
        lines.extend(window_line(window) for window in windows)
    if link:
        lines.append(link)
    return "\n".join(lines)


def day_label(day: date) -> str:
    return f"{day:%a} {day.day} {day:%b}"


def window_line(window: Window) -> str:
    hours = f"{window.start:%H:%M}–{window.end:%H:%M}"
    wind = _range(round(window.wind_min), round(window.wind_max))
    return (
        f"• {window.spot.name} {hours} · {wind} kn {window.direction}, "
        f"gusts {round(window.gust_max)}"
    )


def _range(low: int, high: int) -> str:
    return str(low) if low == high else f"{low}–{high}"
