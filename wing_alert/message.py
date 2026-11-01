"""Short WhatsApp alert text (FR-1.6)."""

from datetime import date
from itertools import groupby

from wing_alert.scoring import Window
from wing_alert.shorebreak import EMOJI, sheltered_options


def format_alert(ranked: list[Window], link: str | None = None) -> str:
    """Group by day (earliest first), keeping the ranked order inside each day.
    The link to the day page goes last (FR-2.5)."""
    lines = ["🪁 Wing alert"]
    by_day = sorted(ranked, key=lambda window: window.date)
    for day, windows in groupby(by_day, key=lambda window: window.date):
        day_windows = list(windows)
        lines.append(day_label(day))
        lines.extend(window_line(window) for window in day_windows)
        lines.extend(_sheltered_lines(day_windows))
    if link:
        lines.append(link)
    return "\n".join(lines)


def day_label(day: date) -> str:
    return f"{day:%a} {day.day} {day:%b}"


def window_line(window: Window) -> str:
    hours = f"{window.start:%H:%M}–{window.end:%H:%M}"
    wind = _range(round(window.wind_min), round(window.wind_max))
    warning = f" {EMOJI[window.shore_break]}" if window.shore_break else ""
    return (
        f"• {window.spot.name} {hours} · {wind} kn {window.direction}, "
        f"gusts {round(window.gust_max)}{warning}"
    )


def _sheltered_lines(day_windows: list[Window]) -> list[str]:
    return [
        f"Sheltered option: {w.spot.name} {w.start:%H:%M}–{w.end:%H:%M}"
        for options in sheltered_options(day_windows).values()
        for w in options
    ]


def _range(low: int, high: int) -> str:
    return str(low) if low == high else f"{low}–{high}"
