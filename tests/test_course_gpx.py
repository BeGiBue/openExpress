"""A GPX file to copy to a device as a course (openexpress/course_gpx.py): what is refused before
anything is read into memory or written, what the file holds, the course's name and its writing
into the copy (that element alone), and the file's name on the device. Made-up files only."""

import math

import pytest

from openexpress import course_gpx
from openexpress.course_gpx import CourseFileError

NS11 = "http://www.topografix.com/GPX/1/1"
NS10 = "http://www.topografix.com/GPX/1/0"


def gpx(body: str, ns: str = NS11, decl: str = '<?xml version="1.0" encoding="UTF-8"?>\n') -> str:
    return f'{decl}<gpx version="1.1" creator="made up" xmlns="{ns}">\n{body}</gpx>\n'


def track(name: str | None = "Morning Loop", points=((52.0, 13.0, 30.0), (52.0, 13.01, 40.0),
                                                       (52.0, 13.02, 35.0))) -> str:
    named = f"<name>{name}</name>" if name is not None else ""
    pts = "".join(f'<trkpt lat="{la}" lon="{lo}"><ele>{e}</ele></trkpt>' for la, lo, e in points)
    return f"  <trk>{named}<trkseg>{pts}</trkseg></trk>\n"


def route(name="To the Lake", points=((52.0, 13.0), (52.01, 13.0), (52.02, 13.01))) -> str:
    pts = "".join(f'<rtept lat="{la}" lon="{lo}"/>' for la, lo in points)
    return f"  <rte><name>{name}</name>{pts}</rte>\n"


def waypoint(name="Spring", lat=52.0, lon=13.0) -> str:
    return f'  <wpt lat="{lat}" lon="{lon}"><name>{name}</name></wpt>\n'


def write(tmp_path, text: str | bytes, name="morning-loop.gpx"):
    p = tmp_path / name
    p.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    return p


# --- what is refused --------------------------------------------------------------------------

def test_a_missing_file_is_said(tmp_path):
    with pytest.raises(CourseFileError, match="Not found"):
        course_gpx.read(tmp_path / "nothing.gpx")


def test_a_file_too_large_is_refused_before_it_is_read(tmp_path, monkeypatch):
    p = write(tmp_path, gpx(track()))
    monkeypatch.setattr(course_gpx, "MAX_SIZE", 100)
    opened = []
    monkeypatch.setattr(course_gpx.Path, "read_bytes", lambda self: opened.append(self) or b"")
    with pytest.raises(CourseFileError, match="too large"):
        course_gpx.read(p)
    assert opened == []  # the size alone refused it


@pytest.mark.parametrize("text", [
    "not xml at all",
    '<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"></kml>',  # another format
    f'<?xml version="1.0"?><gpx xmlns="http://example.com/other">{track()}</gpx>',  # namespace
    '<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1"><trk>',  # cut short
    f'<?xml version="1.0"?><gpx xmlns="{NS11}"><trk><name>&undefined;</name></trk></gpx>',
], ids=["text", "kml", "namespace", "cut", "undefined-entity"])
def test_what_is_no_gpx_is_refused(tmp_path, text):
    with pytest.raises(CourseFileError, match="not a GPX file"):
        course_gpx.read(write(tmp_path, text))


@pytest.mark.parametrize("doctype", [
    # "Billion laughs": entities that would expand to a gigabyte.
    ('<!DOCTYPE gpx [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
     '<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]>'),
    # An external entity: a file of the computer read into the name.
    '<!DOCTYPE gpx [<!ENTITY secret SYSTEM "file:///etc/passwd">]>',
    '<!DOCTYPE gpx SYSTEM "http://example.com/gpx.dtd">',
], ids=["laughs", "external-entity", "external-dtd"])
def test_a_document_type_is_refused_before_any_entity(tmp_path, doctype):
    body = track(name="&c;" if "&b;" in doctype else "&secret;" if "secret" in doctype else "x")
    text = '<?xml version="1.0" encoding="UTF-8"?>\n' + doctype + gpx(body, decl="")
    with pytest.raises(CourseFileError, match="document type"):
        course_gpx.read(write(tmp_path, text))


@pytest.mark.parametrize("body", [
    "",
    "  <trk><name>Empty</name><trkseg></trkseg></trk>\n",
    track(points=((52.0, 13.0, 30.0),)),  # one point: no line
    "  <metadata><name>Only metadata</name></metadata>\n",
], ids=["empty", "no-points", "one-point", "metadata"])
def test_a_file_with_nothing_to_navigate_is_refused(tmp_path, body):
    with pytest.raises(CourseFileError, match="no track, route or waypoint"):
        course_gpx.read(write(tmp_path, gpx(body)))


@pytest.mark.parametrize("body", [
    track(points=((91.0, 13.0, 0), (52.0, 13.0, 0))),
    track(points=((52.0, -180.5, 0), (52.0, 13.0, 0))),
    route(points=((52.0, 13.0), ("north", 13.0))),
    waypoint(lat="nan"),
    '  <wpt lon="13.0"><name>No latitude</name></wpt>\n',
], ids=["latitude", "longitude", "not-a-number", "nan", "missing"])
def test_a_point_off_the_earth_is_refused(tmp_path, body):
    with pytest.raises(CourseFileError, match="impossible position"):
        course_gpx.read(write(tmp_path, gpx(body)))


# --- what the file holds ----------------------------------------------------------------------

def test_a_track_its_length_and_ascent(tmp_path):
    g = course_gpx.read(write(tmp_path, gpx(track())))
    (line,) = g.lines
    assert (line.kind, line.name, line.points) == ("track", "Morning Loop", 3)
    # Two steps of 0.01° of longitude at 52°: about 685 m each.
    expected = 2 * 2 * 6_371_000 * math.asin(math.cos(math.radians(52)) * math.sin(math.radians(0.005)))
    assert line.distance_m == pytest.approx(expected, rel=1e-6)
    assert line.ascent_m == pytest.approx(10.0)  # up 10, down 5
    assert (g.waypoints, g.courses, g.size) == (0, 1, (tmp_path / "morning-loop.gpx").stat().st_size)


def test_gpx_1_0_and_a_namespace_with_a_prefix_are_read(tmp_path):
    g10 = course_gpx.read(write(tmp_path, gpx(track(), ns=NS10), "a.gpx"))
    assert g10.lines[0].points == 3
    prefixed = ('<?xml version="1.0"?>\n<g:gpx xmlns:g="http://www.topografix.com/GPX/1/1">'
                '<g:trk><g:name>P</g:name><g:trkseg><g:trkpt lat="1" lon="2"/><g:trkpt lat="1" '
                'lon="3"/></g:trkseg></g:trk></g:gpx>')
    assert course_gpx.read(write(tmp_path, prefixed, "b.gpx")).lines[0].name == "P"


def test_routes_waypoints_and_several_tracks_are_counted(tmp_path):
    body = track("A") + track("B") + route() + waypoint() + waypoint("Hut")
    g = course_gpx.read(write(tmp_path, gpx(body)))
    assert [(line.kind, line.name) for line in g.lines] == [
        ("track", "A"), ("track", "B"), ("route", "To the Lake")]
    assert (g.courses, g.waypoints) == (3, 2)
    assert g.lines[2].ascent_m is None  # a route without elevation


def test_a_track_of_segments_is_measured_within_each_segment(tmp_path):
    seg = '<trkseg><trkpt lat="0" lon="0"/><trkpt lat="0" lon="1"/></trkseg>'
    far = '<trkseg><trkpt lat="0" lon="50"/><trkpt lat="0" lon="51"/></trkseg>'
    g = course_gpx.read(write(tmp_path, gpx(f"  <trk><name>S</name>{seg}{far}</trk>\n")))
    one_degree = 2 * math.pi * 6_371_000 / 360
    assert g.lines[0].distance_m == pytest.approx(2 * one_degree, rel=1e-6)  # not the 49° gap
    assert g.lines[0].points == 4


def test_only_waypoints_make_no_course(tmp_path):
    g = course_gpx.read(write(tmp_path, gpx(waypoint() + waypoint("B"))))
    assert (g.courses, g.waypoints, g.lines) == (0, 2, ())


# --- the course's name ------------------------------------------------------------------------

def test_the_course_is_named_after_its_track_else_the_file(tmp_path):
    named = course_gpx.read(write(tmp_path, gpx(track("Lake Loop"))))
    assert course_gpx.course_name(named) == "Lake Loop"
    unnamed = course_gpx.read(write(tmp_path, gpx(track(None)), "Sunday ride.gpx"))
    assert course_gpx.course_name(unnamed) == "Sunday ride"
    blank = course_gpx.read(write(tmp_path, gpx(track("   ")), "blank.GPX"))
    assert course_gpx.course_name(blank) == "blank"


def test_a_name_entered_wins_and_an_empty_one_falls_back(tmp_path):
    g = course_gpx.read(write(tmp_path, gpx(track("Lake Loop"))))
    assert course_gpx.course_name(g, "  Evening  ") == "Evening"
    assert course_gpx.course_name(g, "   ") == "Lake Loop"


def test_several_courses_have_no_one_name(tmp_path):
    g = course_gpx.read(write(tmp_path, gpx(track("A") + track("B"))))
    assert course_gpx.course_name(g) is None
    with pytest.raises(ValueError):
        course_gpx.with_course_name(g, "C")


def _renamed(tmp_path, text, name, file="x.gpx"):
    g = course_gpx.read(write(tmp_path, text, file))
    data = course_gpx.with_course_name(g, name)
    again = course_gpx.read(write(tmp_path, data, "copy-" + file))
    return g, data, again


def test_a_new_name_changes_that_element_and_nothing_else(tmp_path):
    text = gpx("  <metadata><name>Planner</name></metadata>\n" + waypoint("Spring") + track("Old"))
    g, data, again = _renamed(tmp_path, text, "Pętla & <okolice>")
    assert again.lines[0].name == "Pętla & <okolice>"
    original = text.encode("utf-8")
    before, after = original.split(b"<name>Old</name>")
    assert data == before + "<name>Pętla &amp; &lt;okolice&gt;</name>".encode() + after
    # The metadata's name and the waypoint's stay.
    assert b"<name>Planner</name>" in data and b"<name>Spring</name>" in data


def test_a_missing_name_is_added_first_in_the_course_with_its_prefix(tmp_path):
    plain = gpx(route(name="X").replace("<name>X</name>", ""))
    _g, data, again = _renamed(tmp_path, plain, "Lake")
    assert b"<rte><name>Lake</name><rtept" in data and again.lines[0].name == "Lake"
    prefixed = ('<?xml version="1.0"?>\n<g:gpx xmlns:g="http://www.topografix.com/GPX/1/1">'
                '<g:trk>\n<g:trkseg><g:trkpt lat="1" lon="2"/><g:trkpt lat="1" lon="3"/>'
                '</g:trkseg></g:trk></g:gpx>')
    _g, data, again = _renamed(tmp_path, prefixed, "P2", "p.gpx")
    assert b"<g:trk><g:name>P2</g:name>\n<g:trkseg>" in data and again.lines[0].name == "P2"


@pytest.mark.parametrize("old", ["<name/>", "<name />", "<name><![CDATA[Old <b>]]></name>",
                                 '<name lang="pl">Old</name>'])
def test_an_empty_or_unusual_name_element_is_replaced(tmp_path, old):
    text = gpx(track("X").replace("<name>X</name>", old))
    _g, data, again = _renamed(tmp_path, text, "New")
    assert again.lines[0].name == "New" and data.count(b"New") == 1


def test_a_name_in_a_file_of_another_encoding_is_written_in_it(tmp_path):
    text = gpx(track("Stara"), decl='<?xml version="1.0" encoding="ISO-8859-2"?>\n')
    g = course_gpx.read(write(tmp_path, text.encode("iso-8859-2"), "l2.gpx"))
    data = course_gpx.with_course_name(g, "Pętla żółta ☀")
    assert "<name>Pętla żółta &#9728;</name>".encode("iso-8859-2") in data
    again = course_gpx.read(write(tmp_path, data, "l2-copy.gpx"))
    assert again.lines[0].name == "Pętla żółta ☀"


# --- the file's name on the device ------------------------------------------------------------

@pytest.mark.parametrize("course,expected", [
    ("Pętla wokół Kamiennej Góry", "Petla_wokol_Kamiennej_Gory.gpx"),
    ("Sopot – Wejherowo", "Sopot_Wejherowo.gpx"),
    ("Łódź → Straße (1)", "Lodz_Strasse_(1).gpx"),
    ("  ..trail.. ", "trail.gpx"),
    ("CON", "CON_.gpx"),
    ("com1", "com1_.gpx"),
    ("日本語", "course.gpx"),
    ("a/b\\c:d*e?f", "abcdef.gpx"),
])
def test_the_name_on_the_device_is_safe(course, expected):
    assert course_gpx.device_name(course) == expected


def test_the_name_on_the_device_is_short_takes_the_declared_extension_and_never_a_taken_one():
    long = course_gpx.device_name("x" * 200)
    assert len(long) == course_gpx.MAX_NAME and long.endswith(".gpx")
    assert course_gpx.device_name("Loop", extension="GPX") == "Loop.GPX"
    taken = {"loop.gpx", "loop_2.gpx"}
    assert course_gpx.device_name("Loop", taken=taken) == "Loop_3.gpx"
    assert course_gpx.device_name("x" * 200, taken={long.casefold()}).endswith("_2.gpx")
    assert len(course_gpx.device_name("x" * 200, taken={long.casefold()})) == course_gpx.MAX_NAME


def test_a_file_in_utf_16_is_read_but_its_course_keeps_its_name(tmp_path):
    text = gpx(track("Wide"), decl='<?xml version="1.0" encoding="UTF-16"?>\n')
    g = course_gpx.read(write(tmp_path, text.encode("utf-16"), "wide.gpx"))
    assert g.lines[0].name == "Wide"
    with pytest.raises(CourseFileError, match="cannot be changed"):
        course_gpx.with_course_name(g, "Narrow")
