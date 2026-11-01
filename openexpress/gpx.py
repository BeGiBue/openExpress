"""A GPX 1.1 track of an activity file: the position, elevation and time of each of its records
that has a position, and nothing else of the file (no heart rate, no device, no serial number).
Written with xml.etree; nothing is written to a disk here.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from openexpress import fit
from openexpress.errors import UserFacingError
from openexpress.i18n import _

NAMESPACE = "http://www.topografix.com/GPX/1/1"
CREATOR = "openExpress"


class NoPositions(UserFacingError):
    """The activity has no record with a position: there is no track to make of it."""


def _utc(unix: int) -> str:
    return datetime.fromtimestamp(unix, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def track(data: bytes, name: str | None = None) -> bytes:
    """The GPX 1.1 file (UTF-8) of the activity file `data`, its track named `name`: one track
    of one segment, a point for each record with a position (degrees with 7 decimals, the
    elevation in metres, the time in UTC). NoPositions when no record has a position, never an
    empty track; FitError where the file cannot be read."""
    found = list(fit.points(data))
    if not found:
        raise NoPositions(_("This activity has no GPS positions, so it cannot be exported as "
                            "GPX."))
    root = ET.Element("gpx", {"xmlns": NAMESPACE, "version": "1.1", "creator": CREATOR})
    first = next((p.time for p in found if p.time is not None), None)
    if first is not None:
        ET.SubElement(ET.SubElement(root, "metadata"), "time").text = _utc(first)
    trk = ET.SubElement(root, "trk")
    if name:
        ET.SubElement(trk, "name").text = name
    segment = ET.SubElement(trk, "trkseg")
    for p in found:
        point = ET.SubElement(segment, "trkpt",
                              {"lat": f"{p.latitude:.7f}", "lon": f"{p.longitude:.7f}"})
        if p.altitude is not None:
            ET.SubElement(point, "ele").text = f"{p.altitude:.1f}"
        if p.time is not None:
            ET.SubElement(point, "time").text = _utc(p.time)
    ET.indent(root)
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True) + b"\n"
