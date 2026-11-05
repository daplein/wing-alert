"""What the browser needs to draw a day's wind maps (prototype of FR-3.1 in the browser)."""

from datetime import date, datetime
from typing import Any

from wing_alert.coast import Coast
from wing_alert.message import day_label
from wing_alert.tides import Tide, tide_tag

PANEL_HOURS = (9, 12, 15, 18)


def map_data(snapshot: dict[str, Any], day: str) -> dict[str, Any]:
    """Spots with their reading at each map hour; hours no spot has are left out."""
    spots = [_spot(spot, day) for spot in snapshot["spots"]]
    hours = [f"{h:02d}" for h in PANEL_HOURS if any(f"{h:02d}" in s["at"] for s in spots)]
    return {"title": day_label(date.fromisoformat(day)), "hours": hours, "spots": spots}


def coast_data(coast: Coast) -> dict[str, Any]:
    return {"lines": coast.lines, "land": coast.land}


def _spot(spot: dict[str, Any], day: str) -> dict[str, Any]:
    tides = [Tide(datetime.fromisoformat(t["time"]), t["kind"]) for t in spot.get("tides", [])]
    at = {}
    for hour in spot["hours"]:
        if hour["time"][:10] == day and int(hour["time"][11:13]) in PANEL_HOURS:
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
