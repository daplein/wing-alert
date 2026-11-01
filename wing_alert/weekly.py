"""Weekly summary: what was good, what we alerted, what we missed (FR-5.1 to FR-5.4)."""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from wing_alert.archive import load_snapshots
from wing_alert.main import DUBLIN, Sender
from wing_alert.site import SITE_URL
from wing_alert.whatsapp import CallMeBotSender, DeliveryError, DrySender, parse_recipients


def summarise(
    snapshots: list[dict[str, Any]], sent: dict[str, list[str]], week_end: date
) -> dict[str, Any]:
    start = week_end - timedelta(days=6)
    mornings = morning_runs(snapshots)
    days = [_day(mornings.get(day.isoformat()), day, sent) for day in _dates(start, week_end)]
    windows = [window for day in days for window in day["windows"]]
    return {
        "start": start.isoformat(),
        "end": week_end.isoformat(),
        "days": days,
        "good_days": sum(1 for day in days if day["windows"]),
        "missed": sum(1 for window in windows if not window["alerted"]),
        "best": max(windows, key=_window_hours, default=None),
    }


def morning_runs(snapshots: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The first run issued each day: the shortest-range forecast for that day."""
    first: dict[str, dict[str, Any]] = {}
    for snapshot in sorted(snapshots, key=lambda s: s["issued"]):
        first.setdefault(snapshot["issued"][:10], snapshot)
    return first


def was_alerted(window: dict[str, Any], sent_that_day: list[str]) -> bool:
    """Sent entries look like "arklow@13-17"; any overlap at the same spot counts."""
    start, end = int(window["start"][11:13]), int(window["end"][11:13])
    for entry in sent_that_day:
        spot, _, hours = entry.partition("@")
        sent_start, sent_end = (int(part) for part in hours.split("-"))
        if spot == window["spot"] and sent_start < end and start < sent_end:
            return True
    return False


def summary_line(week: dict[str, Any], link: str) -> str:
    start = date.fromisoformat(week["start"])
    days = "1 good day" if week["good_days"] == 1 else f"{week['good_days']} good days"
    return f"🪁 Week of {start.day} {start:%b}: {days}, {week['missed']} missed → {link}"


def week_url(site_url: str, start: str) -> str:
    return f"{site_url.rstrip('/')}/weeks/{start}.html"


def _day(snapshot: dict[str, Any] | None, day: date, sent: dict) -> dict[str, Any]:
    key = day.isoformat()
    windows = [w for w in (snapshot or {}).get("windows", []) if w["date"] == key]
    return {
        "date": key,
        "forecast": snapshot is not None,
        "windows": [{**w, "alerted": was_alerted(w, sent.get(key, []))} for w in windows],
    }


def _window_hours(window: dict[str, Any]) -> int:
    return int(window["end"][11:13]) - int(window["start"][11:13])


def _dates(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


class WeeklyJob:
    def __init__(self, data: Path, state: Path, sender: Sender, site_url: str) -> None:
        self._data = data
        self._state = state
        self._sender = sender
        self._site_url = site_url

    def run(self, today: date) -> str:
        sent = json.loads(self._state.read_text()).get("sent", {}) if self._state.exists() else {}
        week = summarise(load_snapshots(self._data), sent, today)
        path = self._data / "weeks" / f"{week['start']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(week, indent=1, ensure_ascii=False) + "\n")
        text = summary_line(week, week_url(self._site_url, week["start"]))
        self._sender.send(text)
        return text


def main(argv: list[str] | None = None, today: date | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wing_alert.weekly", description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--state", type=Path, default=Path("state.json"))
    parser.add_argument("--site-url", default=SITE_URL)
    args = parser.parse_args(argv)
    today = today or datetime.now(DUBLIN).date()
    try:
        recipients = parse_recipients(os.environ.get("WHATSAPP_RECIPIENTS", ""))
        with httpx.Client(timeout=30) as http:
            sender = CallMeBotSender(http, recipients) if recipients else DrySender()
            print(WeeklyJob(args.data, args.state, sender, args.site_url).run(today))
    except (DeliveryError, ValueError) as error:
        print(f"wing-alert weekly failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
