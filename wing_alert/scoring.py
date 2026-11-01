"""Good hours, windows and ranking (FR-1.3 to FR-1.5)."""

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from wing_alert.config import Settings, Spot
from wing_alert.forecast import Daylight, HourForecast, SpotForecast

HOUR = timedelta(hours=1)
COMPASS = "N NNE NE ENE E ESE SE SSE S SSW SW WSW W WNW NW NNW".split()


@dataclass(frozen=True)
class Window:
    spot: Spot
    hours: list[HourForecast]

    @property
    def start(self) -> datetime:
        return self.hours[0].time

    @property
    def end(self) -> datetime:
        return self.hours[-1].time + HOUR

    @property
    def date(self) -> date:
        return self.start.date()

    @property
    def wind_min(self) -> float:
        return min(hour.wind for hour in self.hours)

    @property
    def wind_max(self) -> float:
        return max(hour.wind for hour in self.hours)

    @property
    def gust_max(self) -> float:
        return max(hour.gust for hour in self.hours)

    @property
    def mean_wind(self) -> float:
        return sum(hour.wind for hour in self.hours) / len(self.hours)

    @property
    def direction(self) -> str:
        return compass_point(mean_direction([hour.direction for hour in self.hours]))


def find_windows(forecast: SpotForecast, settings: Settings, now: datetime) -> list[Window]:
    good = [
        hour
        for hour in forecast.hours
        if hour.time >= now.replace(minute=0, second=0, microsecond=0)
        and is_good_hour(hour, forecast.spot, settings, forecast.daylight.get(hour.time.date()))
    ]
    runs = _consecutive_runs(good)
    return [Window(forecast.spot, run) for run in runs if len(run) >= settings.min_window_hours]


def rank(windows: list[Window], settings: Settings) -> list[Window]:
    return sorted(windows, key=lambda w: (-len(w.hours), abs(w.mean_wind - settings.ideal_wind)))


def is_good_hour(
    hour: HourForecast, spot: Spot, settings: Settings, daylight: Daylight | None
) -> bool:
    return (
        settings.min_wind <= hour.wind <= settings.max_wind
        and hour.gust <= settings.max_gust
        and in_direction_range(hour.direction, spot.direction_from, spot.direction_to)
        and daylight is not None
        and is_daylight(hour, daylight, settings.daylight_margin_minutes)
    )


def is_daylight(hour: HourForecast, daylight: Daylight, margin_minutes: int) -> bool:
    """The whole hour must fit between sunrise + margin and sunset - margin."""
    margin = timedelta(minutes=margin_minutes)
    return daylight.sunrise + margin <= hour.time and hour.time + HOUR <= daylight.sunset - margin


def in_direction_range(direction: float, start: float, end: float) -> bool:
    """True if direction lies clockwise from start to end; ranges may wrap through north."""
    direction, start, end = direction % 360, start % 360, end % 360
    if start <= end:
        return start <= direction <= end
    return direction >= start or direction <= end


def mean_direction(directions: list[float]) -> float:
    """Circular mean, so 350° and 10° average to 0°, not 180°."""
    x = sum(math.sin(math.radians(d)) for d in directions)
    y = sum(math.cos(math.radians(d)) for d in directions)
    return math.degrees(math.atan2(x, y)) % 360


def compass_point(direction: float) -> str:
    return COMPASS[round(direction / 22.5) % 16]


def _consecutive_runs(hours: list[HourForecast]) -> list[list[HourForecast]]:
    runs: list[list[HourForecast]] = []
    for hour in hours:
        if runs and hour.time - runs[-1][-1].time == HOUR:
            runs[-1].append(hour)
        else:
            runs.append([hour])
    return runs
