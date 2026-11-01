import json
from datetime import date, datetime

from tests.helpers import ARKLOW, MORNING, SEAPOINT, SETTINGS, forecast, hours, window
from wing_alert.archive import Archive, build_snapshot, load_snapshots
from wing_alert.message import format_alert
from wing_alert.site import SiteBuilder, day_url, latest_per_day, make_env, wind_band

NOON = MORNING.replace(hour=12)


def forecasts(start=NOON):
    return [
        forecast(ARKLOW, hours(start, [18, 22, 20], gust=27, direction=70)),
        forecast(SEAPOINT, hours(start, [12, 12, 12], direction=150)),
    ]


def test_fr_2_1_writes_one_json_file_per_run(tmp_path):
    path = Archive(tmp_path).save(build_snapshot(MORNING, forecasts(), SETTINGS))
    assert path == tmp_path / "2026/11/2026-11-06T07.json"
    data = json.loads(path.read_text())
    assert data["issued"] == "2026-11-06T07:00"
    assert data["settings"]["min_wind"] == 10
    assert (data["spots"][0]["lat"], data["spots"][0]["lon"]) == (52.79, -6.14)
    assert data["spots"][0]["hours"][0] == {
        "time": "2026-11-06T12:00",
        "wind": 18,
        "gust": 27,
        "direction": 70,
        "good": True,
    }
    assert data["spots"][1]["hours"][0]["good"] is False  # SSE is onshore-only at Seapoint
    assert [w["spot"] for w in data["windows"]] == ["arklow"]
    assert load_snapshots(tmp_path) == [data]


def test_fr_2_1_archive_keeps_hours_already_past():
    afternoon = datetime(2026, 11, 6, 16)
    snapshot = build_snapshot(afternoon, forecasts(), SETTINGS)
    assert snapshot["windows"][0]["start"] == "2026-11-06T12:00"


def test_fr_2_3_latest_run_of_each_day_wins():
    runs = [
        {"issued": "2026-11-06T16:00"},
        {"issued": "2026-11-06T07:00"},
        {"issued": "2026-11-05T16:00"},
    ]
    latest = latest_per_day(runs)
    assert latest["2026-11-06"]["issued"] == "2026-11-06T16:00"
    assert sorted(latest) == ["2026-11-05", "2026-11-06"]


def build(tmp_path, issued_list, guides=None):
    data = tmp_path / "data"
    for issued in issued_list:
        Archive(data).save(build_snapshot(issued, forecasts(issued.replace(hour=12)), SETTINGS))
    guides_dir = tmp_path / "guides"
    guides_dir.mkdir()
    for spot_id, text in (guides or {}).items():
        (guides_dir / f"{spot_id}.md").write_text(text)
    out = tmp_path / "site"
    SiteBuilder(make_env(), [ARKLOW, SEAPOINT], guides_dir).build(load_snapshots(data), out)
    return out


def test_fr_2_3_day_page_shows_best_spot_table_and_neighbours(tmp_path):
    out = build(tmp_path, [MORNING, MORNING.replace(day=7)])
    page = (out / "days/2026-11-06.html").read_text()
    assert "Best spot" in page and "Arklow South Beach" in page and "12:00–15:00" in page
    assert page.index("Arklow South Beach") < page.index("Seapoint")
    assert 'href="../days/2026-11-07.html"' in page
    assert 'class="good ok"' in page
    assert "Nothing rideable" not in page


def test_fr_2_3_day_without_windows_says_nothing_rideable(tmp_path):
    data = tmp_path / "data"
    calm = [forecast(ARKLOW, hours(NOON, [5, 5]))]
    Archive(data).save(build_snapshot(MORNING, calm, SETTINGS))
    out = tmp_path / "site"
    SiteBuilder(make_env(), [ARKLOW], tmp_path).build(load_snapshots(data), out)
    assert "Nothing rideable" in (out / "index.html").read_text()


def test_fr_2_4_front_page_is_latest_day_with_past_days(tmp_path):
    out = build(tmp_path, [MORNING, MORNING.replace(day=7)])
    index = (out / "index.html").read_text()
    assert "Saturday 7 November" in index
    assert 'href="days/2026-11-06.html"' in index
    assert (out / "style.css").exists()


def test_fr_2_4_empty_archive_still_builds(tmp_path):
    out = tmp_path / "site"
    SiteBuilder(make_env(), [ARKLOW], tmp_path).build([], out)
    assert "No forecasts yet" in (out / "index.html").read_text()


def test_fr_2_5_alert_ends_with_the_day_page_link():
    link = day_url("https://daplein.github.io/wing-alert/", date(2026, 11, 6))
    assert link == "https://daplein.github.io/wing-alert/days/2026-11-06.html"
    text = format_alert([window(ARKLOW, NOON, [20, 20])], link)
    assert text.endswith("\n" + link)


def test_fr_2_6_site_credits_open_meteo(tmp_path):
    out = build(tmp_path, [MORNING])
    assert 'href="https://open-meteo.com/"' in (out / "index.html").read_text()


def test_fr_2_7_spots_page_renders_guides_and_placeholders(tmp_path):
    out = build(tmp_path, [MORNING], {"arklow": "# Arklow\n\n- Watch the **buoys**"})
    page = (out / "spots.html").read_text()
    assert 'id="arklow"' in page and "<strong>buoys</strong>" in page
    assert 'id="seapoint"' in page and "No guide yet" in page
    day = (out / "index.html").read_text()
    assert 'href="spots.html#arklow"' in day


def test_wind_bands():
    assert [wind_band(k) for k in (5, 10, 25, 35)] == ["light", "good", "strong", "wild"]


def test_fr_2_2_site_command_builds_from_the_archive(tmp_path, capsys):
    from pathlib import Path

    from wing_alert.site import main

    data = tmp_path / "data"
    Archive(data).save(build_snapshot(MORNING, forecasts(), SETTINGS))
    repo = Path(__file__).parents[1]
    out = tmp_path / "site"
    args = [
        "--data",
        str(data),
        "--config",
        str(repo / "config"),
        "--guides",
        str(repo / "docs/spots"),
    ]
    assert main([*args, "--out", str(out)]) == 0
    assert "Arklow" in (out / "spots.html").read_text()
