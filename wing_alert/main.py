"""Daily job: build the parts and run them."""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx

from wing_alert.archive import Archive
from wing_alert.config import ConfigError, Settings, Spot, load_settings, load_spots
from wing_alert.forecast import ForecastError, OpenMeteoClient
from wing_alert.message import format_alert
from wing_alert.scoring import Window, find_windows, rank
from wing_alert.site import SITE_URL, day_url
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
        archive: Archive | None = None,
        site_url: str | None = None,
    ) -> None:
        self._spots = spots
        self._settings = settings
        self._forecasts = forecasts
        self._sender = sender
        self._state = state
        self._persist = persist
        self._archive = archive
        self._site_url = site_url

    def run(self, now: datetime) -> str | None:
        """Archive the forecast, then alert on new or changed windows.
        Returns the message, or None if there was nothing to send."""
        forecasts = [self._forecasts.fetch(spot) for spot in self._spots]
        if self._archive:
            self._archive.write(now, forecasts)
        windows = [w for f in forecasts for w in find_windows(f, self._settings, now)]
        return self._alert(windows, now)

    def _alert(self, windows: list[Window], now: datetime) -> str | None:
        changed = self._state.changed_days(windows)
        fresh = [window for window in windows if window.date in changed]
        if not fresh:
            return None
        text = format_alert(rank(fresh, self._settings), self._day_link(now))
        self._sender.send(text)
        if self._persist:
            self._state.record(fresh, now.date())
            self._state.save()
        return text

    def _day_link(self, now: datetime) -> str | None:
        return day_url(self._site_url, now.date()) if self._site_url else None


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
        print("Not sending: printing instead, state.json not updated.")
    settings = load_settings(args.config / "settings.yaml")
    return DailyJob(
        spots=load_spots(args.config / "spots.yaml"),
        settings=settings,
        forecasts=OpenMeteoClient(http),
        sender=CallMeBotSender(http, recipients) if live else DrySender(),
        state=AlertState(args.state),
        persist=live,
        archive=None if args.dry_run else Archive(args.data, settings),
        site_url=args.site_url,
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="wing_alert", description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config"))
    parser.add_argument("--state", type=Path, default=Path("state.json"))
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--site-url", default=SITE_URL)
    parser.add_argument("--dry-run", action="store_true", help="print only: no send, no files")
    return parser.parse_args(argv)
