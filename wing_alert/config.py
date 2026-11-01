"""Load and validate spots and thresholds from YAML (FR-1.1)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """The config files are missing or invalid."""


@dataclass(frozen=True)
class Spot:
    id: str
    name: str
    lat: float
    lon: float
    direction_from: float
    direction_to: float
    sheltered: bool = False
    worse_at: str = "none"  # tide state when the shore break is worse (FR-4.3)
    watch_wave_m: float | None = None
    danger_wave_m: float | None = None
    wind_at: tuple[float, float] | None = None  # a sea point off the beach (FR-1.11)

    @property
    def wind_point(self) -> tuple[float, float]:
        return self.wind_at or (self.lat, self.lon)


@dataclass(frozen=True)
class Settings:
    min_wind: float = 10
    max_wind: float = 40
    max_gust: float = 45
    ideal_wind: float = 20
    min_window_hours: int = 2
    daylight_margin_minutes: int = 30
    watch_wave_m: float = 0.8
    danger_wave_m: float = 1.5
    long_period_s: float = 10


def load_spots(path: Path) -> list[Spot]:
    raw = _read_yaml(path)
    if not isinstance(raw, list) or not raw:
        raise ConfigError(f"{path}: expected a non-empty list of spots")
    spots = [_parse_spot(item, path) for item in raw]
    _check_unique_ids(spots, path)
    return spots


def load_settings(path: Path) -> Settings:
    raw = _read_yaml(path)
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a mapping of settings")
    unknown = set(raw) - set(Settings.__dataclass_fields__)
    if unknown:
        raise ConfigError(f"{path}: unknown settings {sorted(unknown)}")
    settings = Settings(**{key: _number(value, key, path) for key, value in raw.items()})
    _check_settings(settings, path)
    return settings


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as error:
        raise ConfigError(f"{path}: {error}") from error


def _parse_spot(item: Any, path: Path) -> Spot:
    if not isinstance(item, dict):
        raise ConfigError(f"{path}: each spot must be a mapping")
    spot_id = item.get("id", "?")
    try:
        direction_from, direction_to = item["directions"]
        spot = Spot(
            id=str(item["id"]),
            name=str(item["name"]),
            lat=_number(item["lat"], "lat", path),
            lon=_number(item["lon"], "lon", path),
            direction_from=_number(direction_from, "directions", path),
            direction_to=_number(direction_to, "directions", path),
            sheltered=bool(item.get("sheltered", False)),
            worse_at=str(item.get("worse_at", "none")),
            watch_wave_m=_optional_number(item.get("watch_wave_m"), "watch_wave_m", path),
            danger_wave_m=_optional_number(item.get("danger_wave_m"), "danger_wave_m", path),
            wind_at=_optional_point(item.get("wind_at"), path),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ConfigError(f"{path}: spot {spot_id!r} is invalid ({error})") from error
    _check_spot(spot, path)
    return spot


def _number(value: Any, name: str, path: Path) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(f"{path}: {name} must be a number, got {value!r}")
    return value


def _optional_number(value: Any, name: str, path: Path) -> float | None:
    return None if value is None else _number(value, name, path)


def _optional_point(value: Any, path: Path) -> tuple[float, float] | None:
    if value is None:
        return None
    lat, lon = value
    return _number(lat, "wind_at", path), _number(lon, "wind_at", path)


def _check_spot(spot: Spot, path: Path) -> None:
    if spot.worse_at not in ("high", "low", "none"):
        raise ConfigError(f"{path}: spot {spot.id!r} worse_at must be high, low or none")
    if not all(-90 <= lat <= 90 and -180 <= lon <= 180 for lat, lon in _points(spot)):
        raise ConfigError(f"{path}: spot {spot.id!r} has an invalid position")
    for direction in (spot.direction_from, spot.direction_to):
        if not 0 <= direction <= 360:
            raise ConfigError(f"{path}: spot {spot.id!r} directions must be 0–360")


def _points(spot: Spot) -> list[tuple[float, float]]:
    return [(spot.lat, spot.lon), spot.wind_point]


def _check_unique_ids(spots: list[Spot], path: Path) -> None:
    ids = [spot.id for spot in spots]
    duplicates = sorted({spot_id for spot_id in ids if ids.count(spot_id) > 1})
    if duplicates:
        raise ConfigError(f"{path}: duplicate spot ids {duplicates}")


def _check_settings(settings: Settings, path: Path) -> None:
    if not 0 <= settings.min_wind < settings.max_wind:
        raise ConfigError(f"{path}: need 0 <= min_wind < max_wind")
    if settings.max_gust < settings.min_wind:
        raise ConfigError(f"{path}: max_gust must be at least min_wind")
    if not 0 < settings.watch_wave_m <= settings.danger_wave_m:
        raise ConfigError(f"{path}: need 0 < watch_wave_m <= danger_wave_m")
    if settings.min_window_hours < 1 or settings.daylight_margin_minutes < 0:
        raise ConfigError(f"{path}: min_window_hours >= 1 and daylight_margin_minutes >= 0")
