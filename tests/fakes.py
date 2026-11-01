"""Fakes shared by the tests (imported as `from fakes import …`, like ptp_fake). Only made-up
data; nothing here reaches a device, the network or the disk of this computer."""

import struct
import threading
from collections import namedtuple
from dataclasses import dataclass

Call =namedtuple("Call", "title fn done failed device in_page button")


class RunNow:
    """The window's run_task (gui/window_tasks.py), run at once: the work (in a thread,
    waited for, with `thread=True`), then done or failed; an error `failed` does not take goes
    to `error`: "raise" (default), "record" (into `errors`) or a function (title, words).
    WindowClosed ends the task quietly; `button` spins during the work. Leaves `calls`,
    `titles` and `written` (writes_to_device works)."""

    def __init__(self, error="raise", thread=False, on_call=None, before_done=None):
        self.error, self.thread = error, thread
        self.on_call, self.before_done = on_call, before_done
        self.calls: list[Call] = []
        self.errors: list[str] = []
        self.written: list[str] = []

    @property
    def titles(self) -> list[str]:
        return [call.title for call in self.calls]

    def __call__(self, title, fn, done=None, failed=None, device=True, in_page=False,
                 button=None):
        # Unlike the window: no check of `busy`, no bar, no pending refresh afterwards.
        call = Call(title, fn, done, failed, device, in_page, button)
        self.calls.append(call)
        if self.on_call is not None:
            self.on_call(call)
        restore = None
        if button is not None:
            from openexpress.gui.window_tasks import show_working

            restore = show_working(button)
        result, raised = [], []

        def work():
            try:
                result.append(fn())
            except Exception as e:  # noqa: BLE001 - as the window's run_task: to `failed`
                raised.append(e)

        if self.thread:
            worker = threading.Thread(target=work)
            worker.start()
            worker.join()
        else:
            work()
        if self.before_done is not None:
            self.before_done()
        if restore is not None:
            restore(True)
        from openexpress.gui.tasks import WindowClosed

        try:
            if raised and isinstance(raised[0], WindowClosed):
                pass  # stopped as the window closed: nothing to tell
            elif raised:
                self._failed(title, raised[0], failed)
            elif done is not None:
                done(result[0])  # an error of done is not caught, as in the window
        finally:
            if getattr(fn, "writes_to_device", False):
                self.written.append(title)

    def _failed(self, title, error, failed) -> None:
        if failed is not None and failed(error):
            return
        if self.error == "raise":
            raise error
        words = str(error) or type(error).__name__
        if self.error == "record":
            self.errors.append(words)
        else:
            self.error(title, words)


class SyncClient:
    """The Garmin Connect account as sync uses it: uploads are noted and answered with
    `statuses` by address (201 otherwise); Connect has the activities in `matches`; the queue
    gives a course for an address with "course" in it; acknowledgements are noted.
    `require_verified` refuses, as the real client does, without a device checked against the
    account (`verified_unit_id`) or for another."""

    def __init__(self, statuses=None, matches=None, messages=None, verified_unit_id=None):
        self.statuses = statuses or {}
        self.matches = matches or {}
        self.messages = messages or []
        self.verified_unit_id = verified_unit_id
        self.uploads = []
        self.acks = []

    def require_verified(self, unit_id=None):
        from openexpress.connect import DeviceNotVerified

        if self.verified_unit_id is None or unit_id not in (None, self.verified_unit_id):
            raise DeviceNotVerified("this device was not checked against the account")

    def activity_matches(self, unit_id, ids):
        return {i: i in self.matches for i in ids}

    def upload_file(self, url, data, *, is_zip, last_file, authenticated):
        from openexpress.connect import UploadResult

        self.uploads.append((url, len(data), last_file))
        return UploadResult(self.statuses.get(url, 201), {}, None, None)

    def poll_location(self, url, delay):
        return 201

    def download_message(self, url, absolute):
        return b"COURSE" if "course" in url else None

    def ack_message(self, mid):
        self.acks.append(mid)


# --- Garmin Connect as a whole sync asks it ------------------------------------------------

ACTIVITY_URL = "https://up.example/activity"
MONITORING_URL = "https://up.example/monitoring"
# The upload settings of the test device (tests/conftest.py): its activities and monitoring.
UPLOAD_SETTINGS = {"unittypename": "test", "datatypes": [
    {"datatypename": "FIT_TYPE_4",
     "uploadlocations": [{"url": ACTIVITY_URL, "requiresauthentication": True}]},
    {"datatypename": "FIT_TYPE_32",
     "uploadlocations": [{"url": MONITORING_URL, "requiresauthentication": True}]},
]}
OPT_IN = {"useroption": "opt-in", "sourcetype": "CUSTOMER", "consentenforcementstate": "HARD"}
COURSE = {"messageid": 5, "devicexmldatatype": "FIT_TYPE_6",
          "metadata": {"messageurl": "course/5", "messagename": "A course"}}
# A type the test device does not declare (it takes courses only).
NOT_TAKEN = {"messageid": 6, "devicexmldatatype": "FIT_TYPE_99",
             "metadata": {"messageurl": "other/6", "messagename": "Something"}}


class SyncAccount(SyncClient):
    """Garmin Connect, logged in, as a whole sync asks it, both ways: the account lists the
    test device; `consent` False: no upload consent; the upload settings of
    UPLOAD_SETTINGS; the queue of `messages`; the acknowledgement of each message ID of
    `ack_fails` fails. `asked`: what was asked of it, in order."""

    UNIT = 1234567890  # the test device (tests/conftest.py)

    def __init__(self, *, consent=True, ack_fails=(), **kw):
        super().__init__(**kw)
        self.auth = object()
        self.consent_given = consent
        self.ack_fails = set(ack_fails)
        self.asked = []

    def account_devices(self, fresh=False):
        self.asked.append("account")
        return [{"unitid": self.UNIT}]

    def consent(self, consent_type):
        self.asked.append("consent")
        return OPT_IN if self.consent_given else {**OPT_IN, "useroption": "opt-out"}

    def device_sync_preference(self):
        self.asked.append("device sync")
        return {"key": "account.deviceSync", "value": "true"}

    def profile_country(self, fresh=False):
        return "PL"

    def upload_settings(self, unit_id):
        self.asked.append("upload settings")
        return UPLOAD_SETTINGS

    def activity_matches(self, unit_id, ids):
        self.asked.append("matches")
        return super().activity_matches(unit_id, ids)

    def upload_file(self, url, data, **kw):
        self.asked.append("upload")
        return super().upload_file(url, data, **kw)

    def device_messages(self, unit_id):
        self.asked.append("queue")
        return self.messages

    def download_message(self, url, absolute):
        self.asked.append("download")
        return super().download_message(url, absolute)

    def ack_message(self, mid):
        self.asked.append("acknowledge")
        if mid in self.ack_fails:
            from openexpress.connect import ApiError

            raise ApiError("the queue did not answer", 503)
        super().ack_message(mid)


class DriveAccount(SyncAccount):
    """Garmin Connect as a sync asks it (the account lists `devices`, by default the test
    device), and Garmin's update server answering unit-info with `answer` (an exception:
    raised). unit-info goes through the kept answers as the real client's does; `asked` notes
    each question that reached a server."""

    def __init__(self, answer, devices=None, **kw):
        from openexpress.settings import Settings

        super().__init__(verified_unit_id=None, **kw)
        self.settings = Settings()
        self.answer = answer
        self.devices = [{"unitid": self.UNIT}] if devices is None else devices

    def unit_info(self, unit_id, part_number):
        from openexpress.connect import GarminClient

        return GarminClient.unit_info(self, unit_id, part_number)

    def account_devices(self, fresh=False):
        self.asked.append("account, fresh" if fresh else "account")
        return self.devices

    def _omt(self, method, path, what, quiet=False, **kw):
        self.asked.append("unit-info")
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def drive_session(root, account, storage_class=None):
    """A session on the made-up device in `root` connected as a USB drive (UmsStorage, or
    `storage_class`), as service.open_session makes it."""
    from openexpress import service
    from openexpress.device.gio_storage import GarminUsb
    from openexpress.device.storage import UmsStorage
    from openexpress.device.xmldevice import parse
    from openexpress.settings import Settings

    storage = (storage_class or UmsStorage)(
        root, root.as_uri() + "/", usb=GarminUsb("4f42", 1, 9, serial="MADE-UP-SERIAL-8"))
    device = parse((root / "GARMIN" / "GarminDevice.xml").read_bytes())
    return service.DeviceSession(storage, device, Settings(), account)


def other_bytes_drive():
    """A kind of drive (LocalStorage) that keeps each file written at its size but with other
    bytes (zeros), as a drive whose medium lost what was written while its folder kept the
    size: only reading the file back tells."""
    from openexpress.device.storage import LocalStorage

    class OtherBytes(LocalStorage):
        def _replace(self, real_path, chunks, progress=None, total=0):
            super()._replace(real_path, chunks, progress, total)
            target = self._p(real_path)
            target.write_bytes(bytes(target.stat().st_size))

    return OtherBytes


def stale_sizes(cut, *, still_written=(), fails=None):
    """A kind of storage (LocalStorage) of a device over MTP as gvfs shows it, keeping the size
    a file had when it was first looked at: each file of `cut` (its path from the device's
    root, in any case, and a number of bytes) reads cut to that size until `refresh`, after
    which it reads whole, unless it is in `still_written` too (the device still writes it).
    `refreshes` keeps the progress each refresh was given; `fails`: what a refresh raises
    instead (the device not mounted again)."""
    from openexpress.device.storage import LocalStorage

    still = {p.casefold() for p in still_written}

    class StaleSizes(LocalStorage):
        def __init__(self, root):
            super().__init__(root)
            self.refreshes = []

        def _read(self, real_path):
            data = super()._read(real_path)
            for path, size in cut.items():
                key = path.casefold()
                if key == real_path.casefold() and (not self.refreshes or key in still):
                    return data[:size]
            return data

        def refresh(self, progress=None):
            self.refreshes.append(progress)
            if fails is not None:
                raise fails
            return True

    return StaleSizes

# --- what the window writes of the devices before it draws their tiles ------------------


def login(saved=True):
    """A login saved, as `openexpress login` saves it (made up), and its version
    (store.stamp); `saved` False: none saved (logged out)."""
    from openexpress.auth import store

    if not saved:
        store.delete()
        return None
    if store.stamp() is None:
        store.save(store.ConnectAuth("token", "secret", account={"username": "made-up"}))
    return store.stamp()


def noted(summaries=(), account=None):
    """What the window writes of these connected devices before it draws their tiles
    (tile_facts): each one seen by its detection, what the account's list says of them
    (`account`, read with the login saved now; None: not read) and each count it holds
    (summary.to_sync)."""
    from openexpress import known_devices, tile_facts

    for s in summaries:
        if s.unit_id:
            known_devices.seen(s.unit_id, s.description, s.part_number, s.software_version,
                               s.found.kind)
    if account is not None:
        tile_facts.note_account(account)
    for s in summaries:
        tile_facts.note_count(getattr(s, "to_sync", None))


# --- sync records, as a sync would leave them ----------------------------------------------


def record_sync(unit_id, uploaded, downloaded, skipped_known, errors, lines):
    """A last sync of this device recorded (last_sync.json, as service.save_last_sync writes
    it after a sync): the numbers and the steps (`lines`, as SyncSummary.lines has them)."""
    from openexpress import service

    service.save_last_sync(unit_id, service.SyncSummary(
        uploaded=uploaded, skipped_known=skipped_known, downloaded=downloaded,
        errors=list(errors), lines=list(lines)))


def step_words(lines):
    """The steps of a sync record in words, as the window shows them (service.describe_steps),
    without whether each is a warning."""
    from openexpress import service

    return [text for text, _warning in service.describe_steps(lines)]


# --- the window's own methods on a stand-in ------------------------------------------------


def start_section(start, key):
    """A section of the start page (gui.start.StartPage) by its key, as devicelist names the
    sections ("connected", "remembered", "on-account"): its title, grid and list."""
    return start._sections[key]


def row_words(row):
    """The title and the words under it that a row of the start page's list (gui.start.
    DeviceRow) shows: its labels "title" and "subtitle", "" for one it has not."""
    from gi.repository import Gtk

    def labels(widget):
        child = widget.get_first_child()
        while child is not None:
            if isinstance(child, Gtk.Label):
                yield child
            yield from labels(child)
            child = child.get_next_sibling()

    words = {"title": "", "subtitle": ""}
    for label in labels(row):
        for kind in words:
            if not words[kind] and label.has_css_class(kind):
                words[kind] = label.get_label()
    return words["title"], words["subtitle"]


def window(**changes):
    """A stand-in for the window without GTK: every attribute the real window has, with the
    value it has before anything is shown (MainWindow._init_state), then `changes`. None of
    the window's methods: a test gives those it needs, or binds them with window_methods."""
    import types

    from openexpress.gui.app import MainWindow

    win = types.SimpleNamespace()
    MainWindow._init_state(win)
    for name, value in changes.items():
        setattr(win, name, value)
    return win


def window_methods(win, names):
    """Returns the stand-in window `win` with these methods of MainWindow bound to it, each
    looked up along MainWindow's MRO as the window finds it (in app.py or a mixin), so a method
    moved to a mixin stays in the stand-in. A name no class of openExpress defines (renamed,
    removed, or GTK's only) fails at once, naming it."""
    import types

    from openexpress.gui.app import MainWindow

    missing = []
    for name in names:
        owner = next((cls for cls in MainWindow.__mro__ if name in vars(cls)), None)
        if owner is None or not owner.__module__.startswith("openexpress."):
            missing.append(name)
            continue
        member = vars(owner)[name]
        if isinstance(member, staticmethod):
            setattr(win, name, member.__func__)
        elif isinstance(member, classmethod):
            setattr(win, name, types.MethodType(member.__func__, MainWindow))
        else:
            setattr(win, name, types.MethodType(member, win))
    assert not missing, ("MainWindow has no method " + ", ".join(missing)
                         + " (renamed or removed?): change the stand-in to what the window has")
    return win


# --- a name of the window replaced where the window looks it up -----------------------------


def replace_in_window(monkeypatch, name, value):
    """Replaces `name` (e.g. "eject" or "Adw") in every module of openexpress.gui that holds
    it, never in gui.app alone (test_dead_patches), and returns those modules' names. Fails,
    replacing nothing, when no module holds the name or the modules hold different objects
    under it (some code would not see the replacement). Tests use the fixture in_the_window;
    a helper with `monkeypatch` calls this."""
    import importlib
    import pkgutil

    import openexpress.gui as gui

    modules = [importlib.import_module(f"openexpress.gui.{m.name}")
               for m in pkgutil.iter_modules(gui.__path__)]
    holders = [m for m in modules if name in vars(m)]
    assert holders, f"no module of the window holds {name!r}"
    app = importlib.import_module("openexpress.gui.app")
    original = vars(app)[name] if name in vars(app) else vars(holders[0])[name]
    others = sorted(m.__name__ for m in holders if vars(m)[name] is not original)
    assert not others, (
        f"{name!r} is another object in {', '.join(others)} than in the other modules of "
        "the window: the code there would not see the replacement")
    for module in holders:
        monkeypatch.setattr(module, name, value)
    return [module.__name__ for module in holders]


# --- helpers several test modules use ---------------------------------------------------


def page_window(key):
    """A page of the real kind in a window that is never shown, and a stand-in for the main
    window that loads it the way MainWindow does. A task runs at once, in the order run_task
    keeps: busy on, the work, busy off, then the page is rebuilt."""
    import types

    from gi.repository import Gtk

    from openexpress.gui.app import MainWindow
    from openexpress.gui.device_page import Section
    from openexpress.gui.window_tasks import still_in_window

    section = Section(key, key.title(), "x-symbolic", "Loading…")
    toplevel = Gtk.Window()
    toplevel.set_child(section.stack)

    run_task = RunNow(on_call=lambda call: win.set_busy(True),
                      before_done=lambda: win.set_busy(False))

    def set_busy(busy):
        win.busy = busy
        win._action_buttons = still_in_window(win._action_buttons)

    win = window(session=types.SimpleNamespace(), sections={key: section},
                 busy=False, _action_buttons=[], _retry_sources={},
                 run_task=run_task, set_busy=set_busy, toplevel=toplevel)
    for name in ("_load", "_button", "_trash"):
        setattr(win, name, types.MethodType(getattr(MainWindow, name), win))
    return win, section


# The view of a remembered device and its pictures (once picked by name: "picture",
# "remembered"), found along the whole MRO (window_methods).
REMEMBERED_METHODS = ("_show_remembered", "_show_account", "_fill_account", "_last_sync_text",
                      "_fill_remembered", "_load_tile_pictures", "_on_remembered_page",
                      "_redraw_remembered", "_refresh_remembered", "_refresh_remembered_texts",
                      "_show_device_picture", "_show_page_picture", "_tile_picture_done")


def remembered_device(category="watch", part="006-B0000-00"):
    """A made-up device remembered an hour ago."""
    import time

    from openexpress.known_devices import KnownDevice

    now = time.time()
    return KnownDevice(unit_id=1234567890, description="Test watch", part_number=part,
                       software_version="1.00", kind="mtp", first_seen=now - 86400,
                       last_seen=now - 3600, category=category)


def remembered_window(textures=None):
    """The parts of the window that open the view, with the real view in it; background work
    runs at once."""
    import types

    from openexpress.gui.start import RememberedPage

    pushed = []
    win = window(
        remembered=RememberedPage(), navigation=types.SimpleNamespace(push=pushed.append),
        pushed=pushed, _device_textures=dict(textures or {}), _pictures_asked=set(),
        _account=None, _on_start_page=lambda: True,
        in_background=lambda fn, on_done, on_error=None: on_done(fn()))
    return window_methods(win, REMEMBERED_METHODS)


RTL515_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Device xmlns="http://www.garmin.com/xmlschemas/GarminDevice/v2">
 <Model><PartNumber>006-B3592-03</PartNumber><SoftwareVersion>336</SoftwareVersion>
  <Description>Varia RTL515</Description></Model>
 <Id>3000000003</Id>
 <MassStorageMode>
  <UpdateFile><PartNumber>006-B3592-03</PartNumber>
   <Version><Major>3</Major><Minor>36</Minor></Version>
   <Path>GARMIN/</Path><FileName>GUPDATE.GCD</FileName></UpdateFile>
  <UpdateFile><PartNumber>006-B3593-06</PartNumber>
   <Version><Major>3</Major><Minor>27</Minor></Version>
   <Path>GARMIN/REMOTESW/</Path><FileName>6B359306.GCD</FileName></UpdateFile>
 </MassStorageMode>
</Device>
"""


class UpdateServer:
    """Stands in for the HTTP session of GarminClient: records each request, answers with JSON."""

    def __init__(self, answer):
        self.answer, self.sent = answer, []

    def request(self, method, url, **kw):
        import json

        import requests

        self.sent.append((method, url, kw.get("params"), kw.get("json")))
        resp = requests.Response()
        resp.status_code, resp.url = 200, url
        resp._content = json.dumps(self.answer).encode()
        resp.headers["Content-Type"] = "application/json"
        return resp


DEVICES_PATH = "device-service/deviceregistration/devices"
DEVICE_UNIT = 1234567890  # the test device (conftest.DEVICE_XML)
OTHER_UNIT = 4222333444  # another device of the account


def response(status=200, body=b"[]"):
    import json

    import requests

    r = requests.Response()
    r.status_code = status
    r._content = body if isinstance(body, bytes) else json.dumps(body).encode()
    return r


class RecordingSession:
    """Stands in for requests.Session: records every request, answers from `routes`."""

    def __init__(self, devices=None, **routes):
        self.routes = {DEVICES_PATH: response(body=devices if devices is not None else [])}
        self.routes.update(routes)
        self.handlers = {}  # url part -> function(method, request kwargs) -> response
        self.sent = []

    def request(self, method, url, **kw):
        self.sent.append({"method": method, "url": url, "headers": kw.get("headers") or {},
                          "body": repr((kw.get("data"), kw.get("json"), kw.get("files")))})
        for part, handler in self.handlers.items():
            if part in url:
                return handler(method, kw)
        for part, answer in self.routes.items():
            if part in url:
                if isinstance(answer, Exception):
                    raise answer
                return answer() if callable(answer) else answer
        return response(404, b"")

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def signed_for(self, unit_id):
        """Token-signed requests that name this watch."""
        return [r for r in self.sent
                if "Authorization" in r["headers"] and str(unit_id) in r["url"] + r["body"]]

    def paths(self):
        return [r["url"].split("garmin.com/")[-1].split("?")[0] for r in self.sent]


def another_account() -> None:
    """The next client is of another Garmin Connect account: what the one before was told of
    its account does not hold for it (in the program another account is another login, so
    another key of the kept answers; in a test the login stays the same)."""
    from openexpress import answers

    answers.ANSWERS.forget(answers.ACCOUNT_KINDS)


def make_client(devices=None, auth=True, **routes):
    """A client of a Garmin Connect of its own (RecordingSession)."""
    from openexpress.auth.store import ConnectAuth
    from openexpress.connect import GarminClient
    from openexpress.settings import Consumer, Settings

    return GarminClient(Settings(), Consumer("ck", "cs"),
                        ConnectAuth("t", "ts") if auth else None,
                        RecordingSession(devices, **routes))


# Made-up FIT files. The base types of the FIT protocol, by the byte of a field definition:
# the struct format of one value and the value that means "invalid" (written here apart from
# the program's own table, openexpress/fit.py).
FIT_BASE_TYPES = {
    0x00: ("B", 0xFF), 0x01: ("b", 0x7F), 0x02: ("B", 0xFF), 0x83: ("h", 0x7FFF),
    0x84: ("H", 0xFFFF), 0x85: ("i", 0x7FFFFFFF), 0x86: ("I", 0xFFFFFFFF), 0x07: ("s", None),
    0x88: ("f", float("nan")), 0x89: ("d", float("nan")), 0x0A: ("B", 0), 0x8B: ("H", 0),
    0x8C: ("I", 0), 0x0D: ("B", 0xFF), 0x8E: ("q", 0x7FFFFFFFFFFFFFFF),
    0x8F: ("Q", 0xFFFFFFFFFFFFFFFF), 0x90: ("Q", 0),
}


@dataclass(frozen=True)
class FitDefinition:
    """A definition message: its local type (0–15), the global message number, the fields as
    (field number, base type) or (field number, base type, size) – a string or an array needs
    its size – and developer fields as (field number, size, developer data index)."""

    local: int
    message: int
    fields: tuple = ()
    big_endian: bool = False
    developer: tuple = ()


@dataclass(frozen=True)
class FitData:
    """A data message of the definition last given for `local`: one value for each of its
    fields (None: the invalid value of the field's base type; bytes: written as they are; a
    tuple: an array). `developer`: the bytes of its developer fields (zeros when None).
    `time_offset` (0–31): a compressed-timestamp header instead of the normal one (local
    types 0–3 only)."""

    local: int
    values: tuple = ()
    developer: bytes | None = None
    time_offset: int | None = None


def _fit_size(field: tuple) -> tuple[int, int, int]:
    """(number, base type, size) of a field given as (number, base type[, size])."""
    if len(field) > 2:
        return field[0], field[1], field[2]
    return field[0], field[1], struct.calcsize(FIT_BASE_TYPES[field[1]][0])


def _fit_value(value, base_type: int, size: int, order: str) -> bytes:
    if isinstance(value, bytes):
        assert len(value) == size, f"{len(value)} bytes for a field of {size}"
        return value
    fmt, invalid = FIT_BASE_TYPES[base_type]
    if fmt == "s":
        raw = (value or "").encode("utf-8").ljust(size, b"\0")
    else:
        count = size // struct.calcsize(fmt)
        values = value if isinstance(value, tuple) else (value,) * count
        raw = b"".join(struct.pack(order + fmt, invalid if v is None else v) for v in values)
    assert len(raw) == size, f"{len(raw)} bytes for a field of {size}"
    return raw


def fit_file(*messages, header_size: int = 14, cut: int | None = None,
             bad_crc: bool = False) -> bytes:
    """A made-up FIT file of these messages (FitDefinition and FitData, in order; bytes are
    written as they are, e.g. a message no definition explains), its header of 14 or 12 bytes
    and its CRC right. `cut`: only its first `cut` bytes, as a file the device was still
    writing; `bad_crc`: the CRC at its end wrong."""
    from conftest import fit_crc

    defined = {}
    body = b""
    for m in messages:
        if isinstance(m, bytes):
            body += m
        elif isinstance(m, FitDefinition):
            order = ">" if m.big_endian else "<"
            fields = [_fit_size(f) for f in m.fields]
            body += bytes([0x40 | (0x20 if m.developer else 0) | m.local, 0,
                           1 if m.big_endian else 0])
            body += struct.pack(order + "HB", m.message, len(fields))
            body += b"".join(bytes([num, size, base]) for num, base, size in fields)
            if m.developer:
                body += bytes([len(m.developer)])
                body += b"".join(bytes(f) for f in m.developer)
            defined[m.local] = (m, fields)
        else:
            definition, fields = defined[m.local]
            assert len(m.values) == len(fields), "one value for each field"
            if m.time_offset is None:
                body += bytes([m.local])
            else:
                body += bytes([0x80 | (m.local << 5) | m.time_offset])
            order = ">" if definition.big_endian else "<"
            body += b"".join(_fit_value(v, base, size, order)
                             for v, (_num, base, size) in zip(m.values, fields, strict=True))
            dev_size = sum(f[1] for f in definition.developer)
            body += m.developer if m.developer is not None else bytes(dev_size)
    if header_size == 14:
        header = struct.pack("<BBHI4sH", 14, 0x20, 2132, len(body), b".FIT", 0)
    else:
        header = struct.pack("<BBHI4s", 12, 0x10, 2100, len(body), b".FIT")
    crc = fit_crc(header + body) ^ (0xFFFF if bad_crc else 0)
    data = header + body + struct.pack("<H", crc)
    return data if cut is None else data[:cut]


def fit_activity(start: int, *, sport: int = 1, timer_ms: int | None = 3_600_000,
                 distance_cm: int | None = 1_000_000, ascent: int | None = 100,
                 records: int = 1, position: tuple[int, int] | None = None, **options) -> bytes:
    """A made-up activity that starts at `start` (a time of the FIT protocol): its file_id
    created then, `records` records a second apart (at `position`, in semicircles, when given),
    one session of `sport` with these totals (None: the field's invalid value). `options`: as
    fit_file's (cut, bad_crc)."""
    if position is None:
        record_fields, at = ((253, 0x86),), ()
    else:
        record_fields, at = ((253, 0x86), (0, 0x85), (1, 0x85)), position
    return fit_file(
        FitDefinition(0, 0, ((0, 0x00), (4, 0x86))), FitData(0, (4, start)),
        FitDefinition(1, 20, record_fields),
        *(FitData(1, (start + n, *at)) for n in range(records)),
        FitDefinition(2, 18, ((2, 0x86), (5, 0x00), (8, 0x86), (9, 0x86), (22, 0x84))),
        FitData(2, (start, sport, timer_ms, distance_cm, ascent)), **options)
