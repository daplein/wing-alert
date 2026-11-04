"""Live readings arranged for the day page: by station and local hour (FR-11.1, FR-11.2)."""

import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DUBLIN = ZoneInfo("Europe/Dublin")
EARTH_KM = 6371.0
EIGHT_POINTS = "N NE E SE S SW W NW".split()

Reading = dict[str, Any]


def load_observations(root: Path) -> dict[str, dict[str, Any]]:
    """The kept readings by UTC day (FR-10.6)."""
    return {path.stem: json.loads(path.read_text()) for path in sorted(root.glob("*.json"))}


def readings_by_hour(observations: dict[str, dict], day: str) -> dict[str, dict[int, Reading]]:
    """Each station's last reading in each Dublin hour of the day. A Dublin day spans
    two UTC days in summer, so both files are read."""
    previous = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    by_station: dict[str, dict[int, Reading]] = {}
    for utc_day in (previous, day):
        for station, readings in observations.get(utc_day, {}).get("stations", {}).items():
            for reading in readings:
                local = local_time(reading["time"])
                if local.date().isoformat() == day:
                    by_station.setdefault(station, {})[local.hour] = reading
    return by_station


def local_time(utc: str) -> datetime:
    return datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(DUBLIN)


def stations_about(observations: dict[str, dict]) -> dict[str, dict[str, Any]]:
    """Names and positions in the newest record's order; older records only add stations
    that have since been dropped."""
    newest_first = reversed(list(observations.values()))
    about: dict[str, dict[str, Any]] = {}
    for record in newest_first:
        for station in record["about"]:
            about.setdefault(station["id"], station)
    return about


def where(station: dict[str, Any], spots: list[dict[str, Any]]) -> str:
    """How far and which way the station is from the nearest spot: `5 km NE of Seapoint`."""
    if not spots:
        return ""
    nearest = min(spots, key=lambda spot: distance_km(spot, station))
    km = round(distance_km(nearest, station))
    return f"{km} km {eight_point(bearing(nearest, station))} of {nearest['name']}"


def distance_km(a: dict[str, float], b: dict[str, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_KM * math.asin(math.sqrt(h))


def bearing(a: dict[str, float], b: dict[str, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return math.degrees(math.atan2(y, x)) % 360


def eight_point(degrees: float) -> str:
    """Eight points read better for a place than sixteen."""
    return EIGHT_POINTS[round(degrees / 45) % 8]
