"""Daily job: build the parts and run them."""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx

from wing_alert.config import ConfigError, Settings, Spot, load_settings, load_spots
from wing_alert.forecast import ForecastError, OpenMeteoClient
from wing_alert.message import format_alert
from wing_alert.scoring import Window, find_windows, rank
from wing_alert.state import AlertState
from wing_alert.whatsapp import CallMeBotSender, DeliveryError, DrySender, parse_recipients

DUBLIN = ZoneInfo("Europe/Dublin")


class Sender(Protocol):
    def send(self, text: str) -> None: ...


class DailyJob:
    def __init__(
        self,
        spots: list[Spot],
        settings: Settings,
        forecasts: OpenMeteoClient,
        sender: Sender,
        state: AlertState,
        persist: bool,
    ) -> None:
        self._spots = spots
        self._settings = settings
        self._forecasts = forecasts
        self._sender = sender
        self._state = state
        self._persist = persist

    def run(self, now: datetime) -> str | None:
        """Send new or changed windows. Returns the message, or None if nothing to send."""
        windows = self._all_windows(now)
        changed = self._state.changed_days(windows)
        fresh = [window for window in windows if window.date in changed]
        if not fresh:
            return None
        text = format_alert(rank(fresh, self._settings))
        self._sender.send(text)
        if self._persist:
            self._state.record(fresh, now.date())
            self._state.save()
        return text

    def _all_windows(self, now: datetime) -> list[Window]:
        windows: list[Window] = []
        for spot in self._spots:
            windows += find_windows(self._forecasts.fetch(spot), self._settings, now)
        return windows


def main(argv: list[str] | None = None, now: datetime | None = None) -> int:
    args = _parse_args(argv)
    now = now or datetime.now(DUBLIN).replace(tzinfo=None)
    try:
        with httpx.Client(timeout=30) as http:
            text = build_job(args, http).run(now)
    except (ConfigError, ForecastError, DeliveryError, ValueError) as error:
        print(f"wing-alert failed: {error}", file=sys.stderr)
        return 1
    print(text if text else "No new windows.")
    return 0


def build_job(args: argparse.Namespace, http: httpx.Client) -> DailyJob:
    recipients = parse_recipients(os.environ.get("WHATSAPP_RECIPIENTS", ""))
    live = bool(recipients) and not args.dry_run
    if not live:
        print("Dry run: printing instead of sending, state.json not updated.")
    return DailyJob(
        spots=load_spots(args.config / "spots.yaml"),
        settings=load_settings(args.config / "settings.yaml"),
        forecasts=OpenMeteoClient(http),
        sender=CallMeBotSender(http, recipients) if live else DrySender(),
        state=AlertState(args.state),
        persist=live,
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="wing_alert", description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config"))
    parser.add_argument("--state", type=Path, default=Path("state.json"))
    parser.add_argument("--dry-run", action="store_true", help="print, don't send or save")
    return parser.parse_args(argv)
