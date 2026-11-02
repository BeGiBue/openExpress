"""The words of an activity's page (gui/words.py): times with seconds, distances, pace or speed
by sport, heart rate, calories, ascent, the names of the tiles and the line of a lap, in English
and in Polish. A distance of 0 m and a value not given say nothing. Every value is made up."""

import pytest

from openexpress import fit, i18n

NB = " "
RUNNING, CYCLING, SWIMMING, TRAINING, HIKING = 1, 2, 5, 10, 17


@pytest.fixture(params=["en", "pl"])
def language(request):
    i18n.setup(request.param)
    yield request.param
    i18n.setup("en")


def words():
    from openexpress.gui import words
    return words


@pytest.mark.parametrize(("seconds", "said"), [(41, "0:41"), (302, "5:02"), (3161, "52:41"),
                                               (3761, "1:02:41"), (3761.6, "1:02:42")])
def test_a_time_with_its_seconds(seconds, said):
    assert words().activity_clock(seconds) == said


def test_a_distance(language):
    w = words()
    assert w.activity_distance(10240, RUNNING) == {"en": "10.24 km", "pl": "10,24 km"}[language]
    assert w.activity_distance(1000, CYCLING) == {"en": "1.00 km", "pl": "1,00 km"}[language]
    assert w.activity_distance(1500, SWIMMING) == "1500 m"
    assert w.activity_distance(0, RUNNING) is None
    assert w.activity_distance(None, RUNNING) is None


def test_pace_or_speed_by_sport(language):
    w = words()
    assert w.activity_pace(2.5, RUNNING) == "6:40 /km"  # 400 s a km
    assert w.activity_pace(1000 / 302, HIKING) == "5:02 /km"
    assert w.activity_pace(0.8, SWIMMING) == "2:05 /100 m"
    assert w.activity_pace(6.75, CYCLING) == {"en": "24.3 km/h", "pl": "24,3 km/h"}[language]
    assert w.activity_pace(3.0, TRAINING) == {"en": "10.8 km/h", "pl": "10,8 km/h"}[language]
    assert w.activity_pace(0, RUNNING) is None and w.activity_pace(None, CYCLING) is None


@pytest.mark.parametrize(("sport", "kind"), [(1, "pace"), (11, "pace"), (16, "pace"),
                                             (17, "pace"), (35, "pace"), (5, "swim pace"),
                                             (2, "speed"), (21, "speed"), (13, "speed"),
                                             (None, "speed")])
def test_which_sports_have_a_pace(sport, kind):
    assert words().speed_kind(sport) == kind


def test_heart_rate_calories_and_ascent(language):
    w = words()
    assert w.heart_rate_text(148) == {"en": "148 bpm", "pl": "148 ud./min"}[language]
    assert w.calories_text(520) == "520 kcal"
    assert w.ascent_text(740) == "740 m"
    assert w.ascent_text(0) is None and w.ascent_text(None) is None
    assert w.heart_rate_text(None) is None and w.calories_text(None) is None


TILES = {
    "en": {"distance": "Distance", "time": "Time", "pace": "Average pace",
           "speed": "Average speed", "average heart rate": "Average heart rate",
           "maximum heart rate": "Maximum heart rate", "calories": "Calories",
           "ascent": "Total ascent"},
    "pl": {"distance": "Dystans", "time": "Czas", "pace": "Średnie tempo",
           "speed": "Średnia prędkość", "average heart rate": "Średnie tętno",
           "maximum heart rate": "Maksymalne tętno", "calories": "Kalorie",
           "ascent": "Przewyższenie"},
}


def test_the_names_of_the_tiles(language):
    w = words()
    assert {kind: w.tile_name(kind) for kind in TILES[language]} == TILES[language]
    assert w.tile_name("swim pace") == TILES[language]["pace"]


def lap(**values):
    return fit.Lap(**values)


def test_the_line_of_a_lap(language):
    w = words()
    assert w.lap_title(1) == {"en": "Lap 1", "pl": "Okrążenie 1"}[language]
    run = lap(distance=1000.0, timer_time=302.0, elapsed_time=310.0, avg_speed=1000 / 302,
              avg_heart_rate=141)
    assert w.lap_caption(run, RUNNING) == {
        "en": f"1.00 km{NB}· 5:02{NB}· 5:02 /km{NB}· 141 bpm",
        "pl": f"1,00 km{NB}· 5:02{NB}· 5:02 /km{NB}· 141 ud./min"}[language]
    workout = lap(distance=0.0, timer_time=302.0, avg_heart_rate=141)
    assert w.lap_caption(workout, TRAINING) == {
        "en": f"5:02{NB}· 141 bpm", "pl": f"5:02{NB}· 141 ud./min"}[language]


def test_a_lap_line_has_only_what_the_lap_gives():
    """The timer time first, the elapsed time standing in; the speed worked out from the
    distance and the time when the lap does not give it; a ride in km/h."""
    w = words()
    assert w.lap_caption(lap(distance=5000.0, elapsed_time=600.0), CYCLING) == (
        f"5.00 km{NB}· 10:00{NB}· 30.0 km/h")
    assert w.lap_caption(lap(avg_heart_rate=120), TRAINING) == "120 bpm"
    assert w.lap_caption(lap(), TRAINING) == ""
