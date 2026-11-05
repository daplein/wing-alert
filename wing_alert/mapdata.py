"""What the browser needs to draw a day's wind maps (FR-3.1, FR-3.4)."""

from datetime import date, datetime
from typing import Any

from wing_alert.coast import Coast
from wing_alert.message import day_label
from wing_alert.tides import Tide, tide_tag

PANEL_HOURS = (6, 9, 12, 15, 18, 21)
NO_SUN_HOURS = (9, 12, 15, 18)  # a forecast without sunrise and sunset


def map_hours(daylight: dict[str, str] | None) -> tuple[int, ...]:
    """Every third hour between sunrise and sunset (FR-3.1)."""
    if not daylight:
        return NO_SUN_HOURS
    rise, sunset = daylight["sunrise"][11:16], daylight["sunset"][11:16]
    return tuple(h for h in PANEL_HOURS if rise <= f"{h:02d}:00" <= sunset)


def map_data(snapshot: dict[str, Any], day: str) -> dict[str, Any]:
    """Spots with their reading at each map hour; hours no spot has are left out."""
    wanted = map_hours(snapshot.get("daylight", {}).get(day))
    spots = [_spot(spot, day, wanted) for spot in snapshot["spots"]]
    hours = [f"{h:02d}" for h in wanted if any(f"{h:02d}" in s["at"] for s in spots)]
    return {"title": day_label(date.fromisoformat(day)), "hours": hours, "spots": spots}


def coast_data(coast: Coast) -> dict[str, Any]:
    return {"lines": coast.lines, "land": coast.land}


def _spot(spot: dict[str, Any], day: str, wanted: tuple[int, ...]) -> dict[str, Any]:
    tides = [Tide(datetime.fromisoformat(t["time"]), t["kind"]) for t in spot.get("tides", [])]
    at = {}
    for hour in spot["hours"]:
        if hour["time"][:10] == day and int(hour["time"][11:13]) in wanted:
            at[hour["time"][11:13]] = _reading(hour, tides)
    return {"name": spot["name"], "lat": spot["lat"], "lon": spot["lon"], "at": at}


def _reading(hour: dict[str, Any], tides: list[Tide]) -> dict[str, Any]:
    tag = tide_tag(datetime.fromisoformat(hour["time"]), tides)
    return {
        "wind": round(hour["wind"]),
        "gust": round(hour["gust"]),
        "direction": hour["direction"],
        "knots": hour["wind"],
        "tide": tag,
    }
