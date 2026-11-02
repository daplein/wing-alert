"""Wind map PNG for each forecast date (FR-3.1 to FR-3.6)."""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # no display on GitHub Actions
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.transforms import Transform, offset_copy  # noqa: E402

from wing_alert.coast import Coast, load_coast  # noqa: E402
from wing_alert.site import forecast_days, wind_band  # noqa: E402

PANEL_HOURS = (9, 12, 15, 18)
COLOURS = {"light": "#9aa0a6", "good": "#2e9e4f", "strong": "#f08c00", "wild": "#d62828"}
# In points, so every map draws the same size. The arrow sits out at sea, clear of
# the dot and the label, whichever way the wind blows (FR-3.2).
ARROW_OFFSET, ARROW_HALF, LABEL_GAP = 22, 14, 7
SEA, LAND, SHORE = "#a9cfe8", "#efe6cf", "#3b4650"
BOX = {"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 1}


@dataclass(frozen=True)
class Extent:
    lon: tuple[float, float]
    lat: tuple[float, float]
    sea: tuple[int, int]  # which way the sea is from the spots: (1, 0) east, (0, 1) north

    def contains(self, spot: dict) -> bool:
        return (
            self.lat[0] <= spot["lat"] <= self.lat[1] and self.lon[0] <= spot["lon"] <= self.lon[1]
        )


# Wicklow Harbour to Arklow; Seapoint is 40 km north, so it gets an inset (FR-3.1).
WICKLOW = Extent(lon=(-6.3, -5.95), lat=(52.76, 53.01), sea=(1, 0))
DUBLIN_BAY = Extent(lon=(-6.2, -6.06), lat=(53.27, 53.333), sea=(0, 1))
INSET_BOX = (0.6, 0.02, 0.38, 0.24)  # bottom right, open sea (axes fraction)


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
    dot = (spot["lon"], spot["lat"])
    _draw_arrow(ax, extent, dot, reading)
    ax.plot(*dot, "o", color="black", markersize=4)
    _draw_label(
        ax, extent, dot, f"{spot['name']} {round(reading['wind'])}/{round(reading['gust'])}"
    )


def _draw_arrow(ax: Axes, extent: Extent, dot: tuple[float, float], reading: dict) -> None:
    blows_to = math.radians((reading["direction"] + 180) % 360)
    along = (math.sin(blows_to) * ARROW_HALF, math.cos(blows_to) * ARROW_HALF)
    centre = (extent.sea[0] * ARROW_OFFSET, extent.sea[1] * ARROW_OFFSET)
    tail = _shifted(ax, centre[0] - along[0], centre[1] - along[1])
    head = _shifted(ax, centre[0] + along[0], centre[1] + along[1])
    colour = COLOURS[wind_band(reading["wind"])]
    arrow = {"arrowstyle": "-|>", "color": colour, "lw": 2.8, "mutation_scale": 16}
    ax.annotate("", xy=dot, xycoords=head, xytext=dot, textcoords=tail, arrowprops=arrow)


def _draw_label(ax: Axes, extent: Extent, dot: tuple[float, float], text: str) -> None:
    """On the land side of the dot, away from the arrow."""
    east, north = extent.sea
    offset = (-east * LABEL_GAP, -north * LABEL_GAP)
    align = {"ha": "right" if east else "center", "va": "top" if north else "center"}
    ax.annotate(text, dot, xytext=offset, textcoords="offset points", fontsize=9, bbox=BOX, **align)


def _shifted(ax: Axes, x: float, y: float) -> Transform:
    return offset_copy(ax.transData, fig=ax.figure, x=x, y=y, units="points")


def _reading(spot: dict, day: str, hour: int) -> dict | None:
    stamp = f"{day}T{hour:02d}:00"
    return next((h for h in spot["hours"] if h["time"] == stamp), None)


def _footer() -> str:
    return (
        "kn mean/gust · arrow = where the wind blows to · grey <10, green 10–20, "
        "orange 20–30, red 30+ · Forecast: Open-Meteo · Coastline © OpenStreetMap contributors"
    )
