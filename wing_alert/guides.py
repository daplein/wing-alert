"""Spot guides from docs/spots/*.md, with YouTube links as preview cards (FR-2.7, FR-8)."""

import re
from dataclasses import dataclass
from html import escape
from pathlib import Path

import markdown

_LIST_LINK = re.compile(r"^\s*[-*] \[(?P<title>[^\]]+)\]\((?P<url>[^)\s]+)\)\s*$")
_VIDEO_ID = re.compile(r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|shorts/))(?P<id>[\w-]{11})")


@dataclass(frozen=True)
class Guide:
    """A guide with no spot in the config: shown without a forecast (FR-8.3)."""

    id: str
    name: str
    html: str


def guide_html(path: Path) -> str | None:
    if not path.exists():
        return None
    return markdown.markdown(video_cards(path.read_text()), extensions=["tables"])


def unforecast_guides(folder: Path, spot_ids: set[str]) -> list[Guide]:
    paths = [path for path in sorted(folder.glob("*.md")) if path.stem not in spot_ids]
    return [Guide(path.stem, _title(path), guide_html(path) or "") for path in paths]


def _title(path: Path) -> str:
    for line in path.read_text().splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("_", " ").title()


def video_id(url: str) -> str | None:
    match = _VIDEO_ID.search(url)
    return match["id"] if match else None


def video_cards(text: str) -> str:
    """Each run of list items that are only a YouTube link becomes one grid of cards."""
    out: list[str] = []
    cards: list[str] = []
    for line in text.splitlines():
        if card := _card(line):
            cards.append(card)
            continue
        out += _grid(cards)
        cards = []
        out.append(line)
    return "\n".join(out + _grid(cards)) + "\n"


def _card(line: str) -> str | None:
    match = _LIST_LINK.match(line)
    vid = video_id(match["url"]) if match else None
    if not match or not vid:
        return None
    return (
        f'<a class="video" href="{escape(match["url"])}">'
        f'<img src="https://i.ytimg.com/vi/{vid}/hqdefault.jpg" alt="" loading="lazy">'
        f"<span>{escape(match['title'])}</span></a>"
    )


def _grid(cards: list[str]) -> list[str]:
    return ["", '<div class="videos">', *cards, "</div>", ""] if cards else []
