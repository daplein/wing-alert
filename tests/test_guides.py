from wing_alert.guides import guide_html, unforecast_guides, video_cards, video_id

GUIDE = """# Arklow

## Videos

- [North-easterly, 3 May 2025](https://youtu.be/gHAu4Nts9q0)
- [Buckroney](https://youtube.com/shorts/neevGA6y93o)
- [Long one](https://www.youtube.com/watch?v=sjC9kCzDR2U&t=30)

[Google Maps](https://maps.app.goo.gl/4dmHuTStYvu61gzv8)
"""


def test_fr_8_1_finds_the_id_in_every_youtube_link_form():
    assert video_id("https://youtu.be/gHAu4Nts9q0") == "gHAu4Nts9q0"
    assert video_id("https://youtube.com/shorts/neevGA6y93o") == "neevGA6y93o"
    assert video_id("https://www.youtube.com/watch?v=sjC9kCzDR2U&t=30") == "sjC9kCzDR2U"
    assert video_id("https://maps.app.goo.gl/4dmHuTStYvu61gzv8") is None


def test_fr_8_1_video_links_become_thumbnail_cards(tmp_path):
    path = tmp_path / "arklow.md"
    path.write_text(GUIDE)
    html = guide_html(path)
    assert '<a class="video" href="https://youtu.be/gHAu4Nts9q0">' in html
    assert 'src="https://i.ytimg.com/vi/neevGA6y93o/hqdefault.jpg"' in html
    assert 'loading="lazy"' in html and "<span>North-easterly, 3 May 2025</span>" in html
    assert "<iframe" not in html and "<script" not in html


def test_fr_8_1_other_links_stay_as_they_are():
    text = (
        "- [Google Maps](https://maps.app.goo.gl/x)\n- see [this](https://youtu.be/gHAu4Nts9q0)\n"
    )
    assert video_cards(text) == text


def test_fr_8_1_titles_are_escaped():
    assert "<span>Tom &amp; Jerry</span>" in video_cards(
        "- [Tom & Jerry](https://youtu.be/gHAu4Nts9q0)"
    )


def test_fr_8_2_one_grid_per_run_of_videos(tmp_path):
    cards = video_cards(GUIDE)
    assert cards.count('<div class="videos">') == 1
    assert cards.count('class="video"') == 3


def test_fr_8_3_guides_without_a_spot_are_listed_without_forecast(tmp_path):
    (tmp_path / "arklow.md").write_text(GUIDE)
    (tmp_path / "malahide.md").write_text(
        "# Malahide\n\n- [Session](https://youtu.be/gHAu4Nts9q0)\n"
    )
    (tmp_path / "bull_wall.md").write_text("No heading\n")
    extras = unforecast_guides(tmp_path, {"arklow"})
    assert [(g.id, g.name) for g in extras] == [
        ("bull_wall", "Bull Wall"),
        ("malahide", "Malahide"),
    ]
    assert 'class="video"' in extras[1].html
