"""The laps of an activity's page, under its chart: a row each, the device's laps, or the
kilometres worked out from the records when it kept none (one lap, the whole of it) and the
activity is at least KILOMETRES_FROM long; nothing for a shorter one or a workout. A row chosen
(a click, Enter, Space) is told to the page ("lap-chosen"), which shows the lap on the chart
and on the map; chosen again it is not, another moves it.
Has: no attribute of the window; the list keeps the laps' places on the chart's time and the
one chosen."""
from __future__ import annotations

from itertools import pairwise
from typing import ClassVar

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GObject, Gtk  # noqa: E402 - imports must follow gi.require_version

from openexpress import fit  # noqa: E402
from openexpress.gui.activity_chart import GAP_S  # noqa: E402
from openexpress.gui.words import kilometre_title, lap_caption, lap_title, laps_title  # noqa: E402

KILOMETRES_FROM = 2000  # metres: a shorter activity without laps has no kilometres either
KILOMETRE = 1000
LEAST_LAST = 10  # metres: a last kilometre shorter than this is left out


def lap_span(lap, origin: float) -> tuple[float, float] | None:
    """Where a lap (fit.Lap) is on the chart's time (seconds since the first record,
    `origin`): from its start, its elapsed time long (its timer's standing in); None without
    either."""
    length = lap.elapsed_time if lap.elapsed_time is not None else lap.timer_time
    if lap.start is None or length is None:
        return None
    begin = lap.start - origin
    return begin, begin + length


def _piece(samples, distance: float) -> fit.Lap:
    """A kilometre (or the last, shorter part) of these records, from the first to the one
    that reaches its end: its timer time leaves out the pauses (records more than GAP_S
    apart)."""
    elapsed = samples[-1].time - samples[0].time
    timer = sum(b.time - a.time for a, b in pairwise(samples) if b.time - a.time <= GAP_S)
    beats = [s.heart_rate for s in samples if s.heart_rate is not None]
    return fit.Lap(samples[0].time, float(elapsed), float(timer), distance,
                   distance / timer if timer else None,
                   round(sum(beats) / len(beats)) if beats else None,
                   max(beats) if beats else None)


def _kilometres(samples) -> tuple[fit.Lap, ...]:
    placed = [s for s in samples if s.distance is not None]
    if not placed:
        return ()
    found, first = [], 0
    for i, sample in enumerate(placed):
        if sample.distance >= (len(found) + 1) * KILOMETRE and i > first:
            found.append(_piece(placed[first:i + 1], KILOMETRE))
            first = i
    rest = placed[-1].distance - len(found) * KILOMETRE
    if rest >= LEAST_LAST and len(placed) - first > 1:
        found.append(_piece(placed[first:], rest))
    return tuple(found)


def laps_of(data) -> tuple[tuple[fit.Lap, ...], bool]:
    """The rows of an activity (fit.ActivityData): its laps, or its kilometres (True) where the
    device kept no laps and it is long enough; () without either."""
    if len(data.laps) > 1:
        return data.laps, False
    if (data.distance or 0) >= KILOMETRES_FROM:
        found = _kilometres(data.samples)
        if found:
            return found, True
    return (), False


def _activated(row) -> None:
    shown = row.get_ancestor(LapList)
    if shown is not None:
        shown.choose(row.get_index())


class LapList(Gtk.Box):
    """The section of the laps (or kilometres): their rows, the line large, its name small
    above it; a row chosen tinted with a check mark."""

    __gtype_name__ = "OpenExpressLapList"
    __gsignals__: ClassVar = {
        # chosen or not, and where on the chart's time (0, 0 when not)
        "lap-chosen": (GObject.SignalFlags.RUN_FIRST, None, (bool, float, float)),
    }

    def __init__(self, laps, kilometres: bool, sport: int | None, origin: float):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        group = Adw.PreferencesGroup(title=laps_title(kilometres))
        listed = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        listed.add_css_class("boxed-list")
        self.rows, self.checks, self.spans = [], [], []
        title = kilometre_title if kilometres else lap_title
        for number, lap in enumerate(laps, start=1):
            row = Adw.ActionRow(title=title(number), subtitle=lap_caption(lap, sport),
                                activatable=True)
            row.add_css_class("property")
            check = Gtk.Image(icon_name="object-select-symbolic", visible=False)
            row.add_suffix(check)
            row.connect("activated", _activated)
            listed.append(row)
            self.rows.append(row)
            self.checks.append(check)
            self.spans.append(lap_span(lap, origin))
        group.add(listed)
        self.append(group)
        self.chosen: int | None = None

    def choose(self, index: int) -> None:
        """The lap at `index` chosen, or no lap when it was."""
        self.chosen = None if index == self.chosen else index
        for i, (row, check) in enumerate(zip(self.rows, self.checks, strict=True)):
            if i == self.chosen:
                row.add_css_class("oe-lap-chosen")
            else:
                row.remove_css_class("oe-lap-chosen")
            check.set_visible(i == self.chosen)
        span = self.spans[self.chosen] if self.chosen is not None else None
        if span is None:
            self.emit("lap-chosen", False, 0.0, 0.0)
        else:
            self.emit("lap-chosen", True, float(span[0]), float(span[1]))
