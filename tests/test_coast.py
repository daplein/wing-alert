from wing_alert.coast import FAR_WEST, load_coast, stitch


def inside(point, shape) -> bool:
    """Even-odd rule: a ray going east crosses the shape's edge an odd number of times."""
    x, y = point
    crossings = 0
    for (x1, y1), (x2, y2) in zip(shape, shape[1:] + shape[:1], strict=True):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            crossings += 1
    return crossings % 2 == 1


def is_land(point, land) -> bool:
    return any(inside(point, shape) for shape in land)


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
