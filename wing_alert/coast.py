"""Coastline lines and land shapes for the wind map (FR-3.3, FR-3.6)."""

import json
from dataclasses import dataclass
from pathlib import Path

Point = tuple[float, float]  # (lon, lat)
COASTLINE = Path(__file__).parent / "assets" / "coastline.json"
FAR_WEST = -7.5  # well inland, off every map


@dataclass(frozen=True)
class Coast:
    lines: list[list[Point]]
    land: list[list[Point]]


def load_coast(path: Path = COASTLINE) -> Coast:
    lines = [[(lon, lat) for lon, lat in line] for line in json.loads(path.read_text())["lines"]]
    return Coast(lines, [_close(chain) for chain in stitch(lines)])


def stitch(lines: list[list[Point]]) -> list[list[Point]]:
    """Join OSM coastline ways that run end to start into longer chains."""
    chains = [list(line) for line in lines]
    merged = True
    while merged:
        merged = _merge_one(chains)
    return chains


def _merge_one(chains: list[list[Point]]) -> bool:
    starts = {chain[0]: index for index, chain in enumerate(chains) if chain[0] != chain[-1]}
    for index, chain in enumerate(chains):
        follower = starts.get(chain[-1])
        if follower is not None and follower != index:
            chain.extend(chains.pop(follower)[1:])
            return True
    return False


def _close(chain: list[Point]) -> list[Point]:
    """Closed rings are islands. Open chains get closed inland: OSM keeps land on the
    left of the way, and this coast faces east, so the land lies to the west."""
    if chain[0] == chain[-1]:
        return chain
    return [*chain, (FAR_WEST, chain[-1][1]), (FAR_WEST, chain[0][1])]
