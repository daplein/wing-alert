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


@pytest.mark.parametrize(
    "text",
    [
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
