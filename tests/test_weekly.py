import json
from datetime import date

import respx

from tests.helpers import ARKLOW, MORNING, SEAPOINT, SETTINGS, forecast, hours
from wing_alert.archive import Archive, build_snapshot, load_snapshots
from wing_alert.site import SiteBuilder, make_env
from wing_alert.weekly import (
    main,
    morning_runs,
    summarise,
    summary_line,
    was_alerted,
    week_url,
)
from wing_alert.whatsapp import CallMeBotSender

SUNDAY = date(2026, 11, 8)


def run(day: int, hour: int, spot, winds, start_hour=12, direction=70):
    issued = MORNING.replace(day=day, hour=hour)
    readings = hours(MORNING.replace(day=day, hour=start_hour), winds, direction=direction)
    return issued, [forecast(spot, readings)]


def archive_week(data):
    """Thu: Arklow good in the morning run, weaker by evening. Fri: Seapoint. Sat: calm."""
    runs = [
        run(5, 7, ARKLOW, [20] * 3),
        run(5, 16, ARKLOW, [5] * 3),
        run(6, 7, SEAPOINT, [18, 18], start_hour=10, direction=270),
        run(7, 7, ARKLOW, [4, 4]),
    ]
    for issued, conditions in runs:
        Archive(data).save(build_snapshot(issued, conditions, SETTINGS))


def test_fr_5_2_uses_each_days_morning_run(tmp_path):
    archive_week(tmp_path)
    mornings = morning_runs(load_snapshots(tmp_path))
    assert mornings["2026-11-05"]["issued"] == "2026-11-05T07:00"


def test_fr_5_3_overlap_at_the_same_spot_counts_as_alerted():
    window = {"spot": "arklow", "start": "2026-11-05T12:00", "end": "2026-11-05T15:00"}
    assert was_alerted(window, ["arklow@14-16"])
    assert not was_alerted(window, ["arklow@15-17", "seapoint@12-15"])


def test_fr_5_1_summarises_the_last_seven_days(tmp_path):
    archive_week(tmp_path)
    sent = {"2026-11-05": ["arklow@12-15"]}
    week = summarise(load_snapshots(tmp_path), sent, SUNDAY)
    assert (week["start"], week["end"]) == ("2026-11-02", "2026-11-08")
    assert len(week["days"]) == 7
    assert week["good_days"] == 2
    assert week["missed"] == 1
    assert week["best"]["spot"] == "arklow"
    thursday = next(day for day in week["days"] if day["date"] == "2026-11-05")
    assert thursday["windows"][0]["alerted"] is True
    monday = week["days"][0]
    assert monday == {"date": "2026-11-02", "forecast": False, "windows": []}


def test_fr_5_4_summary_is_one_line_with_the_link():
    week = {"start": "2026-11-02", "good_days": 1, "missed": 0}
    link = week_url("https://daplein.github.io/wing-alert/", "2026-11-02")
    assert summary_line(week, link) == (
        "🪁 Week of 2 Nov: 1 good day, 0 missed → "
        "https://daplein.github.io/wing-alert/weeks/2026-11-02.html"
    )


@respx.mock
def test_fr_5_4_weekly_job_saves_the_week_and_sends_one_line(tmp_path, monkeypatch, capsys):
    archive_week(tmp_path / "data")
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"sent": {"2026-11-05": ["arklow@12-15"]}}))
    monkeypatch.setenv("WHATSAPP_RECIPIENTS", "+353861234567:999")
    whatsapp = respx.get(CallMeBotSender.URL).respond(text="ok")
    args = ["--data", str(tmp_path / "data"), "--state", str(state)]
    assert main(args, today=SUNDAY) == 0
    assert "2 good days, 1 missed" in whatsapp.calls.last.request.url.params["text"]
    saved = json.loads((tmp_path / "data/weeks/2026-11-02.json").read_text())
    assert saved["good_days"] == 2
    assert "Week of 2 Nov" in capsys.readouterr().out


def test_fr_5_4_weekly_job_without_state_or_recipients(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("WHATSAPP_RECIPIENTS", raising=False)
    args = ["--data", str(tmp_path / "data"), "--state", str(tmp_path / "none.json")]
    assert main(args, today=SUNDAY) == 0
    assert "0 good days, 0 missed" in capsys.readouterr().out


def test_fr_5_4_bad_recipients_fail_cleanly(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WHATSAPP_RECIPIENTS", "nonsense")
    assert main(["--data", str(tmp_path)], today=SUNDAY) == 1
    assert "weekly failed" in capsys.readouterr().err


def test_fr_5_4_week_page_lists_alerted_and_missed(tmp_path):
    archive_week(tmp_path / "data")
    snapshots = load_snapshots(tmp_path / "data")
    week = summarise(snapshots, {"2026-11-05": ["arklow@12-15"]}, SUNDAY)
    out = tmp_path / "site"
    SiteBuilder(make_env(), [ARKLOW, SEAPOINT], tmp_path).build(snapshots, out, weeks=[week])
    page = (out / "weeks/2026-11-02.html").read_text()
    assert "✅ Arklow South Beach 12:00–15:00" in page
    assert "❌ missed Seapoint 10:00–12:00" in page
    assert "No forecast" in page and "Nothing rideable" in page
    assert 'href="weeks/2026-11-02.html"' in (out / "index.html").read_text()
