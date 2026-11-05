import json

from tests.helpers import ARKLOW, MORNING, SEAPOINT, SETTINGS, forecast, hours
from wing_alert.archive import build_snapshot
from wing_alert.coast import load_coast
from wing_alert.mapdata import coast_data, map_data, map_hours
from wing_alert.site import SiteBuilder, make_env


def snapshot(start_hour=8, count=12):
    start = MORNING.replace(hour=start_hour)
    return build_snapshot(
        MORNING,
        [
            forecast(ARKLOW, hours(start, [18.4] * count, direction=70)),
            forecast(SEAPOINT, hours(start, [32] * count, direction=270)),
        ],
        SETTINGS,
    )


def test_fr_3_1_one_map_per_hour_with_every_spots_reading():
    data = map_data(snapshot(), "2026-11-06")
    assert data["title"] == "Fri 6 Nov"
    assert data["hours"] == ["09", "12", "15"]  # sunset 16:50
    arklow = data["spots"][0]
    assert (arklow["name"], arklow["lat"], arklow["lon"]) == (ARKLOW.name, ARKLOW.lat, ARKLOW.lon)
    assert arklow["at"]["12"] == {
        "wind": 18,
        "gust": arklow["at"]["12"]["gust"],
        "direction": 70,
        "knots": 18.4,
        "tide": "",
    }


def light(rise: str, sunset: str) -> dict[str, str]:
    return {"sunrise": f"2026-06-21T{rise}", "sunset": f"2026-06-21T{sunset}"}


def test_fr_3_1_winter_maps_stop_before_dark():
    assert map_hours(light("07:30", "16:44")) == (9, 12, 15)


def test_fr_3_1_summer_maps_run_from_six_to_nine():
    assert map_hours(light("05:00", "21:57")) == (6, 9, 12, 15, 18, 21)


def test_fr_3_1_a_map_on_the_minute_of_sunrise_counts():
    assert map_hours(light("06:00", "18:00")) == (6, 9, 12, 15, 18)


def test_fr_3_1_without_sunrise_and_sunset_maps_run_nine_to_six():
    assert map_hours(None) == (9, 12, 15, 18)


def test_fr_3_1_hours_no_spot_has_get_no_map():
    assert map_data(snapshot(start_hour=11, count=3), "2026-11-06")["hours"] == ["12"]


def test_fr_6_6_map_label_carries_the_tide_at_that_hour():
    run = snapshot()
    run["spots"][0]["tides"] = [{"time": "2026-11-06T12:30", "kind": "high"}]
    at = map_data(run, "2026-11-06")["spots"][0]["at"]
    assert at["12"]["tide"] == "HW"
    assert at["09"]["tide"] == "↑"


def test_fr_3_5_coastline_is_published_once_for_the_browser(tmp_path):
    out = tmp_path / "site"
    SiteBuilder(make_env(), [ARKLOW], tmp_path).build([snapshot()], out)
    coast = json.loads((out / "maps/coast.json").read_text())
    assert len(coast["land"]) == len(coast_data(load_coast())["land"]) > 0
    assert (out / "windmap.js").exists()


def test_fr_9_7_day_page_has_hour_buttons_and_maps_in_order(tmp_path):
    out = tmp_path / "site"
    SiteBuilder(make_env(), [ARKLOW], tmp_path).build([snapshot()], out)
    page = (out / "index.html").read_text()
    holders = [f'<div class="windmap" data-hour="{h}"' for h in ("09", "12", "15")]
    assert [page.index(h) for h in holders] == sorted(page.index(h) for h in holders)
    assert page.count('<button type="button" data-hour=') == 3
    assert '<div class="images" style="--cols: 3">' in page
    assert '<script type="application/json" id="map-data">' in page


def test_fr_9_7_more_than_four_maps_wrap_in_rows_of_three(tmp_path):
    run = snapshot(start_hour=5, count=18)
    run["daylight"]["2026-11-06"] = {"sunrise": "2026-11-06T05:00", "sunset": "2026-11-06T21:57"}
    out = tmp_path / "site"
    SiteBuilder(make_env(), [ARKLOW], tmp_path).build([run], out)
    page = (out / "index.html").read_text()
    assert page.count('<button type="button" data-hour=') == 6
    assert '<div class="images" style="--cols: 3">' in page


def test_fr_9_7_maps_know_the_day_before_and_after(tmp_path):
    run = snapshot(count=40)  # 08:00 on the 6th to 23:00 on the 7th
    out = tmp_path / "site"
    SiteBuilder(make_env(), [ARKLOW], tmp_path).build([run], out)
    first = (out / "days/2026-11-06.html").read_text()
    assert '<section class="maps" data-previous="" data-next="../days/2026-11-07.html">' in first
    last = (out / "days/2026-11-07.html").read_text()
    assert '<section class="maps" data-previous="../days/2026-11-06.html" data-next="">' in last
