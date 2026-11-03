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
    run = lap(distance=1500.0, timer_time=453.0, elapsed_time=465.0, avg_speed=1500 / 453,
              avg_heart_rate=141)
    assert w.lap_caption(run, RUNNING) == {
        "en": f"1.50 km{NB}· 7:33{NB}· 5:02 /km{NB}· 141 bpm",
        "pl": f"1,50 km{NB}· 7:33{NB}· 5:02 /km{NB}· 141 ud./min"}[language]
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


def test_the_tiles_by_their_kind_for_their_icons():
    """The same tiles, each by its kind (its icon on the page) with its value."""
    w = words()
    assert w.activity_tile_kinds(HIKE) == [
        ("distance", "12.40 km"), ("time", "3:50:00"), ("pace", "16:40 /km"),
        ("average heart rate", "128 bpm"), ("ascent", "740 m")]
    assert [kind for kind, _value in w.activity_tile_kinds(WORKOUT)] == [
        "time", "average heart rate", "maximum heart rate", "calories"]


ZONES = {
    "en": {"title": "Heart-rate zones", "below": "Below zone 1", "zone": "Zone 3",
           "share": "36:30 · 88%",
           "threshold": "Bounds from the device: % of lactate threshold (165 bpm)",
           "max": "Bounds from the device: % of maximum heart rate (190 bpm)",
           "reserve": "Bounds from the device: % of heart rate reserve",
           "custom": "Bounds from the device: your own"},
    "pl": {"title": "Strefy tętna", "below": "Poniżej strefy 1", "zone": "Strefa 3",
           "share": "36:30 · 88%",
           "threshold": "Granice z\u00a0zegarka, od progu mleczanowego (165 ud./min)",
           "max": "Granice z\u00a0zegarka, od tętna maksymalnego (190 ud./min)",
           "reserve": "Granice z\u00a0zegarka, od rezerwy tętna",
           "custom": "Granice z\u00a0zegarka: własne"},
}


def zones(method="threshold", threshold=165):
    return fit.HeartRateZones(times=(2190, 300, 0, 0, 0, 0), bounds=(120, 140, 155, 165, 178, 190),
                              method=method, max_heart_rate=190, resting_heart_rate=55,
                              threshold_heart_rate=threshold)


def test_the_words_of_the_heart_rate_zones(language):
    w, said = words(), ZONES[language]
    assert w.zones_title() == said["title"]
    assert w.zone_name(0) == said["below"] and w.zone_name(3) == said["zone"]
    assert w.zone_share(2190, 2490) == said["share"]
    for method in ("threshold", "max", "reserve", "custom"):
        assert w.zones_method_text(zones(method)) == said[method]
    assert w.zones_method_text(zones(None)) is None
    assert w.zones_method_text(zones("threshold", None)) is None  # its number not given


EFFECT = {
    "en": {"title": "Training effect", "aerobic": "Aerobic", "anaerobic": "Anaerobic",
           "load": "Training load",
           "words": ["No benefit", "No benefit", "Minor benefit", "Minor benefit", "Maintaining",
                     "Improving", "Highly improving", "Highly improving", "Overreaching"],
           "text": f"1.6{NB}· Minor benefit"},
    # Garmin's own Polish words, as Garmin Connect and Garmin's pages say them.
    "pl": {"title": "Efekt treningu", "aerobic": "Aerobowy", "anaerobic": "Beztlenowy",
           "load": "Obciążenie wysiłkowe",
           "words": ["Brak korzyści", "Brak korzyści", "Umiarkowana korzyść",
                     "Umiarkowana korzyść", "Utrzymanie", "Wzrost", "Znaczna poprawa",
                     "Znaczna poprawa", "Przeciążenie"],
           "text": f"1,6{NB}· Umiarkowana korzyść"},
}


def test_the_words_of_the_training_effect(language):
    """The word of the public scale, at its edges: below 1 no benefit, from 1 minor, 2
    maintaining, 3 improving, 4 highly improving, 5 overreaching."""
    w, said = words(), EFFECT[language]
    assert w.effect_title() == said["title"]
    assert (w.effect_name("aerobic"), w.effect_name("anaerobic")) == (said["aerobic"],
                                                                      said["anaerobic"])
    assert w.training_load_name() == said["load"]
    edges = (0.0, 0.9, 1.0, 1.9, 2.0, 3.0, 4.0, 4.9, 5.0)
    assert [w.effect_word(value) for value in edges] == said["words"]
    assert w.effect_text(1.6) == said["text"]


@pytest.mark.parametrize(("load", "said"), [(28.4, "28"), (28.5, "29"), (0.0, "0"),
                                            (1234.6, "1235")])
def test_the_training_load_as_a_whole_number(load, said):
    assert words().training_load_text(load) == said


TRACK = {
    "en": {"heart rate": "Track colour: heart rate", "elevation": "Track colour: elevation",
           "pace": "Track colour: pace", "swim pace": "Track colour: pace",
           "speed": "Track colour: speed", "switch": "Colours"},
    "pl": {"heart rate": "Kolor trasy: tętno", "elevation": "Kolor trasy: wysokość",
           "pace": "Kolor trasy: tempo", "swim pace": "Kolor trasy: tempo",
           "speed": "Kolor trasy: prędkość", "switch": "Kolory"},
}


def test_the_words_of_the_track_s_colours(language):
    """The series after the colon in lower case, as a sentence goes on in Polish."""
    w, said = words(), TRACK[language]
    for kind in ("heart rate", "elevation", "pace", "swim pace", "speed"):
        assert w.track_colour_text(kind) == said[kind]
    assert w.colours_text() == said["switch"]


# The bounds as a device keeps them: each the first beat of the zone above it, the last the top
# of zone 5 (which has none on the page). Zones from the lactate threshold, as Garmin Connect
# shows them: below zone 1 under 118, zone 1 118–140, …, zone 5 above 182; and from a maximum
# heart rate of 190.
ZONE_SPANS = {
    "threshold": ((118, 141, 158, 170, 183, 195), {
        "en": ["below 118 bpm", "118–140 bpm", "141–157 bpm", "158–169 bpm", "170–182 bpm",
               "above 182 bpm"],
        "pl": ["poniżej 118 ud./min", "118–140 ud./min", "141–157 ud./min", "158–169 ud./min",
               "170–182 ud./min", "powyżej 182 ud./min"]}),
    "max": ((95, 114, 133, 152, 171, 190), {
        "en": ["below 95 bpm", "95–113 bpm", "114–132 bpm", "133–151 bpm", "152–170 bpm",
               "above 170 bpm"],
        "pl": ["poniżej 95 ud./min", "95–113 ud./min", "114–132 ud./min", "133–151 ud./min",
               "152–170 ud./min", "powyżej 170 ud./min"]}),
}


@pytest.mark.parametrize("worked_out", ZONE_SPANS)
def test_the_heart_rates_of_each_zone_from_its_bounds(language, worked_out):
    """A bound is the first beat of the zone above it: below zone 1 under the first, a zone
    from its bound to a beat under the next, zone 5 above a beat under its own, no top."""
    bounds, said = ZONE_SPANS[worked_out][0], ZONE_SPANS[worked_out][1][language]
    assert [words().zone_range(bounds, n) for n in range(6)] == said


@pytest.mark.parametrize(("sport", "metres", "pace"), [
    (11, 1000.0, False), (11, 1004.0, False), (11, 1010.0, True), (11, 995.0, True),
    (5, 100.0, False), (5, 105.0, True), (2, 1000.0, True)])
def test_a_lap_whose_pace_is_its_time_leaves_it_out(sport, metres, pace):
    """A lap shown as 1.00 km at a pace a kilometre (100 m at a pace of 100 m in a swim): its
    pace is its time. One shown otherwise (0.99 km, 1.01 km) keeps it; a speed stays."""
    lap = fit.Lap(1_700_000_000, 600.0, 600.0, metres, metres / 600, 120)
    shown = words().lap_caption(lap, sport)
    assert ("/km" in shown or "/100 m" in shown or "km/h" in shown) is pace


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
