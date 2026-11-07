"""The Courses page of the window (gui/courses_page.py): the courses with the chip of where each
came from, the files waiting under the page's banner, the saved locations, the page without a
course, a device that makes no courses of GPX files, the title with its chip, and Add Course…:
the question (the course's name, what the file holds, its name on the device following the
name, what the device does), the copy and its toast. Made-up files on a folder taken as the
device; nothing reaches a device."""

import time
import types

import pytest
from fakes import (
    COURSE_UNIT,
    course_device,
    course_fit,
    descendants,
    gpx_file,
    gpx_route,
    gpx_track,
    gpx_waypoint,
    locations_fit,
    page_window,
)

from openexpress import courses
from openexpress.device.storage import LocalStorage

pytestmark = pytest.mark.needs_display


@pytest.fixture
def drive(tmp_path):
    root = tmp_path / "device"
    for folder in ("Garmin/NewFiles", "Garmin/Courses", "Garmin/Locations"):
        (root / folder).mkdir(parents=True)
    return root


def courses_window(drive, offered=True):
    from openexpress.gui.app import MainWindow

    win, section = page_window("courses")
    win.session = types.SimpleNamespace(
        device=course_device(gpx_folder="Garmin/NewFiles" if offered else None),
        storage=LocalStorage(drive), unit_info_answer=None)
    for name in ("load_courses", "show_courses", "choose_course", "add_course",
                 "_course_refused"):
        setattr(win, name, types.MethodType(getattr(MainWindow, name), win))
    win.get_width = lambda: 1000  # the window's
    win.loads = []
    win.load_section = lambda key, force=False: (win.loads.append(key), win.load_courses())
    win.progress = lambda text: None
    win.toasts, win.errors = [], []
    win.toast = win.toasts.append
    win.error = lambda title, text: win.errors.append((title, text))
    return win, section


def labels(widget) -> list[str]:
    from gi.repository import Gtk

    return [w.get_label() for w in descendants(widget)
            if isinstance(w, Gtk.Label) and w.get_visible() and w.get_label()]


def rows(group) -> list[list[str]]:
    from gi.repository import Gtk

    return [labels(r) for r in descendants(group) if isinstance(r, Gtk.ListBoxRow)
            and r.get_child() is not None and labels(r)]


def now() -> int:
    return int(time.time())


def test_the_courses_the_files_waiting_and_the_locations(drive, clock):
    (drive / "Garmin/Courses/Along.fit").write_bytes(course_fit(
        "Along the River", made=now(), product=courses.CONNECT_PRODUCT, ascent=None))
    (drive / "Garmin/Courses/Hand.fit").write_bytes(course_fit("By Hand", made=now()))
    (drive / "Garmin/NewFiles/Loop.gpx").write_text(gpx_file(gpx_track()))
    (drive / "Garmin/Locations/Locations.fit").write_bytes(locations_fit(14))
    win, section = courses_window(drive)
    win.load_courses()
    assert section.stack.get_visible_child_name() == "content"
    assert [g.get_title() for g in section.groups] == [
        "On the Device", "Waiting for the Device", "Saved Locations"]
    assert rows(section.groups[0]) == [
        ["Along the River", "Garmin Connect", "12.3 km\u00a0· 2026-10-21"],
        ["By Hand", "12.3 km\u00a0· ↗ 321 m\u00a0· 2026-10-21"]]
    assert rows(section.groups[1]) == [["Morning Loop", "track, 1.4 km\u00a0· Loop.gpx"]]
    assert "14" in labels(section.groups[2])
    assert section.banner.get_revealed()
    assert section.banner.get_title() == (
        "1 file waiting\u00a0– unplug the device so it can import it")


def test_the_day_the_device_made_a_course_and_the_chip_of_openexpress(drive, tmp_path, clock):
    st = LocalStorage(drive)
    plan = courses.plan_add(course_device(), st, _gpx(tmp_path, gpx_track("Hill")))
    courses.add(plan, course_device(), st)
    (drive / plan.path).unlink()  # the device took it
    (drive / "Garmin/Courses/Hill.fit").write_bytes(course_fit("Hill", made=now() + 60))
    win, section = courses_window(drive)
    win.load_courses()
    (row,) = rows(section.groups[0])
    assert row[:2] == ["Hill", "openExpress"]
    assert row[2].endswith("2026-10-21")  # the clock's day
    assert not section.banner.get_revealed()  # nothing waiting


def test_without_a_course_or_a_file_waiting_the_page_says_so(drive):
    win, section = courses_window(drive)
    win.load_courses()
    assert labels(section.page) == [
        "No Courses on the Device",
        "Copy a GPX file with a track or a route\u00a0– the device turns it into a course.",
        "Add Course…"]
    assert not section.banner.get_revealed()


def test_a_device_that_makes_no_courses_of_gpx_files(drive):
    win, section = courses_window(drive, offered=False)
    win.load_courses()
    assert section.stack.get_visible_child_name() == "info"
    assert section.info.get_description() == "This device does not make courses of GPX files."


def test_the_title_in_the_header_carries_the_chip():
    from openexpress.gui.device_page import Section, section_title

    assert labels(section_title(Section("courses", "Courses", "x", "…", chip="experimental"))) == [
        "Courses", "experimental"]
    assert section_title(Section("maps", "Maps", "x", "…")) is None


def _gpx(tmp_path, body, name="loop.gpx"):
    path = tmp_path / name
    path.write_text(gpx_file(body), encoding="utf-8")
    return path


@pytest.fixture
def asked(in_the_window):
    """The questions the page asks: (heading, body, answers, the widget below the text)."""
    questions = []

    def confirm(_parent, name, heading, body, *answers, extra=None, **_kw):
        questions.append(types.SimpleNamespace(name=name, heading=heading, body=body,
                                               answers=answers, extra=extra))

    in_the_window("confirm", confirm)
    return questions


def test_adding_a_course_asks_with_its_name_and_copies_it_under_the_name_left(drive, tmp_path,
                                                                             asked, clock):
    from gi.repository import Adw

    win, section = courses_window(drive)
    win.load_courses()
    win.add_course(_gpx(tmp_path, gpx_track()))
    (q,) = asked
    assert (q.name, q.heading, q.body) == ("course-add", "Copy the Course to the Device?",
                                           "Made-up Edge")
    words = labels(q.extra)
    at = words.index("Contents")
    assert words[at:at + 5] == ["Contents", "track, 1.4 km, ↗ 10 m, 3 track points",
                                "File on the Device", "Morning_\u200bLoop.GPX\u00a0· 340\u00a0B",
                                "Free After Copying"]
    assert words[-1] == "The device makes the course when you unplug the cable."
    (entry,) = [w for w in descendants(q.extra) if isinstance(w, Adw.EntryRow)]
    assert entry.get_text() == "Morning Loop"
    entry.set_text("Pętla nad jeziorem")
    assert "Petla_\u200bnad_\u200bjeziorem.GPX\u00a0· 347\u00a0B" in labels(q.extra)  # it follows the name
    (copy,) = q.answers
    assert copy.label == "Copy"
    copy.run()
    assert win.run_task.written == ["Copying the Course…"]
    written = drive / "Garmin/NewFiles/Petla_nad_jeziorem.GPX"
    assert b"<name>P\xc4\x99tla nad jeziorem</name>" in written.read_bytes()
    assert win.toasts == [
        "Copied “Pętla nad jeziorem”. Unplug the device so it can import the file."]
    assert win.loads == ["courses"]  # the page read again: the file waits now
    assert rows(section.groups[1])[0][0] == "Pętla nad jeziorem"
    assert [c["courses"] for c in courses.recorded(COURSE_UNIT)] == [["Pętla nad jeziorem"]]


def test_a_name_left_as_it_was_copies_the_file_as_it_is(drive, tmp_path, asked):
    win, _section = courses_window(drive)
    local = _gpx(tmp_path, gpx_track())
    win.add_course(local)
    asked[0].answers[0].run()
    assert (drive / "Garmin/NewFiles/Morning_Loop.GPX").read_bytes() == local.read_bytes()


def test_a_route_is_warned_of(drive, tmp_path, asked):
    from gi.repository import Gtk

    win, _section = courses_window(drive)
    win.add_course(_gpx(tmp_path, gpx_route()))
    (q,) = asked
    (warning,) = [w for w in descendants(q.extra) if isinstance(w, Gtk.Label)
                  and w.has_css_class("warning")]
    assert warning.get_label().startswith("Garmin devices join the points of a route with "
                                          "straight lines, not roads.")
    assert warning.has_css_class("oe-note")
    assert "route, 3 route points" in labels(q.extra)


def test_waypoints_only_take_no_name(drive, tmp_path, asked):
    from gi.repository import Adw

    win, _section = courses_window(drive)
    win.add_course(_gpx(tmp_path, gpx_waypoint() + gpx_waypoint("Shelter", 52.1, 13.1),
                        "points.gpx"))
    (q,) = asked
    assert q.heading == "Copy the Waypoints to the Device?"
    assert not [w for w in descendants(q.extra) if isinstance(w, Adw.EntryRow)]
    assert labels(q.extra)[-1] == "Garmin devices save waypoints as saved locations."
    assert "2 waypoints" in labels(q.extra)


def test_several_tracks_ask_for_the_courses(drive, tmp_path, asked):
    win, _section = courses_window(drive)
    win.add_course(_gpx(tmp_path, gpx_track("First") + gpx_track("Second")))
    assert asked[0].heading == "Copy the Courses to the Device?"
    assert "The device makes 2 courses when you unplug the cable." in labels(asked[0].extra)


def test_a_file_that_is_not_copied_is_said_and_nothing_is_asked(drive, tmp_path, asked):
    win, _section = courses_window(drive)
    bad = tmp_path / "bad.gpx"
    bad.write_text("<not a gpx file")
    win.add_course(bad)
    assert asked == [] and win.errors == [("Cannot Add the Course", "bad.gpx is not a GPX file.")]
    assert list((drive / "Garmin/NewFiles").iterdir()) == []


def test_the_chip_is_drawn_only_beside_the_whole_title():
    from gi.repository import Gtk

    from openexpress.gui.device_page import Section, section_title

    title = section_title(Section("courses", "Courses", "x", "…", chip="experimental"))
    holder = Gtk.Window(child=title)  # never shown
    title.measure(Gtk.Orientation.HORIZONTAL, -1)
    title.allocate(400, 40, -1, None)
    chip = title.get_last_child()
    assert chip.get_child_visible()
    assert chip.compute_point(title, _point(0, 0))[1].x > title.get_first_child().get_width()
    title.allocate(60, 40, -1, None)  # the narrowest window's header
    assert not chip.get_child_visible()
    holder.destroy()


def _point(x, y):
    from gi.repository import Graphene

    return Graphene.Point().init(x, y)


def test_saved_locations_that_could_not_be_counted(drive):
    (drive / "Garmin/Locations/Locations.fit").write_bytes(locations_fit(3, cut=60))
    (drive / "Garmin/NewFiles/Loop.gpx").write_text(gpx_file(gpx_track()))
    win, section = courses_window(drive)
    win.load_courses()
    words = labels(section.groups[-1])
    assert "Waypoints from GPX files and locations saved on the device" in words
    assert "Could not be counted" in words and "14" not in words
