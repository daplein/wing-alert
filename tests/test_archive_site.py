import json
from datetime import date, datetime

from tests.helpers import ARKLOW, MORNING, SEAPOINT, SETTINGS, forecast, hours, window
from wing_alert.archive import Archive, build_snapshot, load_snapshots
from wing_alert.message import format_alert
from wing_alert.site import SiteBuilder, day_url, make_env, pages_by_date, wind_band

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


def run_covering(issued: datetime, *days: int) -> dict:
    """A run issued at `issued` with a good Arklow window at noon on each given day."""
    readings = [h for day in days for h in hours(NOON.replace(day=day), [18, 20, 18])]
    return build_snapshot(issued, [forecast(ARKLOW, readings)], SETTINGS)


def test_fr_9_3_each_date_comes_from_the_latest_run_covering_it():
    first, second = run_covering(MORNING, 6, 8), run_covering(MORNING.replace(day=7), 7, 8)
    pages = pages_by_date([second, first])
    assert pages["2026-11-06"] is first  # past: the last run issued that day
    assert pages["2026-11-07"] is second and pages["2026-11-08"] is second


def site_from(tmp_path, runs):
    out = tmp_path / "site"
    SiteBuilder(make_env(), [ARKLOW], tmp_path).build(runs, out)
    return out


def test_fr_9_3_one_day_per_page_and_later_days_are_an_outlook(tmp_path):
    out = site_from(tmp_path, [run_covering(MORNING, 6, 7, 8)])
    ahead = (out / "days/2026-11-08.html").read_text()
    assert "<h1>Sunday 8 November</h1>" in ahead and "Outlook" in ahead
    assert "<h1>Friday 6 November</h1>" not in ahead
    tomorrow = (out / "days/2026-11-07.html").read_text()
    assert "Outlook" not in tomorrow
    assert "<h1>Friday 6 November</h1>" in (out / "index.html").read_text()


def test_fr_9_4_day_strip_shows_peak_wind_and_links_neighbours(tmp_path):
    calm = build_snapshot(
        MORNING.replace(day=9), [forecast(ARKLOW, hours(NOON.replace(day=9), [5]))], SETTINGS
    )
    out = site_from(tmp_path, [run_covering(MORNING, 6, 7, 8), calm])
    page = (out / "days/2026-11-08.html").read_text()
    assert 'aria-current="page"' in page and "Sun 8" in page
    assert 'aria-label="Previous day"' in page and 'href="../days/2026-11-07.html"' in page
    assert page.count('<span class="peak strong">20 kn</span>') == 3  # 6, 7 and 8
    assert '<span class="peak none">–</span>' in page  # the 9th is calm
    assert 'href="../days/2026-11-09.html" aria-label="Next day"' in page


def test_fr_9_6_table_knows_its_first_hour_for_the_hover_link(tmp_path):
    out = site_from(tmp_path, [run_covering(MORNING, 6)])
    page = (out / "index.html").read_text()
    assert 'class="hours sun"' in page and 'data-first="7"' in page
    assert '<tr class="spot-row hourly">' in page


def test_fr_9_4_day_strip_names_the_shore_break_and_why():
    from wing_alert.site import _summary

    run = run_covering(MORNING, 6)
    run["windows"][0].update(shore_break=2, shore_break_reason="1.6 m waves at 6 s")
    assert _summary(run, "2026-11-06") == {
        "peak": 20,
        "band": "strong",
        "warning": 2,
        "reason": "1.6 m waves at 6 s",
        "spot_name": "Arklow South Beach",
    }


def test_fr_16_2_calendar_links_each_day_with_its_best_spot(tmp_path):
    out = site_from(tmp_path, [run_covering(MORNING, 6, 7)])
    archive = (out / "days.html").read_text()
    assert "<h2>November 2026" in archive
    assert 'href="days/2026-11-06.html"' in archive and 'href="days/2026-11-07.html"' in archive
    assert 'title="Arklow South Beach"' in archive
    assert '<div class="day off"><span class="num">5</span></div>' in archive  # no page


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


def test_fr_2_4_pages_carry_the_wing_logo(tmp_path):
    out = build(tmp_path, [MORNING])
    index = (out / "index.html").read_text()
    assert 'src="logo.svg"' in index
    assert 'rel="icon" href="logo.svg"' in index
    assert (out / "logo.svg").exists()


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


def test_fr_8_3_spots_page_adds_guides_without_a_spot(tmp_path):
    out = build(tmp_path, [MORNING], {"malahide": "# Malahide\n"})
    page = (out / "spots.html").read_text()
    assert 'href="#malahide">Malahide</a>' in page
    assert 'id="malahide"' in page and "No forecast" in page


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


def test_fr_12_1_tags_the_hour_nearest_each_tide():
    from wing_alert.site import _tide_tags

    spot = {
        "tides": [
            {"time": "2026-11-06T09:05", "kind": "high"},
            {"time": "2026-11-06T13:40", "kind": "low"},
            {"time": "2026-11-07T10:00", "kind": "high"},
        ]
    }
    assert _tide_tags(spot, "2026-11-06") == {
        9: {"kind": "high", "time": "09:05"},
        14: {"kind": "low", "time": "13:40"},
    }


def test_fr_12_3_no_line_under_the_spot_and_the_warning_says_why(tmp_path):
    run = run_covering(MORNING, 6)
    run["windows"][0].update(shore_break=1, shore_break_reason="1.1 m waves at 5 s")
    page = (site_from(tmp_path, [run]) / "index.html").read_text()
    assert 'class="details"' not in page
    assert 'title="12:00–15:00 · Shore break: watch out · 1.1 m waves at 5 s"' in page


def test_fr_13_1_hours_sit_in_a_pinned_header_with_the_same_columns(tmp_path):
    page = (site_from(tmp_path, [run_covering(MORNING, 6)]) / "index.html").read_text()
    pinned = page[page.index('<div class="pinned">') : page.index('<div class="scroll">')]
    assert "<th>08</th>" in pinned and pinned.count("<col>") == page.count("<col>") // 2
    assert "<thead>" not in page[page.index('<div class="scroll">') :]


def test_fr_13_2_every_hourly_row_takes_part_in_the_hour_cursor(tmp_path):
    page = (site_from(tmp_path, [run_covering(MORNING, 6)]) / "index.html").read_text()
    assert '<tr class="spot-row hourly">' in page and 'closest("tr.hourly td")' in page


def test_fr_13_3_sun_times_and_how_far_into_the_hour():
    from wing_alert.site import _sun

    sun = _sun({"sunrise": "2026-11-05T07:30", "sunset": "2026-11-05T16:45"}, list(range(7, 17)))
    assert sun["rise"] == "07:30" and sun["set"] == "16:45"
    assert sun["rise_pct"] == 50.0 and sun["set_pct"] == 75.0
    assert sun["chart_rise_pct"] == 5.0 and sun["chart_set_pct"] == 97.5  # of 10 hours
    assert _sun(None, [7, 8]) is None


def test_fr_13_3_pinned_row_says_when_the_sun_rises_and_sets(tmp_path):
    page = (site_from(tmp_path, [run_covering(MORNING, 6)]) / "index.html").read_text()
    pinned = page[page.index('<div class="pinned">') : page.index('<div class="scroll">')]
    assert '<span class="icon">🌅</span> 07:' in pinned
    assert '<span class="icon">🌇</span> 16:' in pinned
    assert "--rise: " in page and "--chart-set: " in page
