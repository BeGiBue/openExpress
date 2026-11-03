"""The colours of an activity's track by the series chosen on its chart (gui/activity_colours.py):
the scale from blue (low) to red-orange (high; pace: fast), the activity's own ends (its 5th and
95th percentile), the colour of each point of the track, grey where the series has no value.
Numbers only, no screen; made-up series."""

import pytest
from fakes import contrast


def colours():
    from openexpress.gui import activity_colours
    return activity_colours


def test_the_scale_runs_from_blue_to_red_orange():
    scale = colours().SCALE
    assert len(scale) == 64
    assert (scale[0], scale[-1]) == ("#017dd6", "#f75e1c")


@pytest.mark.parametrize(("background", "least"), [("#fafafb", 3.0), ("#222226", 3.6)])
def test_every_colour_of_the_scale_stands_out_on_the_plain_map(background, least):
    """The map without tiles is the window's background, light or dark; there the colour
    alone has to be seen (on the tiles the dark edge is)."""
    assert min(contrast(c, background) for c in colours().SCALE) >= least
    assert contrast(colours().EDGE, "#aad3df") >= 3.0  # the edge on the tiles' water


def series(kind, values):
    from openexpress.gui.activity_chart import Series

    return Series(kind, tuple(float(t) for t in range(len(values))), tuple(values))


def test_the_ends_are_the_activity_s_5th_and_95th_percentile():
    assert colours().scale_ends(series("heart rate", range(101))) == (5, 95)
    assert colours().scale_ends(series("elevation", [None, 120, None, 80])) == (80, 120)


def test_a_faster_pace_is_the_red_end():
    """Pace is seconds a kilometre: the slow end (more seconds) is blue, the fast one red."""
    pace = series("pace", [300 + 4 * i for i in range(101)])
    assert colours().scale_ends(pace) == (680, 320)
    shown = colours().point_colours((0.0, 5.0, 95.0, 100.0), pace)
    assert shown[0] == shown[1] == colours().SCALE[-1]  # fast, and beyond the end
    assert shown[2] == shown[3] == colours().SCALE[0]


def test_each_point_has_the_colour_of_its_record_and_grey_where_none():
    """The record at the point's time, or the last one before it; no value: grey."""
    c = colours()
    rate = series("heart rate", [100, 110, None, 120])
    assert c.point_colours((0.0, 1.0, 1.5, 2.0, 3.0), rate) == [
        c.SCALE[0], c.SCALE[32], c.SCALE[32], c.NO_VALUE, c.SCALE[-1]]


def test_a_series_of_one_value_is_the_middle_of_the_scale_and_none_no_colours():
    c = colours()
    assert set(c.point_colours((0.0, 1.0), series("heart rate", [120, 120]))) == {c.SCALE[32]}
    assert c.point_colours((0.0, 1.0), series("heart rate", [None, None])) is None
