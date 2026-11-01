"""A GPX 1.1 track of an activity (gpx.track): the position, elevation and time of each of its
records that has a position, nothing else of the file (no heart rate, no device, no serial
number). Made-up files only (fakes.fit_file)."""

import xml.etree.ElementTree as ET

import pytest
from fakes import FitData, FitDefinition, fit_file

GPX = "{http://www.topografix.com/GPX/1/1}"
ENUM, UINT16, SINT32, UINT32, UINT32Z = 0x00, 0x84, 0x85, 0x86, 0x8C
TIMESTAMP = 253
WHEN = 1_162_275_153  # 2026-10-30 06:12:33 UTC, in seconds of the FIT protocol
SERIAL = 3_987_654_321  # a made-up serial number of a device

# timestamp, position_lat, position_long, altitude, enhanced_altitude, heart_rate
RECORDS = FitDefinition(1, 20, ((TIMESTAMP, UINT32), (0, SINT32), (1, SINT32), (2, UINT16),
                                (78, UINT32), (3, 0x02)))


def raw_altitude(metres: float) -> int:
    return round((metres + 500) * 5)


def activity(*records: FitData) -> bytes:
    """A made-up activity: file_id and device_info with a serial number, then `records`."""
    return fit_file(
        FitDefinition(0, 0, ((0, ENUM), (3, UINT32Z), (4, UINT32))), FitData(0, (4, SERIAL, WHEN)),
        FitDefinition(2, 23, ((3, UINT32Z),)), FitData(2, (SERIAL,)),
        RECORDS, *records)


def record(seconds: int = 0, lat=624_000_000, lon=250_000_000, altitude=None,
           enhanced=None, heart_rate=150) -> FitData:
    return FitData(1, (WHEN + seconds, lat, lon,
                       None if altitude is None else raw_altitude(altitude),
                       None if enhanced is None else raw_altitude(enhanced), heart_rate))


def track(data: bytes, **options) -> bytes:
    from openexpress import gpx

    return gpx.track(data, **options)


def points(data: bytes) -> list[ET.Element]:
    root = ET.fromstring(track(data))
    return root.findall(f"{GPX}trk/{GPX}trkseg/{GPX}trkpt")


def test_semicircles_become_degrees_with_seven_decimals():
    found = points(activity(record(0, 1_073_741_824, -536_870_912),
                            record(1, 624_000_000, 250_000_000), record(2, 0, -1)))
    assert [(p.get("lat"), p.get("lon")) for p in found] == [
        ("90.0000000", "-45.0000000"), ("52.3030758", "20.9547579"), ("0.0000000", "-0.0000001")]


def test_the_enhanced_altitude_before_the_altitude():
    found = points(activity(record(0, altitude=100.0, enhanced=250.4),
                            record(1, altitude=100.0), record(2)))
    assert [p.findtext(f"{GPX}ele") for p in found] == ["250.4", "100.0", None]


def test_points_without_a_position_are_left_out():
    found = points(activity(record(0), record(1, lat=None), record(2, lon=None), record(3)))
    assert [p.findtext(f"{GPX}time") for p in found] == [
        "2026-10-30T06:12:33Z", "2026-10-30T06:12:36Z"]


def test_times_are_in_utc_with_z():
    root = ET.fromstring(track(activity(record(0), record(3600))))
    assert root.findtext(f"{GPX}metadata/{GPX}time") == "2026-10-30T06:12:33Z"
    assert [p.findtext(f"{GPX}time")
            for p in root.findall(f"{GPX}trk/{GPX}trkseg/{GPX}trkpt")] == [
        "2026-10-30T06:12:33Z", "2026-10-30T07:12:33Z"]


def test_an_activity_without_any_position_is_an_error_not_an_empty_file():
    from openexpress import gpx

    with pytest.raises(gpx.NoPositions) as refused:
        gpx.track(activity(record(0, lat=None, lon=None), record(1, lat=None, lon=None)))
    assert str(refused.value) == ("This activity has no GPS positions, so it cannot be "
                                  "exported as GPX.")


def test_a_gpx_1_1_file_by_openexpress_and_nothing_of_the_device():
    data = track(activity(record(0, altitude=12.0), record(1)), name="Running 2026-10-30")
    assert data.startswith(b"<?xml version='1.0' encoding='UTF-8'?>")
    root = ET.fromstring(data)
    assert root.tag == f"{GPX}gpx"
    assert (root.get("version"), root.get("creator")) == ("1.1", "openExpress")
    assert root.findtext(f"{GPX}trk/{GPX}name") == "Running 2026-10-30"
    # Position, elevation and time only: no heart rate, no extension.
    assert {child.tag for p in root.iter(f"{GPX}trkpt") for child in p} == {
        f"{GPX}ele", f"{GPX}time"}
    assert str(SERIAL).encode() not in data and f"{SERIAL:x}".encode() not in data.lower()
