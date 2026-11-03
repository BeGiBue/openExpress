"""The laps of an activity's page (gui/activity_laps.py) without a screen: the device's laps
when it kept them, kilometres worked out from the records when it kept none (an activity of
at least 2 km), nothing for a short one or a workout; where each lap is on the chart's time.
Every value is made up."""

import pytest

from openexpress import fit

START = 1_700_000_000  # a Unix time


def laps():
    from openexpress.gui import activity_laps
    return activity_laps


def walk(metres, every=2, speed=1.25, pause=None, laps_=()):
    """A walk of `metres` at `speed`, a record each `every` seconds; `pause`: (from, seconds),
    a gap with no record."""
    samples, t, distance = [], 0, 0.0
    while distance < metres:
        if pause and pause[0] <= t < pause[0] + pause[1]:
            t += every
            continue
        distance = min(metres, distance + speed * every)
        samples.append(fit.Sample(START + t, distance=distance, speed=speed,
                                  heart_rate=100 + int(distance // 1000) * 10))
        t += every
    return fit.ActivityData(fit.FileState.WHOLE, start=START, sport=11, distance=metres,
                            samples=tuple(samples), laps=tuple(laps_))


def test_kilometres_where_the_device_kept_no_laps():
    """Each kilometre from the record that reaches it; the last one shorter."""
    shown, kilometres = laps().laps_of(walk(3250))
    assert kilometres
    assert [round(lap.distance) for lap in shown] == [1000, 1000, 1000, 250]
    first = shown[0]
    assert first.start == START and first.elapsed_time == pytest.approx(800, abs=2)
    assert first.avg_speed == pytest.approx(1.25, rel=0.01)
    assert first.avg_heart_rate == pytest.approx(100, abs=1)
    assert shown[1].avg_heart_rate == pytest.approx(110, abs=1)
    assert shown[1].start == pytest.approx(START + 800, abs=2)


def test_one_lap_of_the_whole_activity_counts_as_none():
    whole = fit.Lap(START, 2600.0, 2600.0, 3250.0)
    shown, kilometres = laps().laps_of(walk(3250, laps_=(whole,)))
    assert kilometres and len(shown) == 4


def test_the_device_s_laps_when_it_kept_them():
    kept = (fit.Lap(START, 400.0, 400.0, 500.0), fit.Lap(START + 400, 400.0, 400.0, 500.0))
    shown, kilometres = laps().laps_of(walk(3250, laps_=kept))
    assert not kilometres and shown == kept


@pytest.mark.parametrize("data", [
    walk(1990),  # shorter than 2 km
    fit.ActivityData(fit.FileState.WHOLE, start=START, sport=10, samples=(
        fit.Sample(START, heart_rate=90), fit.Sample(START + 1, heart_rate=91)))])  # a workout
def test_no_laps_and_no_kilometres(data):
    assert laps().laps_of(data) == ((), False)


def test_a_pause_counts_in_the_elapsed_time_not_in_the_timer_s():
    shown, _kilometres = laps().laps_of(walk(2500, pause=(100, 300)))
    first = shown[0]
    assert first.elapsed_time - first.timer_time == pytest.approx(300, abs=4)
    assert first.avg_speed == pytest.approx(1.25, rel=0.02)


def test_a_last_kilometre_of_a_few_metres_is_left_out():
    assert [round(lap.distance) for lap in laps().laps_of(walk(3005))[0]] == [1000] * 3


def test_where_a_lap_is_on_the_chart_s_time():
    """From the first record of the activity, its elapsed time long (its timer's standing
    in); a lap without a start: nowhere."""
    origin = START - 10
    assert laps().lap_span(fit.Lap(START, 400.0, 380.0), origin) == (10, 410)
    assert laps().lap_span(fit.Lap(START, None, 380.0), origin) == (10, 390)
    assert laps().lap_span(fit.Lap(None, 400.0, 380.0), origin) is None
