from dataclasses import replace
from datetime import datetime

import pytest

from tests.helpers import ARKLOW, MORNING, SETTINGS, forecast, hours, window
from wing_alert.scoring import (
    compass_point,
    find_windows,
    in_direction_range,
    mean_direction,
    rank,
)

NOON = datetime(2026, 11, 6, 12)


def windows_for(hour_list, now=MORNING, settings=SETTINGS):
    return find_windows(forecast(ARKLOW, hour_list), settings, now)


def test_fr_1_3_good_wind_makes_a_window():
    (found,) = windows_for(hours(NOON, [15, 18, 20]))
    assert (found.start, found.end) == (NOON, datetime(2026, 11, 6, 15))


@pytest.mark.parametrize("wind", [9, 41])
def test_fr_1_3_wind_outside_range_is_not_good(wind):
    assert windows_for(hours(NOON, [wind, wind])) == []


def test_fr_1_3_gusts_over_the_limit_are_not_good():
    assert windows_for(hours(NOON, [20, 20], gust=46)) == []


def test_fr_1_3_skips_offshore_wind():
    assert windows_for(hours(NOON, [20, 20], direction=270)) == []


@pytest.mark.parametrize(
    ("direction", "start", "end", "inside"),
    [
        (70, 337, 202, True),
        (350, 337, 202, True),
        (0, 337, 202, True),
        (270, 337, 202, False),
        (150, 90, 248, True),
        (0, 90, 248, False),
        (360, 280, 20, True),
        (100, 280, 20, False),
    ],
)
def test_fr_1_3_direction_ranges_wrap_through_north(direction, start, end, inside):
    assert in_direction_range(direction, start, end) is inside


def test_fr_1_3_whole_hour_must_be_in_daylight_with_margin():
    # Sunrise 07:30 + 30 min = 08:00; sunset 16:50 - 30 min = 16:20.
    early = hours(datetime(2026, 11, 6, 7), [20, 20, 20])
    late = hours(datetime(2026, 11, 6, 14), [20, 20, 20])
    assert [(w.start.hour, w.end.hour) for w in windows_for(early)] == [(8, 10)]
    assert [(w.start.hour, w.end.hour) for w in windows_for(late)] == [(14, 16)]


def test_fr_1_3_ignores_hours_already_past_but_keeps_the_current_one():
    (found,) = windows_for(hours(NOON, [20, 20, 20]), now=datetime(2026, 11, 6, 13, 40))
    assert found.start == datetime(2026, 11, 6, 13)
    assert windows_for(hours(NOON, [20, 20, 20]), now=datetime(2026, 11, 6, 14, 10)) == []


def test_fr_1_4_needs_minimum_consecutive_good_hours():
    assert windows_for(hours(NOON, [20, 5, 20])) == []
    longer = replace(SETTINGS, min_window_hours=3)
    assert windows_for(hours(NOON, [20, 20]), settings=longer) == []


def test_fr_1_4_window_reports_range_gust_and_direction():
    found = window(ARKLOW, NOON, [16, 22, 18], gust=27, direction=70)
    assert (found.wind_min, found.wind_max, found.gust_max, found.direction) == (16, 22, 27, "ENE")


def test_fr_1_4_mean_direction_handles_north():
    assert compass_point(mean_direction([350, 10])) == "N"
    assert compass_point(337) == "NNW"


def test_fr_1_5_ranks_by_length_then_closeness_to_ideal():
    short = window(ARKLOW, NOON, [20, 20])
    long_light = window(ARKLOW, NOON, [12, 12, 12])
    long_ideal = window(ARKLOW, NOON, [19, 21, 20])
    assert rank([short, long_light, long_ideal], SETTINGS) == [long_ideal, long_light, short]
