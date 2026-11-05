"""The names of what a profile's data screens show (profile_names): Garmin's words for the data
fields, the built-in screens an Edge's profile knows, the layouts of an Edge's screens, each with
its Polish; a number nobody has named is said as a number, never guessed (a watch's built-in
screens and layouts among them)."""

import ast
import gettext
from pathlib import Path

import pytest

from openexpress import i18n, profile_names
from openexpress.profiles import Screen

ROOT = Path(__file__).resolve().parent.parent


def screen(code, own_number=None, variant=None):
    return Screen(place=0, code=code, state=1, order=0, fields=(), variant=variant, hidden=None)


def test_a_field_by_its_number():
    assert profile_names.field_name(56) == "Timer"
    assert profile_names.field_name(7) == "Lap Distance"
    assert profile_names.field_name(999) == "Field 999"  # no name known: its number
    assert profile_names.field_name(None) == "Empty field"
    assert profile_names.field_name(216) == "Connect IQ data field"
    assert profile_names.field_name(201) == "Time in Heart Rate Zone 3"
    assert profile_names.field_name(419) == "Time in Power Zone 9"
    assert profile_names.known_field(56) and not profile_names.known_field(999)


def test_the_names_in_polish():
    try:
        i18n.setup("pl")
        assert profile_names.field_name(6) == "Dystans"
        assert profile_names.field_name(7) == "Dystans okrążenia"
        assert profile_names.field_name(999) == "Pole 999"
        assert profile_names.field_name(201) == "Czas w strefie tętna 3"
    finally:
        i18n.setup("en")


# The fields of an Edge that show two values in one place.
COMPOSITE_FIELDS = [
    (351, "Heart Rate (Avg/Max)", "Tętno (średnie/maks.)"),
    (352, "Speed (Avg/Max)", "Prędkość (średnia/maks.)"),
    (353, "Cadence (Avg/Max)", "Kadencja (średnia/maks.)"),
    (354, "Power (Avg/Max)", "Moc (średnia/maks.)"),
    (358, "Elevation (Asc/Desc)", "Wznios/spadek"),
]


# Fields a watch has and the Edge's table does not, named as the fēnix 8's manual names them.
WATCH_FIELDS = [
    (33, "Pace", "Tempo"),
    (34, "Average Pace", "Średnie tempo"),
    (35, "Lap Pace", "Tempo okrążenia"),
    (231, "Ambient Pressure", "Ciśnienie otoczenia"),
    (51, "SOG", "PND"),
    (205, "Stroke Rate", "Tempo ruchów"),
    (228, "Maximum Elevation", "Maksymalna wysokość"),
    (245, "Active Calories", "Aktywne kalorie"),
    (531, "Total Ascent/Descent Gauge", "Wskaź. całkow. wzniosu/spadku"),
    (586, "Elevation Chart", "Wykres wysokości"),
    (588, "Heart Rate Chart", "Wykres tętna"),
    (590, "Speed Chart", "Wykres prędkości"),
    (610, "Heart Rate Zones Ratio", "Stosunek stref tętna"),
    (530, "Training Effect Gauge", "Wskaźnik efektów treningu"),
]


# A field of an Edge the table has not, named as the Edge 1050 shows it.
EDGE_FIELDS = [(711, "Training Effect", "Efekt treningu")]


@pytest.mark.parametrize("number, english, polish",
                         COMPOSITE_FIELDS + WATCH_FIELDS + EDGE_FIELDS)
def test_a_field_has_its_name(number, english, polish):
    assert profile_names.known_field(number)
    assert profile_names.field_name(number) == english
    try:
        i18n.setup("pl")
        assert profile_names.field_name(number) == polish
    finally:
        i18n.setup("en")


# A number a watch gives a field of its own, named so on a watch only: (number, on an Edge,
# on a watch in English and in Polish).
WATCH_NAMES = [(77, "VAM", "Vertical Speed", "Prędkość pionowa"),
               (97, "GPS Signal Strength", "GPS", "GPS")]


@pytest.mark.parametrize("number, edge, english, polish", WATCH_NAMES)
def test_a_watch_names_some_numbers_its_own_way(number, edge, english, polish):
    assert profile_names.field_name(number) == edge
    assert profile_names.field_name(number, edge=False) == english
    try:
        i18n.setup("pl")
        assert profile_names.field_name(number, edge=False) == polish
    finally:
        i18n.setup("en")


def test_every_name_is_translated_and_each_number_named_once():
    tree = ast.parse((ROOT / "openexpress" / "profile_names.py").read_text())
    (table,) = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                and n.name == "_field_names"]
    (names,) = [n for n in ast.walk(table) if isinstance(n, ast.Dict)]
    numbers = [k.value for k in names.keys]
    assert len(numbers) == len(set(numbers)) > 150
    words = [v.args[1].value for v in names.values]
    from openexpress import i18n

    # The Polish catalog as the tests built it (none is kept in the repository).
    with open(i18n.LOCALE_DIR / "pl" / "LC_MESSAGES" / "openexpress.mo", "rb") as f:
        catalog = gettext.GNUTranslations(f)
    missing = [w for w in words if catalog.pgettext("data field", w) == w
               and w not in SAME_IN_POLISH]
    assert missing == []


# Names Garmin's Polish manuals leave in English.
SAME_IN_POLISH = {"Intensity Factor", "Normalized Power", "TSS", "VAM", "Stamina"}


@pytest.mark.parametrize("edge, code, name", [
    (True, 25, "Map"), (True, 104, "ClimbPro"), (True, 127, "Stamina"),
    (True, 999, "Built-in screen 999"),
    (False, 25, "Map"), (False, 35, "Compass"), (False, 21, "Clock with Status Icons"),
    (False, 22, "Heart Rate Zone Gauge"), (False, 100, "Regatta Timer"),
    (False, 101, "Tack Assist"), (False, 221, "Clock with Sun Info"), (False, 80, "Set"),
    (False, 127, "Built-in screen 127"), (False, 20, "Built-in screen 20"),  # not known yet
])
def test_a_built_in_screen_by_its_code(edge, code, name):
    assert profile_names.built_in_name(screen(code), edge) == name
    assert profile_names.built_in_known(screen(code), edge) is not name.startswith("Built-in")


@pytest.mark.parametrize("edge, code, when", [
    (True, 162, "during a group ride"), (True, 57, "during a group ride"),
    (True, 38, "during a workout"), (True, 56, "on a segment"), (True, 104, "on a climb"),
    (True, 125, "with an active power plan"), (True, 25, None), (True, 127, None),
    (False, 38, None),  # a watch's: not known yet
])
def test_a_built_in_screen_shown_when_needed(edge, code, when):
    """An Edge shows some built-in screens only in their situation (a group ride, a workout…)."""
    assert profile_names.when_needed(screen(code), edge) == when


@pytest.mark.parametrize("always, needed, hidden, said", [
    (3, 6, 1, "3 built-in screens (+6 when needed, 1 hidden)"),
    (3, 0, 0, "3 built-in screens"),
    (0, 1, 1, "1 built-in screen when needed (1 hidden)"),
    (2, 0, 2, "2 built-in screens (2 hidden)"),
])
def test_how_many_built_in_screens(always, needed, hidden, said):
    assert profile_names.built_in_count(always, needed, hidden) == said


def test_how_many_built_in_screens_in_polish():
    try:
        i18n.setup("pl")
        said = profile_names.built_in_count(3, 6, 1), profile_names.when_needed(screen(38), True)
    finally:
        i18n.setup("en")
    assert said == ("3 ekrany wbudowane (+6 w\u00a0razie potrzeby, 1 ukryty)", "podczas treningu")


def test_a_watch_s_built_in_screens_in_polish():
    try:
        i18n.setup("pl")
        said = [profile_names.built_in_name(screen(c), False)
                for c in (21, 22, 100, 101, 221, 80)]
    finally:
        i18n.setup("en")
    assert said == ["Zegar z\u00a0ikonami stanu", "Wskaźnik strefy tętna", "Minutnik regatowy",
                    "Asystent halsowania", "Zegar z\u00a0informacjami o\u00a0słońcu", "Seria"]


@pytest.mark.parametrize("edge, variant, said, known", [
    (True, 0, "Layout A", True), (True, 1, "Layout B", True), (True, 2, "Layout C", True),
    (True, 7, "Layout code 7, unknown", False),
    (False, 2, "Layout “Stack”", True), (False, 1, "Layout “No Labels”", True),
    (False, 12, "Layout code 12, unknown", False), (False, 4, "Layout code 4, unknown", False),
    (True, None, "Layout not given", False),
])
def test_a_layout_by_its_variant(edge, variant, said, known):
    assert profile_names.layout_name(variant, edge) == said
    assert profile_names.layout_known(variant, edge) is known


def test_a_watch_s_layouts_in_polish():
    try:
        i18n.setup("pl")
        said = [profile_names.layout_name(v, False) for v in (2, 1)]
    finally:
        i18n.setup("en")
    assert said == ["Układ „stos”", "Układ „bez podpisów”"]


def test_the_reserved_place_is_never_counted():
    """A place an Edge keeps for later (code 32) is no built-in screen, hidden or not: the
    count says what the page lists."""
    from fakes import ScreenRecord, sport_file

    from openexpress import profiles

    data = sport_file("Road", 2, shape="edge", screens=(
        ScreenRecord(place=0, code=0, order=0, fields=(6,), variant=0),
        ScreenRecord(place=1, code=25, order=1),
        ScreenRecord(place=2, code=32, order=2, hidden=1)))
    said = profile_names.built_in_summary(profiles.read_profile(data))
    assert said == "1 built-in screen"
