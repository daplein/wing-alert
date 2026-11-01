"""Remember which windows were already sent, so we don't repeat ourselves (FR-1.7)."""

import json
from datetime import date, timedelta
from pathlib import Path

from wing_alert.scoring import Window

KEEP_DAYS = 14


class AlertState:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._sent: dict[str, list[str]] = self._load()

    def changed_days(self, windows: list[Window]) -> set[date]:
        """Days whose windows differ from what was last sent for that day."""
        days = {window.date for window in windows}
        return {day for day in days if self._sent.get(day.isoformat()) != signature(windows, day)}

    def record(self, windows: list[Window], today: date) -> None:
        for day in {window.date for window in windows}:
            self._sent[day.isoformat()] = signature(windows, day)
        self._prune(today)

    def save(self) -> None:
        self._path.write_text(json.dumps({"sent": self._sent}, indent=2, sort_keys=True) + "\n")

    def _load(self) -> dict[str, list[str]]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text()).get("sent", {})

    def _prune(self, today: date) -> None:
        oldest = (today - timedelta(days=KEEP_DAYS)).isoformat()
        self._sent = {day: sig for day, sig in self._sent.items() if day >= oldest}


def signature(windows: list[Window], day: date) -> list[str]:
    """One entry per window, e.g. "arklow@13-17". Any change of an hour counts."""
    return sorted(f"{w.spot.id}@{w.start:%H}-{w.end:%H}" for w in windows if w.date == day)
