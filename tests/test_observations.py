import json
from datetime import date, datetime

import httpx
import pytest
import respx

from tests.helpers import SETTINGS
from wing_alert.main import DailyJob
from wing_alert.observations import (
    OBS_URL,
    ObservationArchive,
    ObservationClient,
    ObservationError,
    merge_readings,
)
from wing_alert.state import AlertState

DAY = date(2026, 11, 4)


def reading(time: str, wind: float) -> dict:
    return {"time": time, "wind": wind, "gust": None, "direction": 90}


def answer(*readings: dict) -> dict:
    return {"day": DAY.isoformat(), "stations": {"m2": list(readings)}, "about": [{"id": "m2"}]}


@respx.mock
def test_fr_10_6_client_asks_the_worker_for_one_day():
    route = respx.get(OBS_URL, params={"day": "2026-11-04"}).respond(json=answer())
    with httpx.Client() as http:
        assert ObservationClient(http).fetch(DAY)["about"] == [{"id": "m2"}]
    assert route.called


@respx.mock
@pytest.mark.parametrize("reply", [httpx.Response(503), httpx.Response(200, text="<html>")])
def test_fr_10_6_client_fails_cleanly(reply):
    respx.get(OBS_URL).mock(return_value=reply)
    with httpx.Client() as http, pytest.raises(ObservationError, match="2026-11-04"):
        ObservationClient(http).fetch(DAY)


@respx.mock
def test_fr_10_6_client_rejects_an_answer_without_stations():
    respx.get(OBS_URL).respond(json=["nope"])
    with httpx.Client() as http, pytest.raises(ObservationError, match="unexpected"):
        ObservationClient(http).fetch(DAY)


def test_fr_10_3_merge_keeps_one_reading_per_time_newest_wins():
    kept = {"m2": [reading("2026-11-04T18:00Z", 10), reading("2026-11-04T19:00Z", 11)]}
    new = {"m2": [reading("2026-11-04T19:00Z", 12)], "m5": [reading("2026-11-04T19:00Z", 8)]}
    merged = merge_readings(kept, new)
    assert [r["wind"] for r in merged["m2"]] == [10, 12]
    assert list(merged) == ["m2", "m5"]


def test_fr_10_6_archive_keeps_readings_kv_has_forgotten(tmp_path):
    archive = ObservationArchive(tmp_path)
    archive.merge(DAY, answer(reading("2026-11-04T18:00Z", 10)))
    path = archive.merge(DAY, answer(reading("2026-11-04T19:00Z", 11)))
    record = json.loads(path.read_text())
    assert path == tmp_path / "2026-11-04.json"
    assert [r["time"] for r in record["stations"]["m2"]] == [
        "2026-11-04T18:00Z",
        "2026-11-04T19:00Z",
    ]
    assert record["about"] == [{"id": "m2"}]


class FakeObservations:
    def __init__(self, fail: bool = False) -> None:
        self.days: list[date] = []
        self._fail = fail

    def fetch(self, day: date) -> dict:
        self.days.append(day)
        if self._fail:
            raise ObservationError(f"No readings for {day}: down")
        return answer(reading(f"{day}T12:00Z", 15))


class NoForecasts:
    def fetch(self, spot):
        raise AssertionError("not needed")


def _job(tmp_path, observations) -> DailyJob:
    return DailyJob(
        [],
        SETTINGS,
        NoForecasts(),
        sender=None,
        state=AlertState(tmp_path / "s.json"),
        persist=False,
        observations=observations,
        obs_archive=ObservationArchive(tmp_path),
    )


def test_fr_10_6_daily_job_keeps_yesterday_and_today_in_utc(tmp_path):
    observations = FakeObservations()
    # 00:30 in Dublin in summer is still the day before in UTC.
    _job(tmp_path, observations).run(datetime(2026, 7, 2, 0, 30))
    assert observations.days == [date(2026, 6, 30), date(2026, 7, 1)]
    assert (tmp_path / "2026-07-01.json").exists()


def test_fr_10_6_daily_job_carries_on_without_the_worker(tmp_path, capsys):
    assert _job(tmp_path, FakeObservations(fail=True)).run(datetime(2026, 11, 4, 7)) is None
    assert "No readings for 2026-11-04: down" in capsys.readouterr().err
    assert not list(tmp_path.glob("*.json"))
