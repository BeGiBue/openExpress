"""The Activities page of the window: the activities of the open device and of its backups,
the newest 30 first and 30 more at a time on request (activities.py lists and reads them; the
words of a row are in gui/words.py). Nothing is written; exporting an activity is the task of
its row's button.
Has: the activities of the open device (activities) and the groups of the page that grow as
more are read (activities_list, activities_more).
ActivitiesPage is a mixin of MainWindow (gui/app.py), without __init__ of its own; what it uses
of the window (session, run_task, progress, sections, …) is the window's."""
from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402 - imports must follow gi.require_version

from openexpress import paths  # noqa: E402
from openexpress.gui.words import (  # noqa: E402
    activities_count_text,
    activity_caption,
    activity_title,
)
from openexpress.i18n import _, ngettext  # noqa: E402

log = logging.getLogger(__name__)

PAGE_ICON = "x-office-calendar-symbolic"


def _read(found, count: int, progress):
    """In the task's thread: the activity files listed again and the newest `count` read (what
    was read before is kept and not read again)."""
    found.list_files()
    found.read_next(count, progress)
    return found


def _export_button(read) -> Gtk.Button | None:
    """The button that exports an activity as GPX, insensitive with why in its tooltip when it
    has no positions; none for a file the device was still writing or that is no FIT file."""
    from openexpress import fit

    found = read.summary
    if found is None or found.state is fit.FileState.STILL_BEING_WRITTEN:
        return None
    words = _("Export as GPX…")
    button = Gtk.Button(icon_name="document-save-as-symbolic", valign=Gtk.Align.CENTER,
                        sensitive=found.has_positions)
    button.add_css_class("flat")
    button.set_tooltip_text(words if found.has_positions
                            else _("No GPS positions in this activity"))
    button.update_property([Gtk.AccessibleProperty.LABEL], [words])
    return button


def activity_row(read) -> Adw.ActionRow:
    """The row of an activity (activities.Read): its sport as the title, the details in one
    caption that wraps, the export button."""
    row = Adw.ActionRow(title=GLib.markup_escape_text(activity_title(read)),
                        subtitle=GLib.markup_escape_text(activity_caption(read)))
    button = _export_button(read)
    if button is not None:
        row.add_suffix(button)
    return row


def _no_activities(sec) -> None:
    """The page without any activity: the page's icon and why, in its content."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER,
                  margin_top=24, margin_bottom=24)
    box.append(Gtk.Image(icon_name=PAGE_ICON, pixel_size=64))
    words = Gtk.Label(label=_("There are no activities on the device or in its backups."),
                      wrap=True, justify=Gtk.Justification.CENTER)
    words.add_css_class("title-2")
    box.append(words)
    sec.group().add(box)


class ActivitiesPage:
    """The Activities page and its tasks."""

    def load_activities(self) -> None:
        from openexpress import activities

        s = self.session
        sec = self.sections["activities"]
        if not activities.keeps_activities(s.device):
            # As a page that does not apply to the device: information, nothing read.
            sec.clear()
            sec.info.set_icon_name(PAGE_ICON)
            sec.info.set_title(sec.title)
            sec.info.set_description(GLib.markup_escape_text(
                _("This device does not keep activities.")))
            sec.show("info")
            return
        found = self.activities
        if found is None or found.storage is not s.storage:
            found = activities.DeviceActivities(s.device, s.storage, paths.default_backup_dir())
        # Read again (Refresh): as many as were shown, what was read before kept.
        count = max(activities.PAGE, len(found.read))
        self._load("activities", _("Reading activities…"),
                   lambda: _read(found, count, self.progress), self.show_activities)

    def show_activities(self, found) -> None:
        """The rows of the activities read (`found`: activities.DeviceActivities), the button
        for more when some are left."""
        if self.session is None:
            return
        self.activities = found
        sec = self.sections["activities"]
        self.activities_list = self.activities_more = None
        if not found.listing:
            _no_activities(sec)
            return
        self.activities_list = sec.group(description=GLib.markup_escape_text(
            activities_count_text(len(found.listing), found.only_in_backups)))
        for read in found.read:
            self.activities_list.add(activity_row(read))
        _show_more_button(self, found)
        log.info("activities page: %d shown, %d more to read", len(found.read), found.left)


def _show_more_button(win, found) -> None:
    """The button below the rows that reads the next activities, when some are left (the one
    before it goes)."""
    from openexpress import activities

    sec = win.sections["activities"]
    if win.activities_more is not None:
        sec.page.remove(win.activities_more)
        sec.groups.remove(win.activities_more)
        win.activities_more = None
    if not found.left:
        return
    count = min(activities.PAGE, found.left)
    # TRANSLATORS: button below the rows of the Activities page: read the next ones
    button = win._button(ngettext("Show {count} More", "Show {count} More", count).format(
        count=count), lambda clicked: _read_more(win, clicked), style="pill", with_button=True)
    button.set_halign(Gtk.Align.CENTER)
    win.activities_more = sec.group()
    win.activities_more.add(button)


def _read_more(win, button: Gtk.Button) -> None:
    """Reads the next activities, a task on `button`, and adds their rows."""
    found = win.activities
    if found is None:
        return

    def shown(read) -> None:
        if win.activities is not found or win.activities_list is None:
            return  # another device opened meanwhile
        for r in read:
            win.activities_list.add(activity_row(r))
        _show_more_button(win, found)
        log.info("activities page: %d shown, %d more to read", len(found.read), found.left)

    win.run_task(_("Reading activities…"), lambda: found.read_next(progress=win.progress),
                 shown, button=button)
