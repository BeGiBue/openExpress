"""The data screens of a device's sport profiles (activity profiles), read only.

A profile is one FIT file of type 3 (sport) in the device's folder of that data type
(`GARMIN/Sports` on a watch, `Garmin/Sports` on an Edge). Its message 12 names it and gives its
colour; message 14, which the public FIT profile does not describe, is the table of its data
screens: one record a place, most places unused. The facts of message 14 come from two open
projects that learnt them by changing a screen on a device and reading the file again
(Activity Profile Editor, by fullcarbonbike, MIT; Sommet, by skinnie), checked here against the
files of a watch and of a bike computer:

- 254: the place of the record (not the screen's identity);
- 1: its state: 1 a screen, 0 a screen turned off or deleted, 255 a place unused;
- 3: how many of the IDs of field 7 count;
- 7: the IDs of its data fields (eight on a watch, ten on an Edge);
- 8: the variant of its layout;
- 9: its place in the carousel, rising; 255: none;
- 10: its code: below 25 a screen of one's own (a counter), else a built-in screen;
- 12: on an Edge only, 1 when it is hidden.

Message 13 holds the profile's other settings, personal values among them (zones, weight):
it is never decoded."""

from __future__ import annotations

import logging
import time
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from openexpress import applog, fit
from openexpress.errors import UserFacingError
from openexpress.i18n import _
from openexpress.progress import Step, say_to

log = logging.getLogger(__name__)

SPORT_FILE_TYPE = 3
_MESG_FILE_ID, _MESG_SPORT, _MESG_SCREEN = 0, 12, 14
_FILE_TYPE = 0
_SPORT_NAME, _SPORT_COLOUR, _SPORT, _SUB_SPORT = 3, 10, 0, 1
_PLACE, _STATE, _COUNT, _FIELDS, _VARIANT, _ORDER, _CODE, _HIDDEN = 254, 1, 3, 7, 8, 9, 10, 12
SHOWN, OFF, UNUSED = 1, 0, 255
# The codes of the screens of one's own are a counter from 0 (ten screens at most); from 20 on
# they are built-in screens (a watch's clock with status icons is 21, its heart rate zone gauge
# 22; the Map is 25).
FIRST_BUILT_IN_CODE = 20


class ProfileError(UserFacingError):
    """A file of the Sports folder that cannot be read as a sport profile."""


@dataclass(frozen=True)
class Screen:
    """A data screen of a profile: its place in the table, its code, state, place in the
    carousel (None: none), the IDs of its fields (None: an empty place), the variant of its
    layout (None: not given) and, on an Edge, whether it is hidden (None: the file does not
    say)."""

    place: int
    code: int
    state: int
    order: int | None
    fields: tuple[int | None, ...]
    variant: int | None
    hidden: bool | None

    @property
    def own(self) -> bool:
        """A screen of one's own, as opposed to a built-in one (Map, Compass…)."""
        return self.code < FIRST_BUILT_IN_CODE

    @property
    def shown(self) -> bool:
        """Whether the device scrolls to it during an activity."""
        return self.state == SHOWN and self.order is not None and not self.hidden


@dataclass(frozen=True)
class Profile:
    """A sport profile as its file says it: its name, sport and sub-sport, colour (red,
    green, blue), its screens (the places in use), how many field IDs a screen has room for,
    whether the file says which screens are hidden (field 12, an Edge's), and whether the
    file was cut short (read as far as it goes)."""

    name: str
    sport: int | None
    sub_sport: int | None
    colour: tuple[int, int, int] | None
    screens: tuple[Screen, ...]
    slots: int
    has_hidden_flag: bool
    incomplete: bool = field(default=False, compare=False)

    def carousel(self) -> list[Screen]:
        """The screens the device scrolls through, in their order."""
        return sorted((s for s in self.screens if s.shown), key=lambda s: s.order)

    def own_screens(self) -> list[Screen]:
        return [s for s in self.screens if s.own]

    def built_in(self) -> list[Screen]:
        """The built-in screens, shown or not, by their code."""
        return sorted((s for s in self.screens if not s.own), key=lambda s: s.code)


def _int(value) -> int | None:
    return value if isinstance(value, int) else None


def _screen(values: dict) -> Screen | None:
    state, code = _int(values.get(_STATE)), _int(values.get(_CODE))
    if state is None or state == UNUSED or code is None:
        return None
    ids = values.get(_FIELDS)
    ids = ids if isinstance(ids, tuple) else (() if ids is None else (ids,))
    count = _int(values.get(_COUNT)) or 0
    hidden = values.get(_HIDDEN, "absent")
    return Screen(
        place=_int(values.get(_PLACE)) if _int(values.get(_PLACE)) is not None else -1,
        code=code, state=state, order=_int(values.get(_ORDER)),
        fields=tuple(i if isinstance(i, int) else None for i in ids[:count]),
        variant=_int(values.get(_VARIANT)),
        hidden=None if hidden == "absent" else hidden == 1)


def read_profile(data: bytes) -> Profile:
    """The profile a sport file holds. ProfileError when it is no FIT file, no sport profile,
    or too short to say its name."""
    incomplete = fit.not_whole(data) is not None
    file_type, sport, screens, slots, hidden_flag = None, None, [], 0, False
    try:
        for num, values in fit.iter_messages(data, wanted=(_MESG_FILE_ID, _MESG_SPORT,
                                                           _MESG_SCREEN),
                                             arrays=(_MESG_SPORT, _MESG_SCREEN)):
            if num == _MESG_FILE_ID and file_type is None:
                file_type = _int(values.get(_FILE_TYPE))
            elif num == _MESG_SPORT and sport is None:
                sport = values
            elif num == _MESG_SCREEN:
                ids = values.get(_FIELDS)
                slots = max(slots, len(ids) if isinstance(ids, tuple) else 1)
                hidden_flag = hidden_flag or _HIDDEN in values
                screen = _screen(values)
                if screen is not None:
                    screens.append(screen)
    except fit.FitError as e:
        raise ProfileError(_("The file of this profile could not be read ({error})")
                           .format(error=e)) from e
    if file_type is not None and file_type != SPORT_FILE_TYPE:
        raise ProfileError(_("This file is not a sport profile."))
    if sport is None:
        if incomplete or file_type is None:
            raise ProfileError(_("The file of this profile could not be read ({error})")
                               .format(error=_("it ends too soon")))
        raise ProfileError(_("This file is not a sport profile."))
    colour = sport.get(_SPORT_COLOUR)
    colour = (tuple(colour[:3]) if isinstance(colour, tuple) and len(colour) >= 3
              and all(isinstance(c, int) for c in colour[:3]) else None)
    name = sport.get(_SPORT_NAME)
    return Profile(name=name if isinstance(name, str) else "",
                   sport=_int(sport.get(_SPORT)), sub_sport=_int(sport.get(_SUB_SPORT)),
                   colour=colour, screens=tuple(screens), slots=slots,
                   has_hidden_flag=hidden_flag, incomplete=incomplete)


# --- the profiles of a device ----------------------------------------------------------------

SPORT_DATATYPE = "FIT_TYPE_3"


def keeps_profiles(device) -> bool:
    """Whether the device's GarminDevice.xml declares a folder of sport profiles."""
    return bool(device.sources(SPORT_DATATYPE))


@dataclass(frozen=True)
class ProfileFile:
    """A file of the device's Sports folder: its real path and name, its size and time of
    change, and the profile it holds, or why it could not be read."""

    path: str
    name: str
    size: int
    mtime: float
    profile: Profile | None
    error: str | None = None


class ProfileList:
    """The sport profiles of a device, as its storage lists and reads them: each file read
    once, kept by its path, size and time of change (read again once one of them changes).
    Nothing is written. Has: what it read of the open device."""

    def __init__(self, device, storage):
        self.device, self.storage = device, storage
        self._kept: dict[tuple, ProfileFile] = {}

    def read_all(self, progress: Callable[[str], None] | None = None) -> list[ProfileFile]:
        """Every file of the Sports folder: the profiles by their name, then those that could
        not be read. `progress`: a step for each file read, never its name. An error of the
        device stops it (DeviceError)."""
        progress = say_to(progress)
        found = []
        for src in self.device.sources(SPORT_DATATYPE):
            for path, entry in self.storage.walk_files(src.path):
                if src.matches(path):
                    found.append((path, entry))
        keys = {(path.casefold(), entry.size, entry.mtime): (path, entry)
                for path, entry in found}
        to_read = [key for key in keys if key not in self._kept]
        started, size, unreadable = time.monotonic(), 0, 0
        # TRANSLATORS: a step of a long task: the profile files read ("… · 2 of 30")
        head = _("Reading profiles")
        for n, key in enumerate(to_read, 1):
            progress(Step(head, n, len(to_read)))
            path, entry = keys[key]
            data = self.storage.read_at(path)
            size += len(data)
            name = path.rsplit("/", 1)[-1]
            try:
                kept = ProfileFile(path, name, entry.size, entry.mtime, read_profile(data))
            except ProfileError as e:
                unreadable += 1
                kept = ProfileFile(path, name, entry.size, entry.mtime, None, str(e))
            self._kept[key] = kept
        self._kept = {key: self._kept[key] for key in keys}  # files gone are forgotten
        if to_read:
            log.info("profiles: %d files, %d read now in %.1f s (%s), %d not readable",
                     len(keys), len(to_read), time.monotonic() - started, applog.size(size),
                     unreadable)
        return sorted(self._kept.values(), key=lambda f: (
            f.profile is None, sort_key(f.profile.name if f.profile else f.name)))


def sort_key(name: str) -> str:
    """A name as profiles are sorted and searched by it: letter case and diacritics aside (ł
    as l too)."""
    text = unicodedata.normalize("NFKD", name.casefold().replace("ł", "l"))
    return "".join(c for c in text if not unicodedata.combining(c))


def recent_names(summaries: Iterable, limit: int = 5) -> list[str]:
    """The names of the profiles of the newest activities, newest first, each once: from the
    summaries of activity files (fit.ActivitySummary; None: a file that could not be read)."""
    dated = sorted((s for s in summaries if s is not None and s.profile),
                   key=lambda s: s.start or s.created or 0, reverse=True)
    names: list[str] = []
    for s in dated:
        if s.profile not in names:
            names.append(s.profile)
    return names[:limit]

