"""The Activity profiles page of the window (read only): the list of the device's profiles with
those of its newest activities first and a search; a profile's page with its screens in the
order the device scrolls through them; a screen's page with its layout and fields; what is not
known said as a number. All profiles here are made up."""

import types

import pytest
from fakes import (
    FitData,
    FitDefinition,
    ScreenRecord,
    descendants,
    fit_file,
    page_window,
    sport_file,
)
from fakes import window as stand_in

from openexpress.device.storage import LocalStorage
from openexpress.device.xmldevice import parse

pytestmark = pytest.mark.needs_display

RUN = (ScreenRecord(place=0, code=0, order=0, fields=(56, 6, 999, 16), variant=2),
       ScreenRecord(place=1, code=1, order=2, fields=(58, 7), variant=12),
       ScreenRecord(place=2, code=110, order=1, fields=(), variant=12),
       ScreenRecord(place=3, code=127, state=0, order=None, fields=(127,), variant=2),
       ScreenRecord(place=4, code=2, state=0, order=None, fields=(9,), variant=1))
ROAD = (ScreenRecord(place=0, code=0, order=0, fields=(48, 6, 56), variant=0),
        ScreenRecord(place=1, code=104, order=1),
        ScreenRecord(place=2, code=35, order=2, hidden=1),
        ScreenRecord(place=3, code=32, state=0, order=None))


def device(sports=True):
    types_ = [("FIT_TYPE_4", "Garmin/Activity")] + ([("FIT_TYPE_3", "Garmin/Sports")]
                                                     if sports else [])
    files = "".join(
        f"<DataType><Name>{n}</Name><File><Location><Path>{p}</Path><FileExtension>FIT"
        "</FileExtension></Location><TransferDirection>OutputFromUnit</TransferDirection>"
        "</File></DataType>" for n, p in types_)
    return parse(f"""<?xml version="1.0" encoding="UTF-8"?>
<Device xmlns="http://www.garmin.com/xmlschemas/GarminDevice/v2">
 <Model><PartNumber>006-B9999-00</PartNumber><SoftwareVersion>100</SoftwareVersion>
  <Description>Made-up watch</Description></Model>
 <Id>3000000081</Id>
 <MassStorageMode>{files}</MassStorageMode>
</Device>
""".encode())


def activity(start, profile):
    return fit_file(FitDefinition(0, 0, ((0, 0x00), (4, 0x86))), FitData(0, (4, start)),
                    FitDefinition(1, 18, ((2, 0x86), (5, 0x00), (7, 0x86), (8, 0x86))),
                    FitData(1, (start, 1, 600_000, 600_000)),
                    FitDefinition(2, 12, ((3, 0x07, 32), (0, 0x00))), FitData(2, (profile, 1)))


@pytest.fixture
def root(tmp_path):
    sports = tmp_path / "GARMIN" / "Sports"
    sports.mkdir(parents=True)
    (sports / "Run.fit").write_bytes(sport_file("Run", screens=RUN))
    (sports / "Hike.fit").write_bytes(sport_file("Hike", 17, screens=RUN[:1]))
    (sports / "Ćwiczenia.fit").write_bytes(sport_file("Ćwiczenia siłowe", 10, screens=RUN[:2]))
    (sports / "Road.fit").write_bytes(sport_file("Road", 2, screens=ROAD, shape="edge"))
    (sports / "Broken.fit").write_bytes(b"not a FIT file")
    acts = tmp_path / "GARMIN" / "Activity"
    acts.mkdir()
    (acts / "a.fit").write_bytes(activity(1_100_000_000, "Run"))
    (acts / "b.fit").write_bytes(activity(1_100_100_000, "Hike"))
    return tmp_path


def profiles_window(root, sports=True):
    import types as t

    from openexpress.gui.app import MainWindow

    win, section = page_window("profiles")
    win.session = t.SimpleNamespace(device=device(sports), storage=LocalStorage(root),
                                    unit_info_answer=None)
    for name in ("load_profiles", "show_profiles", "load_section"):
        setattr(win, name, t.MethodType(getattr(MainWindow, name), win))
    win.progress = lambda text: None  # the steps of the reading: not shown here
    return win, section


def _titles(widget):
    from gi.repository import Adw

    return [(w.get_title(), w.get_subtitle()) for w in descendants(widget)
            if isinstance(w, Adw.ActionRow) and w.get_visible()]


def _groups(section):
    return [(g.get_title(), g.get_visible()) for g in section.groups]


def test_the_list_of_the_profiles(root):
    win, section = profiles_window(root)
    win.load_profiles()
    assert [t for t, v in _groups(section) if v] == [
        "", "Used recently", "All profiles", "Files that are no profile"]
    recent = section.groups[1]
    assert [t for t, _s in _titles(recent)] == ["Hike", "Run"]  # the newest activity first
    every = section.groups[2]
    assert _titles(every) == [
        ("Ćwiczenia siłowe", "2 data screens"),
        ("Hike", "1 data screen"),
        ("Road", "1 data screen\u00a0· 1 built-in screen when needed (1 hidden)"),
        ("Run", "2 data screens\u00a0· 1 built-in screen")]
    (broken,) = _titles(section.groups[3])
    assert broken[0] == "Broken.fit" and "could not be read" in broken[1]


def test_the_search(root):
    from gi.repository import Gtk

    win, section = profiles_window(root)
    win.load_profiles()
    (entry,) = [w for w in descendants(section.groups[0]) if isinstance(w, Gtk.SearchEntry)]
    assert entry.get_placeholder_text() == "Search 4 profiles"
    entry.set_text("CWICZ")  # letter case and diacritics aside
    entry.emit("search-changed")
    assert [t for t, _s in _titles(section.groups[2])] == ["Ćwiczenia siłowe"]
    assert not section.groups[1].get_visible()  # none of the recent ones
    entry.set_text("")
    entry.emit("search-changed")
    assert len(_titles(section.groups[2])) == 4 and section.groups[1].get_visible()


def test_a_device_without_profiles(root):
    win, section = profiles_window(root, sports=False)
    win.load_profiles()
    assert section.stack.get_visible_child_name() == "info"
    assert section.info.get_description() == "This device keeps no activity profiles."


def test_nothing_is_written(root):
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    win, _section = profiles_window(root)
    win.load_profiles()
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


# --- a profile's page and a screen's ---------------------------------------------------------


def navigated(profile):
    from gi.repository import Adw

    from openexpress import profiles

    navigation = Adw.NavigationView()
    device_view = Adw.NavigationPage(title="Device", child=Adw.Bin())
    navigation.add(device_view)
    win = stand_in(navigation=navigation, device_view=device_view,
                   session=types.SimpleNamespace(device=device(), unit_info_answer=None))
    data = sport_file(*profile[0], screens=profile[1], shape=profile[2])
    found = profiles.ProfileFile("GARMIN/Sports/x.fit", "x.fit", len(data), 0.0,
                                 profiles.read_profile(data))
    return win, found


def _page_texts(win):
    from gi.repository import Gtk

    page = win.navigation.get_visible_page()
    labels = [w.get_label() for w in descendants(page) if isinstance(w, Gtk.Label)]
    return page, _titles(page), labels


def _section_labels(section):
    from gi.repository import Gtk

    return [w.get_label() for g in section.groups if g.get_visible() for w in descendants(g)
            if isinstance(w, Gtk.Label)]


def test_an_empty_folder_of_profiles_says_so(tmp_path):
    """The folder declared but empty: the page says there is no profile (not a blank page)."""
    (tmp_path / "GARMIN" / "Sports").mkdir(parents=True)
    win, section = profiles_window(tmp_path)
    win.load_profiles()
    assert "No activity profiles" in _section_labels(section)


def test_files_that_are_no_profile_alone(tmp_path):
    """Only files that are no profile: no search and no empty list of profiles, those files."""
    sports = tmp_path / "GARMIN" / "Sports"
    sports.mkdir(parents=True)
    (sports / "Broken.fit").write_bytes(b"not a FIT file")
    win, section = profiles_window(tmp_path)
    win.load_profiles()
    labels = _section_labels(section)
    assert "No activity profiles" in labels
    assert [t for t, v in _groups(section) if v] == ["", "Files that are no profile"]
    assert not any(t.startswith("Search") for t in labels)


def test_the_device_s_backups_of_profiles_in_one_line(root):
    """The copies an Edge keeps in Sports/Backups are no "files that are no profile": one line
    says when the device made them."""
    import os
    from datetime import datetime

    from fakes import backup_of_a_profile, descendants
    from gi.repository import Gtk

    backups = root / "GARMIN" / "Sports" / "Backups"
    backups.mkdir()
    (backups / "Run.fit").write_bytes(backup_of_a_profile())
    os.utime(backups / "Run.fit", (1_700_000_000, 1_700_000_000))
    win, section = profiles_window(root)
    win.load_profiles()
    labels = [w.get_label() for g in section.groups for w in descendants(g)
              if isinstance(w, Gtk.Label)]
    day = datetime.fromtimestamp(1_700_000_000).strftime("%Y-%m-%d")
    assert f"The device keeps backups of its profiles from {day}" in labels
    unreadable = [g for g in section.groups if g.get_title() == "Files that are no profile"]
    assert [t for t, _s in _titles(unreadable[0])] == ["Broken.fit"]


def _groups_of(page):
    from gi.repository import Adw

    return [g.get_title() for g in descendants(page) if isinstance(g, Adw.PreferencesGroup)
            and g.get_title()]


def test_a_watch_profile_s_page(monkeypatch):
    from gi.repository import Adw

    from openexpress.gui import profiles_page

    win, found = navigated((("Run",), RUN, "watch"))
    profiles_page.open_profile(win, found)
    page, rows, labels = _page_texts(win)
    assert page.get_tag() == "profile" and page.get_title() == "Run"
    assert _groups_of(page) == ["Data screens", "Built-in screens in the scrolling order",
                                "Off and hidden", "Details"]
    # Each data screen: its place in the scrolling order, its fields numbered, legible.
    assert "No. 1 in the scrolling order\u00a0· 4 fields\u00a0· Layout “Stack”" in labels
    numbered = [t for t in labels if t[:3] in ("1. ", "2. ", "3. ", "4. ")]
    assert numbered[:4] == ["1. Timer", "2. Distance", "3. Field 999", "4. %Max Heart Rate"]
    assert "No. 3 in the scrolling order\u00a0· 2 fields\u00a0· Layout code 12, unknown" in labels
    # A built-in screen: a row with its place; one not known says so.
    assert ("Built-in screen 110",
            "No. 2 in the scrolling order\u00a0· Not known to openExpress yet") in rows
    assert not any(isinstance(w, Adw.ExpanderRow) for w in descendants(page))  # a watch's: none
    assert ("Screen 3", "1 field\u00a0· Layout “No Labels”") in rows  # turned off
    assert ("Built-in screen 127", "Not known to openExpress yet") in rows
    assert "Off" not in labels  # all of them off: no state said
    assert any("not known to openExpress yet" in t for t in labels)  # the watch's note


def test_an_edge_profile_s_page():
    from gi.repository import Adw

    from openexpress.gui import profiles_page

    win, found = navigated((("Road", 2), ROAD, "edge"))
    profiles_page.open_profile(win, found)
    page, rows, labels = _page_texts(win)
    assert _groups_of(page) == ["Data screens", "Off and hidden", "Details"]
    assert "No. 1 in the scrolling order\u00a0· 3 fields\u00a0· Layout A" in labels
    numbered = [t for t in labels if t[:3] in ("1. ", "2. ", "3. ")]
    assert numbered[:3] == ["1. Speed", "2. Distance", "3. Timer"]
    # ClimbPro, shown only on a climb: in the folded group, with when.
    (needed,) = [w for w in descendants(page) if isinstance(w, Adw.ExpanderRow)]
    assert needed.get_title() == "1 built-in screen when needed" and not needed.get_expanded()
    assert ("ClimbPro", "On a climb") in rows
    assert ("Compass", "") in rows and "Hidden" in labels
    assert not any(t.startswith("Built-in screen 32") for t in labels)  # reserved: left out


def test_a_data_screen_s_card_opens_its_page():
    from gi.repository import Gtk

    from openexpress.gui import profiles_page

    win, found = navigated((("Run",), RUN, "watch"))
    profiles_page.open_profile(win, found)
    page = win.navigation.get_visible_page()
    (card, *_rest) = [w for w in descendants(page)
                      if isinstance(w, Gtk.Button) and w.has_css_class("card")]
    card.emit("clicked")
    assert win.navigation.get_visible_page().get_tag() == "profile-screen"


def test_a_built_in_screen_not_known_has_the_icon_of_an_unknown_screen():
    """A code known on an Edge but not on a watch (127, Stamina) gives a watch's row the icon
    of a screen not known, not the Edge's."""
    from gi.repository import Gtk

    from openexpress.gui import profiles_page

    win, found = navigated((("Run",), RUN, "watch"))
    profiles_page.open_profile(win, found)
    page = win.navigation.get_visible_page()
    row = next(r for r in descendants(page) if getattr(r, "get_title", None)
               and r.get_title() == "Built-in screen 127")
    icons = [w.get_icon_name() for w in descendants(row) if isinstance(w, Gtk.Image)]
    assert profiles_page.UNKNOWN_SCREEN_ICON in icons
    assert profiles_page.built_in_icon(127) not in icons


def test_every_built_in_screen_s_icon_is_in_the_theme():
    from gi.repository import Gdk, Gtk

    from openexpress import profile_names
    from openexpress.gui import profiles_page

    theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    from pathlib import Path

    data = Path(__file__).resolve().parent.parent / "openexpress" / "data"
    theme.add_search_path(str(data))  # as the window does
    codes = set(profile_names._edge_screen_names()) | set(profile_names._watch_screen_names())
    names = {profiles_page.built_in_icon(code) for code in codes | {999}}
    assert [n for n in sorted(names) if not theme.has_icon(n)] == []


def test_a_screen_s_page():
    from openexpress.gui import profiles_page

    win, found = navigated((("Run",), RUN, "watch"))
    profiles_page.open_screen(win, found, found.profile.screens[0])
    page, rows, _labels = _page_texts(win)
    assert page.get_tag() == "profile-screen" and page.get_title() == "Screen 1"
    assert rows[:2] == [("Layout", "Layout “Stack”"), ("Number of fields", "4")]
    # "Field" names a data field only (one without a name by its number); its place is a place
    assert [r for r in rows if r[1].startswith("Place ")] == [
        ("Timer", "Place 1\u00a0· number 56"), ("Distance", "Place 2\u00a0· number 6"),
        ("Field 999", "Place 3\u00a0· number 999"), ("%Max Heart Rate", "Place 4\u00a0· number 16")]
    assert ("Code of the screen", "0") in rows


def test_the_pages_go_with_the_device_view():
    from openexpress.gui import profiles_page

    win, found = navigated((("Run",), RUN, "watch"))
    profiles_page.open_profile(win, found)
    profiles_page.open_screen(win, found, found.profile.screens[0])
    profiles_page.leave(win)
    assert win.navigation.get_visible_page() is win.device_view


def test_what_a_screen_s_drawing_says():
    """A screen of one's own: its fields; a built-in one: its name, or for one not known its
    code alone (its title under the drawing says the rest)."""
    from openexpress import profiles
    from openexpress.gui import profiles_page

    watch = profiles.read_profile(sport_file("Run", screens=RUN))
    edge = profiles.read_profile(sport_file("Road", 2, screens=ROAD, shape="edge"))
    by_code = {s.code: s for s in watch.screens}
    assert profiles_page.drawing_lines(watch, by_code[0]) == [
        "Timer", "Distance", "Field 999", "%Max Heart Rate"]
    assert profiles_page.drawing_lines(watch, by_code[110]) == ["110"]
    climb = next(s for s in edge.screens if s.code == 104)
    assert profiles_page.drawing_lines(edge, climb) == ["ClimbPro"]


# Long names of fields as a screen of an Edge and of a watch shows them.
LONG_FIELDS = ["Aktualny czas", "Stoper", "Upływ czasu", "Przygotowanie wydolnościowe",
               "Wskaźnik efektów treningu"]


@pytest.mark.parametrize("edge, size", [(True, 220), (False, 220), (True, 112)])
def test_a_field_s_name_is_drawn_whole(monkeypatch, edge, size):
    """A field's name is never cut short with "…" in a screen's drawing where two lines fit:
    it breaks onto a second line between its words, and the font is smaller when two lines
    would not fit."""
    import cairo
    from gi.repository import Gdk, PangoCairo

    from openexpress.gui import profiles_page

    drawn = []
    show = PangoCairo.show_layout
    monkeypatch.setattr(PangoCairo, "show_layout",
                        lambda cr, layout: (drawn.append(layout), show(cr, layout)))

    class Area:
        def get_color(self):
            return Gdk.RGBA()

    cr = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size))
    profiles_page.draw_screen(Area(), cr, size, size, edge, LONG_FIELDS)
    assert [layout.get_text() for layout in drawn] == LONG_FIELDS
    assert [layout.get_text() for layout in drawn if layout.is_ellipsized()] == []
    assert all(layout.get_line_count() <= 2 for layout in drawn)


# The seven fields of an Edge's first screen, most of them long.
MANY_FIELDS = ["Prędkość (średnia/maks.)", "Tętno (średnie/maks.)", "Dystans",
               "Kadencja (średnia/maks.)", "Moc (średnia/maks.)", "Aktualny czas", "Stoper"]


@pytest.mark.parametrize("edge, lines", [(True, MANY_FIELDS), (False, LONG_FIELDS)])
def test_long_names_on_a_card_never_overlap(monkeypatch, edge, lines):
    """On a card (112 px) long names may not each have two lines: each stays within its row,
    in one line cut short when two do not fit (the tooltip says them in full)."""
    import cairo
    from gi.repository import Gdk, PangoCairo

    from openexpress.gui import profiles_page

    drawn = []
    show = PangoCairo.show_layout
    monkeypatch.setattr(PangoCairo, "show_layout",
                        lambda cr, layout: (drawn.append(layout), show(cr, layout)))

    class Area:
        def get_color(self):
            return Gdk.RGBA()

    size = 112
    cr = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size))
    profiles_page.draw_screen(Area(), cr, size, size, edge, lines)
    # The inside of the drawing (an Edge's rectangle, the square in a watch's circle) in rows.
    inside = size - 4 - 8 if edge else (size / 2 - 2) * 2 ** 0.5
    row = inside / len(lines)
    assert [layout.get_text() for layout in drawn] == lines
    assert all(layout.get_pixel_size()[1] <= row for layout in drawn)


def test_a_screen_s_drawing_tells_its_fields_in_full():
    from openexpress import profiles
    from openexpress.gui import profiles_page

    watch = profiles.read_profile(sport_file("Run", screens=RUN))
    by_code = {s.code: s for s in watch.screens}
    drawing = profiles_page.screen_drawing(watch, by_code[0], 112)
    assert drawing.get_tooltip_text() == "Timer\nDistance\nField 999\n%Max Heart Rate"


@pytest.mark.parametrize("name", ["GroupTrack", "Podsumowanie okrążenia", "Shimano STEPS"])
def test_a_built_in_screen_s_name_keeps_its_words_whole(name):
    """The name of a built-in screen is drawn small enough for its longest word to fit the
    drawing's width: no word is broken in the middle."""
    import cairo
    from gi.repository import PangoCairo

    from openexpress.gui import profiles_page

    cr = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 10, 10))
    width = 52.0  # the inside of the smallest drawing, a card's
    font = profiles_page.name_font(cr, name, width, points=9.0)
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(font)
    widest = 0
    for word in name.split():
        layout.set_text(word, -1)
        widest = max(widest, layout.get_pixel_size()[0])
    assert widest <= width
    assert font.get_size() / 1024 >= 5.0  # never smaller than the least size
