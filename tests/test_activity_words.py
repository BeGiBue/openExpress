"""The words of an activity's page (gui/words.py): times with seconds, distances, pace or speed
by sport, heart rate, calories, ascent, the names of the tiles and the line of a lap, in English
and in Polish. A distance of 0 m and a value not given say nothing. Every value is made up."""

import pytest

from openexpress import fit, i18n

NB = "\u00a0"
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


# --- the tiles on top of the page ----------------------------------------------------------------


def activity(**values):
    return fit.ActivityData(fit.FileState.WHOLE, **values)


HIKE = activity(sport=HIKING, timer_time=13_800.0, elapsed_time=14_400.0, distance=12_400.0,
                avg_speed=1.0, avg_heart_rate=128, max_heart_rate=165, calories=900, ascent=740)
WORKOUT = activity(sport=TRAINING, timer_time=2700.0, distance=0.0, avg_heart_rate=112,
                   max_heart_rate=151, calories=320)

TILES_OF = {
    "en": {"hike": [("12.40 km", "Distance"), ("3:50:00", "Time"), ("16:40 /km", "Average pace"),
                    ("128 bpm", "Average heart rate"), ("740 m", "Total ascent")],
           "workout": [("45:00", "Time"), ("112 bpm", "Average heart rate"),
                       ("151 bpm", "Maximum heart rate"), ("320 kcal", "Calories")]},
    "pl": {"hike": [("12,40 km", "Dystans"), ("3:50:00", "Czas"), ("16:40 /km", "Średnie tempo"),
                    ("128 ud./min", "Średnie tętno"), ("740 m", "Przewyższenie")],
           "workout": [("45:00", "Czas"), ("112 ud./min", "Średnie tętno"),
                       ("151 ud./min", "Maksymalne tętno"), ("320 kcal", "Kalorie")]},
}


def test_the_tiles_of_a_hike_and_of_a_workout(language):
    """With a distance: distance, time, pace, average heart rate and ascent, five at most; a
    workout with a distance of 0 m: time, average and maximum heart rate, calories."""
    w = words()
    assert w.activity_tiles(HIKE) == TILES_OF[language]["hike"]
    assert w.activity_tiles(WORKOUT) == TILES_OF[language]["workout"]


def test_a_ride_has_its_speed_worked_out_when_its_session_does_not_say_it():
    ride = activity(sport=CYCLING, timer_time=3600.0, distance=30_000.0)
    assert words().activity_tiles(ride) == [("30.00 km", "Distance"), ("1:00:00", "Time"),
                                           ("30.0 km/h", "Average speed")]


def test_a_value_not_given_leaves_its_tile_out():
    w = words()
    assert w.activity_tiles(activity(sport=RUNNING, timer_time=600.0)) == [("10:00", "Time")]
    assert w.activity_tiles(activity(sport=TRAINING, calories=0)) == [("0 kcal", "Calories")]
    assert w.activity_tiles(activity()) == []  # no session: no tile


# --- the chart -----------------------------------------------------------------------------------

KINDS = ["heart rate", "elevation", "pace", "swim pace", "speed"]
CHART = {
    "en": {"names": ["Heart rate", "Elevation", "Pace", "Pace", "Speed"],
           "units": ["bpm", "m", "min/km", "min/100 m", "km/h"]},
    "pl": {"names": ["Tętno", "Wysokość", "Tempo", "Tempo", "Prędkość"],
           "units": ["ud./min", "m", "min/km", "min/100 m", "km/h"]},
}


def test_the_names_and_units_of_the_chart(language):
    w = words()
    assert [w.chart_series_name(kind) for kind in KINDS] == CHART[language]["names"]
    assert [w.chart_unit(kind) for kind in KINDS] == CHART[language]["units"]
    assert w.chart_accessible_name("heart rate") == {"en": "Heart rate over time",
                                                     "pl": f"Tętno w{NB}czasie"}[language]
    assert w.no_chart_text() == {
        "en": "No heart rate, elevation or speed in this activity",
        "pl": f"Brak tętna, wysokości i{NB}prędkości w{NB}tej aktywności"}[language]


def test_the_values_on_the_axes(language):
    """Whole numbers for heart rate and elevation, the decimals of the step for a speed, a
    pace as a clock."""
    w = words()
    assert w.chart_tick("heart rate", 125, 25) == "125"
    assert w.chart_tick("elevation", -5, 5) == "-5"
    assert w.chart_tick("speed", 3.5, 0.5) == {"en": "3.5", "pl": "3,5"}[language]
    assert w.chart_tick("speed", 3.0, 0.5) == {"en": "3.0", "pl": "3,0"}[language]
    assert w.chart_tick("speed", 25, 5) == "25"
    assert w.chart_tick("pace", 750, 30) == "12:30"
    assert w.chart_tick("swim pace", 125, 5) == "2:05"


def test_the_value_at_the_cursor(language):
    w = words()
    at = w.chart_cursor_text
    assert at(1880, "heart rate", 152) == {"en": f"31:20{NB}· 152 bpm",
                                           "pl": f"31:20{NB}· 152 ud./min"}[language]
    assert at(1880, "elevation", 412.4) == f"31:20{NB}· 412 m"
    assert at(1880, "pace", 310) == f"31:20{NB}· 5:10 /km"
    assert at(1880, "swim pace", 125) == f"31:20{NB}· 2:05 /100 m"
    assert at(1880, "speed", 24.31) == {"en": f"31:20{NB}· 24.3 km/h",
                                        "pl": f"31:20{NB}· 24,3 km/h"}[language]
    assert at(1880, "heart rate", None) == {"en": f"31:20{NB}· no reading",
                                            "pl": f"31:20{NB}· brak odczytu"}[language]
