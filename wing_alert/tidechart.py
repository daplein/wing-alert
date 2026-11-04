"""Inline SVG tide chart for the day page: one line per station (FR-6.4).

It spans exactly the table's hours and sits in the table's own row, so each hour of
tide lines up with that hour's wind. The SVG stretches to the column width, so it holds
no text (text would stretch too); the page writes the labels and legend around it.
"""

import json
from dataclasses import dataclass
from html import escape
from typing import Any

HOUR_WIDTH, HEIGHT, PAD = 40, 90, 6
COLOURS = ("#0E7C86", "#5B3FD9", "#EB1F1F")  # teal, violet, red, south to north


@dataclass(frozen=True)
class TideChart:
    svg: str
    low: float
    high: float
    legend: list[tuple[str, str]]  # (station name, colour)


def tide_chart(
    stations: dict[str, dict[str, Any]], day: str, rideable: set[int], hours: list[int]
) -> TideChart | None:
    """None when no station has levels for that day."""
    series = {s["name"]: _day_levels(s["levels"], day) for s in stations.values()}
    series = {name: points for name, points in series.items() if len(points) > 1}
    if not series or not hours:
        return None
    low, high = _range([level for points in series.values() for _, level in points])
    scale = _Scale(hours[0], low, high)
    coloured = [
        (name, COLOURS[i % len(COLOURS)], points) for i, (name, points) in enumerate(series.items())
    ]
    parts = [_shading(rideable, hours, scale)]
    parts += [_line(points, scale, colour) for _, colour, points in coloured]
    parts.append(f'<line class="cursor" x1="0" y1="0" x2="0" y2="{HEIGHT}"/>')
    svg = (
        f'<svg class="tidechart" viewBox="0 0 {len(hours) * HOUR_WIDTH} {HEIGHT}" '
        f'preserveAspectRatio="none" role="img" aria-label="Tide height through the day" '
        f"{_readout_data(coloured, hours)}>{''.join(parts)}</svg>"
    )
    return TideChart(svg, low, high, [(name, colour) for name, colour, _ in coloured])


def _readout_data(coloured: list[tuple[str, str, list]], hours: list[int]) -> str:
    """The levels over the table's hours, for the hover and touch readout on the page."""
    first, last = hours[0], hours[-1] + 1
    series = [
        {
            "name": name,
            "colour": colour,
            "points": [[h, round(v, 2)] for h, v in points if first - 1 <= h <= last + 1],
        }
        for name, colour, points in coloured
    ]
    return (
        f'data-first="{first}" data-count="{len(hours)}" data-series="{escape(json.dumps(series))}"'
    )


@dataclass(frozen=True)
class _Scale:
    first_hour: int
    low: float
    high: float

    def x(self, hours: float) -> float:
        return (hours - self.first_hour) * HOUR_WIDTH

    def y(self, level: float) -> float:
        return PAD + (self.high - level) / (self.high - self.low) * (HEIGHT - 2 * PAD)


def _day_levels(levels: list[list], day: str) -> list[tuple[float, float]]:
    """(hours since midnight, metres) for the day, plus the next midnight to close it."""
    points = []
    for stamp, level in levels:
        hours = int(stamp[11:13]) + int(stamp[14:16]) / 60
        if stamp[:10] == day:
            points.append((hours, level))
        elif stamp[:10] > day and hours == 0:
            points.append((24.0, level))
    return points


def _range(levels: list[float]) -> tuple[float, float]:
    low, high = min(levels), max(levels)
    pad = max(0.1, (high - low) * 0.08)
    return low - pad, high + pad


def _shading(rideable: set[int], hours: list[int], scale: _Scale) -> str:
    return "".join(
        f'<rect class="ride" x="{scale.x(hour):.1f}" y="0" width="{HOUR_WIDTH}" height="{HEIGHT}"/>'
        for hour in sorted(rideable & set(hours))
    )


def _line(points: list[tuple[float, float]], scale: _Scale, colour: str) -> str:
    coords = " ".join(f"{scale.x(h):.1f},{scale.y(level):.1f}" for h, level in points)
    return (
        f'<polyline points="{coords}" fill="none" stroke="{colour}" stroke-width="2.5" '
        f'vector-effect="non-scaling-stroke"/>'
    )
