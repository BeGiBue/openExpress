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
