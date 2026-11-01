"""Hourly wind forecast per spot from Open-Meteo (FR-1.2, FR-1.8)."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx

from wing_alert.config import Spot


class ForecastError(Exception):
    """The forecast could not be fetched or read."""


@dataclass(frozen=True)
class HourForecast:
    time: datetime  # local Europe/Dublin time, naive
    wind: float
    gust: float
    direction: float


@dataclass(frozen=True)
class Daylight:
    sunrise: datetime
    sunset: datetime


@dataclass(frozen=True)
class SpotForecast:
    spot: Spot
    hours: list[HourForecast]
    daylight: dict[date, Daylight]


class OpenMeteoClient:
    # https://open-meteo.com/en/docs
    URL = "https://api.open-meteo.com/v1/forecast"
    ATTEMPTS = 2

    def __init__(self, http: httpx.Client, days: int = 2) -> None:
        self._http = http
        self._days = days

    def fetch(self, spot: Spot) -> SpotForecast:
        data = self._get_with_retry(self._params(spot))
        try:
            return parse_forecast(spot, data)
        except (KeyError, TypeError, ValueError) as error:
            raise ForecastError(f"{spot.id}: unexpected forecast format ({error})") from error

    def _params(self, spot: Spot) -> dict[str, Any]:
        return {
            "latitude": spot.lat,
            "longitude": spot.lon,
            "hourly": "wind_speed_10m,wind_gusts_10m,wind_direction_10m",
            "daily": "sunrise,sunset",
            "wind_speed_unit": "kn",
            "timezone": "Europe/Dublin",
            "forecast_days": self._days,
        }

    def _get_with_retry(self, params: dict[str, Any]) -> Any:
        for attempt in range(1, self.ATTEMPTS + 1):
            try:
                response = self._http.get(self.URL, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as error:
                if attempt == self.ATTEMPTS:
                    raise ForecastError(f"Open-Meteo failed: {error}") from error
        raise AssertionError("unreachable")


def parse_forecast(spot: Spot, data: dict[str, Any]) -> SpotForecast:
    return SpotForecast(
        spot=spot, hours=_parse_hours(data["hourly"]), daylight=_parse_daily(data["daily"])
    )


def _parse_hours(hourly: dict[str, list[Any]]) -> list[HourForecast]:
    rows = zip(
        hourly["time"],
        hourly["wind_speed_10m"],
        hourly["wind_gusts_10m"],
        hourly["wind_direction_10m"],
        strict=True,
    )
    return [
        HourForecast(datetime.fromisoformat(time), wind, gust, direction)
        for time, wind, gust, direction in rows
        if None not in (wind, gust, direction)
    ]


def _parse_daily(daily: dict[str, list[str]]) -> dict[date, Daylight]:
    rows = zip(daily["time"], daily["sunrise"], daily["sunset"], strict=True)
    return {
        date.fromisoformat(day): Daylight(
            datetime.fromisoformat(rise), datetime.fromisoformat(set_)
        )
        for day, rise, set_ in rows
    }
