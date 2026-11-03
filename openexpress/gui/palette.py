"""The colours that more than one module of the activity page and of the look of sports uses,
by name, and a colour of "#rrggbb" as GTK and cairo take it (rgba).
Has: nothing of the window."""
from __future__ import annotations

import gi

gi.require_version("Gdk", "4.0")

from gi.repository import Gdk  # noqa: E402 - imports must follow gi.require_version

BLUE = "#3584e4"  # GNOME's blue 3: cycling, zone 1
GREEN = "#26a269"  # GNOME's green 5: on foot, zone 2, the start of a track
GREY = "#8a898e"  # no group of sports, below zone 1, a point without a value


def rgba(colour: str) -> Gdk.RGBA:
    """A colour of "#rrggbb" as GTK and cairo take it."""
    found = Gdk.RGBA()
    found.parse(colour)
    return found
