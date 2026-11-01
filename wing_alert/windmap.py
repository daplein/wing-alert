"""Wind map PNG for each forecast date (FR-3.1 to FR-3.4)."""

import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # no display on GitHub Actions
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402

from wing_alert.site import forecast_days, wind_band  # noqa: E402

PANEL_HOURS = (9, 12, 15, 18)
COLOURS = {"light": "#9aa0a6", "good": "#2e9e4f", "strong": "#f08c00", "wild": "#d62828"}
LON = (-6.32, -5.93)
LAT = (52.74, 53.33)
ARROW_DEGREES = 0.045
COASTLINE = Path(__file__).parent / "assets" / "coastline.json"


class MapWriter:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._coast = json.loads(COASTLINE.read_text())["lines"]

    def write(self, snapshot: dict[str, Any]) -> list[Path]:
        """One map per date the run covers; a later run overwrites it."""
        paths = []
        for day in forecast_days(snapshot):
            path = self._root / f"{day['date']:%Y/%m/%Y-%m-%d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            render(snapshot, day["date"].isoformat(), self._coast, path)
            paths.append(path)
        return paths


def render(snapshot: dict[str, Any], day: str, coast: list, path: Path) -> None:
    figure, axes = plt.subplots(1, len(PANEL_HOURS), figsize=(11, 7.2), dpi=80)
    for index, (ax, hour) in enumerate(zip(axes, PANEL_HOURS, strict=True)):
        _draw_panel(ax, snapshot["spots"], day, hour, coast, names=index == 0)
    figure.suptitle(f"Wind forecast {day}", fontsize=15, fontweight="bold")
    figure.text(0.5, 0.01, _footer(), ha="center", fontsize=8, color="#555")
    figure.subplots_adjust(left=0.01, right=0.99, top=0.9, bottom=0.05, wspace=0.04)
    figure.savefig(path, facecolor="white")
    plt.close(figure)


def _draw_panel(ax: Axes, spots: list[dict], day: str, hour: int, coast: list, names: bool) -> None:
    _draw_base(ax, coast)
    ax.set_title(f"{hour:02d}:00", fontsize=13, fontweight="bold")
    for spot in spots:
        reading = _reading(spot, day, hour)
        if reading:
            _draw_spot(ax, spot, reading, names)


def _draw_base(ax: Axes, coast: list) -> None:
    ax.set_facecolor("#dcecf5")
    for line in coast:
        lons, lats = zip(*line, strict=True)
        ax.plot(lons, lats, color="#4a5560", linewidth=0.8)
    ax.set_xlim(*LON)
    ax.set_ylim(*LAT)
    ax.set_aspect(1 / math.cos(math.radians(sum(LAT) / 2)))
    ax.set_xticks([])
    ax.set_yticks([])


def _draw_spot(ax: Axes, spot: dict, reading: dict, names: bool) -> None:
    lon, lat = spot["lon"], spot["lat"]
    colour = COLOURS[wind_band(reading["wind"])]
    blows_to = math.radians((reading["direction"] + 180) % 360)
    dx = ARROW_DEGREES * math.sin(blows_to) / math.cos(math.radians(lat))
    dy = ARROW_DEGREES * math.cos(blows_to)
    arrow = {"arrowstyle": "-|>", "color": colour, "lw": 2.8, "mutation_scale": 16}
    ax.annotate("", xy=(lon + dx, lat + dy), xytext=(lon, lat), arrowprops=arrow)
    ax.plot(lon, lat, "o", color="black", markersize=4)
    label = f"{round(reading['wind'])}/{round(reading['gust'])}"
    ax.text(lon + 0.03, lat - 0.012, label, fontsize=9, fontweight="bold", color=colour)
    if names:
        ax.text(lon - 0.025, lat, spot["name"], fontsize=7, ha="right", va="center")


def _reading(spot: dict, day: str, hour: int) -> dict | None:
    stamp = f"{day}T{hour:02d}:00"
    return next((h for h in spot["hours"] if h["time"] == stamp), None)


def _footer() -> str:
    return (
        "kn mean/gust · arrow = where the wind blows to · grey <10, green 10–20, "
        "orange 20–30, red 30+ · Forecast: Open-Meteo · Coastline © OpenStreetMap contributors"
    )
