import json

from tests.helpers import ARKLOW, MORNING, SETTINGS, forecast, hours
from wing_alert.archive import Archive, build_snapshot
from wing_alert.measured import (
    bearing,
    distance_km,
    eight_point,
    load_observations,
    readings_by_hour,
    stations_about,
    where,
)
from wing_alert.site import SiteBuilder, make_env

NOON = MORNING.replace(hour=12)
DUBLIN_BAY = {"id": "dublin_bay", "name": "Dublin Bay Buoy", "lat": 53.3319, "lon": -6.0774}
M5 = {"id": "m5", "name": "M5 buoy", "lat": 51.6904, "lon": -6.7043}
SPOTS = [
    {"name": "Seapoint", "lat": 53.2972, "lon": -6.1589},
    {"name": "Arklow", "lat": 52.7878, "lon": -6.1434},
]


def reading(time: str, wind: float | None = 15, **extra) -> dict:
    return {"time": time, "wind": wind, "gust": 21, "direction": 270, **extra}


def obs(day: str, stations: dict, about=(DUBLIN_BAY, M5)) -> dict:
    return {day: {"day": day, "stations": stations, "about": list(about)}}


def test_fr_11_1_last_reading_in_each_dublin_hour():
    observations = obs(
        "2026-11-06",
        {"dublin_bay": [reading("2026-11-06T12:05Z", 14), reading("2026-11-06T12:38Z", 16)]},
    )
    by_hour = readings_by_hour(observations, "2026-11-06")
    assert by_hour["dublin_bay"][12]["wind"] == 16


def test_fr_11_1_summer_hours_are_irish_time_across_two_utc_days():
    observations = {
        **obs("2026-07-01", {"m5": [reading("2026-07-01T23:00Z"), reading("2026-07-01T22:00Z")]}),
        **obs("2026-07-02", {"m5": [reading("2026-07-02T11:00Z")]}),
    }
    by_hour = readings_by_hour(observations, "2026-07-02")
    assert sorted(by_hour["m5"]) == [0, 12]  # 23:00 UTC is midnight in Dublin; 22:00 isn't today


def test_fr_11_2_says_how_far_and_which_way_from_the_nearest_spot():
    assert where(DUBLIN_BAY, SPOTS) == "7 km NE of Seapoint"
    assert where(M5, SPOTS) == "128 km S of Arklow"
    assert where(M5, []) == ""


def test_fr_11_2_distance_and_bearing():
    north = {"lat": 54.0, "lon": -6.0}
    assert round(distance_km({"lat": 53.0, "lon": -6.0}, north)) == 111
    assert round(bearing({"lat": 53.0, "lon": -6.0}, north)) == 0
    assert [eight_point(d) for d in (0, 44, 100, 350)] == ["N", "NE", "E", "N"]


def test_fr_11_1_stations_follow_the_newest_list():
    pier = {"id": "east_pier", "name": "East Pier", "lat": 53.3, "lon": -6.12}
    observations = {
        **obs("2026-11-03", {}, (DUBLIN_BAY, M5)),
        **obs("2026-11-04", {}, (pier, {**DUBLIN_BAY, "name": "Dublin Bay"})),
    }
    about = stations_about(observations)
    assert list(about) == ["east_pier", "dublin_bay", "m5"]
    assert about["dublin_bay"]["name"] == "Dublin Bay"


def test_fr_10_6_loads_kept_readings_by_utc_day(tmp_path):
    (tmp_path / "2026-11-06.json").write_text(json.dumps(obs("2026-11-06", {})["2026-11-06"]))
    assert list(load_observations(tmp_path)) == ["2026-11-06"]


def site(tmp_path, observations, issued=MORNING):
    run = build_snapshot(issued, [forecast(ARKLOW, hours(NOON, [18, 20, 18]))], SETTINGS)
    out = tmp_path / "site"
    SiteBuilder(make_env(), [ARKLOW], tmp_path).build([run], out, observations=observations)
    return (out / "days/2026-11-06.html").read_text()


def test_fr_11_1_measured_rows_under_the_spots_never_outlined(tmp_path):
    readings = [reading("2026-11-06T12:30Z", 22, wave_height=0.8), reading("2026-11-06T13:00Z")]
    page = site(tmp_path, obs("2026-11-06", {"dublin_bay": readings}))
    assert page.index('<tr class="spot-row hourly">') < page.index("Measured")
    row = page[
        page.index('data-station="dublin_bay"') : page.index("</tr>", page.index("dublin_bay"))
    ]
    assert 'class="strong" title="12:30: 22 kn, gusts 21, from 270°"' in row
    assert "ok" not in row
    assert "km N of Arklow South Beach" in row


def test_fr_11_2_waves_line_under_the_wind_hour_by_hour(tmp_path):
    readings = [
        reading("2026-11-06T12:30Z", wave_height=0.8, wave_period=5.4),
        reading("2026-11-06T13:00Z", None, wave_height=1.1),
    ]
    page = site(tmp_path, obs("2026-11-06", {"dublin_bay": readings}))
    waves = page[page.index('<tr class="waves measured-waves') : page.index("</tbody>")]
    assert 'title="12:30: waves 0.8 m, every 5 s">0.8<small>5s</small>' in waves
    assert 'title="13:00: waves 1.1 m">1.1</td>' in waves  # no wind, still waves


def test_fr_11_4_todays_page_lists_every_station_to_fill_in_live(tmp_path):
    page = site(tmp_path, obs("2026-11-05", {"m5": [reading("2026-11-05T12:00Z")]}))
    assert 'data-station="dublin_bay"' in page and 'data-station="m5"' in page
    assert '<tr class="waves measured-waves hourly" data-station="dublin_bay">' in page
    assert "workers.dev/obs" in page and '<p class="now" hidden>' in page


def test_fr_11_3_past_days_only_show_stations_with_readings(tmp_path):
    later = MORNING.replace(day=8)
    run = build_snapshot(MORNING, [forecast(ARKLOW, hours(NOON, [18, 20, 18]))], SETTINGS)
    newer = build_snapshot(later, [forecast(ARKLOW, hours(NOON.replace(day=8), [18]))], SETTINGS)
    out = tmp_path / "site"
    observations = obs("2026-11-06", {"m5": [reading("2026-11-06T12:00Z", None)]})
    SiteBuilder(make_env(), [ARKLOW], tmp_path).build([run, newer], out, observations=observations)
    page = (out / "days/2026-11-06.html").read_text()
    assert 'data-station="m5"' in page and 'data-station="dublin_bay"' not in page
    assert '<tr class="measured-row hourly" data-station="m5">' in page


def test_fr_11_2_no_waves_line_for_a_station_without_a_wave_sensor(tmp_path):
    pier = {"id": "east_pier", "name": "East Pier", "lat": 53.3, "lon": -6.12, "waves": False}
    observations = obs("2026-11-06", {"east_pier": [reading("2026-11-06T12:00Z")]}, (pier,))
    page = site(tmp_path, observations)
    assert 'data-station="east_pier"' in page
    assert '<tr class="waves measured-waves hourly" data-station="east_pier">' not in page


def test_fr_11_1_station_missing_from_about_uses_its_id(tmp_path):
    page = site(tmp_path, obs("2026-11-06", {"kish": [reading("2026-11-06T12:00Z")]}, about=()))
    assert "<th>kish</th>" in page


def test_fr_11_3_site_command_reads_kept_readings(tmp_path):
    from pathlib import Path

    from wing_alert.site import main

    data = tmp_path / "data"
    Archive(data).save(build_snapshot(MORNING, [forecast(ARKLOW, hours(NOON, [18]))], SETTINGS))
    (data / "obs").mkdir()
    record = obs("2026-11-06", {"m5": [reading("2026-11-06T12:00Z")]})["2026-11-06"]
    (data / "obs/2026-11-06.json").write_text(json.dumps(record))
    repo = Path(__file__).parents[1]
    out = tmp_path / "site"
    args = ["--data", str(data), "--config", str(repo / "config"), "--guides", str(tmp_path)]
    assert main([*args, "--out", str(out)]) == 0
    assert 'data-station="m5"' in (out / "index.html").read_text()


def test_fr_11_4_live_readings_before_the_first_hour_leave_the_name_alone(tmp_path):
    page = site(tmp_path, obs("2026-11-05", {"m5": [reading("2026-11-05T12:00Z")]}))
    assert "column >= 1 ? row.cells[column] : null" in page
