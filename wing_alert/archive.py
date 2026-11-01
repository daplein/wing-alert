"""Save every run's forecast, scores and windows as plain JSON (FR-2.1)."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from wing_alert.config import Settings
from wing_alert.forecast import SpotForecast
from wing_alert.scoring import Window, find_windows, is_good_hour, rank


class Archive:
    def __init__(self, root: Path, settings: Settings) -> None:
        self._root = root
        self._settings = settings

    def write(self, issued: datetime, forecasts: list[SpotForecast]) -> Path:
        path = self._root / f"{issued:%Y/%m/%Y-%m-%dT%H}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = build_snapshot(issued, forecasts, self._settings)
        path.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n")
        return path


def build_snapshot(
    issued: datetime, forecasts: list[SpotForecast], settings: Settings
) -> dict[str, Any]:
    """Windows here cover whole days (past hours included), unlike the alert."""
    start_of_day = issued.replace(hour=0, minute=0, second=0, microsecond=0)
    windows = [w for f in forecasts for w in find_windows(f, settings, start_of_day)]
    return {
        "issued": issued.isoformat(timespec="minutes"),
        "settings": vars(settings),
        "daylight": _daylight(forecasts),
        "windows": [_window(window) for window in rank(windows, settings)],
        "spots": [_spot(forecast, settings) for forecast in forecasts],
    }


def load_snapshots(root: Path) -> list[dict[str, Any]]:
    return [json.loads(path.read_text()) for path in sorted(root.glob("*/*/*.json"))]


def _daylight(forecasts: list[SpotForecast]) -> dict[str, dict[str, str]]:
    if not forecasts:
        return {}
    return {
        day.isoformat(): {
            "sunrise": light.sunrise.isoformat(timespec="minutes"),
            "sunset": light.sunset.isoformat(timespec="minutes"),
        }
        for day, light in forecasts[0].daylight.items()
    }


def _spot(forecast: SpotForecast, settings: Settings) -> dict[str, Any]:
    spot = forecast.spot
    return {
        "id": spot.id,
        "name": spot.name,
        "directions": [spot.direction_from, spot.direction_to],
        "sheltered": spot.sheltered,
        "hours": [
            {
                "time": hour.time.isoformat(timespec="minutes"),
                "wind": hour.wind,
                "gust": hour.gust,
                "direction": hour.direction,
                "good": is_good_hour(hour, spot, settings, forecast.daylight.get(hour.time.date())),
            }
            for hour in forecast.hours
        ],
    }


def _window(window: Window) -> dict[str, Any]:
    return {
        "spot": window.spot.id,
        "spot_name": window.spot.name,
        "date": window.date.isoformat(),
        "start": window.start.isoformat(timespec="minutes"),
        "end": window.end.isoformat(timespec="minutes"),
        "wind_min": round(window.wind_min),
        "wind_max": round(window.wind_max),
        "gust_max": round(window.gust_max),
        "direction": window.direction,
    }
