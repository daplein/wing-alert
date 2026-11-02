"""Inline SVG tide chart for the day page: one line per station (FR-6.4).

Plain SVG text, no plotting library: it scales with the page and its text and grid
follow the page colours (dark mode included).
"""

from typing import Any

WIDTH, HEIGHT = 420, 170  # small canvas, so the text stays readable on a phone
LEFT, RIGHT, TOP, BOTTOM = 40, 22, 30, 22
COLOURS = ("#0E7C86", "#5B3FD9", "#EB1F1F")  # teal, violet, red, south to north
HOUR_TICKS = (0, 6, 12, 18, 24)


def tide_chart(stations: dict[str, dict[str, Any]], day: str, rideable: set[int]) -> str:
    """Empty string when no station has levels for that day."""
    series = {s["name"]: _day_levels(s["levels"], day) for s in stations.values()}
    series = {name: points for name, points in series.items() if len(points) > 1}
    if not series:
        return ""
    low, high = _range([level for points in series.values() for _, level in points])
    parts = [_shading(rideable), _grid(low, high)]
    for index, (name, points) in enumerate(series.items()):
        colour = COLOURS[index % len(COLOURS)]
        parts += [_line(points, low, high, colour), _legend(index, name, colour)]
    return (
        f'<svg class="tidechart" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
        f'aria-label="Tide height through the day">{"".join(parts)}</svg>'
    )


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


def _x(hours: float) -> float:
    return LEFT + hours / 24 * (WIDTH - LEFT - RIGHT)


def _y(level: float, low: float, high: float) -> float:
    return TOP + (high - level) / (high - low) * (HEIGHT - TOP - BOTTOM)


def _shading(rideable: set[int]) -> str:
    width = _x(1) - _x(0)
    return "".join(
        f'<rect class="ride" x="{_x(hour):.1f}" y="{TOP}" width="{width:.1f}" '
        f'height="{HEIGHT - TOP - BOTTOM}"/>'
        for hour in sorted(rideable)
    )


def _grid(low: float, high: float) -> str:
    bottom = HEIGHT - BOTTOM
    lines = [
        f'<line class="grid" x1="{_x(h):.1f}" y1="{TOP}" x2="{_x(h):.1f}" y2="{bottom}"/>'
        f'<text x="{_x(h):.1f}" y="{HEIGHT - 6}" text-anchor="middle">{h:02d}:00</text>'
        for h in HOUR_TICKS
    ]
    for level in (low, high):
        label = f"{level:.1f} m"
        lines.append(
            f'<text x="{LEFT - 4}" y="{_y(level, low, high) + 4:.1f}" '
            f'text-anchor="end">{label}</text>'
        )
    return "".join(lines)


def _line(points: list[tuple[float, float]], low: float, high: float, colour: str) -> str:
    coords = " ".join(f"{_x(h):.1f},{_y(level, low, high):.1f}" for h, level in points)
    return f'<polyline points="{coords}" fill="none" stroke="{colour}" stroke-width="2.5"/>'


def _legend(index: int, name: str, colour: str) -> str:
    x = LEFT + index * 120
    return (
        f'<rect x="{x}" y="8" width="18" height="4" rx="2" fill="{colour}"/>'
        f'<text x="{x + 24}" y="15">{name}</text>'
    )
