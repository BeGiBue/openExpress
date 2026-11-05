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
from openexpress.paths import APP_ID  # noqa: E402

log = logging.getLogger(__name__)

PAGE_ICON = f"{APP_ID}-profiles-symbolic"  # sliders
PROFILE_TAG, SCREEN_TAG = "profile", "profile-screen"
NARROWEST = (360, 200)  # a page's own least size (its breakpoints need one)
CONTENT_WIDTH = 760
# The activity files read for the profiles used lately when the Activities page has read none.
RECENT_ACTIVITIES = 10


edge_shaped, screen_title = names.edge_shaped, names.screen_title


def fields_text(count: int) -> str:
    return ngettext("{count} field", "{count} fields", count).format(count=count)


def _sentence(text: str) -> str:
    """A text that begins a row's subtitle: its first letter a capital."""
    return text[:1].upper() + text[1:]


def screen_caption(profile: profiles.Profile, screen: profiles.Screen) -> str:
    """Under the title of a screen of one's own: its fields and layout."""
    return caption(fields_text(len(screen.fields)),
                   names.layout_name(screen.variant, edge_shaped(profile)))


def profile_caption(profile: profiles.Profile) -> str:
    """Under a profile's name: how many screens of one's own and built in it scrolls through."""
    shown = profile.carousel()
    own = sum(1 for s in shown if s.own)
    parts = [ngettext("{count} data screen", "{count} data screens", own).format(count=own)]
    built_in = names.built_in_summary(profile)
    if built_in:
        parts.append(built_in)
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


LEAST_POINTS = 5.0  # the smallest text of a drawing


def name_font(cr, name: str, width: float, points: float) -> Pango.FontDescription:
    """The font of a built-in screen's name in its drawing: `points` at most, smaller when its
    longest word would not fit `width` (a word is then never broken in the middle)."""
    font = Pango.FontDescription.from_string(f"Sans {points:.1f}")
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(font)
    widest = 0
    for word in name.split():
        layout.set_text(word, -1)
        widest = max(widest, layout.get_pixel_size()[0])
    if widest > width:
        # Text grows with its size; a little less, as sizes are rounded to whole pixels.
        smaller = max(LEAST_POINTS, points * width / widest * 0.95)
        font = Pango.FontDescription.from_string(f"Sans {smaller:.1f}")
    return font


def _fits(cr, font: Pango.FontDescription, name: str, width: float, row: float) -> bool:
    """Whether a field's name fits its place: each word within `width`, the whole in two lines
    at most, broken between its words, and within the `row` the field has."""
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(font)
    for word in name.split():
        layout.set_text(word, -1)
        if layout.get_pixel_size()[0] > width:
            return False
    layout.set_text(name, -1)
    layout.set_width(int(width * Pango.SCALE))
    layout.set_wrap(Pango.WrapMode.WORD)
    return layout.get_line_count() <= 2 and layout.get_pixel_size()[1] <= row


def fields_font(cr, names: list[str], width: float, row: float,
                points: float) -> Pango.FontDescription:
    """The font of a screen's fields in its drawing, one for all of them: `points` at most,
    smaller until every name fits its place (`_fits`); never below the least size."""
    size = points
    while True:
        font = Pango.FontDescription.from_string(f"Sans {size:.1f}")
        if size <= LEAST_POINTS or all(_fits(cr, font, n, width, row) for n in names):
            return font
        size = max(LEAST_POINTS, size - 0.5)


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
    # One size for every drawing of a size, smaller for many fields: a drawing of 112 px and
    # one of 220 px read alike.
    points = max(LEAST_POINTS, min(width / 14, row * 0.5))
    if len(lines) == 1:  # a built-in screen's name
        font, two_lines = name_font(cr, lines[0], w, points), False
    else:
        font = fields_font(cr, lines, w, row, points)
        # Two lines only where they fit: on a small card with many long names each stays on
        # its line, cut short (the drawing's tooltip says them in full).
        two_lines = all(_fits(cr, font, line, w, row) for line in lines)
    cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.9)
    for n, line in enumerate(lines):
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(font)
        layout.set_text(line, -1)
        layout.set_width(int(max(w, 4) * Pango.SCALE))
        layout.set_alignment(Pango.Alignment.CENTER)
        # Wrapped between words: a built-in screen's name within its row, a field's name in two
        # lines at most, or one when two do not fit even at the least size.
        layout.set_wrap(Pango.WrapMode.WORD)
        layout.set_height(int(row * Pango.SCALE) if len(lines) == 1 else -2 if two_lines else -1)
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


def drawing_lines(profile: profiles.Profile, screen: profiles.Screen) -> list[str]:
    """What a screen's drawing says: its fields; a built-in screen's name, or for one not
    known its code alone (its title under the drawing says the rest)."""
    edge = edge_shaped(profile)
    if screen.own:
        return [names.field_name(i, edge) for i in screen.fields]
    if names.built_in_known(screen, edge):
        return [screen_title(profile, screen)]
    return [str(screen.code)]


def screen_drawing(profile: profiles.Profile, screen: profiles.Screen, size: int) -> Gtk.Widget:
    edge = edge_shaped(profile)
    lines = drawing_lines(profile, screen)
    area = Gtk.DrawingArea(content_width=size, content_height=size, halign=Gtk.Align.CENTER,
                           accessible_role=Gtk.AccessibleRole.PRESENTATION)
    area.set_draw_func(lambda a, cr, w, h: draw_screen(a, cr, w, h, edge, lines))
    if screen.own:
        area.set_tooltip_text("\n".join(lines))  # the names in full, however small drawn
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


# The icons of the built-in screens in their rows, by their codes (an Edge's and a watch's): one
# for each kind of screen, drawn in packaging/icons (the program's folder of icons is on the
# theme's search path); a kind the window shows elsewhere takes the theme's icon of it.


def _screen_icon(kind: str) -> str:
    return f"{APP_ID}-screen-{kind}-symbolic"


GROUP_ICON, CLOCK_ICON = "system-users-symbolic", "preferences-system-time-symbolic"
BUILT_IN_ICONS = {
    21: CLOCK_ICON, 22: _screen_icon("heart-rate-zone"), 25: _screen_icon("map"),
    26: _screen_icon("virtual-partner"), 30: "audio-x-generic-symbolic",
    35: _screen_icon("compass"), 38: _screen_icon("workout"), 44: _screen_icon("elevation"),
    56: _screen_icon("segment"), 57: GROUP_ICON, 58: _screen_icon("ebike"),
    63: _screen_icon("cycling-dynamics"), 74: _screen_icon("lap-summary"),
    80: _screen_icon("set"), 95: _screen_icon("ebike"), 100: _screen_icon("regatta"),
    101: _screen_icon("regatta"), 104: _screen_icon("climbpro"),
    125: _screen_icon("power-guide"), 127: _screen_icon("stamina"),
    128: "weather-clear-symbolic", 162: GROUP_ICON, 221: CLOCK_ICON, 223: _screen_icon("radar"),
}
# A built-in screen not known on this device (a screen with fields drawn, no kind).
UNKNOWN_SCREEN_ICON = _screen_icon("unknown")


def built_in_icon(code: int) -> str:
    return BUILT_IN_ICONS.get(code, UNKNOWN_SCREEN_ICON)


def place_text(place: int) -> str:
    # TRANSLATORS: where a screen stands among those the device always scrolls through
    return _("No. {place} in the scrolling order").format(place=place)


def data_card(win, profile_file, screen, place: int) -> Gtk.Widget:
    """A data screen: its drawing beside its title, place, layout and its fields, numbered, one
    to a line; a click opens its page."""
    profile = profile_file.profile
    edge = edge_shaped(profile)
    column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
    title = Gtk.Label(label=screen_title(profile, screen), xalign=0, wrap=True,
                      css_classes=["heading"])
    column.append(title)
    column.append(Gtk.Label(
        label=caption(place_text(place), fields_text(len(screen.fields)),
                      names.layout_name(screen.variant, edge)),
        xalign=0, wrap=True, css_classes=["dim-label", "caption"]))
    for n, number in enumerate(screen.fields, 1):
        column.append(Gtk.Label(label=f"{n}. {names.field_name(number, edge)}", xalign=0,
                                wrap=True))
    box = Gtk.Box(spacing=12, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
    box.append(screen_drawing(profile, screen, 120))
    box.append(column)
    button = Gtk.Button(child=box, css_classes=["card"])
    button.update_property([Gtk.AccessibleProperty.LABEL],
                           [f"{title.get_label()}, {place_text(place)}"])
    button.connect("clicked", lambda _b: open_screen(win, profile_file, screen))
    return button


def built_in_row(win, profile_file, screen, subtitle: str, state: str | None = None):
    """A built-in screen: its icon and name, under it `subtitle`; a click opens its page."""
    profile = profile_file.profile
    row = _row(screen_title(profile, screen), subtitle, state)
    known = names.built_in_known(screen, edge_shaped(profile))
    row.add_prefix(Gtk.Image(icon_name=built_in_icon(screen.code) if known
                             else UNKNOWN_SCREEN_ICON))
    row.set_activatable(True)
    row.connect("activated", lambda _r: open_screen(win, profile_file, screen))
    return row


def open_profile(win, profile_file) -> None:
    """A profile's page pushed onto the window's navigation; nothing is read (the section
    read every profile)."""
    profile = profile_file.profile
    edge = edge_shaped(profile)
    box = _box()
    # The screens the device always scrolls through, numbered in its order; those it shows only
    # when they are needed (an Edge's) apart.
    always = [s for s in profile.carousel() if not names.when_needed(s, edge)]
    needed = [s for s in profile.carousel() if names.when_needed(s, edge)]
    data = [(n, s) for n, s in enumerate(always, 1) if s.own]
    if data:
        group = Adw.PreferencesGroup(title=_("Data screens"),
                                     description=_("The fields in their order on the screen"))
        cards = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for place, screen in data:
            cards.append(data_card(win, profile_file, screen, place))
        group.add(cards)
        box.append(group)
    built_in = [(n, s) for n, s in enumerate(always, 1) if not s.own]
    if built_in:
        group = Adw.PreferencesGroup(title=_("Built-in screens in the scrolling order"))
        for place, screen in built_in:
            known = names.built_in_known(screen, edge)
            group.add(built_in_row(win, profile_file, screen, caption(
                place_text(place), *(() if known else (_("Not known to openExpress yet"),)))))
        box.append(group)
    if needed:
        group = Adw.PreferencesGroup()
        folded = Adw.ExpanderRow(title=names.built_in_count(0, len(needed), 0),
                                 subtitle=_("The device shows them only when they are needed"))
        for screen in needed:
            folded.add_row(built_in_row(win, profile_file, screen,
                                        _sentence(names.when_needed(screen, edge)),
                                        state_text(screen)))
        group.add(folded)
        box.append(group)
    if not always and not needed:
        group = Adw.PreferencesGroup(title=_("Data screens"))
        group.add(_row(_("No data screen is shown")))
        box.append(group)
    off_built_in = [s for s in profile.built_in()
                    if not s.shown and s.code != profiles.RESERVED_CODE]
    off_own = [s for s in profile.own_screens() if not s.shown]
    if off_built_in or off_own:
        group = Adw.PreferencesGroup(title=_("Off and hidden"))
        for screen in off_built_in:
            known = names.built_in_known(screen, edge)
            # The state only where it tells hidden from off.
            group.add(built_in_row(win, profile_file, screen,
                                   "" if known else _("Not known to openExpress yet"),
                                   state_text(screen) if screen.hidden else None))
        for screen in off_own:
            group.add(_row(screen_title(profile, screen), screen_caption(profile, screen)))
        box.append(group)
    details = Adw.PreferencesGroup(title=_("Details"))
    if not edge:
        details.set_description(_(
            "The fields are named as Garmin's Edge devices number them; the codes of some of "
            "this device's layouts and built-in screens are not known to openExpress yet."))
    details.add(_row(_("File"), profile_file.name))
    box.append(details)
    log.info("profile page: %d screens always shown, %d when needed, %d off or hidden (%s)",
             len(always), len(needed), len(off_built_in) + len(off_own),
             "an Edge's" if edge else "a watch's")
    win.navigation.push(_page(profile_file.title, _device_name(win),
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
            # TRANSLATORS: the n-th place of a data screen, where a field stands ("Field" is
            # said only of a data field)
            place = _("Place {place}").format(place=n)
            if number is None:
                sub = place
            else:
                # TRANSLATORS: the number of a data field in the profile file
                said = _("number {number}").format(number=number)
                sub = caption(place, said)
            fields.add(_row(names.field_name(number, edge), sub))
        box.append(fields)
    details = Adw.PreferencesGroup(title=_("Details"))
    details.add(_row(_("Code of the screen"), str(screen.code)))
    details.add(_row(_("State"), state_text(screen)))
    box.append(details)
    win.navigation.push(_page(screen_title(profile, screen), profile_file.title, SCREEN_TAG,
                              box))


def profile_row(win, group, profile_file) -> Adw.ActionRow:
    """A profile in the list: its colour, name and screens; activated, its page opens."""
    profile = profile_file.profile
    row = Adw.ActionRow(title=GLib.markup_escape_text(profile_file.title),
                        subtitle=GLib.markup_escape_text(profile_caption(profile)),
                        activatable=True)
    row.add_prefix(colour_dot(profile))
    row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
    row.connect("activated", lambda _r: open_profile(win, profile_file))
    group.add(row)
    return row


def _no_profiles(sec) -> None:
    """The page without any profile: the page's icon and that it has none, in its content."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER,
                  margin_top=24, margin_bottom=24)
    box.append(Gtk.Image(icon_name=PAGE_ICON, pixel_size=64))
    words = Gtk.Label(label=_("No activity profiles"), wrap=True,
                      justify=Gtk.Justification.CENTER, css_classes=["title-2"])
    box.append(words)
    sec.group().add(box)


def _profile_groups(win, sec, readable, recent) -> int:
    """A search, the profiles of the newest activities and every profile; how many of the
    newest activities' profiles are shown."""
    rows: list[tuple[Adw.PreferencesGroup, Adw.ActionRow, str]] = []
    groups = []
    search = Gtk.SearchEntry(placeholder_text=ngettext(
        "Search {count} profile", "Search {count} profiles", len(readable)).format(
        count=len(readable)), hexpand=True)
    sec.group().add(search)
    by_name = {f.profile.name: f for f in readable}
    recent_files = [by_name[n] for n in recent if n in by_name]
    if recent_files:
        g = sec.group(_("Used recently"), _("From the newest activities on the device"))
        groups.append(g)
        for f in recent_files:
            rows.append((g, profile_row(win, g, f), f.title))
    g = sec.group(_("All profiles"))
    groups.append(g)
    for f in readable:
        rows.append((g, profile_row(win, g, f), f.title))

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
    return len(recent_files)


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
        every profile, the files that are no profile; without a profile, that it has none."""
        if self.session is None:
            return
        self.profiles = found
        sec = self.sections["profiles"]
        readable = [f for f in files if f.profile is not None]
        recent_count = 0
        if readable:
            recent_count = _profile_groups(self, sec, readable, recent)
        else:
            # In the page's content: the loading shows the content when it is done.
            _no_profiles(sec)
        unreadable = [f for f in files if f.profile is None]
        if unreadable:
            g = sec.group(_("Files that are no profile"))
            for f in unreadable:
                g.add(_row(f.name, f.error or ""))
        backup_time = getattr(found, "backup_time", None)  # none read: no list of them
        if backup_time is not None:
            # TRANSLATORS: the copies an Edge keeps of its profiles itself; {date}: when made
            sec.group("", _("The device keeps backups of its profiles from {date}").format(
                date=profiles.backup_day(backup_time)))
        log.info("profiles page: %d profiles, %d of the newest activities, %d files not read",
                 len(readable), recent_count, len(unreadable))
