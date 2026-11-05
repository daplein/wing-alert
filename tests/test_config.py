from pathlib import Path

import pytest

from wing_alert.config import ConfigError, Settings, load_settings, load_spots

REPO_CONFIG = Path(__file__).parents[1] / "config"


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "file.yaml"
    path.write_text(text)
    return path


def test_fr_1_1_loads_the_repo_config():
    spots = load_spots(REPO_CONFIG / "spots.yaml")
    settings = load_settings(REPO_CONFIG / "settings.yaml")
    assert [s.id for s in spots][:2] == ["arklow", "ennereilly"]
    assert next(s for s in spots if s.id == "seapoint").sheltered
    assert settings == Settings()


def test_fr_1_1_parses_a_spot(tmp_path):
    path = write(tmp_path, "- {id: a, name: A, lat: 52.1, lon: -6, directions: [280, 20]}")
    (spot,) = load_spots(path)
    assert (spot.direction_from, spot.direction_to, spot.sheltered) == (280, 20, False)


def test_fr_1_11_wind_at_defaults_to_the_beach(tmp_path):
    path = write(tmp_path, "- {id: a, name: A, lat: 52.1, lon: -6, directions: [0, 90]}")
    assert load_spots(path)[0].wind_point == (52.1, -6)
    path = write(
        tmp_path, "- {id: a, name: A, lat: 52, lon: -6, directions: [0, 90], wind_at: [52, -5.9]}"
    )
    assert load_spots(path)[0].wind_point == (52, -5.9)


def test_fr_1_11_every_real_spot_reads_wind_out_at_sea():
    spots = load_spots(REPO_CONFIG / "spots.yaml")
    assert all(spot.wind_at and spot.wind_at != (spot.lat, spot.lon) for spot in spots)


@pytest.mark.parametrize(
    "text",
    [
        "- {id: a, name: A, lat: 52, lon: -6, directions: [0, 90], wind_at: [52]}",
        "- {id: a, name: A, lat: 52, lon: -6, directions: [0, 90], wind_at: [95, -6]}",
        "[]",
        "- just a string",
        "- {id: a, name: A, lat: 52, lon: -6}",
        "- {id: a, name: A, lat: 52, lon: -6, directions: [10]}",
        "- {id: a, name: A, lat: north, lon: -6, directions: [0, 90]}",
        "- {id: a, name: A, lat: 95, lon: -6, directions: [0, 90]}",
        "- {id: a, name: A, lat: 52, lon: -6, directions: [0, 400]}",
        "- {id: a, name: A, lat: 52, lon: -6, directions: [0, 90]}\n"
        "- {id: a, name: B, lat: 52, lon: -6, directions: [0, 90]}",
        "- [unclosed",
    ],
)
def test_fr_1_1_rejects_invalid_spots(tmp_path, text):
    with pytest.raises(ConfigError):
        load_spots(write(tmp_path, text))


@pytest.mark.parametrize(
    "text",
    [
        "- 1",
        "min_wind: ten",
        "min_wind: true",
        "windy: 3",
        "min_wind: 30\nmax_wind: 20",
        "min_wind: 10\nmax_gust: 5",
        "min_window_hours: 0",
    ],
)
def test_fr_1_1_rejects_invalid_settings(tmp_path, text):
    with pytest.raises(ConfigError):
        load_settings(write(tmp_path, text))


def test_fr_1_1_missing_file_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError):
        load_spots(tmp_path / "nope.yaml")


def test_fr_11_6_station_links_need_a_source_and_a_page(tmp_path):
    from wing_alert.config import load_station_links

    path = tmp_path / "stations.yaml"
    path.write_text("m2: {source: Marine Institute}")
    with pytest.raises(ConfigError):
        load_station_links(path)
    path.write_text("- m2")
    with pytest.raises(ConfigError):
        load_station_links(path)
    path.write_text("m2: {source: Marine Institute, page: https://marine.ie}")
    assert load_station_links(path)["m2"]["page"] == "https://marine.ie"
