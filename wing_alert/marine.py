"""Waves, swell and tide per spot from the Open-Meteo Marine API (FR-4.1, FR-4.2)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx

from wing_alert.config import Spot

TIDE_NEAR = timedelta(hours=1, minutes=30)
MIN_SWING = 0.2  # metres


class MarineError(Exception):
    """The marine forecast could not be fetched or read."""


@dataclass(frozen=True)
class SeaHour:
    wave_height: float | None
    wave_period: float | None
    swell_period: float | None
    sea_level: float | None


@dataclass(frozen=True)
class Tide:
    time: datetime
    kind: str  # "high" or "low"


class MarineClient:
    # https://open-meteo.com/en/docs/marine-weather-api
    URL = "https://marine-api.open-meteo.com/v1/marine"
    ATTEMPTS = 2
    FIELDS = ("wave_height", "wave_period", "swell_wave_period", "sea_level_height_msl")

    def __init__(self, http: httpx.Client, days: int = 2) -> None:
        self._http = http
        self._days = days

    def fetch(self, spot: Spot) -> dict[datetime, SeaHour]:
        params = {
            "latitude": spot.lat,
            "longitude": spot.lon,
            "hourly": ",".join(self.FIELDS),
            "timezone": "Europe/Dublin",
            "forecast_days": self._days,
        }
        try:
            return parse_sea(self._get_with_retry(params)["hourly"])
        except (KeyError, TypeError, ValueError) as error:
            raise MarineError(f"{spot.id}: unexpected marine format ({error})") from error

    def _get_with_retry(self, params: dict[str, Any]) -> Any:
        for attempt in range(1, self.ATTEMPTS + 1):
            try:
                response = self._http.get(self.URL, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as error:
                if attempt == self.ATTEMPTS:
                    raise MarineError(f"Open-Meteo Marine failed: {error}") from error
        raise AssertionError("unreachable")


def parse_sea(hourly: dict[str, list[Any]]) -> dict[datetime, SeaHour]:
    columns = [hourly[field] for field in MarineClient.FIELDS]
    return {
        datetime.fromisoformat(time): SeaHour(*values)
        for time, *values in zip(hourly["time"], *columns, strict=True)
    }


def find_tides(sea: dict[datetime, SeaHour]) -> list[Tide]:
    """Highs and lows are the peaks and troughs of the hourly sea level.

    Around Arklow the tide is small and often has a double high water, so wiggles
    smaller than MIN_SWING are dropped, keeping the main high and low of each cycle.
    """
    levels = [(time, hour.sea_level) for time, hour in sorted(sea.items())]
    levels = [(time, level) for time, level in levels if level is not None]
    turns = _turning_points(levels)
    while len(turns) > 1:
        swings = [abs(a[1] - b[1]) for a, b in zip(turns, turns[1:], strict=False)]
        smallest = min(range(len(swings)), key=swings.__getitem__)
        if swings[smallest] >= MIN_SWING:
            break
        del turns[smallest : smallest + 2]
    return [Tide(time, kind) for time, _, kind in turns]


def _turning_points(levels: list[tuple[datetime, float]]) -> list[tuple[datetime, float, str]]:
    turns = []
    levels = _flatten_plateaus(levels)
    for (_, before), (time, level), (_, after) in zip(levels, levels[1:], levels[2:], strict=False):
        if before < level > after:
            turns.append((time, level, "high"))
        elif before > level < after:
            turns.append((time, level, "low"))
    return turns


def _flatten_plateaus(levels: list[tuple[datetime, float]]) -> list[tuple[datetime, float]]:
    """A run of equal hourly levels counts once, at its middle hour. Otherwise a flat
    stretch before a rise looks like a high (and before a fall, like a low)."""
    runs: list[list[tuple[datetime, float]]] = []
    for point in levels:
        if runs and runs[-1][-1][1] == point[1]:
            runs[-1].append(point)
        else:
            runs.append([point])
    return [run[(len(run) - 1) // 2] for run in runs]


def tide_state(time: datetime, tides: list[Tide]) -> str | None:
    """The nearest tide's kind ("high"/"low") within 1.5 h, otherwise None (mid-tide)."""
    near = [tide for tide in tides if abs(tide.time - time) <= TIDE_NEAR]
    return min(near, key=lambda tide: abs(tide.time - time)).kind if near else None
