"""The look of a sport on an activity's page (gui/sports.py) without a screen: its group by the
sport of the FIT profile, the group's colour read on the cards of both styles (an icon needs a
contrast of 3:1), and the program's style for each group."""

import pytest

LIGHT_CARD = "#ffffff"
DARK_CARD = "#343437"  # libadwaita's dark card: white at 8 % over its window, #222226


def sports():
    from openexpress.gui import sports
    return sports


@pytest.mark.parametrize(("sport", "group"), [
    (1, "foot"), (11, "foot"), (17, "foot"), (16, "foot"), (31, "foot"), (87, "foot"),
    (2, "cycling"), (21, "cycling"),
    (5, "water"), (15, "water"), (29, "water"), (41, "water"), (88, "water"),
    (12, "winter"), (13, "winter"), (14, "winter"), (35, "winter"),
    (10, "training"), (4, "training"), (62, "training"), (84, "training"),
    (0, "others"), (18, "others"), (25, "others"), (254, "others"), (None, "others")])
def test_the_group_of_a_sport(sport, group):
    assert sports().sport_group(sport) == group


def luminance(color: str) -> float:
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_each_colour_reads_on_the_cards_of_both_styles():
    colors = sports().COLOURS
    assert colors == {"foot": "#26a269", "cycling": "#3584e4", "water": "#2190a4",
                      "winter": "#6f8396", "training": "#c061cb", "others": "#8a898e"}
    for color in colors.values():
        assert contrast(color, LIGHT_CARD) >= 3 and contrast(color, DARK_CARD) >= 3


def test_the_program_s_style_has_a_class_for_each_group():
    css = sports().css()
    for group, color in sports().COLOURS.items():
        assert f".oe-sport-{group} {{ color: {color}; }}" in css
        assert f".oe-sport-dot.oe-sport-{group} {{ background-color: {color}; }}" in css
