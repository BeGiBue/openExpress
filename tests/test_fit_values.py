"""The FIT reader reads each field by its base type, works out the time a compressed-timestamp
header gives a message, and steps over the messages it is not asked for. Made-up files only
(fakes.fit_file)."""

import struct

import pytest
from fakes import FitData, FitDefinition, fit_file

from openexpress.fit import iter_messages, not_whole

SESSION, LAP, RECORD, WORKOUT = 18, 19, 20, 26
ENUM, SINT32, UINT32, STRING = 0x00, 0x85, 0x86, 0x07
TIMESTAMP = 253
WHEN = 1_100_000_008  # a made-up time whose lowest five bits are 8


def _messages(*messages, **options):
    return list(iter_messages(fit_file(*messages), **options))


def test_the_made_up_files_are_whole_unless_asked_otherwise():
    messages = (FitDefinition(0, RECORD, ((TIMESTAMP, UINT32), (0, SINT32))),
                FitData(0, (WHEN, 5)))
    assert not_whole(fit_file(*messages)) is None
    assert not_whole(fit_file(*messages, header_size=12)) is None
    cut_short, _words = not_whole(fit_file(*messages, cut=20))
    assert cut_short
    cut_short, words = not_whole(fit_file(*messages, bad_crc=True))
    assert not cut_short and "CRC" in words


@pytest.mark.parametrize("big_endian", [False, True])
def test_a_position_west_of_greenwich_reads_negative(big_endian):
    # position_lat and position_long of a record, in semicircles
    [(number, values)] = _messages(
        FitDefinition(0, RECORD, ((0, SINT32), (1, SINT32)), big_endian=big_endian),
        FitData(0, (600_000, -1)))
    assert number == RECORD
    assert values == {0: 600_000, 1: -1}


def test_the_invalid_value_of_a_sint32_reads_none():
    [(_number, values)] = _messages(FitDefinition(0, RECORD, ((0, SINT32), (1, SINT32))),
                                    FitData(0, (None, -5)))
    assert values == {0: None, 1: -5}


@pytest.mark.parametrize(("base_type", "size", "value"), [
    (0x00, 1, 7),           # enum
    (0x01, 1, -7),          # sint8
    (0x02, 1, 200),         # uint8
    (0x83, 2, -300),        # sint16
    (0x84, 2, 60_000),      # uint16
    (0x85, 4, -70_000),     # sint32
    (0x86, 4, 3_000_000_000),  # uint32
    (0x88, 4, 1.5),         # float32
    (0x89, 8, -2.25),       # float64
    (0x0A, 1, 9),           # uint8z
    (0x8B, 2, 9),           # uint16z
    (0x8C, 4, 9),           # uint32z
    (0x0D, 1, 0x42),        # byte
    (0x8E, 8, -(2 ** 40)),  # sint64
    (0x8F, 8, 2 ** 40),     # uint64
    (0x90, 8, 2 ** 40),     # uint64z
])
def test_every_base_type_reads_its_value_and_its_invalid_value_as_none(base_type, size, value):
    [(_number, values)] = _messages(
        FitDefinition(0, RECORD, ((0, base_type, size), (1, base_type, size))),
        FitData(0, (value, None)))
    assert values == {0: value, 1: None}


def test_a_string_field_reads_as_text():
    # wkt_name and sport of a workout
    [(_number, values)] = _messages(FitDefinition(0, WORKOUT, ((8, STRING, 24), (4, ENUM))),
                                    FitData(0, ("Interwały 5×1 km", 1)))
    assert values == {8: "Interwały 5×1 km", 4: 1}


def test_an_empty_string_reads_none():
    [(_number, values)] = _messages(FitDefinition(0, WORKOUT, ((8, STRING, 8),)),
                                    FitData(0, ("",)))
    assert values == {8: None}


def test_an_array_is_not_read():
    [(_number, values)] = _messages(FitDefinition(0, RECORD, ((0, 0x84, 6), (1, 0x84))),
                                    FitData(0, ((1, 2, 3), 4)))
    assert values == {0: None, 1: 4}


def test_a_base_type_the_reader_does_not_know_reads_as_an_unsigned_number():
    [(_number, values)] = _messages(FitDefinition(0, RECORD, ((0, 0x1F, 4),)),
                                    FitData(0, (struct.pack("<I", 70_000),)))
    assert values == {0: 70_000}


# The offset of a compressed-timestamp header takes the place of the lowest five bits of the
# time before it (here 8); an offset smaller than them is in the next 32 seconds.
@pytest.mark.parametrize(("offset", "expected"), [(12, WHEN + 4), (3, WHEN + 27), (8, WHEN)])
def test_a_record_after_a_compressed_header_gets_the_time_it_encodes(offset, expected):
    messages = _messages(
        FitDefinition(0, RECORD, ((TIMESTAMP, UINT32), (0, SINT32))),
        FitData(0, (WHEN, 1)),
        FitDefinition(1, RECORD, ((0, SINT32),)),
        FitData(1, (2,), time_offset=offset))
    assert messages == [(RECORD, {TIMESTAMP: WHEN, 0: 1}), (RECORD, {TIMESTAMP: expected, 0: 2})]


def test_compressed_headers_count_from_the_time_of_the_one_before():
    messages = _messages(
        FitDefinition(0, RECORD, ((TIMESTAMP, UINT32),)),
        FitData(0, (WHEN,)),
        FitDefinition(1, RECORD, ((0, SINT32),)),
        FitData(1, (1,), time_offset=12),
        FitData(1, (2,), time_offset=20),
        FitData(1, (3,), time_offset=4))
    assert [values.get(TIMESTAMP) for _number, values in messages] == [
        WHEN, WHEN + 4, WHEN + 12, WHEN + 28]


def test_a_compressed_header_before_any_time_gives_no_time():
    [(_number, values)] = _messages(FitDefinition(1, RECORD, ((0, SINT32),)),
                                    FitData(1, (7,), time_offset=12))
    assert values == {0: 7}


def test_a_message_not_wanted_is_skipped_and_the_next_one_read():
    messages = _messages(
        # a lap with a developer field of 3 bytes, not asked for
        FitDefinition(0, LAP, ((TIMESTAMP, UINT32), (7, UINT32), (8, UINT32)),
                      developer=((0, 3, 0),)),
        FitData(0, (WHEN, 100_000, 90_000), developer=b"\x01\x02\x03"),
        FitDefinition(1, SESSION, ((TIMESTAMP, UINT32), (5, ENUM), (9, UINT32))),
        FitData(1, (WHEN + 60, 1, 1234)),
        wanted={SESSION})
    assert messages == [(SESSION, {TIMESTAMP: WHEN + 60, 5: 1, 9: 1234})]


def test_the_time_of_a_message_not_wanted_counts_for_a_compressed_header_after_it():
    messages = _messages(
        FitDefinition(0, LAP, ((TIMESTAMP, UINT32),)),
        FitData(0, (WHEN,)),
        FitDefinition(1, RECORD, ((0, SINT32),)),
        FitData(1, (5,), time_offset=12),
        wanted={RECORD})
    assert messages == [(RECORD, {0: 5, TIMESTAMP: WHEN + 4})]


def test_a_creation_time_that_is_no_whole_number_is_not_known():
    from openexpress.fit import parse_file_id

    for base_type, value in ((STRING, "1234"), (0x88, 1.5)):
        data = fit_file(FitDefinition(0, 0, ((0, ENUM), (4, base_type, 4))), FitData(0, (4, value)))
        assert parse_file_id(data).time_created is None


def test_a_trueup_time_that_is_no_whole_number_is_not_known():
    from openexpress.fit import MESG_CALLBACK_DELAY, true_up_time

    for base_type, value in ((STRING, "1234"), (0x88, 1.5)):
        data = fit_file(FitDefinition(0, MESG_CALLBACK_DELAY, ((0, base_type, 4),)),
                        FitData(0, (value,)))
        assert true_up_time(data) is None
