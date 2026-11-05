"""The icons of the built-in screens on a profile's page: one for each kind of screen, drawn in
the style of GNOME's symbolic icons (a 16 px grid, 2 px lines with round ends) in
packaging/icons and made into shapes by tools/symbolic-icons.py; a few kinds take an icon of
the theme by its name; a screen not known has an icon of its own, not the page's."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_ID = "io.github.tomaszbojanowski.OpenExpress"

# The kind of each built-in screen, an Edge's and a watch's codes together.
OWN = {25: "map", 44: "elevation", 35: "compass", 127: "stamina", 104: "climbpro",
       38: "workout", 56: "segment", 125: "power-guide", 80: "set", 22: "heart-rate-zone",
       100: "regatta", 101: "regatta", 74: "lap-summary", 58: "ebike", 95: "ebike",
       63: "cycling-dynamics", 223: "radar", 26: "virtual-partner"}
# Kinds the theme has an icon for, the same as elsewhere in the window.
THEME = {57: "system-users-symbolic", 162: "system-users-symbolic",
         21: "preferences-system-time-symbolic", 221: "preferences-system-time-symbolic",
         30: "audio-x-generic-symbolic", 128: "weather-clear-symbolic"}
KINDS = sorted(set(OWN.values()) | {"unknown"})


@pytest.mark.parametrize("kind", KINDS)
def test_each_icon_is_drawn_and_made_into_shapes(kind):
    """The drawing is lines on the 16 px grid; the icon made of it has no stroke (GTK fills
    every shape of a symbolic icon) and says which drawing it was made from."""
    drawing = (ROOT / "packaging" / "icons" / f"screen-{kind}.svg").read_text()
    assert 'viewBox="0 0 16 16"' in drawing and 'stroke="currentColor"' in drawing
    assert 'stroke-width="2"' in drawing and 'stroke-linecap="round"' in drawing
    icon = (ROOT / "openexpress" / "data" / f"{APP_ID}-screen-{kind}-symbolic.svg").read_text()
    assert "stroke" not in icon and f"packaging/icons/screen-{kind}.svg" in icon


def test_the_flatpak_installs_the_icons():
    manifest = (ROOT / "packaging" / "flatpak" / f"{APP_ID}.yml").read_text()
    assert "openexpress/data/${FLATPAK_ID}-screen-*-symbolic.svg" in manifest


@pytest.mark.needs_display
def test_each_built_in_screen_has_the_icon_of_its_kind():
    from openexpress import profile_names
    from openexpress.gui import profiles_page

    said = {code: profiles_page.built_in_icon(code) for code in (*OWN, *THEME, 999)}
    assert said == {**{c: f"{APP_ID}-screen-{k}-symbolic" for c, k in OWN.items()}, **THEME,
                    999: f"{APP_ID}-screen-unknown-symbolic"}
    codes = set(profile_names._edge_screen_names()) | set(profile_names._watch_screen_names())
    assert sorted(codes) == sorted({*OWN, *THEME})  # every screen with a name has its kind
    unknown = profiles_page.UNKNOWN_SCREEN_ICON
    assert unknown == f"{APP_ID}-screen-unknown-symbolic"
