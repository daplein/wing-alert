import json
from pathlib import Path

import respx

from tests.helpers import (
    ARKLOW,
    MORNING,
    SETTINGS,
    forecast,
    hours,
    open_meteo_payload,
    sea_payload,
    tide_csv,
)
from wing_alert.forecast import OpenMeteoClient
from wing_alert.main import DailyJob, main
from wing_alert.marine import MarineClient
from wing_alert.state import AlertState
from wing_alert.tides import TideClient
from wing_alert.whatsapp import CallMeBotSender

REPO_CONFIG = Path(__file__).parents[1] / "config"
NOON = MORNING.replace(hour=12)


class FakeForecasts:
    def __init__(self, winds: list[float]) -> None:
        self.winds = winds

    def fetch(self, spot):
        return forecast(spot, hours(NOON, self.winds))


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, text: str) -> None:
        self.sent.append(text)


def job(tmp_path, winds, persist=True):
    sender = FakeSender()
    state = AlertState(tmp_path / "state.json")
    return DailyJob([ARKLOW], SETTINGS, FakeForecasts(winds), sender, state, persist), sender


def test_fr_1_6_sends_one_message_when_there_is_a_window(tmp_path):
    daily, sender = job(tmp_path, [18, 20])
    assert daily.run(MORNING) == sender.sent[0]
    assert "Arklow South Beach 12:00–14:00" in sender.sent[0]


def test_fr_1_6_sends_nothing_without_windows(tmp_path):
    daily, sender = job(tmp_path, [5, 5])
    assert daily.run(MORNING) is None
    assert sender.sent == []


def test_fr_1_7_second_run_with_same_windows_sends_nothing(tmp_path):
    daily, sender = job(tmp_path, [18, 20])
    daily.run(MORNING)
    again, again_sender = job(tmp_path, [18, 20])
    assert again.run(MORNING) is None
    assert again_sender.sent == []


def test_fr_1_7_dry_run_does_not_save_state(tmp_path):
    daily, _ = job(tmp_path, [18, 20], persist=False)
    daily.run(MORNING)
    assert not (tmp_path / "state.json").exists()


@respx.mock
def test_fr_1_6_main_sends_to_recipients_and_saves_state(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WHATSAPP_RECIPIENTS", "+353861234567:999")
    respx.get(OpenMeteoClient.URL).respond(json=_windy_day())
    respx.get(MarineClient.URL).respond(json=_sea_day())
    respx.get(url__startswith=TideClient.URL).respond(text=_tide_day())
    whatsapp = respx.get(CallMeBotSender.URL).respond(text="ok")
    state = tmp_path / "state.json"
    assert (
        main(
            ["--config", str(REPO_CONFIG), "--state", str(state), "--data", str(tmp_path / "d")],
            now=MORNING,
        )
        == 0
    )
    assert whatsapp.called
    assert json.loads(state.read_text())["sent"]
    assert "999" not in capsys.readouterr().out


@respx.mock
def test_fr_1_6_main_without_recipients_prints_only(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("WHATSAPP_RECIPIENTS", raising=False)
    respx.get(OpenMeteoClient.URL).respond(json=_windy_day())
    respx.get(MarineClient.URL).respond(json=_sea_day())
    respx.get(url__startswith=TideClient.URL).respond(text=_tide_day())
    state = tmp_path / "state.json"
    assert (
        main(
            ["--config", str(REPO_CONFIG), "--state", str(state), "--data", str(tmp_path / "d")],
            now=MORNING,
        )
        == 0
    )
    assert "Not sending" in capsys.readouterr().out
    assert not state.exists()


@respx.mock
def test_fr_1_8_main_fails_cleanly_when_forecast_is_down(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("WHATSAPP_RECIPIENTS", raising=False)
    respx.get(OpenMeteoClient.URL).respond(503)
    respx.get(url__startswith=TideClient.URL).respond(text=_tide_day())
    assert (
        main(
            [
                "--config",
                str(REPO_CONFIG),
                "--state",
                str(tmp_path / "s.json"),
                "--data",
                str(tmp_path / "d"),
            ],
            now=MORNING,
        )
        == 1
    )
    assert "wing-alert failed" in capsys.readouterr().err


def _windy_day():
    return open_meteo_payload(MORNING.replace(hour=0), [18] * 24, direction=70)


@respx.mock
def test_fr_2_1_main_archives_and_links_unless_dry_run(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("WHATSAPP_RECIPIENTS", raising=False)
    respx.get(OpenMeteoClient.URL).respond(json=_windy_day())
    respx.get(MarineClient.URL).respond(json=_sea_day())
    respx.get(url__startswith=TideClient.URL).respond(text=_tide_day())
    data = tmp_path / "data"
    args = ["--config", str(REPO_CONFIG), "--state", str(tmp_path / "s.json"), "--data", str(data)]
    assert main(args, now=MORNING) == 0
    (archived,) = data.glob("*/*/*.json")
    snapshot = json.loads(archived.read_text())
    assert sorted(snapshot["tide_stations"]) == ["Arklow", "Dublin_Port", "Wicklow_MODELLED"]
    assert snapshot["tide_stations"]["Wicklow_MODELLED"]["name"] == "Wicklow"
    arklow = next(spot for spot in snapshot["spots"] if spot["id"] == "arklow")
    assert arklow["tide_station"] == "Arklow"
    assert [tide["kind"] for tide in arklow["tides"]][:2] == ["low", "high"]
    assert "days/2026-11-06.html" in capsys.readouterr().out
    other = tmp_path / "other"
    assert main([*args[:-1], str(other), "--dry-run"], now=MORNING) == 0
    assert not other.exists()


def _sea_day():
    return sea_payload(MORNING.replace(hour=0), [1.0] * 24)


def _tide_day():
    # Every 30 min from midnight: low at 06:00, high at 12:00 (UTC = Irish time in November).
    levels = [abs(((i % 24) - 12) / 12) * 2 for i in range(40)]
    return tide_csv(MORNING.replace(hour=0), levels)


@respx.mock
def test_fr_6_7_tide_outage_still_alerts(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("WHATSAPP_RECIPIENTS", raising=False)
    respx.get(OpenMeteoClient.URL).respond(json=_windy_day())
    respx.get(MarineClient.URL).respond(json=_sea_day())
    respx.get(url__startswith=TideClient.URL).respond(500)
    args = ["--config", str(REPO_CONFIG), "--state", str(tmp_path / "s.json")]
    assert main([*args, "--data", str(tmp_path / "d")], now=MORNING) == 0
    captured = capsys.readouterr()
    assert "No tides for Arklow" in captured.err
    assert "Arklow South Beach" in captured.out
