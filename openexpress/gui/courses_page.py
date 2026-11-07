"""The Courses page of the window (experimental): the courses on the open device, each with where
it came from, the GPX files waiting for it under a banner of the page, how many saved locations it
keeps, and Add Course…: a GPX file chosen (through the portal in the Flatpak, so from any
folder), checked and planned, a question with the course's name to change, the copy. courses.py
decides all of it; this page shows it and asks. Removing a course is a later step: a row has no
button for it yet.
Has: nothing of its own in the window (the page reads the device each time it is shown).
CoursesPage is a mixin of MainWindow (gui/app.py), without __init__ of its own; what it uses of
the window (session, run_task, sections, toast, error, …) is the window's."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, GObject, Gtk, Pango  # noqa: E402 - imports must follow gi.require_version

from openexpress import courses  # noqa: E402
from openexpress.course_gpx import CourseFileError  # noqa: E402
from openexpress.gui.device_page import device_name  # noqa: E402
from openexpress.gui.tasks import read_again_after_failure, writes_to_device  # noqa: E402
from openexpress.gui.window_tasks import WRAP_BOX, Answer, confirm  # noqa: E402
from openexpress.gui.words import metres_text, space_text  # noqa: E402
from openexpress.i18n import _, caption, decimal, human_size, ngettext, npgettext, pgettext  # noqa: E402
from openexpress.paths import APP_ID  # noqa: E402

log = logging.getLogger(__name__)

# Until the page has an icon of its own: the distance's (a line between two points).
PAGE_ICON = f"{APP_ID}-activity-distance-symbolic"
# The width of the question's content: a file's name on one line beside its title (libadwaita
# gives a question 312 px at most); never more than the window leaves a dialog's content, 108 px
# less than its own width (measured with libadwaita 1.9).
QUESTION_WIDTH = 480
DIALOG_MARGINS = 108


# --- the words of the page -----------------------------------------------------------------------


def _km(metres: float) -> str:
    return _("{distance} km").format(distance=decimal(f"{metres / 1000:.1f}"))


def course_caption(course: courses.Course) -> str:
    """Under a course's name: its distance, ascent and the day the device made it (each left
    out when its file does not say)."""
    parts = []
    if course.distance_m:
        parts.append(_km(course.distance_m))
    if course.ascent_m is not None:
        parts.append(f"↗ {metres_text(course.ascent_m)}")
    if course.made is not None:
        parts.append(datetime.fromtimestamp(course.made).strftime(_("%Y-%m-%d")))
    return caption(*parts)


def _points(line) -> str:
    if line.kind == "track":
        # TRANSLATORS: the points of a track of a GPX file, on the Courses page (not its
        # waypoints)
        return npgettext("course file", "{count} track point", "{count} track points",
                         line.points).format(count=line.points)
    # TRANSLATORS: the points of a route of a GPX file, on the Courses page (not its waypoints)
    return npgettext("course file", "{count} route point", "{count} route points",
                     line.points).format(count=line.points)


def contents_text(gpx, short: bool = False) -> str:
    """What a GPX file holds, each kind of it ("track, 12.3 km, ↗ 321 m, 120 track points");
    `short`: a track by its distance alone (the row of a waiting file)."""
    tracks = [line for line in gpx.lines if line.kind == "track"]
    routes = [line for line in gpx.lines if line.kind == "route"]
    parts = []
    if len(tracks) == 1:
        (track,) = tracks
        # TRANSLATORS: what a GPX file holds, on the Courses page: one track
        words = [pgettext("course file", "track"), _km(track.distance_m)]
        if not short:
            if track.ascent_m is not None:
                words.append(f"↗ {metres_text(track.ascent_m)}")
            words.append(_points(track))
        parts.append(", ".join(words))
    elif tracks:
        parts.append(npgettext("course file", "{count} track, {distance}",
                               "{count} tracks, {distance}", len(tracks)).format(
            count=len(tracks), distance=_km(sum(track.distance_m for track in tracks))))
    if len(routes) == 1:
        # TRANSLATORS: what a GPX file holds, on the Courses page: one route
        parts.append(", ".join([pgettext("course file", "route"), _points(routes[0])]))
    elif routes:
        parts.append(npgettext("course file", "{count} route", "{count} routes",
                               len(routes)).format(count=len(routes)))
    if gpx.waypoints:
        # TRANSLATORS: what a GPX file holds, on the Courses page: its waypoints, which the
        # device saves as saved locations
        parts.append(npgettext("course file", "{count} waypoint", "{count} waypoints",
                               gpx.waypoints).format(count=gpx.waypoints))
    return "; ".join(parts)


def waiting_banner(count: int) -> str:
    # TRANSLATORS: banner of the Courses page: GPX files copied to the device that it has not
    # imported yet (it does when it is unplugged)
    # (A hard space before the dash: a line never starts with it.)
    return ngettext("{count} file waiting\u00a0– unplug the device so it can import it",
                    "{count} files waiting\u00a0– unplug the device so it can import them",
                    count).format(count=count)


def copied_toast(name: str) -> str:
    # TRANSLATORS: toast after a GPX file was copied to the device; {name}: its course's name,
    # else the file's
    return _("Copied “{name}”. Unplug the device so it can import the file.").format(name=name)


def question_heading(plan) -> str:
    if not plan.gpx.courses:
        # TRANSLATORS: heading of the question before a GPX file of waypoints only is copied
        return _("Copy the Waypoints to the Device?")
    # TRANSLATORS: heading of the question before a GPX file is copied to the device
    return ngettext("Copy the Course to the Device?", "Copy the Courses to the Device?",
                    plan.gpx.courses)


def file_text(name: str, size: int) -> str:
    """A file's name and size on the device; the name may break after each "_" (a zero-width
    space), so that in a narrow window the name breaks, not the line before its size."""
    return caption(name.replace("_", "_\u200b"), human_size(size))


# --- the widgets of the page ---------------------------------------------------------------------


def _chip(words: str, accent: bool) -> Gtk.Label:
    return Gtk.Label(label=words, valign=Gtk.Align.CENTER,
                     css_classes=["oe-chip", "accent" if accent else "dimmed"])


def _row(title: str, subtitle: str, origin: str | None = None) -> Gtk.ListBoxRow:
    """A row of a course or of a waiting file: its name with the chip of where it came from
    beside it (on the next line when the window is too narrow), the caption under them."""
    name = Gtk.Label(label=title, xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
    if origin is None:
        head = name
    else:
        chip = _chip(origin, accent=origin == courses.ORIGIN_OPENEXPRESS)
        if WRAP_BOX is not None:
            head = WRAP_BOX(child_spacing=8, line_spacing=4, halign=Gtk.Align.START)
        else:  # libadwaita before 1.7
            head = Gtk.Box(spacing=8)
        head.append(name)
        head.append(chip)
    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True,
                   margin_start=12, margin_end=12, margin_top=8, margin_bottom=8)
    text.append(head)
    if subtitle:
        text.append(Gtk.Label(label=subtitle, xalign=0, wrap=True,
                              wrap_mode=Pango.WrapMode.WORD_CHAR,
                              css_classes=["dim-label", "caption"]))
    row = Gtk.ListBoxRow(activatable=False, child=text)
    row.update_property([Gtk.AccessibleProperty.LABEL],
                        [", ".join(p for p in (title, origin, subtitle) if p)])
    return row


def _empty(win, sec) -> None:
    """No course and no file waiting: the page's icon, that there is none, and Add Course…"""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER,
                  margin_top=48, margin_bottom=24)
    box.append(Gtk.Image(icon_name=PAGE_ICON, pixel_size=64, css_classes=["dim-label"]))
    box.append(Gtk.Label(label=_("No Courses on the Device"), wrap=True,
                         justify=Gtk.Justification.CENTER, css_classes=["title-2"]))
    box.append(Gtk.Label(
        label=_("Copy a GPX file with a track or a route\u00a0– the device turns it into a "
                "course."),
        wrap=True, justify=Gtk.Justification.CENTER, max_width_chars=48))
    add = win._button(_("Add Course…"), win.choose_course)
    add.set_halign(Gtk.Align.CENTER)
    add.add_css_class("suggested-action")
    add.add_css_class("pill")
    add.set_margin_top(12)
    add.set_tooltip_text(add_tooltip())
    box.append(add)
    sec.group().add(box)


def add_tooltip() -> str:
    # TRANSLATORS: tooltip of Add Course… on the Courses page
    return _("Copy a GPX file to the device (experimental)")


def _fact(name: str, value: Gtk.Label) -> Gtk.Box:
    """A line of the question: its name on one line, never broken (each line takes the room
    its own name needs), the value right of it, wrapped when it is long."""
    line = Gtk.Box(spacing=16)
    line.append(Gtk.Label(label=name, xalign=0, valign=Gtk.Align.START,
                          css_classes=["dim-label"]))
    line.append(value)
    return line


def _value(text: str) -> Gtk.Label:
    return Gtk.Label(label=text, xalign=1, hexpand=True, wrap=True,
                     wrap_mode=Pango.WrapMode.WORD_CHAR, css_classes=["heading"])


def _note(text: str, warning: bool = False) -> Gtk.Label:
    note = Gtk.Label(label=text, xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                     css_classes=["oe-note"])
    if warning:
        note.add_css_class("warning")
    return note


def question_width(window_width: int) -> int:
    return max(0, min(QUESTION_WIDTH, window_width - DIALOG_MARGINS))


def question_body(plan, entered: dict, width: int = 0) -> Gtk.Widget:
    """What the question before a copy shows under its heading: the course's name to change
    (a file of one course), what the file holds, its name and size on the device (following
    the name), the space left, and what the device does with it. A name typed goes into
    `entered` (the answer takes it from there, never from the widget). `width`: its own (none:
    the dialog's)."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    if width:
        box.set_size_request(width, -1)
    file_value = _value(file_text(plan.name, plan.size))
    if plan.course is not None:
        names = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        # TRANSLATORS: the entry of the question before a GPX file is copied: the name the
        # device gives the course
        entry = Adw.EntryRow(title=pgettext("course", "Course Name"), text=plan.course)
        entry.connect("changed", lambda e: entered.__setitem__("name", e.get_text()))
        # The file's name on the device follows the course's (a binding: no handler holds
        # a widget).
        entry.bind_property("text", file_value, "label", GObject.BindingFlags.DEFAULT,
                            lambda _binding, text: file_text(*plan.file_for(text)))
        names.append(entry)
        box.append(names)
    facts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    # TRANSLATORS: a line of the question before a GPX file is copied: what the file holds
    facts.append(_fact(pgettext("course", "Contents"), _value(contents_text(plan.gpx))))
    # TRANSLATORS: a line of the question before a GPX file is copied: its name and size there
    facts.append(_fact(pgettext("course", "File on the Device"), file_value))
    free = None if plan.free is None else max(0, plan.free - plan.size)
    # TRANSLATORS: a line of the question before a GPX file is copied: the space left after it
    facts.append(_fact(pgettext("course", "Free After Copying"),
                       _value(human_size(free) if free is not None else space_text(None))))
    box.append(facts)
    if plan.same_waiting is not None:
        box.append(_note(_("The same file is already waiting on the device as {name}.").format(
            name=plan.same_waiting)))
    for said, warning in courses.what_the_device_does(plan.gpx):
        box.append(_note(said, warning))
    return box


def _copy(s, path: Path, name: str | None, progress):
    """The copy under the name the question was left with: planned again with the device (its
    folder and space as they are now), then written. The plan written."""
    plan = courses.plan_add(s.device, s.storage, path, name)
    courses.add(plan, s.device, s.storage, progress=progress)
    return plan


class CoursesPage:
    """The Courses page and its tasks."""

    def load_courses(self) -> None:
        s = self.session
        sec = self.sections["courses"]
        if not courses.offered(s.device):
            # As a page that does not apply to the device: information, nothing read.
            sec.clear()
            sec.info.set_icon_name(PAGE_ICON)
            sec.info.set_title(sec.title)
            sec.info.set_description(GLib.markup_escape_text(courses.not_offered_text()))
            sec.show("info")
            return
        self._load("courses", _("Reading Courses…"),
                   lambda: courses.overview(s.device, s.storage), self.show_courses)

    def show_courses(self, seen: courses.Overview) -> None:
        """The courses read, the files waiting (and the banner), the saved locations; without a
        course or a file waiting, that there is none and Add Course…"""
        if self.session is None:
            return
        sec = self.sections["courses"]
        if seen.waiting:
            sec.banner.set_title(waiting_banner(len(seen.waiting)))
            sec.banner.set_revealed(True)
        if not seen.courses and not seen.waiting and not seen.unreadable:
            _empty(self, sec)
            log.info("courses page: none on the device")
            return
        # TRANSLATORS: group of the Courses page: the courses the device keeps
        g = sec.group(pgettext("courses", "On the Device"))
        add = self._button(_("Add Course…"), self.choose_course)
        add.set_tooltip_text(add_tooltip())
        g.set_header_suffix(add)
        if "courses" in seen.unreadable:
            g.add(Adw.ActionRow(title=_("The courses could not be read from the device")))
        elif not seen.courses:
            g.add(Adw.ActionRow(title=_("No Courses on the Device")))
        for course in seen.courses:
            g.add(_row(course.title, course_caption(course), course.origin))
        if seen.waiting or "waiting" in seen.unreadable:
            # TRANSLATORS: group of the Courses page: GPX files the device has not imported yet
            g = sec.group(pgettext("courses", "Waiting for the Device"))
            if "waiting" in seen.unreadable:
                g.add(Adw.ActionRow(title=_("The files waiting could not be read")))
            for waiting in seen.waiting:
                parts = [contents_text(waiting.gpx, short=True)] if waiting.gpx else []
                if waiting.title != waiting.filename:
                    parts.append(waiting.filename)
                if waiting.gpx is None:
                    parts.append(human_size(waiting.size))
                g.add(_row(waiting.title, caption(*parts)))
        if seen.locations is not None or "locations" in seen.unreadable:
            # TRANSLATORS: group of the Courses page: the device's saved locations
            g = sec.group(pgettext("courses", "Saved Locations"))
            # TRANSLATORS: the row of the saved locations kept on the device
            row = Adw.ActionRow(title=pgettext("saved locations", "On the Device"),
                                subtitle=_("Waypoints from GPX files and locations saved on "
                                           "the device"))
            row.add_suffix(Gtk.Label(
                label=(str(seen.locations) if seen.locations is not None
                       # TRANSLATORS: in place of how many saved locations the device keeps,
                       # when its locations file does not read whole
                       else pgettext("saved locations", "Could not be counted")),
                wrap=True, justify=Gtk.Justification.RIGHT, css_classes=["dim-label"]))
            g.add(row)
        log.info("courses page: %d courses, %d files waiting", len(seen.courses),
                 len(seen.waiting))

    def choose_course(self) -> None:
        """Add Course…: a GPX file chosen through the file chooser (the portal in the Flatpak:
        any folder), then checked and asked about (add_course)."""
        dialog = Gtk.FileDialog(title=_("Choose a GPX File"))
        only_gpx = Gtk.FileFilter(name=_("GPX files (*.gpx)"))
        only_gpx.add_pattern("*.gpx")
        only_gpx.add_pattern("*.GPX")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(only_gpx)
        dialog.set_filters(filters)

        def chosen(dlg, res):
            try:
                path = dlg.open_finish(res).get_path()
            except GLib.Error:
                return  # cancelled
            if path is None:
                self.toast(_("Choose files stored on this computer"))
                return
            self.add_course(Path(path))

        dialog.open(self, None, chosen)

    def _course_refused(self, e) -> bool:
        """A refusal of courses.py or course_gpx.py over the page; True when it was one."""
        if isinstance(e, CourseFileError | courses.CourseError):
            # TRANSLATORS: title of the message why a GPX file was not copied
            self.error(_("Cannot Add the Course"), str(e))
            return True
        return False

    def add_course(self, path: Path) -> None:
        """The file checked and planned with the device, then the question; Copy copies it
        under the name the question was left with."""
        s = self.session

        def copied(plan):
            self.toast(copied_toast(plan.course or plan.gpx.path.name))
            self.load_section("courses", force=True)

        def copy(plan, entered):
            name = entered["name"]
            if name is not None and name.strip() == (plan.course or ""):
                name = None  # unchanged: the file as it is
            self.run_task(
                _("Copying the Course…"),
                writes_to_device(lambda: _copy(s, path, name, self.progress)),
                copied, read_again_after_failure(self, "courses", self._course_refused))

        def ask(plan):
            entered = {"name": None}
            confirm(self, "course-add", question_heading(plan), device_name(s),
                    Answer("copy", _("Copy"), lambda: copy(plan, entered), look="suggested"),
                    default="copy", wide=True,
                    extra=question_body(plan, entered, question_width(self.get_width())))

        self.run_task(_("Checking the File…"),
                      lambda: courses.plan_add(s.device, s.storage, path), ask,
                      self._course_refused)
