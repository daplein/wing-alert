import json
from datetime import date, datetime

from tests.helpers import ARKLOW, SEAPOINT, window
from wing_alert.message import format_alert
from wing_alert.state import AlertState

FRI_1PM = datetime(2026, 11, 6, 13)
SAT_10AM = datetime(2026, 11, 7, 10)


def test_fr_1_6_message_has_one_short_line_per_window_grouped_by_day():
    ranked = [
        window(SEAPOINT, SAT_10AM, [15, 18], gust=26, direction=270),
        window(ARKLOW, FRI_1PM, [18, 22, 20, 19], gust=27, direction=70),
    ]
    assert format_alert(ranked) == (
        "🪁 Wing alert\n"
        "Fri 6 Nov\n"
        "• Arklow South Beach 13:00–17:00 · 18–22 kn ENE, gusts 27\n"
        "Sat 7 Nov\n"
        "• Seapoint 10:00–12:00 · 15–18 kn W, gusts 26"
    )


def test_fr_1_6_steady_wind_shows_a_single_value():
    assert "· 18 kn" in format_alert([window(ARKLOW, FRI_1PM, [18, 18])])


def test_fr_1_7_new_windows_are_changed_then_not_after_recording(tmp_path):
    state = AlertState(tmp_path / "state.json")
    windows = [window(ARKLOW, FRI_1PM, [20, 20])]
    assert state.changed_days(windows) == {date(2026, 11, 6)}
    state.record(windows, date(2026, 11, 6))
    state.save()
    assert AlertState(tmp_path / "state.json").changed_days(windows) == set()


def test_fr_1_7_a_window_moving_by_an_hour_counts_as_changed(tmp_path):
    state = AlertState(tmp_path / "state.json")
    state.record([window(ARKLOW, FRI_1PM, [20, 20])], date(2026, 11, 6))
    later = [window(ARKLOW, FRI_1PM, [20, 20, 20])]
    assert state.changed_days(later) == {date(2026, 11, 6)}


def test_fr_1_7_only_the_changed_day_is_reported(tmp_path):
    state = AlertState(tmp_path / "state.json")
    thursday = window(ARKLOW, FRI_1PM, [20, 20])
    state.record([thursday], date(2026, 11, 6))
    friday = window(SEAPOINT, SAT_10AM, [20, 20])
    assert state.changed_days([thursday, friday]) == {date(2026, 11, 7)}


def test_fr_1_7_old_days_are_pruned(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"sent": {"2026-10-01": ["arklow@13-15"]}}))
    state = AlertState(path)
    state.record([window(ARKLOW, FRI_1PM, [20, 20])], date(2026, 11, 6))
    state.save()
    assert json.loads(path.read_text()) == {"sent": {"2026-11-06": ["arklow@13-15"]}}
