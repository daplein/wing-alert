"""Waves and swell per spot from the Open-Meteo Marine API (FR-4.1)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from wing_alert.config import Spot


class MarineError(Exception):
    """The marine forecast could not be fetched or read."""


@dataclass(frozen=True)
class SeaHour:
    wave_height: float | None
    wave_period: float | None
    swell_period: float | None


class MarineClient:
    # https://open-meteo.com/en/docs/marine-weather-api
    URL = "https://marine-api.open-meteo.com/v1/marine"
    ATTEMPTS = 2
    FIELDS = ("wave_height", "wave_period", "swell_wave_period")

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
