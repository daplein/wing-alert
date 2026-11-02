"""Tide predictions per station from the Marine Institute (FR-6.1 to FR-6.3, FR-6.6)."""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

DUBLIN = ZoneInfo("Europe/Dublin")
UTC = ZoneInfo("UTC")
PAD = timedelta(hours=3)  # so a tide just before midnight is still a peak
MIN_SWING = 0.2  # metres
TIDE_NEAR = timedelta(hours=1, minutes=30)  # "at high tide" for the shore break (FR-4.3)
TAG_NEAR = timedelta(hours=1)  # "HW"/"LW" on the map (FR-6.6)

Level = tuple[datetime, float]


class TideError(Exception):
    """The tide predictions could not be fetched or read."""


@dataclass(frozen=True)
class Tide:
    time: datetime
    kind: str  # "high" or "low"


@dataclass(frozen=True)
class StationTides:
    id: str
    levels: list[Level]
    tides: list[Tide]

    @property
    def name(self) -> str:
        return station_name(self.id)


def station_name(station_id: str) -> str:
    """ "Wicklow_MODELLED" -> "Wicklow", "Dublin_Port" -> "Dublin Port"."""
    return station_id.removesuffix("_MODELLED").replace("_", " ")


class TideClient:
    # https://erddap.marine.ie/erddap/tabledap/IMI-TidePrediction.html
    URL = "https://erddap.marine.ie/erddap/tabledap/IMI-TidePrediction.csv"
    ATTEMPTS = 2

    def __init__(self, http: httpx.Client, days: int = 2) -> None:
        self._http = http
        self._days = days

    def fetch(self, station: str, today: date) -> StationTides:
        start = datetime.combine(today, time()) - PAD
        end = start + timedelta(days=self._days) + 2 * PAD
        try:
            levels = parse_levels(self._get_with_retry(self._url(station, start, end)))
        except (IndexError, ValueError) as error:
            raise TideError(f"{station}: unexpected tide format ({error})") from error
        if not levels:
            raise TideError(f"{station}: no tide predictions")
        return StationTides(station, levels, find_tides(levels))

    def _url(self, station: str, start: datetime, end: datetime) -> str:
        query = f'time,Water_Level&stationID="{station}"&time>={_utc(start)}&time<={_utc(end)}'
        return f"{self.URL}?{quote(query, safe='=&,')}"

    def _get_with_retry(self, url: str) -> str:
        for attempt in range(1, self.ATTEMPTS + 1):
            try:
                response = self._http.get(url)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as error:
                if attempt == self.ATTEMPTS:
                    raise TideError(f"Marine Institute tides failed: {error}") from error
        raise AssertionError("unreachable")


def parse_levels(text: str) -> list[Level]:
    """ERDDAP CSV: a header row, a units row, then `2026-11-02T00:00:00Z,0.74` rows."""
    rows = list(csv.reader(io.StringIO(text)))[2:]
    return [(_local(row[0]), float(row[1])) for row in rows if row and row[1] not in ("", "NaN")]


def find_tides(levels: list[Level]) -> list[Tide]:
    """Highs and lows are the peaks and troughs of the curve.

    Around Arklow the tide is small and lopsided, often with a long stand or a double
    high water, so wiggles smaller than MIN_SWING are dropped, keeping the main high
    and low of each cycle.
    """
    turns = _turning_points(sorted(levels))
    while len(turns) > 1:
        swings = [abs(a[1] - b[1]) for a, b in zip(turns, turns[1:], strict=False)]
        smallest = min(range(len(swings)), key=swings.__getitem__)
        if swings[smallest] >= MIN_SWING:
            break
        del turns[smallest : smallest + 2]
    return [Tide(when, kind) for when, _, kind in turns]


def tide_state(when: datetime, tides: list[Tide], near: timedelta = TIDE_NEAR) -> str | None:
    """The nearest tide's kind ("high"/"low") within `near`, otherwise None (mid-tide)."""
    close = [tide for tide in tides if abs(tide.time - when) <= near]
    return min(close, key=lambda tide: abs(tide.time - when)).kind if close else None


def tide_tag(when: datetime, tides: list[Tide]) -> str:
    """Short map tag: HW / LW within an hour of it, otherwise rising ↑ or falling ↓."""
    state = tide_state(when, tides, TAG_NEAR)
    if state:
        return "HW" if state == "high" else "LW"
    upcoming = [tide for tide in tides if tide.time > when]
    if not upcoming:
        return ""
    return "↑" if min(upcoming, key=lambda tide: tide.time).kind == "high" else "↓"


def _turning_points(levels: list[Level]) -> list[tuple[datetime, float, str]]:
    turns = []
    levels = _flatten_plateaus(levels)
    for (_, before), (when, level), (_, after) in zip(levels, levels[1:], levels[2:], strict=False):
        if before < level > after:
            turns.append((when, level, "high"))
        elif before > level < after:
            turns.append((when, level, "low"))
    return turns


def _flatten_plateaus(levels: list[Level]) -> list[Level]:
    """A run of equal levels counts once, at its middle. Otherwise a flat stretch
    before a rise looks like a high (and before a fall, like a low)."""
    runs: list[list[Level]] = []
    for point in levels:
        if runs and runs[-1][-1][1] == point[1]:
            runs[-1].append(point)
        else:
            runs.append([point])
    return [run[(len(run) - 1) // 2] for run in runs]


def _utc(local: datetime) -> str:
    return local.replace(tzinfo=DUBLIN).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _local(stamp: str) -> datetime:
    utc = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return utc.astimezone(DUBLIN).replace(tzinfo=None)
