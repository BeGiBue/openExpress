"""The chart of an activity's page: one of the series its records give (heart rate, elevation,
and pace or speed by its sport; their words in gui/words.py) over the time since its first
record. A value not given and records that stop for a while (a pause) leave a gap in the line;
pace is smoothed over about 30 s and drawn with the faster on top, the slowest of it (the stops)
left off its axis; the points are brought down to two a pixel column without losing a peak; the
axes have round values. A click, a drag or the keys place a cursor, its value said beside the
switch. The numbers need no screen; the drawing is Cairo in a Gtk.DrawingArea.
Has: no attribute of the window; the chart's widgets keep their series and cursor themselves."""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("PangoCairo", "1.0")

from gi.repository import Adw, Gdk, Gtk, Pango, PangoCairo  # noqa: E402 - imports must follow gi.require_version

from openexpress.gui.words import (  # noqa: E402
    activity_clock,
    chart_accessible_name,
    chart_cursor_text,
    chart_series_name,
    chart_tick,
    chart_unit,
    speed_kind,
)

GAP_S = 60  # records further apart than this: a pause, a gap in the line
SMOOTHING_S = 30  # pace: the mean speed over this time around each record
MOVING = 0.2  # metres a second: slower is standing still, without a pace
STOPS = 0.95  # pace: its axis ends at the pace of this share of the records
KEY_STEP = 100  # a key moves the cursor by a hundredth of the activity
CHART_HEIGHT = 200
PACES = ("pace", "swim pace")
WHOLE = ("heart rate", "elevation")  # their axes have whole steps
LEAST_SPAN = {"heart rate": 10, "elevation": 10, "speed": 1, "pace": 60, "swim pace": 10}
NICE = (1, 2, 2.5, 5, 10)
TIME_STEPS = (5, 10, 15, 30, 60, 120, 300, 600, 900, 1200, 1800, 3600, 7200, 10_800, 21_600,
              43_200, 86_400)
PACE_STEPS = (1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600)
ACCENT = "#3584e4"  # libadwaita's blue, where the accent colour is not known


@dataclass(frozen=True)
class Series:
    """A series of the chart: its kind ("heart rate", "elevation", "pace", "swim pace",
    "speed"), the time of each record in seconds since the first one, and its value there in
    the unit of the axis (beats a minute, metres, seconds a kilometre or a hundred metres,
    kilometres an hour); None: a gap."""

    kind: str
    times: tuple[float, ...]
    values: tuple[float | None, ...]

    @property
    def duration(self) -> float:
        return self.times[-1] if self.times else 0


def _speeds(samples) -> list[float | None]:
    """The speed of each record (metres a second): as recorded, else worked out from the
    distance since the record before."""
    if any(s.speed is not None for s in samples):
        return [s.speed for s in samples]
    speeds, before = [], None
    for s in samples:
        speed = None
        if before is not None and s.distance is not None and s.time > before.time:
            speed = (s.distance - before.distance) / (s.time - before.time)
        speeds.append(speed)
        if s.distance is not None:
            before = s
    return speeds


def _pieces(times, values) -> list[tuple[int, int]]:
    """The pieces of a line as ranges of indexes [first, last): a value not given, or records
    more than GAP_S apart, ends one."""
    pieces, first = [], None
    for i, value in enumerate(values):
        if value is None:
            if first is not None:
                pieces.append((first, i))
                first = None
            continue
        if first is not None and times[i] - times[i - 1] > GAP_S:
            pieces.append((first, i))
            first = None
        if first is None:
            first = i
    if first is not None:
        pieces.append((first, len(values)))
    return pieces


def _smoothed(times, speeds) -> list[float | None]:
    """The mean speed over SMOOTHING_S around each record, within its piece of the line."""
    out: list[float | None] = [None] * len(times)
    half = SMOOTHING_S / 2
    for first, last in _pieces(times, speeds):
        sums = [0.0]
        for i in range(first, last):
            sums.append(sums[-1] + speeds[i])
        low = high = first
        for i in range(first, last):
            while times[low] < times[i] - half:
                low += 1
            while high < last and times[high] <= times[i] + half:
                high += 1
            out[i] = (sums[high - first] - sums[low - first]) / (high - low)
    return out


def chart_series(data) -> list[Series]:
    """The series of an activity (fit.ActivityData) its records give, in the order of the
    switch: heart rate, elevation, then for an activity with a distance its pace (smoothed;
    none while standing still) or its speed, by its sport."""
    samples = data.samples
    if not samples:
        return []
    origin = samples[0].time
    times = tuple(s.time - origin for s in samples)
    found = []
    for kind, values in (("heart rate", tuple(s.heart_rate for s in samples)),
                         ("elevation", tuple(s.altitude for s in samples))):
        if any(v is not None for v in values):
            found.append(Series(kind, times, values))
    if data.distance or any((s.distance or 0) > 0 for s in samples):
        speeds = _speeds(samples)
        kind = speed_kind(data.sport)
        if kind == "speed":
            values = tuple(None if v is None else v * 3.6 for v in speeds)
        else:
            per = 1000 if kind == "pace" else 100
            values = tuple(None if v is None or v < MOVING else per / v
                           for v in _smoothed(times, speeds))
        if any(v is not None for v in values):
            found.append(Series(kind, times, values))
    return found


def runs(series: Series) -> list[list[tuple[float, float]]]:
    """The pieces of a series' line, each a list of (time, value)."""
    return [list(zip(series.times[first:last], series.values[first:last], strict=True))
            for first, last in _pieces(series.times, series.values)]


def brought_down(run, start: float, end: float, columns: int) -> list[tuple[float, float]]:
    """At most two points of a piece for each of `columns` columns between the times `start`
    and `end`: the lowest and the highest of the column, in their order, so that no peak is
    lost."""
    if len(run) <= 2 * columns:
        return list(run)
    scale = columns / (end - start) if end > start else 0
    out, column, low, high = [], None, None, None
    for point in run:
        at = int((point[0] - start) * scale)
        if at != column:
            if column is not None:
                out.extend(_in_order(low, high))
            column, low, high = at, point, point
            continue
        if point[1] < low[1]:
            low = point
        if point[1] > high[1]:
            high = point
    out.extend(_in_order(low, high))
    return out


def _in_order(low, high) -> list:
    if low is high:
        return [low]
    return [low, high] if low[0] <= high[0] else [high, low]


@dataclass(frozen=True)
class Axis:
    """An axis from `low` to `high`, a value every `step` from `low`."""

    low: float
    high: float
    step: float

    @property
    def ticks(self) -> tuple[float, ...]:
        count = math.floor((self.high - self.low) / self.step + 1e-9)
        return tuple(_clean(self.low + i * self.step) for i in range(count + 1))


def _clean(value: float) -> float:
    return round(value, 9)


def _step(span: float, count: int, steps=None, whole: bool = False) -> float:
    """The round step that gives at most about `count` steps over `span`."""
    raw = span / max(count, 1)
    if steps is not None:
        return next((s for s in steps if s >= raw), steps[-1] * math.ceil(raw / steps[-1]))
    magnitude = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for nice in NICE:
        step = _clean(nice * magnitude)
        if (whole and step != int(step)) or step < raw - 1e-12:
            continue
        return step
    return 10 * magnitude


def value_axis(series: Series, count: int) -> Axis:
    """The axis of a series' values, round values around all of them (a pace: but its slowest,
    the stops), about `count` steps."""
    values = [v for v in series.values if v is not None]
    low, high = min(values), max(values)
    if series.kind in PACES:
        ordered = sorted(values)
        high = ordered[max(0, math.ceil(STOPS * len(ordered)) - 1)]
    least = LEAST_SPAN[series.kind]
    if high - low < least:
        middle = (low + high) / 2
        low, high = middle - least / 2, middle + least / 2
    step = _step(high - low, count, PACE_STEPS if series.kind in PACES else None,
                 whole=series.kind in WHOLE)
    first = math.floor(low / step + 1e-9) * step
    last = math.ceil(high / step - 1e-9) * step
    if last <= first:
        last = first + step
    return Axis(_clean(first), _clean(last), step)


def time_axis(duration: float, count: int) -> Axis:
    """The axis of the time since the first record: from it to the last, a round step."""
    return Axis(0, duration, _step(max(duration, 1), count, TIME_STEPS))


def faster_on_top(kind: str) -> bool:
    return kind in PACES


def value_at(series: Series, at: float) -> tuple[float, float | None]:
    """Where the cursor goes for the time `at` and the value there: the nearest record, or
    no value in a gap or a pause (no record within half of GAP_S)."""
    times = series.times
    at = min(max(at, 0), series.duration)
    i = bisect.bisect_left(times, at)
    nearest = min((j for j in (i - 1, i) if 0 <= j < len(times)), key=lambda j: abs(times[j] - at))
    if abs(times[nearest] - at) > GAP_S / 2:
        return at, None
    return times[nearest], series.values[nearest]


def cursor_after(series: Series, cursor: float | None, key: str) -> float:
    """The cursor after a key ("left", "right", "home", "end"): to the next record at least a
    hundredth of the activity away (never stuck at a pause); Home and End to the first and the
    last; without a cursor yet, Right starts at the first and Left at the last."""
    times = series.times
    if key == "home" or (cursor is None and key == "right"):
        return times[0]
    if key == "end" or cursor is None:
        return times[-1]
    step = series.duration / KEY_STEP
    if key == "right":
        return times[min(bisect.bisect_left(times, cursor + step), len(times) - 1)]
    return times[max(bisect.bisect_right(times, cursor - step) - 1, 0)]


# --- the drawing -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Plot:
    """Where the series is drawn in the widget (pixels) and its axes."""

    left: float
    top: float
    right: float
    bottom: float
    times: Axis
    values: Axis
    faster_on_top: bool

    def x(self, at: float) -> float:
        span = max(self.times.high - self.times.low, 1e-9)
        return self.left + (at - self.times.low) / span * (self.right - self.left)

    def time(self, x: float) -> float:
        span = max(self.times.high - self.times.low, 1e-9)
        return self.times.low + (x - self.left) / max(self.right - self.left, 1) * span

    def y(self, value: float) -> float:
        share = (value - self.values.low) / (self.values.high - self.values.low)
        if self.faster_on_top:
            return self.top + share * (self.bottom - self.top)
        return self.bottom - share * (self.bottom - self.top)


def _layout(area, text: str):
    layout = area.create_pango_layout(text)
    attributes = Pango.AttrList()
    attributes.insert(Pango.attr_scale_new(0.85))
    layout.set_attributes(attributes)
    return layout


def _plot(area, width: int, height: int) -> Plot:
    """The place of the plot in a widget of this size: room for the unit on top, the values
    on the left and the times below; as many round values as fit."""
    series = area.series
    text_height = _layout(area, "0").get_pixel_size()[1]
    top, bottom = text_height + 8, height - text_height - 6
    values = value_axis(series, max(2, int((bottom - top) // 40)))
    widest = max(_layout(area, chart_tick(series.kind, v, values.step)).get_pixel_size()[0]
                 for v in values.ticks)
    left = widest + 8
    last = _layout(area, activity_clock(series.duration)).get_pixel_size()[0]
    right = width - max(8, last / 2 + 2)
    times = time_axis(series.duration, max(2, int((right - left) // (last + 24))))
    return Plot(left, top, right, bottom, times, values, faster_on_top(series.kind))


def _accent() -> Gdk.RGBA:
    """The accent colour of the desktop for a line (libadwaita 1.6 and later), else blue."""
    manager = Adw.StyleManager.get_default()
    if hasattr(manager, "get_accent_color") and hasattr(Adw, "AccentColor"):
        return Adw.AccentColor.to_standalone_rgba(manager.get_accent_color(), manager.get_dark())
    rgba = Gdk.RGBA()
    rgba.parse(ACCENT)
    return rgba


def _text(area, cr, text: str, x: float, y: float, align: float, color) -> None:
    """`text` at `y` (its top), `align` 0 left of `x`… 1 right of it."""
    layout = _layout(area, text)
    width = layout.get_pixel_size()[0]
    cr.set_source_rgba(color.red, color.green, color.blue, 0.7)
    cr.move_to(x - width * align, y)
    PangoCairo.show_layout(cr, layout)


def _draw(area, cr, width: int, height: int) -> None:
    """The draw function of the chart (Gtk.DrawingArea): grid, values, times, the line, the
    cursor and, with the keyboard's focus, a frame."""
    series, kind = area.series, area.series.kind
    plot = _plot(area, width, height)
    fg, accent = area.get_color(), _accent()
    text_height = _layout(area, "0").get_pixel_size()[1]
    cr.set_line_width(1)
    for value in plot.values.ticks:
        y = round(plot.y(value)) + 0.5
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.12)
        cr.move_to(plot.left, y)
        cr.line_to(plot.right, y)
        cr.stroke()
        _text(area, cr, chart_tick(kind, value, plot.values.step), plot.left - 6,
              y - text_height / 2, 1, fg)
    _text(area, cr, chart_unit(kind), 0, 0, 0, fg)
    for at in plot.times.ticks:
        _text(area, cr, activity_clock(at), plot.x(at), plot.bottom + 4, 0.5, fg)
    cr.save()
    cr.rectangle(plot.left, plot.top - 2, plot.right - plot.left, plot.bottom - plot.top + 4)
    cr.clip()
    cr.set_source_rgba(accent.red, accent.green, accent.blue, 1)
    cr.set_line_width(2)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    for run in _drawn_runs(area, plot):
        if len(run) == 1:
            cr.arc(plot.x(run[0][0]), plot.y(run[0][1]), 1.5, 0, 2 * math.pi)
            cr.fill()
            continue
        cr.move_to(plot.x(run[0][0]), plot.y(run[0][1]))
        for at, value in run[1:]:
            cr.line_to(plot.x(at), plot.y(value))
        cr.stroke()
    cr.restore()
    if area.cursor is not None:
        at, value = value_at(series, area.cursor)
        x = round(plot.x(at)) + 0.5
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.5)
        cr.set_line_width(1)
        cr.move_to(x, plot.top)
        cr.line_to(x, plot.bottom)
        cr.stroke()
        if value is not None:
            y = min(max(plot.y(value), plot.top), plot.bottom)
            cr.arc(x, y, 4.5, 0, 2 * math.pi)
            cr.set_source_rgba(accent.red, accent.green, accent.blue, 1)
            cr.fill_preserve()
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 1)  # seen on the line too
            cr.set_line_width(1.5)
            cr.stroke()
    if area.has_visible_focus():
        cr.set_source_rgba(accent.red, accent.green, accent.blue, 0.5)
        cr.set_line_width(2)
        cr.rectangle(1, 1, width - 2, height - 2)
        cr.stroke()


def _drawn_runs(area, plot: Plot) -> list:
    """The pieces of the line brought down to the plot's width, kept until the series or the
    width changes."""
    key = (area.series, plot.left, plot.right)
    if area.drawn is None or area.drawn[0] != key:
        columns = max(1, int(plot.right - plot.left))
        area.drawn = (key, [brought_down(run, plot.times.low, plot.times.high, columns)
                            for run in runs(area.series)])
    return area.drawn[1]


# --- the widgets -----------------------------------------------------------------------------


def _drag_begin(gesture, x, _y) -> None:
    area = gesture.get_widget()
    area.grab_focus()
    area.drag_from = x
    _place_at(area, x)


def _drag_update(gesture, dx, _dy) -> None:
    area = gesture.get_widget()
    _place_at(area, area.drag_from + dx)


def _place_at(area, x: float) -> None:
    area.place(_plot(area, area.get_width(), area.get_height()).time(x))


KEYS = {Gdk.KEY_Left: "left", Gdk.KEY_KP_Left: "left", Gdk.KEY_Right: "right",
        Gdk.KEY_KP_Right: "right", Gdk.KEY_Home: "home", Gdk.KEY_KP_Home: "home",
        Gdk.KEY_End: "end", Gdk.KEY_KP_End: "end"}


def _key_pressed(controller, keyval, _keycode, _state) -> bool:
    key = KEYS.get(keyval)
    if key is None:
        return False
    area = controller.get_widget()
    area.place(cursor_after(area.series, area.cursor, key))
    return True


def _redraw(controller) -> None:
    controller.get_widget().queue_draw()


class ChartArea(Gtk.DrawingArea):
    """The drawing of one series and its cursor; a click, a drag and the keys move the
    cursor. Its handlers reach it through their controller."""

    __gtype_name__ = "OpenExpressChartArea"

    def __init__(self, series: Series):
        super().__init__(content_height=CHART_HEIGHT, hexpand=True, focusable=True)
        self.series = series
        self.cursor: float | None = None
        self.drag_from = 0.0
        self.drawn = None  # the line brought down to the width last drawn
        self.set_draw_func(_draw)
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", _drag_begin)
        drag.connect("drag-update", _drag_update)
        self.add_controller(drag)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", _key_pressed)
        self.add_controller(keys)
        focus = Gtk.EventControllerFocus()
        focus.connect("enter", _redraw)
        focus.connect("leave", _redraw)
        self.add_controller(focus)
        self.show_series(series)

    def show_series(self, series: Series) -> None:
        """Another series, the cursor at the same time."""
        self.series = series
        if self.cursor is not None:
            self.cursor = value_at(series, self.cursor)[0]
        self.update_property([Gtk.AccessibleProperty.LABEL], [chart_accessible_name(series.kind)])
        self.queue_draw()

    def place(self, at: float) -> None:
        """The cursor at the time `at` (at its nearest record), its value said beside the
        switch."""
        self.cursor = value_at(self.series, at)[0]
        self.queue_draw()
        text = self.cursor_text()
        self.update_property([Gtk.AccessibleProperty.DESCRIPTION], [text])
        chart = self.get_ancestor(ActivityChart)
        if chart is not None:
            chart.value_label.set_label(text)

    def cursor_text(self) -> str:
        if self.cursor is None:
            return ""
        at, value = value_at(self.series, self.cursor)
        return chart_cursor_text(at, self.series.kind, value)


def _toggled(button) -> None:
    if not button.get_active():
        return
    chart = button.get_ancestor(ActivityChart)
    if chart is not None:
        chart.show(button.kind)


class ActivityChart(Gtk.Box):
    """The chart with its switch (or the name of its one series) and, beside it, the value at
    its cursor. Its handlers reach it through the widget of their signal."""

    __gtype_name__ = "OpenExpressActivityChart"

    def __init__(self, series: list[Series]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.series = {s.kind: s for s in series}
        # The value beside the switch, under it in a narrow window.
        top = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, min_children_per_line=1,
                          max_children_per_line=2, column_spacing=12, row_spacing=4)
        if len(series) > 1:
            switch = Gtk.Box(valign=Gtk.Align.CENTER)
            switch.add_css_class("linked")
            first = None
            for s in series:
                button = Gtk.ToggleButton(label=chart_series_name(s.kind), active=first is None)
                button.kind = s.kind
                if first is None:
                    first = button
                else:
                    button.set_group(first)
                button.connect("toggled", _toggled)
                switch.append(button)
            first_widget = switch
        else:
            first_widget = Gtk.Label(label=chart_series_name(series[0].kind), xalign=0)
            first_widget.add_css_class("heading")
        self.value_label = Gtk.Label(xalign=1, wrap=True, justify=Gtk.Justification.RIGHT)
        self.value_label.add_css_class("numeric")
        for widget, expand in ((first_widget, False), (self.value_label, True)):
            top.append(Gtk.FlowBoxChild(child=widget, focusable=False, hexpand=expand))
        self.append(top)
        self.area = ChartArea(series[0])
        self.append(self.area)

    def show(self, kind: str) -> None:
        self.area.show_series(self.series[kind])
        self.value_label.set_label(self.area.cursor_text())
