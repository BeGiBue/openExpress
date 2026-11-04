"""Reading the data screens of a sport profile (FIT file type 3) without changing anything: its
name and colour, and the screens of message 14 – the place, code, state, order, field IDs,
variant and, on an Edge, whether it is hidden. Message 13, which holds personal settings, is
never decoded. All profiles here are made up."""

import pytest
from fakes import FitData, FitDefinition, ScreenRecord, fit_file, sport_file

from openexpress import fit, profiles

RUN_SCREENS = (
    ScreenRecord(place=0, code=0, order=0, fields=(56, 6, 33, 16), variant=2),
    ScreenRecord(place=1, code=1, order=1, fields=(58, 7), variant=2),
    ScreenRecord(place=2, code=25, order=2, fields=(), variant=12),
    ScreenRecord(place=3, code=127, state=0, order=None, fields=(127, 33), variant=2),
)


def screen_of(code):
    return profiles.Screen(place=0, code=code, state=1, order=0, fields=(), variant=None,
                           hidden=None)


def test_a_watch_profile():
    p = profiles.read_profile(sport_file("Bieg", 1, 0, (230, 20, 30, 255), RUN_SCREENS,
                                         unused=5))
    assert (p.name, p.sport, p.sub_sport, p.colour) == ("Bieg", 1, 0, (230, 20, 30))
    assert p.slots == 8 and p.has_hidden_flag is False
    assert [s.place for s in p.screens] == [0, 1, 2, 3]  # the unused places are left out
    first = p.screens[0]
    assert (first.code, first.state, first.order, first.fields, first.variant) == (
        0, 1, 0, (56, 6, 33, 16), 2)
    assert first.own and first.shown and first.hidden is None
    assert not p.screens[2].own  # code 25: built in
    assert not screen_of(21).own and not screen_of(22).own and screen_of(9).own  # 20 on: built in
    assert not p.screens[3].shown  # off: no place in the carousel
    assert [s.place for s in p.carousel()] == [0, 1, 2]
    assert [s.code for s in p.own_screens()] == [0, 1]
    assert [s.code for s in p.built_in()] == [25, 127]


def test_an_edge_s_screen_hidden_by_its_visibility():
    """On an Edge 1050 a built-in screen hidden on the device (the Map of an indoor trainer's
    profile) says so in field 11 (2; 1: shown), field 12 staying 0."""
    p = profiles.read_profile(sport_file("Indoor", 2, 6, screens=(
        ScreenRecord(place=0, code=0, order=0, fields=(56,), variant=1),
        ScreenRecord(place=1, code=25, order=1, visibility=2),
        ScreenRecord(place=2, code=44, order=2)), shape="edge"))
    by_code = {s.code: s for s in p.screens}
    assert by_code[25].hidden and not by_code[25].shown
    assert not by_code[44].hidden and by_code[44].shown
    assert [s.code for s in p.carousel()] == [0, 44]


def test_an_edge_profile_says_which_screens_are_hidden():
    screens = (ScreenRecord(place=0, code=0, order=0, fields=(48, 6, 56, 16, 23, 2),
                            variant=0),
               ScreenRecord(place=1, code=35, order=1, hidden=1),
               ScreenRecord(place=2, code=25, order=2))
    p = profiles.read_profile(sport_file("Road", 2, 7, screens=screens, shape="edge"))
    assert p.slots == 10 and p.has_hidden_flag and p.colour == (200, 40, 40)
    assert [s.hidden for s in p.screens] == [False, True, False]
    assert [s.code for s in p.carousel()] == [0, 25]  # a hidden screen does not scroll


def test_the_carousel_follows_the_order_not_the_place():
    screens = (ScreenRecord(place=0, code=0, order=2, fields=(56,)),
               ScreenRecord(place=1, code=1, order=0, fields=(6,)),
               ScreenRecord(place=2, code=25, order=1))
    p = profiles.read_profile(sport_file(screens=screens))
    assert [s.place for s in p.carousel()] == [1, 2, 0]


def test_the_fields_are_those_the_count_says():
    """Places past the count keep old IDs, which the device does not clear; an empty place in
    the count is None."""
    screens = (ScreenRecord(place=0, code=0, order=0, fields=(56, None, 6, 16)),)
    data = sport_file(screens=screens)
    p = profiles.read_profile(data)
    assert p.screens[0].fields == (56, None, 6, 16)
    fewer = (ScreenRecord(place=0, code=0, order=0, fields=(56, 6)),)
    assert profiles.read_profile(sport_file(screens=fewer)).screens[0].fields == (56, 6)


def test_message_13_is_never_decoded(monkeypatch):
    """The personal settings of a profile (zones, weight…) are stepped over, not read."""
    asked = []
    real = fit.iter_messages

    def spy(data, wanted=None, arrays=()):
        asked.append(set(wanted or ()))
        return real(data, wanted=wanted, arrays=arrays)

    monkeypatch.setattr(fit, "iter_messages", spy)
    p = profiles.read_profile(sport_file(screens=RUN_SCREENS, personal=b"secret"))
    assert asked and all(13 not in wanted and wanted for wanted in asked)
    assert "secret" not in repr(p)


@pytest.mark.parametrize("data, said", [
    (b"not a FIT file at all", "could not be read"),
    (sport_file(screens=RUN_SCREENS, cut=40), "could not be read"),
    (fit_file(FitDefinition(0, 0, ((0, 0x00),)), FitData(0, (4,))), "not a sport profile"),
], ids=["no FIT", "cut short", "an activity"])
def test_a_file_that_is_no_profile_is_refused(data, said):
    with pytest.raises(profiles.ProfileError, match=said):
        profiles.read_profile(data)


def test_a_profile_cut_after_its_screens_is_read_as_far_as_it_goes():
    whole = sport_file(screens=RUN_SCREENS)
    p = profiles.read_profile(whole[:-2])  # its CRC gone
    assert len(p.screens) == len(RUN_SCREENS) and p.incomplete
    assert not profiles.read_profile(whole).incomplete


def test_a_profile_without_screens():
    p = profiles.read_profile(sport_file(screens=()))
    assert p.screens == () and p.carousel() == []


def test_the_profile_s_repr_names_no_file_content():
    p = profiles.read_profile(sport_file(screens=RUN_SCREENS))
    assert "1234567" not in repr(p)  # the made-up serial number of file_id is not kept


# --- the copies of real profiles (testdata/, the user's own; skipped without them) -----------

REAL = {"sports": (8, False), "sports-edge": (10, True)}


@pytest.mark.parametrize("folder", sorted(REAL))
def test_every_copied_profile_reads(folder):
    """Every copied profile reads, in the shape of its device; no value of it is compared."""
    from pathlib import Path

    files = sorted((Path(__file__).parent.parent / "testdata" / folder).glob("*.fit"))
    if not files:
        pytest.skip(f"no copies in testdata/{folder}")
    shapes = {(p.slots, p.has_hidden_flag)
              for p in (profiles.read_profile(f.read_bytes()) for f in files)}
    assert shapes == {REAL[folder]}
