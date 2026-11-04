"""The Activity profiles page of the window, read only: the sport profiles of the open device,
those of its newest activities first, with a search; a profile's page with its data screens in
the order the device scrolls through them, each drawn in the shape of the device's screen with
its fields in their order, and its built-in screens; a screen's page with its layout and its
fields (profiles.py reads them, profile_names names them). Nothing is written to the device;
what openExpress does not know (a code of a built-in screen or of a layout nobody has named, a
field without a name) is said as a number.
Has: the profiles of the open device as their page read them (profiles).
ProfilesPage is a mixin of MainWindow (gui/app.py), without __init__ of its own; what it uses of
the window (session, run_task, sections, navigation, …) is the window's."""
from __future__ import annotations

import logging
import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk, Pango, PangoCairo  # noqa: E402 - imports must follow gi.require_version

from openexpress import profile_names as names  # noqa: E402
from openexpress import profiles  # noqa: E402
from openexpress.i18n import _, caption, ngettext  # noqa: E402

log = logging.getLogger(__name__)

PAGE_ICON = "view-grid-symbolic"
PROFILE_TAG, SCREEN_TAG = "profile", "profile-screen"
NARROWEST = (360, 200)  # a page's own least size (its breakpoints need one)
CONTENT_WIDTH = 760
# The activity files read for the profiles used lately when the Activities page has read none.
RECENT_ACTIVITIES = 10
# The code of a place an Edge keeps for later ("reserved"): never a screen of its own.
EDGE_RESERVED_CODE = 32


def edge_shaped(profile: profiles.Profile) -> bool:
    """Whether the file is in the shape of an Edge's (it says which screens are hidden): the
    codes and layouts of the Edge bike computers are known; a watch's are not yet."""
    return profile.has_hidden_flag


def own_titles(profile: profiles.Profile) -> dict[int, str]:
    """The titles of the screens of one's own, by their place in the table: "Screen 1, 2…" in
    the order the device scrolls through them, then those turned off."""
    own = [s for s in profile.carousel() if s.own]
    own += [s for s in profile.own_screens() if s not in own]
    # TRANSLATORS: a data screen of one's own, by its order on the device
    return {s.place: _("Screen {number}").format(number=n) for n, s in enumerate(own, 1)}


def screen_title(profile: profiles.Profile, screen: profiles.Screen) -> str:
    if screen.own:
        return own_titles(profile).get(screen.place, "")
    return names.built_in_name(screen, edge_shaped(profile))


def fields_text(count: int) -> str:
    return ngettext("{count} field", "{count} fields", count).format(count=count)


def screen_caption(profile: profiles.Profile, screen: profiles.Screen) -> str:
    """Under a screen's title: its fields and layout, or what kind of screen it is."""
    if screen.own:
        return caption(fields_text(len(screen.fields)),
                       names.layout_name(screen.variant, edge_shaped(profile)))
    if names.built_in_known(screen, edge_shaped(profile)):
        # TRANSLATORS: a screen of the device of its own (Map, Compass…), not one of the user's
        return _("Built-in screen")
    return _("Not known to openExpress yet")


def profile_caption(profile: profiles.Profile) -> str:
    """Under a profile's name: how many screens of one's own and built in it scrolls through."""
    shown = profile.carousel()
    own = sum(1 for s in shown if s.own)
    built_in = len(shown) - own
    parts = [ngettext("{count} data screen", "{count} data screens", own).format(count=own)]
    if built_in:
        parts.append(ngettext("{count} built-in screen", "{count} built-in screens",
                              built_in).format(count=built_in))
    return caption(*parts)


def state_text(screen: profiles.Screen) -> str:
    """A built-in screen's state on the device."""
    if screen.hidden:
        # TRANSLATORS: a built-in screen hidden on the device
        return _("Hidden")
    if screen.shown:
        # TRANSLATORS: a built-in screen turned on
        return _("On")
    # TRANSLATORS: a built-in screen turned off
    return _("Off")


# --- the drawing of a screen ----------------------------------------------------------------


def draw_screen(area, cr, width, height, edge: bool, lines: list[str]) -> None:
    """A screen of the device: a circle for a watch, a rounded rectangle for an Edge, with
    `lines` (its fields, or the name of a built-in screen) one under another, in their order:
    where each field stands on the screen depends on the layout, which this does not draw."""
    fg = area.get_color()
    pad = 2
    if edge:
        w, h = min(width, height * 0.62) - 2 * pad, height - 2 * pad
        left, top, radius = (width - w) / 2, pad, max(6.0, w * 0.08)
        cr.new_sub_path()
        cr.arc(left + w - radius, top + radius, radius, -math.pi / 2, 0)
        cr.arc(left + w - radius, top + h - radius, radius, 0, math.pi / 2)
        cr.arc(left + radius, top + h - radius, radius, math.pi / 2, math.pi)
        cr.arc(left + radius, top + radius, radius, math.pi, 3 * math.pi / 2)
        cr.close_path()
        inner = (left + 4, top + 4, w - 8, h - 8)
    else:
        r = min(width, height) / 2 - pad
        cx, cy = width / 2, height / 2
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        side = r * math.sqrt(2)  # the square inside the circle
        inner = (cx - side / 2, cy - side / 2, side, side)
    cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.06)
    cr.fill_preserve()
    cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.55)
    cr.set_line_width(2)
    cr.stroke()
    if not lines:
        return
    x, y, w, h = inner
    row = h / max(len(lines), 1)
    font = Pango.FontDescription.from_string(f"Sans {max(6, min(12, int(row * 0.45)))}")
    cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.9)
    for n, line in enumerate(lines):
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(font)
        layout.set_text(line, -1)
        layout.set_width(int(max(w, 4) * Pango.SCALE))
        layout.set_alignment(Pango.Alignment.CENTER)
        layout.set_ellipsize(Pango.EllipsizeMode.END)
        _tw, th = layout.get_pixel_size()
        cr.move_to(x, y + row * n + (row - th) / 2)
        PangoCairo.show_layout(cr, layout)
        if n:
            cr.save()
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.25)
            cr.set_line_width(1)
            cr.move_to(x, y + row * n)
            cr.line_to(x + w, y + row * n)
            cr.stroke()
            cr.restore()


def screen_drawing(profile: profiles.Profile, screen: profiles.Screen, size: int) -> Gtk.Widget:
    edge = edge_shaped(profile)
    lines = ([names.field_name(i) for i in screen.fields] if screen.own
             else [screen_title(profile, screen)])
    area = Gtk.DrawingArea(content_width=size, content_height=size, halign=Gtk.Align.CENTER,
                           accessible_role=Gtk.AccessibleRole.PRESENTATION)
    area.set_draw_func(lambda a, cr, w, h: draw_screen(a, cr, w, h, edge, lines))
    return area


def colour_dot(profile: profiles.Profile) -> Gtk.Widget:
    """The profile's colour, for the eye only."""
    rgb = profile.colour

    def draw(area, cr, width, height):
        if rgb is None:
            fg = area.get_color()
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.3)
        else:
            cr.set_source_rgb(*(c / 255 for c in rgb))
        cr.arc(width / 2, height / 2, min(width, height) / 2, 0, 2 * math.pi)
        cr.fill()

    area = Gtk.DrawingArea(content_width=12, content_height=12, valign=Gtk.Align.CENTER,
                           accessible_role=Gtk.AccessibleRole.PRESENTATION)
    area.set_draw_func(draw)
    return area


# --- the pages ------------------------------------------------------------------------------


def _read(found, activities, device, storage, progress):
    """In the task's thread: every profile, and the names of the profiles of the newest
    activities (those the Activities page read, else the newest few read here)."""
    from openexpress import activities as acts

    files = found.read_all(progress)
    if activities is None or not activities.read:
        activities = acts.DeviceActivities(device, storage, None)
        activities.list_files()
        activities.read_next(RECENT_ACTIVITIES)
    recent = profiles.recent_names(r.summary for r in activities.read)
    return files, recent


def leave(win) -> None:
    """Back to the device view when a profile's or a screen's page is shown: the pages of the
    device are drawn anew."""
    from openexpress.gui import activity_map

    page = activity_map.visible_page(win)
    if page is not None and page.get_tag() in (PROFILE_TAG, SCREEN_TAG):
        log.info("profile page: closed with the device view")
        win.navigation.pop_to_page(win.device_view)


def _page(title: str, subtitle: str, tag: str, content: Gtk.Widget) -> Adw.NavigationPage:
    header = Adw.HeaderBar(title_widget=Adw.WindowTitle(title=title, subtitle=subtitle))
    scrolled = Gtk.ScrolledWindow(
        child=Adw.Clamp(maximum_size=CONTENT_WIDTH, child=content),
        hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
    toolbar = Adw.ToolbarView(content=scrolled)
    toolbar.add_top_bar(header)
    sized = Adw.BreakpointBin(child=toolbar, width_request=NARROWEST[0],
                              height_request=NARROWEST[1])
    return Adw.NavigationPage(title=title, tag=tag, child=sized)


def _box() -> Gtk.Box:
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24, margin_top=24,
                   margin_bottom=24, margin_start=12, margin_end=12)


def _row(title: str, subtitle: str = "", suffix: str | None = None) -> Adw.ActionRow:
    row = Adw.ActionRow(title=GLib.markup_escape_text(title),
                        subtitle=GLib.markup_escape_text(subtitle))
    row.set_subtitle_lines(0)
    if suffix is not None:
        row.add_suffix(Gtk.Label(label=suffix, css_classes=["dim-label"], wrap=True))
    return row


def _device_name(win) -> str:
    from openexpress.gui.device_page import device_name

    return device_name(win.session) if win.session is not None else ""


def screen_card(win, profile_file, screen) -> Gtk.Widget:
    """A screen in the carousel: its drawing, title and caption; a click opens its page."""
    profile = profile_file.profile
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=12,
                  margin_bottom=12, margin_start=12, margin_end=12)
    box.append(screen_drawing(profile, screen, 112))
    title = Gtk.Label(label=screen_title(profile, screen), xalign=0, wrap=True,
                      css_classes=["heading"])
    caption = Gtk.Label(label=screen_caption(profile, screen), xalign=0, wrap=True,
                        css_classes=["dim-label", "caption"])
    box.append(title)
    box.append(caption)
    button = Gtk.Button(child=box, css_classes=["card"])
    button.update_property([Gtk.AccessibleProperty.LABEL],
                           [f"{title.get_label()}, {caption.get_label()}"])
    button.connect("clicked", lambda _b: open_screen(win, profile_file, screen))
    return button


def open_profile(win, profile_file) -> None:
    """A profile's page pushed onto the window's navigation; nothing is read (the section
    read every profile)."""
    profile = profile_file.profile
    edge = edge_shaped(profile)
    box = _box()
    screens = Adw.PreferencesGroup(
        title=_("Data screens"),
        description=_("In the order the device scrolls through them"))
    flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                       min_children_per_line=2, max_children_per_line=4,
                       column_spacing=12, row_spacing=12)
    for screen in profile.carousel():
        flow.append(screen_card(win, profile_file, screen))
    if not profile.carousel():
        screens.add(_row(_("No data screen is shown")))
    else:
        screens.add(flow)
    box.append(screens)
    built_in = [s for s in profile.built_in()
                if not (edge and s.code == EDGE_RESERVED_CODE)]
    if built_in:
        group = Adw.PreferencesGroup(title=_("Built-in screens"))
        for screen in built_in:
            caption = ("" if names.built_in_known(screen, edge)
                       else _("Not known to openExpress yet"))
            group.add(_row(screen_title(profile, screen), caption, state_text(screen)))
        box.append(group)
    off = [s for s in profile.own_screens() if not s.shown]
    if off:
        group = Adw.PreferencesGroup(title=_("Screens turned off"))
        for screen in off:
            group.add(_row(screen_title(profile, screen), screen_caption(profile, screen)))
        box.append(group)
    details = Adw.PreferencesGroup(title=_("Details"))
    if not edge:
        details.set_description(_(
            "The fields are named as Garmin's Edge devices number them; the codes of this "
            "device's built-in screens and layouts are not known to openExpress yet."))
    details.add(_row(_("File"), profile_file.name))
    box.append(details)
    log.info("profile page: %d screens shown, %d built-in, %d turned off (%s)",
             len(profile.carousel()), len(built_in), len(off),
             "an Edge's" if edge else "a watch's")
    win.navigation.push(_page(profile.name or profile_file.name, _device_name(win),
                              PROFILE_TAG, box))


def open_screen(win, profile_file, screen) -> None:
    """A screen's page: its drawing, layout and fields, each field with its number."""
    profile = profile_file.profile
    edge = edge_shaped(profile)
    box = _box()
    box.append(screen_drawing(profile, screen, 220))
    if screen.own:
        box.append(Gtk.Label(
            label=_("The fields in their order; where each stands on the screen depends on "
                    "the layout"), wrap=True, justify=Gtk.Justification.CENTER,
            css_classes=["dim-label", "caption"]))
        layout = Adw.PreferencesGroup(title=_("Layout"))
        layout.add(_row(_("Layout"), names.layout_name(screen.variant, edge)))
        layout.add(_row(_("Number of fields"), str(len(screen.fields))))
        box.append(layout)
        fields = Adw.PreferencesGroup(title=_("Fields"),
                                      description=_("In their order on the screen"))
        for n, number in enumerate(screen.fields, 1):
            if number is None:
                # TRANSLATORS: the n-th place of a screen
                sub = _("Field {place}").format(place=n)
            else:
                # TRANSLATORS: the number of a data field in the profile file
                sub = caption(_("Field {place}").format(place=n),
                              _("number {number}").format(number=number))
            fields.add(_row(names.field_name(number), sub))
        box.append(fields)
    details = Adw.PreferencesGroup(title=_("Details"))
    details.add(_row(_("Code of the screen"), str(screen.code)))
    details.add(_row(_("State"), state_text(screen)))
    box.append(details)
    win.navigation.push(_page(screen_title(profile, screen), profile.name, SCREEN_TAG, box))


def profile_row(win, group, profile_file) -> Adw.ActionRow:
    """A profile in the list: its colour, name and screens; activated, its page opens."""
    profile = profile_file.profile
    row = Adw.ActionRow(title=GLib.markup_escape_text(profile.name or profile_file.name),
                        subtitle=GLib.markup_escape_text(profile_caption(profile)),
                        activatable=True)
    row.add_prefix(colour_dot(profile))
    row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
    row.connect("activated", lambda _r: open_profile(win, profile_file))
    group.add(row)
    return row


class ProfilesPage:
    """The Activity profiles page and its task."""

    def load_profiles(self) -> None:
        s = self.session
        sec = self.sections["profiles"]
        if not profiles.keeps_profiles(s.device):
            # As a page that does not apply to the device: information, nothing read.
            sec.clear()
            sec.info.set_icon_name(PAGE_ICON)
            sec.info.set_title(sec.title)
            sec.info.set_description(GLib.markup_escape_text(
                _("This device keeps no activity profiles.")))
            sec.show("info")
            return
        found = self.profiles
        if found is None or found.storage is not s.storage:
            found = profiles.ProfileList(s.device, s.storage)
        acts = self.activities
        if acts is not None and acts.storage is not s.storage:
            acts = None
        self._load("profiles", _("Reading profiles…"),
                   lambda: _read(found, acts, s.device, s.storage, self.progress),
                   lambda result: self.show_profiles(found, *result))

    def show_profiles(self, found, files, recent) -> None:
        """The list of the profiles read: a search, the profiles of the newest activities,
        every profile, the files that are no profile."""
        if self.session is None:
            return
        self.profiles = found
        sec = self.sections["profiles"]
        readable = [f for f in files if f.profile is not None]
        if not files:
            sec.info.set_icon_name(PAGE_ICON)
            sec.info.set_title(_("No activity profiles"))
            sec.info.set_description("")
            sec.show("info")
            return
        rows: list[tuple[Adw.PreferencesGroup, Adw.ActionRow, str]] = []
        search = Gtk.SearchEntry(placeholder_text=ngettext(
            "Search {count} profile", "Search {count} profiles", len(readable)).format(
            count=len(readable)), hexpand=True)
        top = sec.group()
        top.add(search)
        by_name = {f.profile.name: f for f in readable}
        groups = []
        recent_files = [by_name[n] for n in recent if n in by_name]
        if recent_files:
            g = sec.group(_("Used recently"), _("From the newest activities on the device"))
            groups.append(g)
            for f in recent_files:
                rows.append((g, profile_row(self, g, f), f.profile.name))
        g = sec.group(_("All profiles"))
        groups.append(g)
        for f in readable:
            rows.append((g, profile_row(self, g, f), f.profile.name))
        unreadable = [f for f in files if f.profile is None]
        if unreadable:
            g = sec.group(_("Files that are no profile"))
            for f in unreadable:
                g.add(_row(f.name, f.error or ""))

        def changed(entry):
            wanted = profiles.sort_key(entry.get_text().strip())
            seen = set()
            for group, row, name in rows:
                shown = not wanted or wanted in profiles.sort_key(name)
                row.set_visible(shown)
                if shown:
                    seen.add(group)
            for group in groups:
                group.set_visible(group in seen)

        search.connect("search-changed", changed)
        log.info("profiles page: %d profiles, %d of the newest activities, %d files not read",
                 len(readable), len(recent_files), len(unreadable))
