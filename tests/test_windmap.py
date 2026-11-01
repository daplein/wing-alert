from pathlib import Path

from tests.helpers import ARKLOW, MORNING, SEAPOINT, SETTINGS, forecast, hours
from wing_alert.archive import build_snapshot
from wing_alert.config import load_spots
from wing_alert.site import SiteBuilder, make_env
from wing_alert.windmap import DUBLIN_BAY, WICKLOW, MapWriter

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


def test_fr_3_1_writes_one_png_per_forecast_date(tmp_path):
    (path,) = MapWriter(tmp_path).write(snapshot())
    assert path == tmp_path / "2026/11/2026-11-06.png"
    assert path.read_bytes().startswith(PNG)
    assert 20_000 < path.stat().st_size < 400_000


def test_fr_3_4_a_later_run_overwrites_the_days_map(tmp_path):
    first = MapWriter(tmp_path).write(snapshot())
    second = MapWriter(tmp_path).write(snapshot())
    assert first == second
    assert len(list(tmp_path.glob("*/*/*.png"))) == 1


def test_fr_3_1_day_page_shows_the_map(tmp_path):
    (path,) = MapWriter(tmp_path / "data").write(snapshot())
    out = tmp_path / "site"
    SiteBuilder(make_env(), [ARKLOW], tmp_path).build([snapshot()], out, {"2026-11-06": path})
    assert (out / "maps/2026-11-06.png").exists()
    assert 'src="maps/2026-11-06.png"' in (out / "index.html").read_text()


def test_fr_3_1_seapoint_gets_the_inset_and_every_spot_is_on_one_map():
    spots = [{"id": s.id, "lat": s.lat, "lon": s.lon} for s in load_spots(REPO_SPOTS)]
    for spot in spots:
        assert WICKLOW.contains(spot) != DUBLIN_BAY.contains(spot)
    assert [s["id"] for s in spots if DUBLIN_BAY.contains(s)] == ["seapoint"]
