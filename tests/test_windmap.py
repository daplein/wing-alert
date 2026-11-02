from pathlib import Path

from tests.helpers import ARKLOW, MORNING, SEAPOINT, SETTINGS, forecast, hours
from wing_alert.archive import build_snapshot
from wing_alert.config import load_spots
from wing_alert.site import SiteBuilder, make_env
from wing_alert.windmap import DUBLIN_BAY, WICKLOW, MapWriter, spread

PNG = b"\x89PNG"
REPO_SPOTS = Path(__file__).parents[1] / "config" / "spots.yaml"


def snapshot():
    start = MORNING.replace(hour=8)
    return build_snapshot(
        MORNING,
        [
            forecast(ARKLOW, hours(start, [18] * 12, direction=70)),
            forecast(SEAPOINT, hours(start, [32] * 12, direction=270)),
        ],
        SETTINGS,
    )


def test_fr_3_1_writes_one_png_per_hour(tmp_path):
    paths = MapWriter(tmp_path).write(snapshot())
    assert [path.name for path in paths] == [
        "2026-11-06-09.png",
        "2026-11-06-12.png",
        "2026-11-06-15.png",
        "2026-11-06-18.png",
    ]
    assert paths[0].parent == tmp_path / "2026/11"
    assert paths[0].read_bytes().startswith(PNG)
    assert 15_000 < paths[0].stat().st_size < 150_000


def test_fr_3_4_a_later_run_overwrites_the_days_maps(tmp_path):
    first = MapWriter(tmp_path).write(snapshot())
    second = MapWriter(tmp_path).write(snapshot())
    assert first == second
    assert len(list(tmp_path.glob("*/*/*.png"))) == 4


def test_fr_2_8_day_page_shows_the_hourly_maps_in_order(tmp_path):
    paths = MapWriter(tmp_path / "data").write(snapshot())
    out = tmp_path / "site"
    maps = {path.stem: path for path in reversed(paths)}
    SiteBuilder(make_env(), [ARKLOW], tmp_path).build([snapshot()], out, maps)
    page = (out / "index.html").read_text()
    assert (out / "maps/2026-11-06-09.png").exists()
    sources = [f'src="maps/2026-11-06-{hour}.png"' for hour in ("09", "12", "15", "18")]
    assert all(source in page for source in sources)
    assert [page.index(source) for source in sources] == sorted(page.index(s) for s in sources)
    assert 'class="maps"' in page


def test_fr_3_1_seapoint_gets_the_inset_and_every_spot_is_on_one_map():
    spots = [{"id": s.id, "lat": s.lat, "lon": s.lon} for s in load_spots(REPO_SPOTS)]
    for spot in spots:
        assert WICKLOW.contains(spot) != DUBLIN_BAY.contains(spot)
    assert [s["id"] for s in spots if DUBLIN_BAY.contains(s)] == ["seapoint"]


def test_fr_3_2_close_arrows_are_spread_apart_around_their_middle():
    shifts = spread([100.0, 114.0, 300.0], spacing=30)
    assert shifts == [-8.0, 8.0, 0.0]


def test_fr_3_2_arrows_far_enough_apart_stay_put():
    assert spread([300.0, 100.0, 200.0], spacing=30) == [0.0, 0.0, 0.0]


def test_fr_6_6_map_label_shows_the_tide_at_that_hour():
    from wing_alert.windmap import _label

    spot = {"name": "Arklow", "tides": [{"time": "2026-11-06T12:30", "kind": "high"}]}
    reading = {"time": "2026-11-06T12:00", "wind": 14.4, "gust": 19.2}
    assert _label(spot, reading) == "Arklow 14/19 · HW"
    assert _label(spot, {**reading, "time": "2026-11-06T09:00"}) == "Arklow 14/19 · ↑"
    assert _label({"name": "Arklow"}, reading) == "Arklow 14/19"
