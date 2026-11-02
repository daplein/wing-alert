from datetime import date, datetime, timedelta

import httpx
import pytest
import respx

from tests.helpers import MORNING, tide_csv
from wing_alert.tides import (
    StationTides,
    Tide,
    TideClient,
    TideError,
    find_tides,
    parse_levels,
    station_name,
    tide_state,
    tide_tag,
)

NOON = MORNING.replace(hour=12)


def test_fr_4_2_finds_high_and_low_tides():
    levels = [0.0, 0.5, 0.9, 0.6, 0.1, -0.4, -0.7, -0.3, 0.2]
    series = [(NOON + timedelta(hours=i), lv) for i, lv in enumerate(levels)]
    assert find_tides(series) == [
        Tide(NOON + timedelta(hours=2), "high"),
        Tide(NOON + timedelta(hours=6), "low"),
    ]


def test_fr_4_2_tide_state_is_near_a_tide_or_mid():
    tides = [Tide(NOON, "high"), Tide(NOON + timedelta(hours=6), "low")]
    assert tide_state(NOON + timedelta(minutes=80), tides) == "high"
    assert tide_state(NOON + timedelta(hours=3), tides) is None
    assert tide_state(NOON + timedelta(hours=5), tides) == "low"


def test_fr_4_2_double_high_water_keeps_the_main_high():
    # Real Arklow shape (1 Nov 2026): a high at 11:00, a small dip, a higher high at 16:00.
    levels = [
        -0.73,
        -0.60,
        -0.40,
        -0.27,
        -0.30,
        -0.38,
        -0.38,
        -0.27,
        -0.17,
        -0.22,
        -0.44,
        -0.72,
        -0.91,
        -0.95,
        -0.84,
    ]
    start = MORNING.replace(hour=8)
    series = [(start + timedelta(hours=i), lv) for i, lv in enumerate(levels)]
    assert [(t.time.hour, t.kind) for t in find_tides(series)] == [(16, "high"), (21, "low")]


def test_fr_4_2_a_flat_stretch_is_not_a_tide():
    # Real Arklow levels, 2 Nov 2026 22:00 to 3 Nov 07:00: a low, a flat hour, then the rise.
    levels = [-0.91, -0.88, -0.81, -0.78, -0.78, -0.71, -0.55, -0.36, -0.26, -0.28]
    start = MORNING.replace(hour=22)
    series = [(start + timedelta(hours=i), lv) for i, lv in enumerate(levels)]
    assert [(t.time.hour, t.kind) for t in find_tides(series)] == [(6, "high")]


def test_fr_4_2_both_days_keep_their_tides():
    levels = [
        -0.68,
        -0.73,
        -0.73,
        -0.59,
        -0.38,
        -0.26,
        -0.29,
        -0.44,
        -0.59,
        -0.64,
        -0.56,
        -0.42,
        -0.34,
        -0.34,
        -0.37,
        -0.33,
        -0.2,
        -0.12,
        -0.18,
        -0.37,
        -0.62,
        -0.82,
        -0.91,
        -0.88,
        -0.81,
        -0.78,
        -0.78,
        -0.71,
        -0.55,
        -0.36,
        -0.26,
        -0.28,
        -0.4,
        -0.54,
        -0.62,
        -0.59,
        -0.49,
        -0.4,
        -0.37,
        -0.34,
        -0.26,
        -0.14,
        -0.07,
        -0.1,
        -0.24,
        -0.46,
        -0.68,
        -0.82,
    ]
    start = MORNING.replace(hour=0)
    series = [(start + timedelta(hours=i), lv) for i, lv in enumerate(levels)]
    kinds = [tide.kind for tide in find_tides(series)]
    assert len(kinds) >= 6
    assert all(a != b for a, b in zip(kinds, kinds[1:], strict=False))


@respx.mock
def test_fr_6_1_fetches_a_station_for_today_and_tomorrow_in_local_time():
    route = respx.get(url__startswith=TideClient.URL).respond(
        text=tide_csv(datetime(2026, 11, 6, 9), [0.5, 1.0, 1.5, 1.0, 0.5])
    )
    with httpx.Client() as http:
        station = TideClient(http).fetch("Wicklow_MODELLED", date(2026, 11, 6))
    url = str(route.calls.last.request.url)
    assert "%22Wicklow_MODELLED%22" in url
    assert "time%3E=2026-11-05T21%3A00%3A00Z" in url  # 3 h before midnight
    assert "time%3C=2026-11-08T03%3A00%3A00Z" in url  # 3 h after the second midnight
    assert station.name == "Wicklow"
    assert station.levels[0] == (datetime(2026, 11, 6, 9), 0.5)  # GMT in November
    assert station.tides == [Tide(datetime(2026, 11, 6, 10), "high")]


def test_fr_6_1_times_are_irish_local_time_in_summer():
    (level,) = parse_levels(tide_csv(datetime(2026, 7, 1, 9), [1.2]))
    assert level == (datetime(2026, 7, 1, 10), 1.2)


def test_fr_6_1_skips_missing_values():
    text = tide_csv(datetime(2026, 11, 6, 9), [1.0, 2.0]).replace(",2.0", ",NaN")
    assert len(parse_levels(text)) == 1


@respx.mock
def test_fr_6_7_tide_service_failure_is_a_tide_error():
    respx.get(url__startswith=TideClient.URL).respond(500)
    with httpx.Client() as http, pytest.raises(TideError):
        TideClient(http).fetch("Arklow", date(2026, 11, 6))


@respx.mock
def test_fr_6_7_an_empty_answer_is_a_tide_error():
    respx.get(url__startswith=TideClient.URL).respond(text="time,Water_Level\nUTC,m\n")
    with httpx.Client() as http, pytest.raises(TideError):
        TideClient(http).fetch("Arklow", date(2026, 11, 6))


def test_fr_6_1_station_names_read_well():
    assert station_name("Wicklow_MODELLED") == "Wicklow"
    assert station_name("Dublin_Port") == "Dublin Port"
    assert StationTides("Arklow", [], []).name == "Arklow"


@pytest.mark.parametrize(
    ("minutes", "tag"),
    [(-50, "HW"), (0, "HW"), (90, "↓"), (240, "↓"), (330, "LW"), (-120, "↑")],
)
def test_fr_6_6_map_tag_is_hw_lw_or_rising_falling(minutes, tag):
    tides = [Tide(NOON, "high"), Tide(NOON + timedelta(hours=6), "low")]
    assert tide_tag(NOON + timedelta(minutes=minutes), tides) == tag


def test_fr_6_6_no_tag_without_a_next_tide():
    assert tide_tag(NOON, []) == ""


STATIONS = {
    "Arklow": {
        "name": "Arklow",
        "levels": [["2026-11-06T00:00", 0.6], ["2026-11-06T06:00", 1.2], ["2026-11-07T00:00", 0.7]],
    },
    "Dublin_Port": {
        "name": "Dublin Port",
        "levels": [["2026-11-06T00:00", 1.1], ["2026-11-06T06:00", 3.8], ["2026-11-06T12:00", 1.2]],
    },
}


def test_fr_6_4_chart_draws_one_line_per_station_and_shades_rideable_hours():
    from wing_alert.tidechart import tide_chart

    svg = tide_chart(STATIONS, "2026-11-06", {13, 14})
    assert svg.startswith("<svg") and svg.count("<polyline") == 2
    assert ">Arklow<" in svg and ">Dublin Port<" in svg
    assert svg.count('class="ride"') == 2
    assert "12:00</text>" in svg


def test_fr_6_4_no_chart_without_levels_for_the_day():
    from wing_alert.tidechart import tide_chart

    assert tide_chart(STATIONS, "2026-11-09", set()) == ""
    assert tide_chart({}, "2026-11-06", set()) == ""
