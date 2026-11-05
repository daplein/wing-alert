from wing_alert.month_grid import months

TODAY = "2026-11-05"


def day(peak=None, spot=None):
    return {"peak": peak, "band": None, "warning": 0, "reason": "", "spot_name": spot}


def cells(month):
    return {c["date"]: c for week in month["weeks"] for c in week["days"] if c}


def test_fr_16_1_only_months_with_a_day_page_newest_first():
    shown = months({"2026-10-31": day(), "2026-11-01": day()}, [], TODAY)
    assert [m["label"] for m in shown] == ["November 2026", "October 2026"]


def test_fr_16_1_weeks_run_monday_to_sunday_and_other_months_are_blank():
    first_week = months({"2026-11-01": day()}, [], TODAY)[0]["weeks"][0]["days"]
    assert first_week[:6] == [None] * 6 and first_week[6]["date"] == "2026-11-01"


def test_fr_16_1_a_day_without_a_page_has_no_summary():
    november = cells(months({"2026-11-01": day()}, [], TODAY)[0])
    assert november["2026-11-02"]["summary"] is None
    assert november["2026-11-01"]["summary"] == day()


def test_fr_16_2_marks_today_and_the_outlook_days():
    november = cells(months({TODAY: day()}, [], TODAY)[0])
    assert november["2026-11-05"]["today"] and not november["2026-11-05"]["outlook"]
    assert not november["2026-11-06"]["outlook"]  # tomorrow
    assert november["2026-11-07"]["outlook"]


def test_fr_16_3_week_report_sits_on_the_row_with_its_sunday():
    report = {"start": "2026-10-26", "good_days": 0, "missed": 0, "best": None}
    summaries = {"2026-10-31": day(), "2026-11-01": day()}
    november, october = months(summaries, [report], TODAY)
    assert november["weeks"][0]["report"] is report
    assert october["weeks"][-1]["report"] is None and not october["weeks"][-1]["pending"]


def test_fr_16_3_only_this_week_waits_for_its_report():
    weeks = months({"2026-11-01": day()}, [], TODAY)[0]["weeks"]
    assert not weeks[0]["pending"]  # ended 1 Nov, its report just never came
    assert weeks[1]["pending"]  # 2 to 8 Nov, still running
    assert not weeks[2]["pending"]  # 9 to 15 Nov, not started


def test_fr_16_4_counts_rideable_days_up_to_today_and_the_usual_best_spot():
    summaries = {
        "2026-11-02": day(16, "Seapoint"),
        "2026-11-03": day(17, "Arklow"),
        "2026-11-04": day(),
        "2026-11-06": day(20, "Arklow"),  # an outlook: not counted
    }
    november = months(summaries, [], TODAY)[0]
    assert november["rideable"] == 2 and november["mostly"] == "Seapoint"  # tie: seen first


def test_fr_16_4_no_rideable_days():
    november = months({"2026-11-04": day()}, [], TODAY)[0]
    assert november["rideable"] == 0 and november["mostly"] is None
