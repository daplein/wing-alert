"""Live readings recorded by the Worker, kept in git one file per UTC day (FR-10.6)."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx

OBS_URL = "https://wing-alert-trigger.game-scores.workers.dev/obs"

Readings = dict[str, list[dict[str, Any]]]


class ObservationError(Exception):
    """The Worker could not be reached or answered something unexpected."""


class ObservationClient:
    def __init__(self, http: httpx.Client, url: str = OBS_URL) -> None:
        self._http = http
        self._url = url

    def fetch(self, day: date) -> dict[str, Any]:
        try:
            response = self._http.get(self._url, params={"day": day.isoformat()})
            response.raise_for_status()
            answer = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ObservationError(f"No readings for {day}: {error}") from error
        if not isinstance(answer, dict) or not isinstance(answer.get("stations"), dict):
            raise ObservationError(f"No readings for {day}: unexpected answer")
        return answer


class ObservationArchive:
    def __init__(self, root: Path) -> None:
        self._root = root

    def merge(self, day: date, answer: dict[str, Any]) -> Path:
        """Add the Worker's readings to what's kept; KV forgets after 8 days, git doesn't."""
        path = self._root / f"{day.isoformat()}.json"
        kept = json.loads(path.read_text()) if path.exists() else {"stations": {}}
        record = {
            "day": day.isoformat(),
            "about": answer.get("about", kept.get("about", [])),
            "stations": merge_readings(kept["stations"], answer["stations"]),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n")
        return path


def merge_readings(kept: Readings, new: Readings) -> Readings:
    """One reading per station and time; the newer copy wins."""
    merged = {}
    for station in sorted(kept.keys() | new.keys()):
        by_time = {r["time"]: r for r in kept.get(station, []) + new.get(station, [])}
        merged[station] = [by_time[time] for time in sorted(by_time)]
    return merged
