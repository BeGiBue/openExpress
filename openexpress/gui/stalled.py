"""A device that stopped responding, as the window tells it: a banner on top of the start page
and of the device view, with the device's name when it is known, until the device is gone
from its place on USB (unplugged, or restarted: a new device number); the session of that
device closed as if it were unplugged; no error dialog besides. What gio_storage finds and
counts on USB leaves that place out meanwhile (gio_storage.stalled_places), so nothing tries
it again; the other devices stay as they are.

Has: the devices that stopped responding (_stalled: their place on USB and name), and whether
a stall is being told (_telling_stall: error() shows no dialog meanwhile).
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass

from openexpress.device import gio_storage
from openexpress.device.gio_storage import usb_place
from openexpress.device.storage import DeviceNotResponding
from openexpress.gui.connected import close_as_unplugged
from openexpress.gui.words import stalled_text

log = logging.getLogger(__name__)


@dataclass(eq=False)
class Stalled:
    """A device that stopped responding: its place on USB (None: not known) and its name
    (None: not known); `usb_then`: the Garmin devices on USB when its place was not known, so
    that it counts as gone once they change."""

    usb: gio_storage.GarminUsb | None
    name: str | None
    usb_then: tuple[str, ...] = ()


def _is_open(win, place) -> bool:
    """Whether the device at `place` (None: not known) is the one open."""
    if win.session is None:
        return False
    storage = win.session.storage
    if place is None:
        return storage.stalled
    # A folder given with --path has no place on USB.
    return usb_place(getattr(storage, "usb", None)) == place


def _name_of(win, usb) -> str | None:
    """The name of the device at `usb`: of the one open, or of one on the list of devices
    connected; None when neither is it."""
    place = usb_place(usb)
    if _is_open(win, place):
        return win.session.device.description or None
    for summary in win.connected.devices if place is not None else []:
        if usb_place(summary.found.usb) == place:
            return summary.description or None
    return None


def _still_there(stalled: Stalled) -> bool:
    if stalled.usb is not None:
        return gio_storage.usb_still_there(stalled.usb)
    return tuple(gio_storage.garmin_products_on_usb()) == stalled.usb_then


def _close_if_open(win, place, unless_busy: bool = False) -> None:
    """The device at `place` closed if it is the one open, as an unplugged one is: nothing can
    be done with it. `unless_busy`: a running task closes it itself, as it fails at once."""
    if not _is_open(win, place) or (unless_busy and win.busy):
        return
    log.info("window: the device open stopped responding, closed as if it were unplugged")
    close_as_unplugged(win)


def note(win, error: DeviceNotResponding) -> None:
    """A task met a device that stopped responding: the banner says it, and the device is
    closed if it is the one open."""
    usb = error.usb
    place = usb_place(usb)
    # A device whose place is not known is one entry, however often it is met.
    if all((s.usb is not None) if place is None else (usb_place(s.usb) != place)
           for s in win._stalled):
        win._stalled = [*win._stalled, Stalled(
            usb if place is not None else None, _name_of(win, usb),
            () if place is not None else tuple(gio_storage.garmin_products_on_usb()))]
        log.info("window: a device stopped responding (its place on USB %s), the banner says "
                 "it until it is gone from there", "known" if place is not None else "not known")
    _close_if_open(win, place)
    show(win)


def look(win) -> None:
    """From the USB poll: those gone from their place are forgotten, and a stall that only a
    work in the background met (gio_storage keeps its place) gets the banner too."""
    left = [s for s in win._stalled if _still_there(s)]
    known = {usb_place(s.usb) for s in left}
    for usb in gio_storage.stalled_places():
        if usb_place(usb) not in known:
            left.append(Stalled(usb, _name_of(win, usb)))
            known.add(usb_place(usb))
            log.info("window: a device stopped responding in a work in the background, the "
                     "banner says it")
    changed = [id(s) for s in left] != [id(s) for s in win._stalled]
    if changed:
        gone = len([s for s in win._stalled if s not in left])
        if gone:
            log.info("window: %d device(s) that stopped responding gone from their place on "
                     "USB", gone)
        win._stalled = left
    for stalled in left:
        _close_if_open(win, usb_place(stalled.usb), unless_busy=True)
    if changed:
        show(win)


def show(win) -> None:
    """The banners of the start page and of the device view, as _stalled has it."""
    text = stalled_text([s.name for s in win._stalled]) if win._stalled else None
    if win.start is not None:
        win.start.set_stalled(text)
    win._update_banner()


@contextmanager
def telling(win, error: BaseException):
    """While a task's failure is told (its on_error, the error dialog): for a stall no error
    dialog, then the banner (note), also when the telling fails."""
    if not isinstance(error, DeviceNotResponding):
        yield
        return
    win._telling_stall = True
    try:
        yield
    finally:
        win._telling_stall = False
        note(win, error)
