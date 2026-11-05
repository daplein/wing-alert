from dataclasses import replace
from datetime import datetime, timedelta

import httpx
import pytest
import respx

from tests.helpers import (
    ARKLOW,
    MORNING,
    SEAPOINT,
    SETTINGS,
    forecast,
    hours,
    sea_payload,
    window,
)
from wing_alert.archive import build_snapshot
from wing_alert.config import ConfigError, load_spots
from wing_alert.marine import MarineClient, MarineError, SeaHour
from wing_alert.message import format_alert
from wing_alert.shorebreak import rate_window
from wing_alert.site import SiteBuilder, make_env
from wing_alert.tides import StationTides, Tide

NOON = MORNING.replace(hour=12)


def sea(waves: float, period: float = 6) -> SeaHour:
    return SeaHour(waves, period, period)


def rated(waves: float, spot=ARKLOW, period: float = 6, tides=(), hours_count: int = 2):
    readings = hours(NOON, [20] * hours_count)
    conditions = replace(
        forecast(spot, readings),
        sea={hour.time: sea(waves, period) for hour in readings},
        tides=list(tides),
    )
    return rate_window(window(spot, NOON, [20] * hours_count), conditions, SETTINGS)


@respx.mock
def test_fr_4_1_fetches_waves_and_swell():
    route = respx.get(MarineClient.URL).respond(json=sea_payload(NOON, [1.2, None]))
    with httpx.Client() as http:
        result = MarineClient(http).fetch(ARKLOW)
    assert "swell_wave_period" in route.calls.last.request.url.params["hourly"]
    assert result[NOON] == SeaHour(1.2, 6, 6)
    assert result[NOON + timedelta(hours=1)].wave_height is None


@respx.mock
def test_fr_4_1_marine_failure_is_a_marine_error():
    respx.get(MarineClient.URL).respond(503)
    with httpx.Client() as http, pytest.raises(MarineError):
        MarineClient(http).fetch(ARKLOW)


@respx.mock
def test_fr_4_1_odd_marine_payload_is_a_marine_error():
    respx.get(MarineClient.URL).respond(json={"hourly": {"time": []}})
    with httpx.Client() as http, pytest.raises(MarineError):
        MarineClient(http).fetch(ARKLOW)


@pytest.mark.parametrize(("waves", "level"), [(0.3, 0), (0.9, 1), (1.6, 2)])
def test_fr_4_3_wave_height_sets_the_level(waves, level):
    assert rated(waves).shore_break == level


def test_fr_4_3_long_swell_goes_up_one_level():
    result = rated(0.9, period=11)
    assert result.shore_break == 2
    assert "long swell (11 s)" in result.shore_break_reason


def test_fr_4_3_worse_tide_goes_up_one_level():
    spot = replace(ARKLOW, worse_at="high")
    result = rated(0.5, spot=spot, tides=[Tide(NOON, "high")])
    assert result.shore_break == 1
    assert "high tide" in result.shore_break_reason


def test_fr_4_3_flat_sea_gets_no_bumps():
    spot = replace(ARKLOW, worse_at="high")
    assert rated(0.2, spot=spot, period=12, tides=[Tide(NOON, "high")]).shore_break == 0


def test_fr_4_3_spot_can_override_wave_heights():
    assert rated(0.9, spot=replace(ARKLOW, watch_wave_m=1.0, danger_wave_m=2.0)).shore_break == 0


def test_fr_4_3_missing_sea_data_means_no_warning():
    conditions = forecast(ARKLOW, hours(NOON, [20, 20]))
    assert rate_window(window(ARKLOW, NOON, [20, 20]), conditions, SETTINGS).shore_break == 0


def test_fr_4_3_spot_config_accepts_worse_at(tmp_path):
    path = tmp_path / "spots.yaml"
    path.write_text("- {id: a, name: A, lat: 52, lon: -6, directions: [0, 90], worse_at: low}")
    assert load_spots(path)[0].worse_at == "low"
    path.write_text("- {id: a, name: A, lat: 52, lon: -6, directions: [0, 90], worse_at: mid}")
    with pytest.raises(ConfigError):
        load_spots(path)


def test_fr_4_4_alert_shows_only_the_emoji():
    text = format_alert([rated(1.6)])
    assert text.splitlines()[-1].endswith("gusts 25 🚨")
    assert "waves" not in text


def test_fr_4_5_dangerous_exposed_spot_suggests_the_sheltered_one():
    sheltered = window(SEAPOINT, NOON, [20, 20])
    text = format_alert([rated(1.6), sheltered])
    assert "Sheltered option: Seapoint 12:00–14:00" in text
    assert "Sheltered option" not in format_alert([rated(0.9), sheltered])


def test_fr_4_4_day_page_shows_waves_and_reason(tmp_path):
    readings = hours(NOON, [20, 20])
    waves = {hour.time: sea(1.6) for hour in readings}
    spot = replace(ARKLOW, tide_station="Arklow")
    conditions = replace(forecast(spot, readings), sea=waves)
    station = StationTides(
        "Arklow",
        [(NOON - timedelta(hours=6), 0.5), (NOON, 1.3), (NOON + timedelta(hours=6), 0.4)],
        [Tide(NOON, "high"), Tide(NOON + timedelta(hours=6), "low")],
    )
    conditions = replace(conditions, tides=station.tides)
    snapshot = build_snapshot(MORNING, [conditions], SETTINGS, {"Arklow": station})
    assert snapshot["windows"][0]["shore_break"] == 2
    out = tmp_path / "site"
    SiteBuilder(make_env(), [ARKLOW], tmp_path).build([snapshot], out)
    page = (out / "index.html").read_text()
    assert "Shore break: dangerous · 1.6 m waves at 6 s" in page
    assert 'title="12:00: waves 1.6 m, every 6 s">1.6<small>6s</small>' in page  # FR-12.2
    assert 'title="High water 12:00">HW</span>' in page  # FR-12.1
    assert 'class="tidechart"' in page  # FR-6.4


def test_fr_4_4_marine_outage_still_alerts(tmp_path, monkeypatch, capsys):
    from wing_alert.main import DailyJob
    from wing_alert.state import AlertState

    class Wind:
        def fetch(self, spot):
            return forecast(spot, hours(NOON, [20, 20]))

    class DownMarine:
        def fetch(self, spot):
            raise MarineError("down")

    class Sender:
        sent: list[str] = []

        def send(self, text):
            self.sent.append(text)

    job = DailyJob(
        [ARKLOW],
        SETTINGS,
        Wind(),
        Sender(),
        AlertState(tmp_path / "s.json"),
        False,
        marine=DownMarine(),
    )
    assert "Arklow" in job.run(MORNING)
    assert "No shore break warning for arklow" in capsys.readouterr().err


def test_fr_4_1_marine_payload_survives_the_archive():
    when = datetime(2026, 11, 6, 12)
    conditions = replace(forecast(ARKLOW, hours(when, [20])), sea={when: sea(0.7, 5)})
    hour = build_snapshot(MORNING, [conditions], SETTINGS)["spots"][0]["hours"][0]
    assert (hour["wave_height"], hour["wave_period"]) == (0.7, 5)
