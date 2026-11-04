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
    assert profile_names.field_name(588) == "Field 588"  # no name known: its number
    assert profile_names.field_name(None) == "Empty field"
    assert profile_names.field_name(216) == "Connect IQ data field"
    assert profile_names.field_name(201) == "Time in Heart Rate Zone 3"
    assert profile_names.field_name(419) == "Time in Power Zone 9"
    assert profile_names.known_field(56) and not profile_names.known_field(588)


def test_the_names_in_polish():
    try:
        i18n.setup("pl")
        assert profile_names.field_name(6) == "Dystans"
        assert profile_names.field_name(7) == "Dystans okrążenia"
        assert profile_names.field_name(588) == "Pole 588"
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
]


@pytest.mark.parametrize("number, english, polish", COMPOSITE_FIELDS + WATCH_FIELDS)
def test_a_field_has_its_name(number, english, polish):
    assert profile_names.known_field(number)
    assert profile_names.field_name(number) == english
    try:
        i18n.setup("pl")
        assert profile_names.field_name(number) == polish
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
    with open(ROOT / "openexpress" / "locale" / "pl" / "LC_MESSAGES" / "openexpress.mo",
              "rb") as f:
        catalog = gettext.GNUTranslations(f)
    missing = [w for w in words if catalog.pgettext("data field", w) == w
               and w not in SAME_IN_POLISH]
    assert missing == []


# Names Garmin's Polish manuals leave in English.
SAME_IN_POLISH = {"Intensity Factor", "Normalized Power", "TSS", "VAM", "Stamina"}


@pytest.mark.parametrize("edge, code, name", [
    (True, 25, "Map"), (True, 104, "ClimbPro"), (True, 127, "Stamina"),
    (True, 999, "Built-in screen 999"),
    (False, 25, "Built-in screen 25"),  # a watch's codes are not known yet
    (False, 127, "Built-in screen 127"),
])
def test_a_built_in_screen_by_its_code(edge, code, name):
    assert profile_names.built_in_name(screen(code), edge) == name
    assert profile_names.built_in_known(screen(code), edge) is not name.startswith("Built-in")


@pytest.mark.parametrize("edge, variant, said, known", [
    (True, 0, "Layout A", True), (True, 1, "Layout B", True), (True, 2, "Layout C", True),
    (True, 7, "Layout code 7, unknown", False),
    (False, 2, "Layout code 2, unknown", False),  # a watch's: not known yet
    (False, 12, "Layout code 12, unknown", False),
    (True, None, "Layout not given", False),
])
def test_a_layout_by_its_variant(edge, variant, said, known):
    assert profile_names.layout_name(variant, edge) == said
    assert profile_names.layout_known(variant, edge) is known
