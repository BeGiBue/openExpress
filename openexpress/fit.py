"""Minimal FIT reader, written from the public FIT protocol: the data messages of a file with
their values by base type, whether a file is whole, and the messages the program needs (the
creation time in file_id, from which Garmin Connect's activity identifier for duplicate checks
comes, and TrueUp's callback).
"""

from __future__ import annotations

import math
import struct
from collections.abc import Collection, Iterator
from dataclasses import dataclass, field
from enum import Enum

from openexpress.i18n import _

FIT_EPOCH_OFFSET = 631065600  # 1989-12-31T00:00:00Z as Unix time

_MESG_FILE_ID = 0
_FIELD_TIME_CREATED = 4
# FIT profile: session (one part of an activity; a multisport activity has one per sport)
_MESG_SESSION = 18
_SESSION_START_TIME = 2
_SESSION_START_LAT, _SESSION_START_LONG = 3, 4  # semicircles
_SESSION_SPORT = 5
_SESSION_TIMER_TIME = 8  # milliseconds, pauses left out
_SESSION_DISTANCE = 9  # centimetres
_SESSION_ASCENT = 22  # metres
# FIT profile: record (one point of an activity)
_MESG_RECORD = 20
_RECORD_LAT, _RECORD_LONG = 0, 1  # semicircles
_RECORD_ALTITUDE, _RECORD_ENHANCED_ALTITUDE = 2, 78  # metres: value / 5 - 500
# FIT profile: the sport "multisport"
SPORT_MULTISPORT = 18
# The field number of a message's time (date_time) in every message of the FIT profile.
FIELD_TIMESTAMP = 253

# The base types of the FIT protocol by their number (the lowest five bits of the base type
# of a field definition): the struct format of one value and the value that means "invalid"
# (None for a string, which is invalid when empty, and for the floats, invalid as NaN).
_BASE_TYPES = {
    0: ("B", 0xFF),                 # enum
    1: ("b", 0x7F),                 # sint8
    2: ("B", 0xFF),                 # uint8
    3: ("h", 0x7FFF),               # sint16
    4: ("H", 0xFFFF),               # uint16
    5: ("i", 0x7FFFFFFF),           # sint32
    6: ("I", 0xFFFFFFFF),           # uint32
    7: ("s", None),                 # string: UTF-8, ends at its first zero byte
    8: ("f", None),                 # float32
    9: ("d", None),                 # float64
    10: ("B", 0),                   # uint8z
    11: ("H", 0),                   # uint16z
    12: ("I", 0),                   # uint32z
    13: ("B", 0xFF),                # byte
    14: ("q", 0x7FFFFFFFFFFFFFFF),  # sint64
    15: ("Q", 0xFFFFFFFFFFFFFFFF),  # uint64
    16: ("Q", 0),                   # uint64z
}
_BASE_TYPE_NUMBER = 0x1F

Value = int | float | str | None


class FitError(Exception):
    pass


@dataclass
class FileId:
    time_created: int | None = None


@dataclass
class _Def:
    big_endian: bool
    global_num: int
    fields: list[tuple[int, int, int]]  # (field number, size, base type)
    size: int  # of its data messages, developer fields included
    # Its timestamp field, if it has one: (where it starts in a data message, size, base type).
    time_field: tuple[int, int, int] | None


def _read_uint(raw: bytes, big_endian: bool) -> int | None:
    if len(raw) not in (1, 2, 4):
        return None
    fmt = {1: "B", 2: "H", 4: "I"}[len(raw)]
    value = struct.unpack((">" if big_endian else "<") + fmt, raw)[0]
    invalid = (1 << (8 * len(raw))) - 1
    return None if value == invalid else value


def _value(raw: bytes, size: int, base_type: int, big_endian: bool) -> Value:
    """The value of a field by its base type; None when it is the type's invalid value, an
    array, of a size that does not fit its type, or cut off by the end of the file. A base
    type the protocol does not define is read as an unsigned integer of its size."""
    if len(raw) < size:
        return None
    kind = _BASE_TYPES.get(base_type & _BASE_TYPE_NUMBER)
    if kind is None:
        return _read_uint(raw, big_endian)
    fmt, invalid = kind
    if fmt == "s":
        return raw.split(b"\0", 1)[0].decode("utf-8", "replace") or None
    if struct.calcsize(fmt) != size:
        return None
    value = struct.unpack((">" if big_endian else "<") + fmt, raw)[0]
    if fmt in ("f", "d"):
        return None if math.isnan(value) else value
    return None if value == invalid else value


def iter_messages(data: bytes, wanted: Collection[int] | None = None):
    """Yields (global message number, {field number: value}) for each data message, each value
    by its base type (_value). A message after a compressed-timestamp header has the time that
    header gives it as its timestamp field (FIELD_TIMESTAMP), once a time came before it.
    `wanted`: only the messages of these global numbers; the others are stepped over without
    reading them, but for their time, which a compressed-timestamp header counts from.

    Malformed or truncated input raises FitError (never IndexError/struct.error).
    """
    try:
        yield from _iter_messages(data, wanted)
    except (IndexError, struct.error) as e:
        raise FitError(_("Damaged FIT file ({error})").format(error=e)) from e


def _check_header(data: bytes) -> int:
    """The size of the header of a FIT file; FitError when `data` is no FIT file."""
    if len(data) < 12:
        raise FitError(_("File too short"))
    header_size = data[0]
    if header_size not in (12, 14) or data[8:12] != b".FIT":
        raise FitError(_("Not a FIT file"))
    return header_size


def _iter_messages(data: bytes, wanted: Collection[int] | None):
    header_size = _check_header(data)
    data_size = struct.unpack_from("<I", data, 4)[0]
    end = min(len(data), header_size + data_size)
    pos = header_size
    defs: dict[int, _Def] = {}
    last_time: int | None = None  # the time of the last message that had one
    while pos < end:
        hdr = data[pos]
        pos += 1
        offset = None
        if hdr & 0x80:  # compressed timestamp: a regular data message
            local = (hdr >> 5) & 0x03
            offset = hdr & 0x1F
            is_def = False
            has_dev = False
        else:
            local = hdr & 0x0F
            is_def = bool(hdr & 0x40)
            has_dev = bool(hdr & 0x20)
        if is_def:
            if pos + 5 > end:
                break
            big_endian = data[pos + 1] == 1
            global_num = struct.unpack_from(">H" if big_endian else "<H", data, pos + 2)[0]
            nfields = data[pos + 4]
            pos += 5
            if pos + 3 * nfields > end:
                raise FitError(_("Truncated FIT definition message"))
            fields = []
            time_field = None
            size = 0
            for _field in range(nfields):
                num, field_size, base_type = data[pos], data[pos + 1], data[pos + 2]
                if num == FIELD_TIMESTAMP and time_field is None:
                    time_field = (size, field_size, base_type)
                fields.append((num, field_size, base_type))
                size += field_size
                pos += 3
            if has_dev:
                if pos + 1 > end:
                    raise FitError(_("Truncated FIT definition message"))
                ndev = data[pos]
                pos += 1
                if pos + 3 * ndev > end:
                    raise FitError(_("Truncated FIT definition message"))
                for _dev in range(ndev):
                    size += data[pos + 1]
                    pos += 3
            defs[local] = _Def(big_endian, global_num, fields, size, time_field)
            continue
        d = defs.get(local)
        if d is None:
            raise FitError(_("Data message without a definition (local type {local})")
                           .format(local=local))
        if offset is not None:
            # The offset takes the place of the lowest five bits of the time before it; one
            # smaller than them is in the next 32 seconds.
            if last_time is not None:
                last_time += (offset - last_time) & 0x1F
        elif d.time_field is not None:
            start, field_size, base_type = d.time_field
            time = _value(data[pos + start : pos + start + field_size], field_size, base_type,
                          d.big_endian)
            if isinstance(time, int):
                last_time = time
        if wanted is not None and d.global_num not in wanted:
            pos += d.size
            continue
        values: dict[int, Value] = {}
        p = pos
        for num, field_size, base_type in d.fields:
            values[num] = _value(data[p : p + field_size], field_size, base_type, d.big_endian)
            p += field_size
        if offset is not None and last_time is not None:
            values[FIELD_TIMESTAMP] = last_time
        yield d.global_num, values
        pos += d.size


# CRC-16 of the FIT protocol, four bits at a time.
_CRC_TABLE = (0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
              0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400)


def crc16(data: bytes, crc: int = 0) -> int:
    for byte in data:
        tmp = _CRC_TABLE[crc & 0xF]
        crc = ((crc >> 4) & 0x0FFF) ^ tmp ^ _CRC_TABLE[byte & 0xF]
        tmp = _CRC_TABLE[crc & 0xF]
        crc = ((crc >> 4) & 0x0FFF) ^ tmp ^ _CRC_TABLE[(byte >> 4) & 0xF]
    return crc


class Problem(Enum):
    """Why data are not a whole FIT file (check)."""
    NO_HEADER = "no FIT header"
    AFTER_THE_END = "data after the end that are no FIT file"
    CUT_SHORT = "cut short"
    CRC = "the CRC does not match"


@dataclass(frozen=True)
class NotWhole:
    """What check found: the problem, the bytes read, and the bytes the header declares (cut
    short: header, data and CRC) or those after the whole FIT data (after the end)."""

    problem: Problem
    read: int
    declared: int = 0
    after: int = 0

    def words(self) -> str:
        """For the log: sizes, never the content."""
        if self.problem is Problem.NO_HEADER:
            return f"no FIT header ({self.read} B read)"
        if self.problem is Problem.AFTER_THE_END:
            return f"{self.after} B after the whole FIT data are no FIT file"
        if self.problem is Problem.CUT_SHORT:
            return f"{self.read} B read, {self.declared} B declared"
        return f"the CRC does not match ({self.read} B read)"


def check(data: bytes) -> NotWhole | None:
    """Why `data` is not a whole FIT file, or None when it is: every part (a file may chain
    several) has a header of 12 or 14 bytes with ".FIT", the size its header declares (header,
    data and the CRC of 2 bytes) and that CRC; zeros after the last part are padding. Cut
    short: a header declares more bytes than were read, as when the device was still writing
    the file; else no header, data after the end that are no FIT file, or a CRC that does not
    match."""
    pos = 0
    while True:
        if pos and not any(data[pos:]):
            return None  # zeros after whole FIT data: padding, nothing cut short
        if len(data) - pos < 12 or data[pos] not in (12, 14) or data[pos + 8:pos + 12] != b".FIT":
            if pos == 0:
                return NotWhole(Problem.NO_HEADER, len(data))
            return NotWhole(Problem.AFTER_THE_END, len(data), after=len(data) - pos)
        header = data[pos]
        (size,) = struct.unpack_from("<I", data, pos + 4)
        end = pos + header + size + 2
        if end > len(data):
            return NotWhole(Problem.CUT_SHORT, len(data), declared=end)
        (crc,) = struct.unpack_from("<H", data, end - 2)
        if crc16(data[pos:end - 2]) != crc:
            return NotWhole(Problem.CRC, len(data))
        if end == len(data):
            return None
        pos = end


def not_whole(data: bytes) -> tuple[bool, str] | None:
    """Why `data` is not a whole FIT file (check), as (cut short, the words for the log), or
    None when it is."""
    found = check(data)
    return None if found is None else (found.problem is Problem.CUT_SHORT, found.words())


def incompleteness(data: bytes) -> str | None:
    """Why `data` is not a whole FIT file (not_whole), for the log; None when it is."""
    found = not_whole(data)
    return found[1] if found else None


def find_message(data: bytes, global_num: int) -> dict[int, Value] | None:
    return next((v for g, v in iter_messages(data) if g == global_num), None)


def _whole_number(value: Value) -> int | None:
    """A time or a count of a field: only an integer (a field of another base type: None)."""
    return value if isinstance(value, int) else None


def parse_file_id(data: bytes) -> FileId:
    v = find_message(data, _MESG_FILE_ID)
    if v is None:
        raise FitError(_("No file_id message"))
    return FileId(time_created=_whole_number(v.get(_FIELD_TIME_CREATED)))


MESG_CALLBACK_DELAY = 197  # Garmin-internal message used by TrueUp


def true_up_time(data: bytes) -> int | None:
    """Unix time at which Connect asks the client to check back (TrueUp)."""
    v = find_message(data, MESG_CALLBACK_DELAY)
    t = _whole_number(v.get(0)) if v else None
    return None if t is None else t + FIT_EPOCH_OFFSET


class FileState(Enum):
    """How a FIT file is, as not_whole finds it (a file that is no FIT file: FitError)."""
    WHOLE = "whole"
    STILL_BEING_WRITTEN = "still being written"  # cut short: the device was writing it
    DAMAGED = "damaged"  # a CRC that does not match, or data that cannot be read


@dataclass(frozen=True)
class ActivitySummary:
    """What an activity file says of itself (summary). Times are Unix times; None: not said."""

    state: FileState
    created: int | None = None  # file_id's time_created
    start: int | None = None  # the start of its first session
    sport: int | None = None  # the FIT sport of its sessions; several: SPORT_MULTISPORT
    timer_time: float | None = None  # seconds, pauses left out
    distance: float | None = None  # metres
    ascent: int | None = None  # metres
    has_positions: bool = False  # a GPX of it can be made


def _unix_time(value: Value) -> int | None:
    time = _whole_number(value)
    return None if time is None else time + FIT_EPOCH_OFFSET


def _created(data: bytes) -> int | None:
    """The creation time in the first file_id, from as much of the file as reads."""
    try:
        for _num, values in iter_messages(data, wanted=(_MESG_FILE_ID,)):
            return _unix_time(values.get(_FIELD_TIME_CREATED))
    except FitError:
        pass
    return None


def _total(sessions: list[dict[int, Value]], number: int, scale: int = 1) -> float | int | None:
    """The sum of a field over the sessions that give it; None when none does."""
    known = [n for n in (_whole_number(s.get(number)) for s in sessions) if n is not None]
    if not known:
        return None
    return sum(known) / scale if scale != 1 else sum(known)


def _has_position(values: dict[int, Value], lat: int, long: int) -> bool:
    return all(_whole_number(values.get(number)) is not None for number in (lat, long))


def _a_record_has_a_position(data: bytes) -> bool:
    """Whether a record has a position; the search stops at the first that has one."""
    try:
        return any(_has_position(values, _RECORD_LAT, _RECORD_LONG)
                   for _num, values in iter_messages(data, wanted=(_MESG_RECORD,)))
    except FitError:
        return False


def summary(data: bytes) -> ActivitySummary:
    """What the activity file `data` says of itself. Of a file the device was still writing
    (not_whole: cut short) only when it was created; of a damaged one what can be read up to
    where it breaks off; of a file without a session only when it was created. Positions: a
    session's start position, else the first record that has one. FitError for what is no FIT
    file, as parse_file_id."""
    _check_header(data)
    found = not_whole(data)
    if found is not None and found[0]:
        return ActivitySummary(FileState.STILL_BEING_WRITTEN, created=_created(data))
    state = FileState.WHOLE if found is None else FileState.DAMAGED
    created = None
    sessions: list[dict[int, Value]] = []
    try:
        for num, values in iter_messages(data, wanted=(_MESG_FILE_ID, _MESG_SESSION)):
            if num == _MESG_SESSION:
                sessions.append(values)
            elif created is None:
                created = _unix_time(values.get(_FIELD_TIME_CREATED))
    except FitError:
        state = FileState.DAMAGED
    if not sessions:
        return ActivitySummary(state, created=created)
    sports = {_whole_number(s.get(_SESSION_SPORT)) for s in sessions} - {None}
    sport = None
    if len(sports) == 1:
        sport = sports.pop()
    elif sports:
        sport = SPORT_MULTISPORT
    has_positions = (any(_has_position(s, _SESSION_START_LAT, _SESSION_START_LONG)
                         for s in sessions)
                     or _a_record_has_a_position(data))
    return ActivitySummary(
        state, created=created, start=_unix_time(sessions[0].get(_SESSION_START_TIME)),
        sport=sport, timer_time=_total(sessions, _SESSION_TIMER_TIME, 1000),
        distance=_total(sessions, _SESSION_DISTANCE, 100),
        ascent=_total(sessions, _SESSION_ASCENT), has_positions=has_positions)


# FIT profile: the names of the messages `fit inspect` names (others: by number).
MESSAGE_NAMES = {
    0: "file_id", 12: "sport", 15: "goal", 18: "session", 19: "lap", 20: "record", 21: "event",
    23: "device_info", 26: "workout", 27: "workout_step", 28: "schedule", 31: "course",
    32: "course_point", 34: "activity", 49: "file_creator", 72: "training_file", 78: "hrv",
    206: "field_description", 207: "developer_data_id",
}
# FIT profile: the messages that describe developer data (field_description, developer_data_id)
DEVELOPER_MESSAGES = (206, 207)
# FIT profile: file_id's fields type, manufacturer and product, and the names of manufacturers
_FILE_ID_TYPE, _FILE_ID_MANUFACTURER, _FILE_ID_PRODUCT = 0, 1, 2
MANUFACTURER_NAMES = {1: "Garmin", 255: "development"}


@dataclass(frozen=True)
class Inspection:
    """What a FIT file holds (inspect). Its first part: the sizes its header declares, the
    type, manufacturer, product and creation time of its first file_id (never its serial
    number), and how many messages of each global number there are, as far as they read."""

    size: int
    not_whole: NotWhole | None
    header_size: int | None = None  # None: no FIT file
    data_size: int | None = None
    file_type: int | None = None
    manufacturer: int | None = None
    product: int | None = None
    created: int | None = None  # Unix time
    messages: dict[int, int] = field(default_factory=dict)
    broke_off: str | None = None  # why the messages could not be read to the end

    @property
    def whole(self) -> bool:
        return self.not_whole is None and self.broke_off is None


def inspect(data: bytes) -> Inspection:
    """What the FIT file `data` holds (Inspection); of what is no FIT file only its check."""
    found = check(data)
    try:
        header_size = _check_header(data)
    except FitError:
        return Inspection(len(data), found)
    (data_size,) = struct.unpack_from("<I", data, 4)
    counts: dict[int, int] = {}
    file_id: dict[int, Value] = {}
    broke_off = None
    try:
        for num, values in iter_messages(data):
            counts[num] = counts.get(num, 0) + 1
            if num == _MESG_FILE_ID and counts[num] == 1:
                file_id = values
    except FitError as e:
        broke_off = str(e)
    return Inspection(
        len(data), found, header_size, data_size,
        file_type=_whole_number(file_id.get(_FILE_ID_TYPE)),
        manufacturer=_whole_number(file_id.get(_FILE_ID_MANUFACTURER)),
        product=_whole_number(file_id.get(_FILE_ID_PRODUCT)),
        created=_unix_time(file_id.get(_FIELD_TIME_CREATED)), messages=counts,
        broke_off=broke_off)


@dataclass(frozen=True)
class Point:
    """A record of an activity that has a position: degrees, metres and a Unix time."""

    latitude: float
    longitude: float
    altitude: float | None = None
    time: int | None = None


def _degrees(semicircles: int) -> float:
    return semicircles * 180 / 2**31


def _metres(value: Value) -> float | None:
    raw = _whole_number(value)
    return None if raw is None else raw / 5 - 500


def points(data: bytes) -> Iterator[Point]:
    """The records of the activity file `data` that have a position, in their order: the
    enhanced altitude when it is given, else the altitude. FitError where the file breaks
    off, after the points before it."""
    for _num, values in iter_messages(data, wanted=(_MESG_RECORD,)):
        lat, long = (_whole_number(values.get(n)) for n in (_RECORD_LAT, _RECORD_LONG))
        if lat is None or long is None:
            continue
        altitude = _metres(values.get(_RECORD_ENHANCED_ALTITUDE))
        if altitude is None:
            altitude = _metres(values.get(_RECORD_ALTITUDE))
        yield Point(_degrees(lat), _degrees(long), altitude,
                    _unix_time(values.get(FIELD_TIMESTAMP)))
