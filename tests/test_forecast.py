from datetime import date, datetime

import httpx
import pytest
import respx

from tests.helpers import ARKLOW, MORNING, SUNRISE, open_meteo_payload
from wing_alert.forecast import ForecastError, OpenMeteoClient

URL = OpenMeteoClient.URL


@pytest.fixture
def client():
    with httpx.Client() as http:
        yield OpenMeteoClient(http)


@respx.mock
def test_fr_1_2_fetches_hourly_wind_in_knots_for_today_and_tomorrow(client):
    route = respx.get(URL).respond(json=open_meteo_payload(MORNING, [12, 15]))
    forecast = client.fetch(ARKLOW)
    params = route.calls.last.request.url.params
    assert params["wind_speed_unit"] == "kn"
    assert params["timezone"] == "Europe/Dublin"
    assert params["forecast_days"] == "2"
    assert params["latitude"] == "52.79"
    assert [(h.time, h.wind, h.gust) for h in forecast.hours] == [
        (MORNING, 12, 18),
        (datetime(2026, 11, 6, 8), 15, 21),
    ]
    assert forecast.daylight[date(2026, 11, 6)].sunrise == SUNRISE


@respx.mock
def test_fr_1_2_skips_hours_with_missing_values(client):
    respx.get(URL).respond(json=open_meteo_payload(MORNING, [12, None, 14]))
    assert [h.wind for h in client.fetch(ARKLOW).hours] == [12, 14]


@respx.mock
def test_fr_1_8_retries_once_then_succeeds(client):
    route = respx.get(URL)
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(200, json=open_meteo_payload(MORNING, [12])),
    ]
    assert len(client.fetch(ARKLOW).hours) == 1
    assert route.call_count == 2


@respx.mock
def test_fr_1_8_fails_after_the_retry(client):
    route = respx.get(URL).mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(ForecastError):
        client.fetch(ARKLOW)
    assert route.call_count == 2


@respx.mock
def test_fr_1_8_unexpected_format_is_a_forecast_error(client):
    respx.get(URL).respond(json={"hourly": {}})
    with pytest.raises(ForecastError):
        client.fetch(ARKLOW)


@pytest.mark.live
def test_live_open_meteo_answers():
    with httpx.Client(timeout=30) as http:
        assert OpenMeteoClient(http).fetch(ARKLOW).hours
