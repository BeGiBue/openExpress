"""The page of one activity, pushed onto the window's navigation from its row: its sport and
start in the header bar with the back arrow and the GPX export, its tiles, and what a file
that could not be read, one still being written, a damaged one and one without a summary say;
its file read again in a task from the device or from a backup's copy. Every file is made up
from the public FIT protocol."""

import types
from datetime import UTC, datetime

import pytest
from fakes import (
    FitData,
    FitDefinition,
    RunNow,
    fit_file,
    replace_in_window,
    tasks_at_once,
    window,
    window_methods,
)

pytestmark = pytest.mark.needs_display

FIT_EPOCH = int(datetime(1989, 12, 31, tzinfo=UTC).timestamp())
START = 1_100_000_000  # a time of the FIT protocol
HIKING, TRAINING = 17, 10
SESSION = FitDefinition(2, 18, ((2, 0x86), (5, 0x00), (6, 0x00), (7, 0x86), (8, 0x86),
                                (9, 0x86), (11, 0x84), (14, 0x84), (124, 0x86), (16, 0x02),
                                (17, 0x02), (22, 0x84)))
PLACED = FitDefinition(1, 20, ((253, 0x86), (0, 0x85), (1, 0x85), (3, 0x02)))
HEART = FitDefinition(1, 20, ((253, 0x86), (3, 0x02)))
NOTHING_READ = "The file of this activity could not be read."


def hike(cut=None, bad_crc=False) -> bytes:
    return fit_file(PLACED, FitData(1, (START, 624_000_000, 250_000_000, 120)),
                    FitData(1, (START + 1, 624_000_100, 250_000_000, 121)),
                    SESSION, FitData(2, (START, HIKING, 0, 14_400_000, 13_800_000, 1_240_000,
                                         900, None, 1000, 128, 165, 740)),
                    cut=cut, bad_crc=bad_crc)


def workout() -> bytes:
    return fit_file(HEART, FitData(1, (START, 110)), FitData(1, (START + 1, 112)),
                    SESSION, FitData(2, (START, TRAINING, 0, 2_700_000, 2_700_000, 0, 320,
                                         None, None, 112, 151, None)))


def read_of(source="device", sport=HIKING, state="WHOLE", positions=True):
    """The row's activity (activities.Read) and what its summary says (`state` None: no FIT
    file)."""
    from openexpress import activities, fit

    found = None if state is None else fit.ActivitySummary(
        getattr(fit.FileState, state), start=START + FIT_EPOCH, sport=sport, timer_time=600.0,
        has_positions=positions)
    where = activities.Activity(activities.Source(source), "GARMIN/Activity/a.fit", "a.fit",
                                100, 1.0, None if source == "device" else datetime(2026, 1, 2))
    return activities.Read(where, found)


def a_window(data, *, error="raise", busy=False):
    """A stand-in window with the real navigation: the list under it; reading gives `data`
    (bytes, None: not readable, an exception: raised)."""
    from gi.repository import Adw, Gtk

    navigation = Adw.NavigationView()
    the_list = Adw.NavigationPage(title="Device", tag="device", child=Gtk.Label())
    navigation.add(the_list)
    toplevel = Gtk.Window(child=navigation)

    def read_file(activity):
        if isinstance(data, Exception):
            raise data
        return data

    toasts = []
    win = window(navigation=navigation, toplevel=toplevel, busy=busy, _action_buttons=[],
                 run_task=RunNow(error=error), toast=toasts.append,
                 activities=types.SimpleNamespace(read_file=read_file))
    win.toasts = toasts
    return win, the_list


def shown(win):
    return win.navigation.get_visible_page()


def _all(widget):
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from _all(child)
        child = child.get_next_sibling()


def seen(widget, page) -> bool:
    """Whether the widget would be seen on the page: it and every widget up to the page shown
    (a page of a Gtk.Stack that is not the visible one is not)."""
    while widget is not page:
        if not widget.get_visible() or not widget.get_child_visible():
            return False
        widget = widget.get_parent()
    return True


def labels(page) -> list[str]:
    from gi.repository import Gtk

    return [w.get_label() for w in _all(page) if isinstance(w, Gtk.Label) and seen(w, page)]


def status_texts(page) -> list[str]:
    from gi.repository import Adw

    return [t for w in _all(page) if isinstance(w, Adw.StatusPage) and seen(w, page)
            for t in (w.get_title(), w.get_description()) if t]


def open_page(win, read):
    from openexpress.gui import activity_page

    activity_page.open_activity(win, read)
    return shown(win)


def test_a_row_opens_the_page_of_its_activity_and_reads_it():
    from gi.repository import Adw

    win, the_list = a_window(hike())
    page = open_page(win, read_of())
    assert page is not the_list and page.get_tag() == "activity"
    (call,) = win.run_task.calls
    assert call.title == "Reading the activity…" and call.in_page and call.device
    title = next(w for w in _all(page) if isinstance(w, Adw.WindowTitle))
    assert title.get_title() == "Hiking" and title.get_subtitle()
    texts = labels(page)
    for value, name in [("12.40 km", "Distance"), ("3:50:00", "Time"),
                        ("16:40 /km", "Average pace"), ("128 bpm", "Average heart rate"),
                        ("740 m", "Total ascent")]:
        assert value in texts and name in texts


def test_back_returns_to_the_list():
    win, the_list = a_window(hike())
    open_page(win, read_of())
    win.navigation.pop()
    assert shown(win) is the_list


def test_the_gpx_button_in_the_header_exports_as_the_row_does(monkeypatch):
    from gi.repository import Adw, Gtk

    from openexpress.gui import activities_page

    exported = []
    monkeypatch.setattr(activities_page, "_export",
                        lambda win, read, button: exported.append(read))
    win, _the_list = a_window(hike())
    read = read_of()
    page = open_page(win, read)
    header = next(w for w in _all(page) if isinstance(w, Adw.HeaderBar))
    (button,) = [w for w in _all(header) if isinstance(w, Gtk.Button)
                 and w.get_tooltip_text() == "Export as GPX…"]
    button.emit("clicked")
    assert exported == [read]


def test_an_activity_without_positions_has_its_gpx_button_off():
    from gi.repository import Gtk

    win, _the_list = a_window(workout())
    page = open_page(win, read_of(sport=TRAINING, positions=False))
    (button,) = [w for w in _all(page) if isinstance(w, Gtk.Button)
                 and w.get_tooltip_text() == "No GPS positions in this activity"]
    assert not button.get_sensitive()
    texts = labels(page)
    assert {"45:00", "Time", "112 bpm", "151 bpm", "320 kcal", "Calories"} <= set(texts)
    assert "Distance" not in texts


def test_a_copy_in_a_backup_is_read_without_the_device():
    win, _the_list = a_window(hike())
    open_page(win, read_of(source="backup"))
    (call,) = win.run_task.calls
    assert not call.device


@pytest.mark.parametrize("fails", ["copy", "device", "no FIT file"])
def test_a_file_that_could_not_be_read_is_said_on_the_page(fails):
    """A copy in a backup that could not be read, an error of the device, a file that is no
    FIT file: the page says it, no error dialog (RunNow raises one)."""
    from openexpress.device.storage import DeviceError

    data = {"copy": None, "device": DeviceError("Cannot read GARMIN/Activity/a.fit: gone"),
            "no FIT file": b"not a FIT file at all"}[fails]
    win, _the_list = a_window(data)
    page = open_page(win, read_of())
    assert NOTHING_READ in status_texts(page)
    assert labels(page).count("12.40 km") == 0


def test_what_a_file_still_being_written_a_damaged_one_and_one_without_a_summary_say():
    win, _the_list = a_window(hike(cut=len(hike()) - 40))
    page = open_page(win, read_of())
    assert "Still being written: disconnect and reconnect the device" in status_texts(page)
    win, _the_list = a_window(hike(bad_crc=True))
    page = open_page(win, read_of())
    assert "Damaged file" in labels(page) and "12.40 km" in labels(page)
    win, _the_list = a_window(fit_file(HEART, FitData(1, (START, 110))))  # no session
    page = open_page(win, read_of())
    assert "This activity has no summary." in status_texts(page)


def test_while_another_task_runs_no_page_opens():
    win, the_list = a_window(hike(), busy=True)
    open_page(win, read_of())
    assert shown(win) is the_list and win.run_task.calls == []
    assert win.toasts == ["Another operation is in progress"]


def test_a_stall_while_the_activity_is_read_closes_the_page_with_the_device(monkeypatch):
    """No error dialog: the banner says it, and the page goes with the device."""
    from openexpress.device.gio_storage import GarminUsb
    from openexpress.device.storage import DeviceNotResponding
    from openexpress.gui.app import MainWindow

    tasks_at_once(monkeypatch)
    error = DeviceNotResponding.during("Cannot read GARMIN/Activity/a.fit")
    error.usb = GarminUsb("51b4", 3, 14)
    win, the_list = a_window(error)
    told = []
    replace_in_window(monkeypatch, "inform",
                      lambda parent, name, heading, body, **kw: told.append(body))
    window_methods(win, ["error"])
    win.run_task = types.MethodType(MainWindow.run_task, win)
    win.set_busy = lambda busy, *a, **kw: setattr(win, "busy", busy)
    win._run_pending_refresh = lambda: None
    win.session = types.SimpleNamespace(storage=types.SimpleNamespace(
        usb=GarminUsb("51b4", 3, 14), device_uri="mtp://Made_Up/", stalled=True),
        device=types.SimpleNamespace(description="Made-up watch"))
    win.start = types.SimpleNamespace(set_stalled=lambda text: None)
    win._update_banner = lambda: None
    win.connected = types.SimpleNamespace(devices=[])
    win.show_no_device = lambda: win.navigation.pop_to_page(the_list)
    open_page(win, read_of())
    assert told == [] and shown(win) is the_list and win.session is None


def test_rows_open_their_activity_but_for_a_file_that_is_no_fit_file():
    from gi.repository import Gtk

    from openexpress.gui.activities_page import activity_row

    win, _the_list = a_window(hike())
    row = activity_row(win, read_of())
    assert row.get_activatable()
    assert "go-next-symbolic" in [w.get_icon_name() for w in _all(row)
                                  if isinstance(w, Gtk.Image)]
    row.emit("activated")
    assert shown(win).get_tag() == "activity"
    unreadable = activity_row(win, read_of(state=None))
    assert not unreadable.get_activatable()


@pytest.mark.parametrize(("data", "sport", "count"), [(hike, HIKING, 5), (workout, TRAINING, 4)])
def test_the_tiles_share_the_whole_line_of_a_wide_window(data, sport, count):
    """No empty place at the end of the line: five tiles or four, they take its whole width."""
    from gi.repository import GLib, Gtk

    win, _the_list = a_window(data())
    page = open_page(win, read_of(sport=sport))
    win.toplevel.set_default_size(1000, 600)
    win.toplevel.present()
    try:
        flow = next(w for w in _all(page) if isinstance(w, Gtk.FlowBox))
        tiles = [w for w in _all(flow) if isinstance(w, Gtk.FlowBoxChild)]
        for _ in range(500):
            if flow.get_width() > 0:
                break
            GLib.MainContext.default().iteration(False)
        bounds = [t.compute_bounds(flow)[1] for t in tiles]
        assert len(tiles) == count and len({round(b.get_y()) for b in bounds}) == 1
        assert bounds[-1].get_x() + bounds[-1].get_width() >= flow.get_width() - 1
    finally:
        win.toplevel.destroy()


# --- the chart -------------------------------------------------------------------------------

WALKING = 11
# timestamp, position, enhanced altitude, heart rate, distance, enhanced speed
WALK_RECORD = FitDefinition(1, 20, ((253, 0x86), (0, 0x85), (1, 0x85), (78, 0x86), (3, 0x02),
                                    (5, 0x86), (73, 0x86)))


def walk() -> bytes:
    """Two minutes of a walk, a record each second: heart rate from 100 to 119 bpm and again,
    the elevation up from 100 m by 0.1 m a second, 1.2 m/s."""
    records = [FitData(1, (START + s, 624_000_000 + s * 10, 250_000_000,
                           round((100 + s * 0.1 + 500) * 5), 100 + s % 20, round(s * 120),
                           1200)) for s in range(120)]
    return fit_file(WALK_RECORD, *records, SESSION,
                    FitData(2, (START, WALKING, 0, 120_000, 119_000, 14_280, 30, None, 1200, 110,
                                119, 12)))


def heart_only() -> bytes:
    return fit_file(HEART, *(FitData(1, (START + s, 100 + s)) for s in range(30)), SESSION,
                    FitData(2, (START, TRAINING, 0, 30_000, 30_000, 0, 5, None, None, 115, 129,
                                None)))


def chart_of(page):
    from openexpress.gui.activity_chart import ActivityChart

    found = [w for w in _all(page) if isinstance(w, ActivityChart)]
    return found[0] if found else None


def switch_of(page) -> list:
    from gi.repository import Gtk

    return [w for w in _all(page) if isinstance(w, Gtk.ToggleButton)]


def test_the_chart_of_a_walk_switches_between_what_it_has():
    """Heart rate first; the switch shows the elevation and the pace in its place."""
    win, _the_list = a_window(walk())
    page = open_page(win, read_of(sport=WALKING))
    buttons = switch_of(page)
    assert [b.get_label() for b in buttons] == ["Heart rate", "Elevation", "Pace"]
    assert [b.get_active() for b in buttons] == [True, False, False]
    chart = chart_of(page)
    assert chart.area.series.kind == "heart rate" and chart.value_label.get_label() == ""
    buttons[1].set_active(True)
    assert chart.area.series.kind == "elevation"
    assert [b.get_active() for b in buttons] == [False, True, False]


def test_one_series_has_its_name_in_place_of_the_switch():
    win, _the_list = a_window(heart_only())
    page = open_page(win, read_of(sport=TRAINING, positions=False))
    assert switch_of(page) == [] and chart_of(page).area.series.kind == "heart rate"
    assert "Heart rate" in labels(chart_of(page))


def test_without_heart_rate_elevation_or_speed_no_chart_but_a_line():
    win, _the_list = a_window(workout())  # its records: heart rate only…
    page = open_page(win, read_of(sport=TRAINING, positions=False))
    assert chart_of(page) is not None
    positions = fit_file(PLACED, *(FitData(1, (START + s, 624_000_000 + s, 250_000_000, None))
                                   for s in range(3)),
                         SESSION, FitData(2, (START, HIKING, 0, 14_400_000, 13_800_000, 1_240_000,
                                              900, None, 1000, None, None, 740)))
    win, _the_list = a_window(positions)  # …positions only: nothing to chart
    page = open_page(win, read_of())
    assert chart_of(page) is None
    assert "No heart rate, elevation or speed in this activity" in labels(page)


def controllers(widget, kind):
    model = widget.observe_controllers()
    return next(c for c in (model.get_item(i) for i in range(model.get_n_items()))
                if isinstance(c, kind))


def cursor_time(text: str) -> int:
    minutes, seconds = text.split(" ", 1)[0].split(":")
    return int(minutes) * 60 + int(seconds)


def test_the_cursor_by_click_drag_and_the_arrow_keys():
    """A click puts it where it is, a drag moves it, the arrows and Home and End too; another
    series keeps its place."""
    from gi.repository import Gdk, GLib, Gtk

    win, _the_list = a_window(walk())
    page = open_page(win, read_of(sport=WALKING))
    win.toplevel.set_default_size(1000, 700)
    win.toplevel.present()
    try:
        chart = chart_of(page)
        area = chart.area
        for _ in range(500):
            if area.get_width() > 0:
                break
            GLib.MainContext.default().iteration(False)
        drag = controllers(area, Gtk.GestureDrag)
        keys = controllers(area, Gtk.EventControllerKey)
        said = chart.value_label.get_label

        drag.emit("drag-begin", area.get_width() / 2, 100)
        middle = cursor_time(said())
        assert 40 <= middle <= 80 and said().endswith(" bpm")
        for _ in range(50):
            GLib.MainContext.default().iteration(False)
        value = chart.value_label.compute_bounds(chart)[1]
        switch = switch_of(page)[0].compute_bounds(chart)[1]
        assert value.get_y() < switch.get_y() + switch.get_height()  # beside it, wide
        drag.emit("drag-update", area.get_width() / 4, 0)
        assert cursor_time(said()) > middle + 15
        before = cursor_time(said())
        assert keys.emit("key-pressed", Gdk.KEY_Left, 0, Gdk.ModifierType(0))
        assert cursor_time(said()) < before
        keys.emit("key-pressed", Gdk.KEY_Home, 0, Gdk.ModifierType(0))
        assert said() == "0:00 · 100 bpm"
        keys.emit("key-pressed", Gdk.KEY_End, 0, Gdk.ModifierType(0))
        assert said() == "1:59 · 119 bpm"
        switch_of(page)[1].set_active(True)
        assert said() == "1:59 · 112 m"
    finally:
        win.toplevel.destroy()


def test_the_chart_draws_each_series_with_its_cursor():
    import cairo

    from openexpress.gui import activity_chart

    win, _the_list = a_window(walk())
    page = open_page(win, read_of(sport=WALKING))
    chart = chart_of(page)
    for button in switch_of(page):
        button.set_active(True)
        for cursor in (None, 60):
            chart.area.cursor = cursor
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 600, 200)
            activity_chart._draw(chart.area, cairo.Context(surface), 600, 200)
            assert any(surface.get_data()), button.get_label()


def test_the_page_and_its_chart_are_released_once_closed():
    """No handler of the chart holds its widget or a sibling: back to the list, they go."""
    import gc

    from gi.repository import GLib

    win, _the_list = a_window(walk())
    page = open_page(win, read_of(sport=WALKING))
    chart = chart_of(page)
    switch_of(page)[1].set_active(True)
    chart.area.place(30)
    gone = []
    chart.area.weak_ref(lambda: gone.append("chart"))
    page.weak_ref(lambda: gone.append("page"))
    del chart, page
    win.navigation.pop()
    win.run_task.calls.clear()  # the stand-in keeps every task; the window keeps none
    win._action_buttons.clear()  # what the window drops as its pages are drawn again
    for _ in range(3):
        gc.collect()
        while GLib.main_context_default().iteration(False):
            pass
    assert sorted(gone) == ["chart", "page"]


# --- the map ---------------------------------------------------------------------------------

NOTE = ("The map can show streets and terrain under the track, from OpenStreetMap. The "
        "OpenStreetMap server then learns the area of each activity you open. You can turn this "
        "off again in Preferences.")


def map_of(page):
    from openexpress.gui.activity_map import ActivityMap

    found = [w for w in _all(page) if isinstance(w, ActivityMap)]
    return found[0] if found else None


def tile_layers(widget) -> list:
    from gi.repository import Shumate

    return [w for w in _all(widget) if isinstance(w, Shumate.MapLayer)]


def show_the_map_button(page):
    from gi.repository import Gtk

    found = [w for w in _all(page) if isinstance(w, Gtk.Button)
             and w.get_label() == "Show the Map" and seen(w, page)]
    return found[0] if found else None


@pytest.fixture
def no_tile_server(monkeypatch):
    """Tiles asked are answered at once, never by a server: what was asked in `asked`."""
    from openexpress.gui import activity_map

    asked = []

    def fetch(url, etag):
        asked.append(url)
        return activity_map.Fetched(404, None, None, 0)

    monkeypatch.setattr(activity_map, "_fetch", fetch)
    return asked


def test_before_the_yes_the_track_is_on_a_plain_background_with_the_note(no_tile_server):
    """No tile layer, so nothing is asked of OpenStreetMap; the note and its button say what
    turning the tiles on does; no attribution without tiles."""
    win, _the_list = a_window(walk())
    page = open_page(win, read_of(sport=WALKING))
    shown = map_of(page)
    assert shown is not None and tile_layers(shown) == [] and shown.tiles is None
    assert NOTE in labels(page) and show_the_map_button(page) is not None
    assert not shown.attribution.get_visible()
    assert no_tile_server == []


def test_show_the_map_turns_the_tiles_on_for_the_program(no_tile_server):
    """Once for the program: the next activity has its tiles at once."""
    from openexpress.gui.activity_map import COPYRIGHT_URL
    from openexpress.gui.gui_settings import load_gui_settings

    win, _the_list = a_window(walk())
    page = open_page(win, read_of(sport=WALKING))
    show_the_map_button(page).emit("clicked")
    shown = map_of(page)
    assert load_gui_settings().get("map_tiles") is True
    assert len(tile_layers(shown)) == 1 and NOTE not in labels(page)
    assert shown.attribution.get_visible()
    assert COPYRIGHT_URL in shown.attribution.get_label()
    assert "© OpenStreetMap contributors" in shown.attribution.get_label()
    win, _the_list = a_window(walk())
    page = open_page(win, read_of(sport=WALKING))
    assert len(tile_layers(map_of(page))) == 1 and show_the_map_button(page) is None


def test_the_yes_is_taken_back_in_preferences(no_tile_server):
    """The switch in Preferences: off, the map open now loses its tiles and the note is back."""
    from gi.repository import Adw

    from openexpress.gui.activity_map import set_tiles
    from openexpress.gui.gui_settings import load_gui_settings
    from openexpress.gui.preferences import maps_group

    set_tiles(True)
    win, _the_list = a_window(walk())
    page = open_page(win, read_of(sport=WALKING))
    group = maps_group(win)
    (row,) = [w for w in _all(group) if isinstance(w, Adw.SwitchRow)]
    assert row.get_title() == "Streets and terrain from OpenStreetMap" and row.get_active()
    assert row.get_subtitle() == ("The OpenStreetMap server learns the area of each activity "
                                  "you open")
    row.set_active(False)
    assert load_gui_settings().get("map_tiles") is False
    assert tile_layers(map_of(page)) == [] and NOTE in labels(page)


def test_an_activity_without_positions_has_no_map():
    win, _the_list = a_window(heart_only())
    page = open_page(win, read_of(sport=TRAINING, positions=False))
    assert map_of(page) is None
    assert not [t for t in labels(page) if "map" in t.lower()]


def test_without_libshumate_a_line_says_what_is_missing(monkeypatch):
    from openexpress.gui import activity_map

    monkeypatch.setattr(activity_map, "Shumate", None)
    win, _the_list = a_window(walk())
    page = open_page(win, read_of(sport=WALKING))
    assert map_of(page) is None
    assert "The map needs the libshumate library, which is not installed" in labels(page)


def test_a_libshumate_too_old_for_tiles_keeps_the_plain_track(monkeypatch, no_tile_server):
    """It cannot ask tiles as openExpress: no button, no tiles even with the yes, a line."""
    from openexpress.gui import activity_map

    monkeypatch.setattr(activity_map, "can_ask", lambda: False)
    activity_map.set_tiles(True)
    win, _the_list = a_window(walk())
    page = open_page(win, read_of(sport=WALKING))
    shown = map_of(page)
    assert shown is not None and tile_layers(shown) == [] and show_the_map_button(page) is None
    assert ("The map needs a newer libshumate library to show streets and terrain"
            in labels(page))


def test_no_map_makes_libshumate_s_own_cache(tmp_path):
    """Neither with the tiles nor without them, nor with an older libshumate: its own cache
    (~/.cache/shumate, made as soon as one of its downloaders is) is never made. In a process
    of its own: GLib keeps the cache folder it found first, maybe before the tests' own."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    code = (
        "import gi\n"
        "gi.require_version('Gtk', '4.0')\n"
        "from gi.repository import Gtk\n"
        "Gtk.init()\n"
        "from openexpress.gui import activity_map\n"
        "track = activity_map.Track((0, 1), ((51.5, -0.16), (51.501, -0.161)))\n"
        "for older in (False, True):\n"
        "    if older:\n"
        "        activity_map.can_ask = lambda: False\n"
        "    for tiles in (False, True):\n"
        "        activity_map.set_tiles(tiles)\n"
        "        activity_map.ActivityMap(track)\n")
    env = {**os.environ, "XDG_CACHE_HOME": str(tmp_path / "cache"),
           "XDG_CONFIG_HOME": str(tmp_path / "config")}
    subprocess.run([sys.executable, "-c", code], env=env, check=True, timeout=60,
                   cwd=Path(__file__).resolve().parent.parent)
    assert not (tmp_path / "cache" / "shumate").exists()


class Monitor:
    """A stand-in for Gio.NetworkMonitor: `available`, and its change told to the map."""

    def __init__(self, available):
        self.available, self.handlers = available, {}

    def get_network_available(self):
        return self.available

    def connect(self, name, handler):
        self.handlers[len(self.handlers) + 1] = handler
        return len(self.handlers)

    def disconnect(self, handler_id):
        del self.handlers[handler_id]

    def change(self, available):
        self.available = available
        for handler in list(self.handlers.values()):
            handler(self, available)


def present(win):
    from gi.repository import GLib

    win.toplevel.set_default_size(1000, 800)
    win.toplevel.present()
    for _ in range(200):
        GLib.MainContext.default().iteration(False)


def test_without_internet_the_map_says_only_tiles_downloaded_before_are_shown(
        monkeypatch, no_tile_server):
    from openexpress.gui import activity_map

    monitor = Monitor(False)
    monkeypatch.setattr(activity_map, "_network_monitor", lambda: monitor)
    activity_map.set_tiles(True)
    win, _the_list = a_window(walk())
    page = open_page(win, read_of(sport=WALKING))
    present(win)
    try:
        offline = ("No internet connection: only the parts of the map downloaded before are "
                   "shown")
        assert offline in labels(page)
        monitor.change(True)
        assert offline not in labels(page)
    finally:
        win.toplevel.destroy()
    assert monitor.handlers == {}  # let go once the map is gone from the screen


def test_the_chart_s_cursor_is_marked_on_the_map():
    """The marker at the record of the cursor; hidden until the cursor is placed."""
    win, _the_list = a_window(walk())
    page = open_page(win, read_of(sport=WALKING))
    shown = map_of(page)
    assert not shown.marker.get_visible()
    chart_of(page).area.place(60)
    assert shown.marker.get_visible()
    point = shown.track.points[shown.track.times.index(60)]
    assert (shown.marker.get_latitude(), shown.marker.get_longitude()) == pytest.approx(point)


def test_the_map_has_a_name_for_a_screen_reader_and_is_released_once_closed(no_tile_server):
    import gc

    from gi.repository import GLib

    from openexpress.gui import activity_map

    activity_map.set_tiles(True)
    win, _the_list = a_window(walk())
    page = open_page(win, read_of(sport=WALKING))
    shown = map_of(page)
    assert shown.accessible_name == "Map of the track"
    gone = []
    shown.weak_ref(lambda: gone.append("map"))
    del shown, page
    win.navigation.pop()
    win.run_task.calls.clear()
    win._action_buttons.clear()
    for _ in range(3):
        gc.collect()
        while GLib.main_context_default().iteration(False):
            pass
    assert gone == ["map"]
