"""Minimal FIT reader, written from the public FIT protocol: the data messages of a file with
their values by base type, whether a file is whole, and the messages the program needs (the
creation time in file_id, from which Garmin Connect's activity identifier for duplicate checks
comes, and TrueUp's callback).
"""

from __future__ import annotations

import math
import struct
from collections.abc import Collection
from dataclasses import dataclass

from openexpress.i18n import _

FIT_EPOCH_OFFSET = 631065600  # 1989-12-31T00:00:00Z as Unix time

_MESG_FILE_ID = 0
_FIELD_TIME_CREATED = 4
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


def _iter_messages(data: bytes, wanted: Collection[int] | None):
    if len(data) < 12:
        raise FitError(_("File too short"))
    header_size = data[0]
    if header_size not in (12, 14) or data[8:12] != b".FIT":
        raise FitError(_("Not a FIT file"))
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


def not_whole(data: bytes) -> tuple[bool, str] | None:
    """Why `data` is not a whole FIT file, as (cut short, the words for the log), or None when
    it is: every part (a file may chain several) has a header of 12 or 14 bytes with ".FIT",
    the size its header declares (header, data and the CRC of 2 bytes) and that CRC; zeros
    after the last part are padding. Cut short: a header declares more bytes than were read,
    as when the device was still writing the file; else no header, data after the end that
    are no FIT file, or a CRC that does not match. For the log: sizes, never the content."""
    pos = 0
    while True:
        if pos and not any(data[pos:]):
            return None  # zeros after whole FIT data: padding, nothing cut short
        if len(data) - pos < 12 or data[pos] not in (12, 14) or data[pos + 8:pos + 12] != b".FIT":
            return False, (f"no FIT header ({len(data)} B read)" if pos == 0
                           else f"{len(data) - pos} B after the whole FIT data are no FIT file")
        header = data[pos]
        (size,) = struct.unpack_from("<I", data, pos + 4)
        end = pos + header + size + 2
        if end > len(data):
            return True, f"{len(data)} B read, {end} B declared"
        (crc,) = struct.unpack_from("<H", data, end - 2)
        if crc16(data[pos:end - 2]) != crc:
            return False, f"the CRC does not match ({len(data)} B read)"
        if end == len(data):
            return None
        pos = end


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
