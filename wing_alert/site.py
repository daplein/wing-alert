"""Build the static GitHub Pages site from the data/ archive (FR-2.2 to FR-2.7)."""

import argparse
import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import jinja2

from wing_alert.archive import load_snapshots
from wing_alert.config import Spot, load_spots
from wing_alert.guides import guide_html, unforecast_guides
from wing_alert.measured import (
    load_observations,
    local_time,
    readings_by_hour,
    stations_about,
    where,
)
from wing_alert.observations import OBS_URL
from wing_alert.tidechart import tide_chart

SITE_URL = "https://daplein.github.io/wing-alert/"
TEMPLATES = Path(__file__).parent / "templates"
ASSETS = ("style.css", "logo.svg")
STRIP_BEFORE, STRIP_AFTER = 2, 3  # days either side of the current page in the day strip


def day_url(site_url: str, day: date) -> str:
    return f"{site_url.rstrip('/')}/days/{day.isoformat()}.html"


class SiteBuilder:
    def __init__(self, env: jinja2.Environment, spots: list[Spot], guides: Path) -> None:
        self._env = env
        self._spots = spots
        self._guides = guides

    def build(
        self,
        snapshots: list[dict[str, Any]],
        out: Path,
        maps: dict[str, Path] | None = None,
        weeks: list[dict[str, Any]] | None = None,
        observations: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        pages = pages_by_date(snapshots)
        days = sorted(pages)
        self._observations = observations or {}
        self._today = max((snapshot["issued"][:10] for snapshot in snapshots), default=None)
        (out / "days").mkdir(parents=True, exist_ok=True)
        self._maps = self._copy_maps(maps or {}, out)
        self._summaries = {day: _summary(pages[day], day) for day in days}
        for day in days:
            self._render_day(out / "days" / f"{day}.html", "../", pages[day], day, days)
        if days:
            today = self._today
            self._render_day(out / "index.html", "", pages[today], today, days)
        else:
            self._write(out / "index.html", self._env.get_template("empty.html").render(root=""))
        self._write(out / "days.html", self._archive_page(days, weeks or []))
        self._write(out / "spots.html", self._spots_page())
        self._week_pages(weeks or [], out)
        for asset in ASSETS:
            shutil.copy(TEMPLATES / asset, out / asset)

    def _render_day(self, path: Path, root: str, snapshot: dict, day: str, days: list) -> None:
        forecast = _forecast_day(snapshot, day)
        html = self._env.get_template("day.html").render(
            root=root,
            issued=snapshot["issued"],
            day=forecast,
            measured=self._measured(snapshot, day, forecast["hours"]),
            obs_url=OBS_URL,
            outlook=day > _next_day(snapshot["issued"][:10]),
            maps=self._maps.get(day, []),
            strip=_strip(days, day, self._summaries),
            **_neighbours(days, days.index(day)),
        )
        self._write(path, html)

    def _measured(self, snapshot: dict, day: str, hours: list[int]) -> list[dict[str, Any]]:
        """Stations with readings that day; on the newest page every known station, so
        the page can fill them in live (FR-11.1, FR-11.4)."""
        by_hour = readings_by_hour(self._observations, day)
        about = stations_about(self._observations)
        shown = [s for s in about if s in by_hour or day == self._today]
        shown += sorted(s for s in by_hour if s not in about)
        return [
            _measured_row(s, about.get(s), by_hour.get(s, {}), hours, snapshot["spots"])
            for s in shown
        ]

    def _archive_page(self, days: list[str], weeks: list[dict[str, Any]]) -> str:
        return self._env.get_template("days.html").render(
            root="", days=days, summaries=self._summaries, weeks=[w["start"] for w in weeks]
        )

    def _week_pages(self, weeks: list[dict[str, Any]], out: Path) -> None:
        (out / "weeks").mkdir(parents=True, exist_ok=True)
        template = self._env.get_template("week.html")
        for week in weeks:
            html = template.render(root="../", week=week)
            self._write(out / "weeks" / f"{week['start']}.html", html)

    @staticmethod
    def _copy_maps(maps: dict[str, Path], out: Path) -> dict[str, list[str]]:
        """Copies the maps; returns each date's map names (`YYYY-MM-DD-HH`), in hour order."""
        (out / "maps").mkdir(parents=True, exist_ok=True)
        by_day: dict[str, list[str]] = {}
        for name, path in sorted(maps.items()):
            shutil.copy(path, out / "maps" / f"{name}.png")
            by_day.setdefault(name[:10], []).append(name)
        return by_day

    def _spots_page(self) -> str:
        guides = [(spot, guide_html(self._guides / f"{spot.id}.md")) for spot in self._spots]
        extras = unforecast_guides(self._guides, {spot.id for spot in self._spots})
        return self._env.get_template("spots.html").render(root="", guides=guides, extras=extras)

    @staticmethod
    def _write(path: Path, html: str) -> None:
        path.write_text(html)


def pages_by_date(snapshots: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Each date's page comes from the latest run that covers it: the last run issued
    that day once it has passed, the newest run for today and the days ahead."""
    pages: dict[str, dict[str, Any]] = {}
    for snapshot in sorted(snapshots, key=lambda s: s["issued"]):
        for day in _covered_dates(snapshot):
            pages[day] = snapshot
    return pages


def _covered_dates(snapshot: dict[str, Any]) -> list[str]:
    dates = {hour["time"][:10] for spot in snapshot["spots"] for hour in spot["hours"]}
    return sorted(day for day in dates if day >= snapshot["issued"][:10])


def _next_day(day: str) -> str:
    return (date.fromisoformat(day) + timedelta(days=1)).isoformat()


def _summary(snapshot: dict[str, Any], day: str) -> dict[str, Any]:
    """What the day strip shows for a date: the peak wind of its windows (a number, not
    a go/no-go light) and, apart from it, the worst shore break and why."""
    windows = [window for window in snapshot["windows"] if window["date"] == day]
    peak = max((window["wind_max"] for window in windows), default=None)
    worst = max(windows, key=lambda window: window.get("shore_break") or 0, default=None)
    return {
        "peak": peak,
        "band": wind_band(peak) if peak is not None else None,
        "warning": (worst or {}).get("shore_break") or 0,
        "reason": (worst or {}).get("shore_break_reason") or "",
    }


def _strip(days: list[str], current: str, summaries: dict[str, dict]) -> list[dict[str, Any]]:
    """A few days either side of the current page."""
    index = days.index(current)
    shown = days[max(0, index - STRIP_BEFORE) : index + STRIP_AFTER + 1]
    return [{"date": day, "current": day == current, **summaries[day]} for day in shown]


def forecast_days(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """One entry per date the run covers, from the day it was issued."""
    return [_forecast_day(snapshot, day) for day in _covered_dates(snapshot)]


def _forecast_day(snapshot: dict[str, Any], day: str) -> dict[str, Any]:
    windows = [window for window in snapshot["windows"] if window["date"] == day]
    hours = _daylight_hours(snapshot["daylight"].get(day))
    return {
        "date": date.fromisoformat(day),
        "best": windows[0] if windows else None,
        "tide": tide_chart(_stations_in_spot_order(snapshot), day, _rideable(windows), hours),
        "hours": hours,
        "rows": [_row(spot, day, hours, windows) for spot in _ranked_spots(snapshot, windows)],
    }


def _stations_in_spot_order(snapshot: dict[str, Any]) -> dict[str, dict]:
    """South to north, as the spots are listed: Arklow, Wicklow, Dublin Port."""
    stations = snapshot.get("tide_stations", {})
    order = dict.fromkeys(spot.get("tide_station") for spot in snapshot["spots"])
    return {key: stations[key] for key in order if key in stations}


def _rideable(windows: list[dict]) -> set[int]:
    """Hours of the day when any spot has a window: shaded on the tide chart."""
    return {
        hour
        for window in windows
        for hour in range(int(window["start"][11:13]), int(window["end"][11:13]))
    }


def _day_tides(spot: dict, day: str) -> dict[str, list[str]]:
    """The spot's station tides that day as HH:MM lists (FR-6.5)."""
    tides = [tide for tide in spot.get("tides", []) if tide["time"][:10] == day]
    return {kind: [t["time"][11:] for t in tides if t["kind"] == kind] for kind in ("high", "low")}


def _daylight_hours(daylight: dict[str, str] | None) -> list[int]:
    if not daylight:
        return list(range(7, 20))
    return list(range(int(daylight["sunrise"][11:13]), int(daylight["sunset"][11:13]) + 1))


def _ranked_spots(snapshot: dict[str, Any], windows: list[dict]) -> list[dict[str, Any]]:
    order = list(dict.fromkeys(window["spot"] for window in windows))
    position = {spot_id: index for index, spot_id in enumerate(order)}
    return sorted(snapshot["spots"], key=lambda spot: position.get(spot["id"], len(order)))


def _row(spot: dict, day: str, hours: list[int], windows: list[dict]) -> dict[str, Any]:
    by_hour = {int(h["time"][11:13]): h for h in spot["hours"] if h["time"][:10] == day}
    return {
        "id": spot["id"],
        "name": spot["name"],
        "windows": [window for window in windows if window["spot"] == spot["id"]],
        "cells": [_cell(by_hour.get(hour)) for hour in hours],
        "waves": _max_waves([by_hour.get(hour) for hour in hours]),
        "tides": _day_tides(spot, day),
    }


def _measured_row(
    station: str, about: dict | None, by_hour: dict[int, dict], hours: list[int], spots: list
) -> dict[str, Any]:
    waves = [r["wave_height"] for r in by_hour.values() if r.get("wave_height") is not None]
    return {
        "id": station,
        "name": about["name"] if about else station,
        "where": where(about, spots) if about else "",
        "cells": [_reading_cell(by_hour.get(hour)) for hour in hours],
        "waves": (min(waves), max(waves)) if waves else None,
    }


def _reading_cell(reading: dict[str, Any] | None) -> dict[str, Any] | None:
    if reading is None or reading.get("wind") is None:
        return None
    direction = reading.get("direction")
    return {
        **reading,
        "local": f"{local_time(reading['time']):%H:%M}",
        "band": wind_band(reading["wind"]),
        "arrow": None if direction is None else (direction + 180) % 360,
    }


def _max_waves(readings: list[dict | None]) -> float | None:
    heights = [r["wave_height"] for r in readings if r and r.get("wave_height") is not None]
    return max(heights) if heights else None


def _cell(hour: dict[str, Any] | None) -> dict[str, Any] | None:
    if hour is None:
        return None
    return {**hour, "band": wind_band(hour["wind"]), "arrow": (hour["direction"] + 180) % 360}


def wind_band(knots: float) -> str:
    if knots < 10:
        return "light"
    if knots < 20:
        return "good"
    return "strong" if knots < 30 else "wild"


def _neighbours(days: list[str], index: int) -> dict[str, str | None]:
    return {
        "previous": days[index - 1] if index > 0 else None,
        "next": days[index + 1] if index + 1 < len(days) else None,
    }


def make_env() -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES), autoescape=True, trim_blocks=True
    )
    env.filters["day_label"] = lambda d: f"{d:%A} {d.day} {d:%B}"
    env.filters["iso_label"] = lambda text: env.filters["day_label"](date.fromisoformat(text))
    env.filters["short_label"] = lambda text: f"{date.fromisoformat(text):%a %-d}"
    env.filters["warning"] = lambda level: {1: "⚠️", 2: "🚨"}.get(level, "")
    return env


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wing_alert.site", description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--config", type=Path, default=Path("config"))
    parser.add_argument("--guides", type=Path, default=Path("docs/spots"))
    parser.add_argument("--out", type=Path, default=Path("_site"))
    args = parser.parse_args(argv)
    builder = SiteBuilder(make_env(), load_spots(args.config / "spots.yaml"), args.guides)
    maps = {path.stem: path for path in sorted(args.data.glob("*/*/*.png"))}
    weeks = [json.loads(path.read_text()) for path in sorted(args.data.glob("weeks/*.json"))]
    observations = load_observations(args.data / "obs")
    builder.build(load_snapshots(args.data), args.out, maps, weeks, observations)
    print(f"Site built in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
