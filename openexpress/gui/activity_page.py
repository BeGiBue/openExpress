"""The page of one activity, opened from its row on the Activities page: its sport and start in
its header bar with the back arrow and the GPX export, the tiles of what its sessions say (the
words in gui/words.py), and what a file that could not be read, one still being written and
one without a summary say. Its file is read again each time it opens, in a task
(fit.activity_data), from the device or from a copy in a backup; nothing is kept and nothing is
written. The page is pushed onto the window's navigation above the device view and goes with
the pages of that view (the device gone, or drawn anew).
Has: no attribute of the window; the page keeps what it needs in its closures."""
from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402 - imports must follow gi.require_version

from openexpress.activities import Source  # noqa: E402
from openexpress.errors import UserFacingError  # noqa: E402
from openexpress.gui.activities_page import PAGE_ICON, export_button  # noqa: E402
from openexpress.gui.words import activity_start, activity_tiles, activity_title  # noqa: E402
from openexpress.i18n import _  # noqa: E402

log = logging.getLogger(__name__)

TAG = "activity"
CONTENT_WIDTH = 1000  # its content in one column, at most this wide
TILES_IN_A_LINE = 5  # all of them on a wide window; two by two on a narrow one


class ReadFailed(UserFacingError):
    """The file of an activity that could not be read again: a copy in a backup that could
    not be read, or no FIT file."""


def _data(found, activity):
    """In the task's thread: the activity's file read again (activities.DeviceActivities) and
    what it holds."""
    from openexpress import fit

    data = found.read_file(activity)
    if data is None:
        raise ReadFailed(_("The file of this activity could not be read."))
    try:
        return fit.activity_data(data)
    except fit.FitError as e:
        log.info("activity page: no FIT file (%s)", type(e).__name__)
        raise ReadFailed(_("The file of this activity could not be read.")) from e


def leave(win) -> None:
    """Back to the device view when an activity's page is shown: the pages of the device are
    drawn anew, or Refresh or Sync is asked from the keyboard (the bar of their task is in the
    device view)."""
    navigation = win.navigation
    page = navigation.get_visible_page() if navigation is not None else None
    if isinstance(page, Adw.NavigationPage) and page.get_tag() == TAG:
        log.info("activity page: closed with the device view")
        navigation.pop_to_page(win.device_view)


def open_activity(win, read) -> None:
    """The page of an activity (activities.Read) pushed onto the window's navigation, its file
    read in a task; while another task runs, a toast only."""
    if win.busy:
        win.toast(_("Another operation is in progress"))
        return
    found = win.activities
    view = ActivityView(win, read)
    win.navigation.push(view.page)

    def done(data) -> None:
        if win.navigation.get_visible_page() is not view.page:
            log.info("activity page: gone before its file was read")
            return
        view.show(data)

    def failed(_error) -> bool:
        # Said on the page, no error dialog (a stall: the banner, and the page goes with the
        # device); the log has why.
        view.say(_("The file of this activity could not be read."))
        return True

    win.run_task(_("Reading the activity…"), lambda: _data(found, read.activity), done, failed,
                 device=read.activity.source is Source.DEVICE, in_page=True)


def _tile(value: str, name: str) -> Gtk.Widget:
    """A tile: the value large, its name under it."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_top=12,
                  margin_bottom=12, margin_start=12, margin_end=12)
    shown = Gtk.Label(label=value, wrap=True, justify=Gtk.Justification.CENTER)
    shown.add_css_class("title-3")
    named = Gtk.Label(label=name, wrap=True, justify=Gtk.Justification.CENTER)
    named.add_css_class("caption")
    named.add_css_class("dim-label")
    box.append(shown)
    box.append(named)
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    card.add_css_class("card")
    card.append(box)
    return card


class ActivityView:
    """The widgets of one activity's page: its header bar, and in turn the spinner while its
    file is read, its content, or a message."""

    def __init__(self, win, read):
        title = activity_title(read)
        header = Adw.HeaderBar(title_widget=Adw.WindowTitle(title=title,
                                                            subtitle=activity_start(read)))
        button = export_button(win, read)
        if button is not None:
            header.pack_end(button)
        self.loading = Adw.StatusPage(title=_("Reading the activity…"))
        if hasattr(Adw, "SpinnerPaintable"):
            self.loading.set_paintable(Adw.SpinnerPaintable.new(self.loading))
        self.message = Adw.StatusPage()
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=24,
                               margin_bottom=24, margin_start=12, margin_end=12)
        scrolled = Gtk.ScrolledWindow(
            child=Adw.Clamp(maximum_size=CONTENT_WIDTH, child=self.content),
            hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        for name, widget in (("loading", self.loading), ("content", scrolled),
                             ("message", self.message)):
            self.stack.add_named(widget, name)
        self.stack.set_visible_child_name("loading")
        toolbar = Adw.ToolbarView(content=self.stack)
        toolbar.add_top_bar(header)
        self.page = Adw.NavigationPage(title=title, tag=TAG, child=toolbar)

    def say(self, text: str, icon: str = "dialog-warning-symbolic") -> None:
        self.message.set_icon_name(icon)
        self.message.set_title(text)
        self.stack.set_visible_child_name("message")

    def show(self, data) -> None:
        """What the file holds (fit.ActivityData): the tiles, a damaged file said under them;
        of a file still being written and of one without a summary, only that."""
        from openexpress import fit

        if data.state is fit.FileState.STILL_BEING_WRITTEN:
            self.say(_("Still being written: disconnect and reconnect the device"))
            return
        tiles = activity_tiles(data)
        if not tiles:
            self.say(_("This activity has no summary."), PAGE_ICON)
            return
        flow = Gtk.FlowBox(homogeneous=True, selection_mode=Gtk.SelectionMode.NONE,
                           min_children_per_line=2, max_children_per_line=TILES_IN_A_LINE,
                           column_spacing=12, row_spacing=12)
        for value, name in tiles:
            flow.append(Gtk.FlowBoxChild(child=_tile(value, name), focusable=False))
        self.content.append(flow)
        if data.state is fit.FileState.DAMAGED:
            damaged = Gtk.Label(label=_("Damaged file"), wrap=True, xalign=0)
            damaged.add_css_class("warning")
            self.content.append(damaged)
        self.stack.set_visible_child_name("content")
        log.info("activity page: %d tiles, %s", len(tiles), data.state.value)
