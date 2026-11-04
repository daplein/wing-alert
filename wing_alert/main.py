"""Daily job: build the parts and run them."""

import argparse
import os
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx

from wing_alert.archive import Archive, build_snapshot
from wing_alert.config import ConfigError, Settings, Spot, load_settings, load_spots
from wing_alert.forecast import ForecastError, OpenMeteoClient, SpotForecast
from wing_alert.marine import MarineClient, MarineError
from wing_alert.message import format_alert
from wing_alert.observations import (
    OBS_URL,
    ObservationArchive,
    ObservationClient,
    ObservationError,
)
from wing_alert.scoring import Window, find_windows, rank
from wing_alert.shorebreak import rate_window
from wing_alert.site import SITE_URL, day_url
from wing_alert.state import AlertState
from wing_alert.tides import StationTides, TideClient, TideError
from wing_alert.whatsapp import CallMeBotSender, DeliveryError, DrySender, parse_recipients
from wing_alert.windmap import MapWriter

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
        maps: MapWriter | None = None,
        site_url: str | None = None,
        marine: MarineClient | None = None,
        tides: TideClient | None = None,
        observations: ObservationClient | None = None,
        obs_archive: ObservationArchive | None = None,
    ) -> None:
        self._spots = spots
        self._settings = settings
        self._forecasts = forecasts
        self._sender = sender
        self._state = state
        self._persist = persist
        self._archive = archive
        self._maps = maps
        self._site_url = site_url
        self._marine = marine
        self._tides = tides
        self._observations = observations
        self._obs_archive = obs_archive

    def run(self, now: datetime) -> str | None:
        """Archive the forecast, then alert on new or changed windows.
        Returns the message, or None if there was nothing to send."""
        self._keep_readings(now)
        stations = self._station_tides(now)
        forecasts = [self._conditions(spot, stations) for spot in self._spots]
        self._keep_record(now, forecasts, stations)
        windows = [
            rate_window(window, forecast, self._settings)
            for forecast in forecasts
            for window in find_windows(forecast, self._settings, now)
        ]
        return self._alert(windows, now)

    def _keep_readings(self, now: datetime) -> None:
        """Yesterday and today in UTC; without the Worker the run carries on (FR-10.6)."""
        if not (self._observations and self._obs_archive):
            return
        today = now.replace(tzinfo=DUBLIN).astimezone(UTC).date()
        for day in (today - timedelta(days=1), today):
            try:
                self._obs_archive.merge(day, self._observations.fetch(day))
            except ObservationError as error:
                print(error, file=sys.stderr)

    def _station_tides(self, now: datetime) -> dict[str, StationTides]:
        """Each station once per run; a failing one is left out (FR-6.7)."""
        wanted = sorted({spot.tide_station for spot in self._spots if spot.tide_station})
        stations = {}
        for station in wanted if self._tides else []:
            try:
                stations[station] = self._tides.fetch(station, now.date())
            except TideError as error:
                print(f"No tides for {station}: {error}", file=sys.stderr)
        return stations

    def _conditions(self, spot: Spot, stations: dict[str, StationTides]) -> SpotForecast:
        """Wind is required; sea data and tides only add warnings, so they may be missing."""
        forecast = self._forecasts.fetch(spot)
        station = stations.get(spot.tide_station or "")
        if station:
            forecast = replace(forecast, tides=station.tides)
        if not self._marine:
            return forecast
        try:
            return replace(forecast, sea=self._marine.fetch(spot))
        except MarineError as error:
            print(f"No shore break warning for {spot.id}: {error}", file=sys.stderr)
            return forecast

    def _keep_record(
        self, now: datetime, forecasts: list[SpotForecast], stations: dict[str, StationTides]
    ) -> None:
        if not self._archive:
            return
        snapshot = build_snapshot(now, forecasts, self._settings, stations)
        self._archive.save(snapshot)
        if self._maps:
            self._maps.write(snapshot)

    def _alert(self, windows: list[Window], now: datetime) -> str | None:
        last = now.date() + timedelta(days=self._settings.alert_days)
        windows = [window for window in windows if window.date < last]
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
        forecasts=OpenMeteoClient(http, settings.forecast_days),
        sender=CallMeBotSender(http, recipients) if live else DrySender(),
        state=AlertState(args.state),
        persist=live,
        archive=None if args.dry_run else Archive(args.data),
        maps=None if args.dry_run else MapWriter(args.data),
        site_url=args.site_url,
        marine=MarineClient(http, settings.forecast_days),
        tides=TideClient(http, settings.forecast_days),
        observations=ObservationClient(http, args.obs_url),
        obs_archive=None if args.dry_run else ObservationArchive(args.data / "obs"),
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="wing_alert", description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config"))
    parser.add_argument("--state", type=Path, default=Path("state.json"))
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--site-url", default=SITE_URL)
    parser.add_argument("--obs-url", default=OBS_URL, help="the Worker's /obs address")
    parser.add_argument("--dry-run", action="store_true", help="print only: no send, no files")
    return parser.parse_args(argv)
