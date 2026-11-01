from matplotlib.path import Path as Shape

from wing_alert.coast import FAR_WEST, load_coast, stitch


def is_land(point, land) -> bool:
    return any(Shape(shape).contains_point(point) for shape in land)


def test_fr_3_6_stitches_ways_that_run_end_to_start():
    assert stitch([[(0, 0), (1, 1)], [(1, 1), (2, 2)], [(5, 5), (6, 6), (5, 5)]]) == [
        [(0, 0), (1, 1), (2, 2)],
        [(5, 5), (6, 6), (5, 5)],
    ]


def test_fr_3_6_land_is_inland_and_the_sea_is_not():
    land = load_coast().land
    assert is_land((-6.2, 52.9), land)  # Wicklow mountains side
    assert is_land((-6.17, 53.29), land)  # Blackrock, behind Seapoint
    assert not is_land((-6.07, 52.7878), land)  # off Arklow, where the wind is read
    assert not is_land((-6.12, 53.31), land)  # Dublin Bay
    assert all(shape[-1][0] == FAR_WEST for shape in land if shape[0] != shape[-1])
