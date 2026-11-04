"""Wind map PNG for each forecast date (FR-3.1 to FR-3.6)."""

import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # no display on GitHub Actions
import matplotlib.patheffects as patheffects  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.text import Annotation  # noqa: E402
from matplotlib.transforms import Transform, offset_copy  # noqa: E402

from wing_alert.coast import Coast, load_coast  # noqa: E402
from wing_alert.message import day_label  # noqa: E402
from wing_alert.site import forecast_days, wind_band  # noqa: E402
from wing_alert.tides import Tide, tide_tag  # noqa: E402

PANEL_HOURS = (9, 12, 15, 18)
COLOURS = {"light": "#80868b", "good": "#2e9e4f", "strong": "#f08c00", "wild": "#d62828"}
# Grey and orange text need a darker shade than the arrows to read on land (FR-3.2).
TEXT_COLOURS = {**COLOURS, "light": "#5f6368", "strong": "#d97700"}
# In points, so every map draws the same size. The arrow sits out at sea, clear of
# the dot and the label, whichever way the wind blows (FR-3.2).
ARROW_OFFSET, ARROW_HALF, LABEL_GAP = 22, 14, 7
ARROW_SPACING = 30  # closer spots (Buckroney, Ennereilly) get their arrows spread apart
SEA, SHALLOWS, LAND, SHORE = "#7fb8df", "#b9dcf0", "#e3e8cf", "#4f6f80"
INK, FRAME, NOTE = "#1f2933", "#7d95a5", "#4f6f80"
HALO = [patheffects.withStroke(linewidth=3, foreground="white")]
TEXT = {"textcoords": "offset points", "path_effects": HALO}
TAB_PAD, FRAME_WIDTH = 2.5, 1.5


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
WICKLOW = Extent(lon=(-6.37, -5.95), lat=(52.76, 53.01), sea=(1, 0))
DUBLIN_BAY = Extent(lon=(-6.2, -6.06), lat=(53.27, 53.333), sea=(0, 1))
# Top left, over empty land: Dublin Bay is north and a little west of Wicklow (axes fraction).
INSET_BOX = (0.02, 0.74, 0.30, 0.24)


class MapWriter:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._coast = load_coast()

    def write(self, snapshot: dict[str, Any]) -> list[Path]:
        """One map per hour for each date the run covers; a later run overwrites them."""
        paths = []
        for day in forecast_days(snapshot):
            for hour in PANEL_HOURS:
                path = self._root / f"{day['date']:%Y/%m/%Y-%m-%d}-{hour:02d}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                render(snapshot, day["date"], hour, self._coast, path)
                paths.append(path)
        return paths


def render(snapshot: dict[str, Any], day: date, hour: int, coast: Coast, path: Path) -> None:
    figure, ax = plt.subplots(figsize=(5.4, 6.9), dpi=100)
    _draw_panel(ax, snapshot["spots"], day.isoformat(), hour, coast)
    ax.set_title(f"{day_label(day)} · {hour:02d}:00", fontsize=15, fontweight="bold", color=INK)
    footer = {"transform": ax.transAxes, "ha": "center", "va": "top", "color": "#555"}
    ax.text(0.5, -0.012, _footer(), fontsize=7, **footer)  # right under the map
    figure.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.055)
    # The map is wider than tall, so crop the empty bands above and below it (FR-3.1).
    figure.savefig(path, facecolor="white", bbox_inches="tight", pad_inches=0.08)
    plt.close(figure)


def _draw_panel(ax: Axes, spots: list[dict], day: str, hour: int, coast: Coast) -> None:
    _draw_map(ax, WICKLOW, spots, day, hour, coast)
    inset = ax.inset_axes(INSET_BOX)
    _draw_map(inset, DUBLIN_BAY, spots, day, hour, coast)
    _draw_frame(inset, FRAME, FRAME_WIDTH)
    _draw_inset_notes(inset)


def _draw_inset_notes(inset: Axes) -> None:
    """A "Dublin Bay" tab tucked in the top-left corner and the distance under the box."""
    inside = TAB_PAD + FRAME_WIDTH / 2  # the tab's padding grows outward; keep it in the box
    tab = {"facecolor": FRAME, "edgecolor": "none", "pad": TAB_PAD}
    corner = {"xycoords": "axes fraction", "textcoords": "offset points", "ha": "left", "va": "top"}
    bold = {"fontsize": 9.5, "fontweight": "bold", "color": "white"}
    inset.annotate("Dublin Bay", (0, 1), xytext=(inside, -inside), bbox=tab, **bold, **corner)
    inset.annotate("↑ 40 km north", (0, 0), xytext=(0, -4), fontsize=9, color=NOTE, **corner)


def _draw_frame(ax: Axes, colour: str, width: float) -> None:
    for side in ax.spines.values():
        side.set_edgecolor(colour)
        side.set_linewidth(width)


def _draw_map(
    ax: Axes, extent: Extent, spots: list[dict], day: str, hour: int, coast: Coast
) -> None:
    _draw_base(ax, extent, coast)
    shown = [
        (spot, reading)
        for spot in spots
        if extent.contains(spot)
        if (reading := _reading(spot, day, hour))
    ]
    nudges = spread(_along_coast(ax, extent, [spot for spot, _ in shown]), ARROW_SPACING)
    for (spot, reading), nudge in zip(shown, nudges, strict=True):
        _draw_spot(ax, extent, spot, reading, nudge)


def spread(positions: list[float], spacing: float) -> list[float]:
    """Shifts that keep neighbours at least `spacing` apart, each group centred where it was."""
    order = sorted(range(len(positions)), key=positions.__getitem__)
    shifts = [0.0] * len(positions)
    for group in _close_groups(order, positions, spacing):
        middle = sum(positions[i] for i in group) / len(group)
        for rank, index in enumerate(group):
            target = middle + (rank - (len(group) - 1) / 2) * spacing
            shifts[index] = target - positions[index]
    return shifts


def _close_groups(order: list[int], positions: list[float], spacing: float) -> list[list[int]]:
    groups: list[list[int]] = []
    for index in order:
        if groups and positions[index] - positions[groups[-1][-1]] < spacing:
            groups[-1].append(index)
        else:
            groups.append([index])
    return groups


def _along_coast(ax: Axes, extent: Extent, spots: list[dict]) -> list[float]:
    """Each spot's position in points along the coast (across the sea direction)."""
    ax.apply_aspect()
    points = ax.transData.transform([(spot["lon"], spot["lat"]) for spot in spots])
    across = 1 if extent.sea[0] else 0  # an east-facing coast runs north-south
    scale = 72 / ax.figure.dpi
    return [float(point[across]) * scale for point in points]


def _draw_base(ax: Axes, extent: Extent, coast: Coast) -> None:
    ax.set_facecolor(SEA)
    for line in coast.lines:  # under the land (zorder 1), so only the sea side shows
        ax.plot(*zip(*line, strict=True), color=SHALLOWS, linewidth=9, zorder=0.5)
    for shape in coast.land:
        ax.fill(*zip(*shape, strict=True), color=LAND, linewidth=0)
    for line in coast.lines:
        ax.plot(*zip(*line, strict=True), color=SHORE, linewidth=0.8)
    ax.set_xlim(*extent.lon)
    ax.set_ylim(*extent.lat)
    ax.set_aspect(1 / math.cos(math.radians(sum(extent.lat) / 2)))
    ax.set_xticks([])
    ax.set_yticks([])
    _draw_frame(ax, "#8aa3b5", 1)


def _draw_spot(ax: Axes, extent: Extent, spot: dict, reading: dict, nudge: float) -> None:
    dot = (spot["lon"], spot["lat"])
    _draw_arrow(ax, extent, dot, reading, nudge)
    ax.plot(*dot, "o", color="white", markeredgecolor=INK, markeredgewidth=1.5, markersize=6)
    _draw_label(ax, extent, dot, spot, reading)


def _draw_arrow(
    ax: Axes, extent: Extent, dot: tuple[float, float], reading: dict, nudge: float
) -> None:
    blows_to = math.radians((reading["direction"] + 180) % 360)
    along = (math.sin(blows_to) * ARROW_HALF, math.cos(blows_to) * ARROW_HALF)
    east, north = extent.sea
    centre = (east * ARROW_OFFSET + north * nudge, north * ARROW_OFFSET + east * nudge)
    tail = _shifted(ax, centre[0] - along[0], centre[1] - along[1])
    head = _shifted(ax, centre[0] + along[0], centre[1] + along[1])
    colour = COLOURS[wind_band(reading["wind"])]
    arrow = {"arrowstyle": "-|>", "color": colour, "lw": 2.8, "mutation_scale": 16}
    ax.annotate("", xy=dot, xycoords=head, xytext=dot, textcoords=tail, arrowprops=arrow)


def _draw_label(
    ax: Axes, extent: Extent, dot: tuple[float, float], spot: dict, reading: dict
) -> None:
    """Numbers next to the dot on the land side, away from the arrow; the name beyond them."""
    east, north = extent.sea
    offset = (-east * LABEL_GAP, -north * LABEL_GAP)
    align = {"ha": "right" if east else "center", "va": "top" if north else "center"}
    colour = TEXT_COLOURS[wind_band(reading["wind"])]
    numbers = ax.annotate(
        _wind_text(spot, reading),
        dot,
        xytext=offset,
        color=colour,
        fontweight="bold",
        fontsize=12,
        **align,
        **TEXT,
    )
    _draw_name(ax, numbers, spot["name"], beyond_east=bool(east))


def _draw_name(ax: Axes, numbers: Annotation, name: str, beyond_east: bool) -> None:
    """West of the numbers on the main map; under them in the inset, where the sea is north."""
    if beyond_east:
        anchor, offset, align = (0, 0.5), (-4, 0), {"ha": "right", "va": "center"}
    else:
        anchor, offset, align = (0.5, 0), (0, -2), {"ha": "center", "va": "top"}
    ax.annotate(
        name, anchor, xycoords=numbers, xytext=offset, color=INK, fontsize=11.5, **align, **TEXT
    )


def _shifted(ax: Axes, x: float, y: float) -> Transform:
    return offset_copy(ax.transData, fig=ax.figure, x=x, y=y, units="points")


def _wind_text(spot: dict, reading: dict) -> str:
    """ "14/19 · HW": mean/gust, tide at that hour (FR-6.6). The name is drawn beside it."""
    text = f"{round(reading['wind'])}/{round(reading['gust'])}"
    tides = [Tide(datetime.fromisoformat(t["time"]), t["kind"]) for t in spot.get("tides", [])]
    tag = tide_tag(datetime.fromisoformat(reading["time"]), tides)
    return f"{text} · {tag}" if tag else text


def _reading(spot: dict, day: str, hour: int) -> dict | None:
    stamp = f"{day}T{hour:02d}:00"
    return next((h for h in spot["hours"] if h["time"] == stamp), None)


def _footer() -> str:
    return (
        "kn mean/gust · arrow = where the wind blows to · grey <10, green 10–20, "
        "orange 20–30, red 30+\nForecast: Open-Meteo · Coastline © OpenStreetMap contributors"
    )
