"""Shore break warning level per window (FR-4.3, FR-4.4).

A first guess to tune with the crew: wave height sets the base level; long-period
swell and the spot's worse tide each push it up one level.
"""

from dataclasses import dataclass, replace

from wing_alert.config import Settings, Spot
from wing_alert.forecast import SpotForecast
from wing_alert.marine import SeaHour, tide_state
from wing_alert.scoring import Window

NONE, WATCH, DANGER = 0, 1, 2
EMOJI = {NONE: "", WATCH: "⚠️", DANGER: "🚨"}


@dataclass(frozen=True)
class Rating:
    level: int
    reason: str


def rate_window(window: Window, forecast: SpotForecast, settings: Settings) -> Window:
    ratings = [_rate_hour(forecast, hour.time, settings) for hour in window.hours]
    worst = max(ratings, key=lambda rating: rating.level, default=Rating(NONE, ""))
    return replace(window, shore_break=worst.level, shore_break_reason=worst.reason)


def _rate_hour(forecast: SpotForecast, time, settings: Settings) -> Rating:
    sea = forecast.sea.get(time)
    if sea is None or sea.wave_height is None:
        return Rating(NONE, "")
    level = _base_level(sea.wave_height, forecast.spot, settings)
    reasons = [f"{sea.wave_height:.1f} m waves at {sea.wave_period or 0:.0f} s"]
    if sea.wave_height >= _watch(forecast.spot, settings) / 2:
        level, reasons = _bumps(sea, forecast, time, settings, level, reasons)
    return Rating(min(level, DANGER), ", ".join(reasons))


def _bumps(
    sea: SeaHour, forecast: SpotForecast, time, settings: Settings, level: int, reasons: list
) -> tuple[int, list[str]]:
    if (sea.swell_period or 0) >= settings.long_period_s:
        level, reasons = level + 1, [*reasons, f"long swell ({sea.swell_period:.0f} s)"]
    state = tide_state(time, forecast.tides)
    if state and state == forecast.spot.worse_at:
        level, reasons = level + 1, [*reasons, f"{state} tide"]
    return level, reasons


def _base_level(wave_height: float, spot: Spot, settings: Settings) -> int:
    if wave_height >= (spot.danger_wave_m or settings.danger_wave_m):
        return DANGER
    return WATCH if wave_height >= _watch(spot, settings) else NONE


def _watch(spot: Spot, settings: Settings) -> float:
    return spot.watch_wave_m or settings.watch_wave_m


def sheltered_options(windows: list[Window]) -> dict:
    """Per day: sheltered spots' windows, when an exposed spot that day is 🚨 (FR-4.5)."""
    days = {w.date for w in windows if w.shore_break == DANGER and not w.spot.sheltered}
    return {
        day: [w for w in windows if w.date == day and w.spot.sheltered]
        for day in sorted(days)
        if any(w.date == day and w.spot.sheltered for w in windows)
    }
