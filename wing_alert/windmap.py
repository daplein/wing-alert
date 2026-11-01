"""Wind map PNG for each forecast date (FR-3.1 to FR-3.6)."""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # no display on GitHub Actions
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402

from wing_alert.coast import Coast, load_coast  # noqa: E402
from wing_alert.site import forecast_days, wind_band  # noqa: E402

PANEL_HOURS = (9, 12, 15, 18)
COLOURS = {"light": "#9aa0a6", "good": "#2e9e4f", "strong": "#f08c00", "wild": "#d62828"}
LABEL_GAP = 0.03  # label distance from the dot as a share of the map's width
SEA, LAND, SHORE = "#a9cfe8", "#efe6cf", "#3b4650"
BOX = {"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 1}


@dataclass(frozen=True)
class Extent:
    lon: tuple[float, float]
    lat: tuple[float, float]
    arrow_share: float  # arrow length as a share of the map's height

    def contains(self, spot: dict) -> bool:
        return (
            self.lat[0] <= spot["lat"] <= self.lat[1] and self.lon[0] <= spot["lon"] <= self.lon[1]
        )


# Wicklow Harbour to Arklow; Seapoint is 40 km north, so it gets an inset (FR-3.1).
WICKLOW = Extent(lon=(-6.24, -5.93), lat=(52.76, 53.01), arrow_share=0.07)
DUBLIN_BAY = Extent(lon=(-6.2, -6.06), lat=(53.27, 53.333), arrow_share=0.3)
INSET_BOX = (0.5, 0.02, 0.48, 0.26)  # bottom right, open sea (axes fraction)


class MapWriter:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._coast = load_coast()

    def write(self, snapshot: dict[str, Any]) -> list[Path]:
        """One map per date the run covers; a later run overwrites it."""
        paths = []
        for day in forecast_days(snapshot):
            path = self._root / f"{day['date']:%Y/%m/%Y-%m-%d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            render(snapshot, day["date"].isoformat(), self._coast, path)
            paths.append(path)
        return paths


def render(snapshot: dict[str, Any], day: str, coast: Coast, path: Path) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(10, 12.4), dpi=80)
    for ax, hour in zip(axes.flat, PANEL_HOURS, strict=True):
        _draw_panel(ax, snapshot["spots"], day, hour, coast)
    figure.suptitle(f"Wind forecast {day}", fontsize=16, fontweight="bold")
    figure.text(0.5, 0.012, _footer(), ha="center", fontsize=8, color="#555", wrap=True)
    figure.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.04, wspace=0.03, hspace=0.06)
    figure.savefig(path, facecolor="white")
    plt.close(figure)


def _draw_panel(ax: Axes, spots: list[dict], day: str, hour: int, coast: Coast) -> None:
    ax.set_title(f"{hour:02d}:00", fontsize=14, fontweight="bold")
    _draw_map(ax, WICKLOW, spots, day, hour, coast)
    inset = ax.inset_axes(INSET_BOX)
    _draw_map(inset, DUBLIN_BAY, spots, day, hour, coast)
    inset.set_title("Dublin Bay", fontsize=9, pad=2)
    for side in inset.spines.values():
        side.set_linewidth(1.5)


def _draw_map(
    ax: Axes, extent: Extent, spots: list[dict], day: str, hour: int, coast: Coast
) -> None:
    _draw_base(ax, extent, coast)
    for spot in filter(extent.contains, spots):
        reading = _reading(spot, day, hour)
        if reading:
            _draw_spot(ax, extent, spot, reading)


def _draw_base(ax: Axes, extent: Extent, coast: Coast) -> None:
    ax.set_facecolor(SEA)
    for shape in coast.land:
        ax.fill(*zip(*shape, strict=True), color=LAND, linewidth=0)
    for line in coast.lines:
        ax.plot(*zip(*line, strict=True), color=SHORE, linewidth=0.9)
    ax.set_xlim(*extent.lon)
    ax.set_ylim(*extent.lat)
    ax.set_aspect(1 / math.cos(math.radians(sum(extent.lat) / 2)))
    ax.set_xticks([])
    ax.set_yticks([])


def _draw_spot(ax: Axes, extent: Extent, spot: dict, reading: dict) -> None:
    lon, lat = spot["lon"], spot["lat"]
    colour = COLOURS[wind_band(reading["wind"])]
    blows_to = math.radians((reading["direction"] + 180) % 360)
    length = extent.arrow_share * (extent.lat[1] - extent.lat[0])
    dx = length * math.sin(blows_to) / math.cos(math.radians(lat))
    dy = length * math.cos(blows_to)
    arrow = {"arrowstyle": "-|>", "color": colour, "lw": 2.8, "mutation_scale": 16}
    ax.annotate("", xy=(lon + dx, lat + dy), xytext=(lon, lat), arrowprops=arrow)
    ax.plot(lon, lat, "o", color="black", markersize=4)
    label = f"{round(reading['wind'])}/{round(reading['gust'])}"
    gap = LABEL_GAP * (extent.lon[1] - extent.lon[0])
    ax.text(
        lon + gap, lat, label, fontsize=11, fontweight="bold", color=colour, va="center", bbox=BOX
    )
    ax.text(lon - gap, lat, spot["name"], fontsize=9, ha="right", va="center", bbox=BOX)


def _reading(spot: dict, day: str, hour: int) -> dict | None:
    stamp = f"{day}T{hour:02d}:00"
    return next((h for h in spot["hours"] if h["time"] == stamp), None)


def _footer() -> str:
    return (
        "kn mean/gust · arrow = where the wind blows to · grey <10, green 10–20, "
        "orange 20–30, red 30+ · Forecast: Open-Meteo · Coastline © OpenStreetMap contributors"
    )
