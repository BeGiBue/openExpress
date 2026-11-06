"""Courses on the device and GPX files copied to it (openexpress/courses.py): which devices are
offered them, what is read of the device (its courses with their origin, the files waiting, the
saved locations), the plan and the copy of a file, the removal of a course or of a waiting file,
and the record of the copies. Made-up files on a folder taken as the device; no device."""

import json
import time

import pytest
from fakes import FitData, FitDefinition, fit_file, gpx_file, gpx_track, gpx_waypoint

from openexpress import applog, courses, fit, paths, service
from openexpress.course_gpx import CourseFileError
from openexpress.courses import CourseError
from openexpress.device.storage import DeviceError, LocalStorage
from openexpress.device.xmldevice import INPUT, OUTPUT, DeviceFile, GarminDevice

UNIT = 1234


def device(gpx_folder="Garmin/NewFiles", extension="GPX", locations="Garmin/Locations"):
    """A made-up device with the declarations of a fēnix 8 and an Edge 1050: courses out of
    Garmin/Courses, GPX files and courses into Garmin/NewFiles, saved locations out of
    `locations` (None: none declared); `gpx_folder` None: no GPX files at all."""
    files = [DeviceFile("FIT_TYPE_6", OUTPUT, "Garmin/Courses", extension="FIT"),
             DeviceFile("FIT_TYPE_6", INPUT, "Garmin/NewFiles", extension="FIT")]
    if gpx_folder is not None:
        files.append(DeviceFile("GPSData", INPUT, gpx_folder, extension=extension))
    if locations is not None:
        files.append(DeviceFile("FIT_TYPE_8", OUTPUT, locations, extension="FIT"))
    return GarminDevice(UNIT, "006-B0000-00", 100, "Made-up Edge", files)


@pytest.fixture
def drive(tmp_path):
    root = tmp_path / "device"
    for folder in ("Garmin/NewFiles", "Garmin/Courses", "Garmin/Locations"):
        (root / folder).mkdir(parents=True)
    return root


def put(root, path: str, data: bytes | str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)


def course_fit(name: str | None = "Morning Loop", *, made: int, product=courses.DEVICE_PRODUCT,
               manufacturer=1, distance_cm: int | None = 1_234_500, ascent: int | None = 321,
               lap_after_points=False, points=3) -> bytes:
    """A made-up course file: file_id (type 6, made at `made`, a Unix time), its course, one lap
    and `points` records, the lap before them as the devices write it (or after)."""
    at = made - fit.FIT_EPOCH_OFFSET
    head = (FitDefinition(0, 0, ((0, 0x00), (1, 0x84), (2, 0x84), (4, 0x86))),
            FitData(0, (6, manufacturer, product, at)),
            FitDefinition(1, 31, ((5, 0x07, 48), (4, 0x00))), FitData(1, (name, 0)))
    lap = (FitDefinition(2, 19, ((9, 0x86), (21, 0x84))), FitData(2, (distance_cm, ascent)))
    records = (FitDefinition(3, 20, ((253, 0x86), (0, 0x85), (1, 0x85))),
               *(FitData(3, (at + n, 0, n * 1000)) for n in range(points)))
    return fit_file(*head, *(records + lap if lap_after_points else lap + records))


def locations_fit(count: int, cut: int | None = None) -> bytes:
    """A made-up locations file (type 8) of `count` saved locations."""
    return fit_file(FitDefinition(0, 0, ((0, 0x00),)), FitData(0, (8,)),
                    FitDefinition(1, 29, ((0, 0x07, 16), (1, 0x85), (2, 0x85))),
                    *(FitData(1, (f"Place {n}", n, n)) for n in range(count)), cut=cut)


def a_gpx(tmp_path, body=None, name="morning-loop.gpx"):
    path = tmp_path / name
    path.write_text(gpx_file(gpx_track() if body is None else body), encoding="utf-8")
    return path


def now() -> int:
    return int(time.time())


# --- which devices -------------------------------------------------------------------------------


def test_courses_are_offered_where_gpx_files_go_to_garmin_newfiles():
    assert courses.offered(device())
    assert courses.offered(device(gpx_folder="GARMIN/NEWFILES/"))  # its case, its slashes
    assert not courses.offered(device(gpx_folder=None))


def test_a_device_whose_gpx_files_go_elsewhere_is_not_offered_and_the_log_says_where(log_file):
    applog.setup("cli")
    assert not courses.offered(device(gpx_folder="Garmin/GPX"))
    assert "GPX files go to Garmin/GPX on this device, not Garmin/NewFiles" in log_file.read_text()


def test_a_device_not_offered_has_nothing_read(drive, monkeypatch):
    st = LocalStorage(drive)
    monkeypatch.setattr(st, "listdir", lambda path: pytest.fail("the device was read"))
    seen = courses.overview(device(gpx_folder=None), st)
    assert (seen.folder, seen.courses, seen.waiting, seen.locations) == (None, [], [], None)


# --- the courses on the device -------------------------------------------------------------------


def test_each_course_with_what_its_file_says(drive, clock):
    put(drive, "Garmin/Courses/Morning_Loop.fit", course_fit(made=now() - 3600))
    put(drive, "Garmin/Courses/Straight.fit",
        course_fit("Straight Lines", made=now() - 7200, distance_cm=340_862, ascent=None))
    put(drive, "Garmin/Courses/notes.txt", "not a course")
    put(drive, "Garmin/Courses/Inside/Deeper.fit", course_fit("Deeper", made=now()))
    seen = courses.overview(device(), LocalStorage(drive))
    assert seen.folder == "Garmin/NewFiles" and seen.unreadable == ()
    assert [(c.filename, c.path, c.name, c.distance_m, c.ascent_m, c.made)
            for c in seen.courses] == [
        ("Morning_Loop.fit", "Garmin/Courses/Morning_Loop.fit", "Morning Loop", 12345.0, 321,
         now() - 3600),
        ("Straight.fit", "Garmin/Courses/Straight.fit", "Straight Lines", 3408.62, None,
         now() - 7200)]


def test_a_course_of_garmin_connect_and_one_of_nobody_known(drive, clock):
    put(drive, "Garmin/Courses/A.fit", course_fit("Along the River", made=now(),
                                                  product=courses.CONNECT_PRODUCT))
    put(drive, "Garmin/Courses/B.fit", course_fit("By Hand", made=now()))
    put(drive, "Garmin/Courses/C.fit", course_fit("Another Maker", made=now(), manufacturer=255,
                                                  product=courses.CONNECT_PRODUCT))
    seen = courses.overview(device(), LocalStorage(drive))
    assert [(c.name, c.origin) for c in seen.courses] == [
        ("Along the River", "Garmin Connect"), ("By Hand", None), ("Another Maker", None)]


def test_a_file_that_is_no_course_is_listed_with_nothing_said_of_it(drive):
    put(drive, "Garmin/Courses/Broken.fit", b"not a FIT file at all")
    (course,) = courses.overview(device(), LocalStorage(drive)).courses
    assert (course.name, course.distance_m, course.made, course.origin, course.title) == (
        None, None, None, None, "Broken.fit")


def test_only_the_start_of_a_course_is_read_when_its_lap_comes_first(drive, monkeypatch, clock):
    put(drive, "Garmin/Courses/Long.fit", course_fit(made=now(), points=50))
    put(drive, "Garmin/Courses/Late.fit", course_fit("Lap at the End", made=now(), points=50,
                                                     lap_after_points=True))
    monkeypatch.setattr(courses, "START", 200)
    st = LocalStorage(drive)
    whole = []
    real_read = st.read
    monkeypatch.setattr(st, "read", lambda path: whole.append(path) or real_read(path))
    seen = courses.overview(device(), st)
    assert whole == ["Garmin/Courses/Late.fit"]  # its lap was past the start
    assert [(c.name, c.distance_m) for c in seen.courses] == [
        ("Lap at the End", 12345.0), ("Morning Loop", 12345.0)]


def test_a_folder_that_cannot_be_read_is_said_and_the_rest_still_shows(drive):
    class NoCourses(LocalStorage):
        def _list(self, real_path):
            if real_path.endswith("Courses"):
                raise DeviceError("made-up failure")
            return super()._list(real_path)

    put(drive, "Garmin/NewFiles/Loop.gpx", gpx_file(gpx_track()))
    seen = courses.overview(device(), NoCourses(drive))
    assert seen.unreadable == ("courses",)
    assert [w.filename for w in seen.waiting] == ["Loop.gpx"]


# --- where a course came from: openExpress's record ----------------------------------------------


def copy_a_file(drive, tmp_path, body=None, name=None):
    st = LocalStorage(drive)
    plan = courses.plan_add(device(), st, a_gpx(tmp_path, body), name)
    courses.add(plan, device(), st)
    return plan


def test_a_course_the_device_made_of_a_copy_is_openexpress_s(drive, tmp_path, clock):
    copy_a_file(drive, tmp_path)
    put(drive, "Garmin/Courses/Morning_Loop.fit", course_fit(made=now() + 120))
    (course,) = courses.overview(device(), LocalStorage(drive)).courses
    assert course.origin == "openExpress"


@pytest.mark.parametrize("made, name, product", [
    (-3600, "Morning Loop", courses.DEVICE_PRODUCT),  # made an hour before the copy
    (120, "Evening Loop", courses.DEVICE_PRODUCT),  # another name
    (120, "Morning Loop", 12345),  # not made by the device of a file
])
def test_a_course_not_made_of_a_copy_is_not_openexpress_s(drive, tmp_path, clock, made, name,
                                                          product):
    copy_a_file(drive, tmp_path)
    put(drive, "Garmin/Courses/X.fit", course_fit(name, made=now() + made, product=product))
    (course,) = courses.overview(device(), LocalStorage(drive)).courses
    assert course.origin is None


def test_a_name_the_device_cut_still_tells_the_copy(drive, tmp_path, clock):
    copy_a_file(drive, tmp_path, gpx_track("A Long Way Around the Lake"))
    put(drive, "Garmin/Courses/A_Long_Way.fit", course_fit("A Long Way Arou", made=now() + 60))
    (course,) = courses.overview(device(), LocalStorage(drive)).courses
    assert course.origin == "openExpress"


def test_the_other_install_s_copies_count_and_are_never_written(drive, tmp_path, clock):
    other = paths.other_install_dir() / "devices" / str(UNIT) / "courses.json"
    other.parent.mkdir(parents=True)
    other.write_text(json.dumps({"copies": [
        {"file": "Hill.GPX", "courses": ["Up the Hill"], "size": 1, "md5": "0" * 32,
         "copied": now() - 600}]}), encoding="utf-8")
    before = other.read_bytes()
    put(drive, "Garmin/Courses/Hill.fit", course_fit("Up the Hill", made=now() - 60))
    (course,) = courses.overview(device(), LocalStorage(drive)).courses
    assert course.origin == "openExpress"
    copy_a_file(drive, tmp_path)
    courses.remove(courses.plan_remove(device(), LocalStorage(drive), course), device(),
                   LocalStorage(drive))
    assert other.read_bytes() == before


# --- the files waiting and the saved locations --------------------------------------------------


def test_the_gpx_files_waiting_with_what_they_hold(drive):
    put(drive, "Garmin/NewFiles/Morning_Loop.GPX", gpx_file(gpx_track()))
    put(drive, "Garmin/NewFiles/broken.gpx", "<not a gpx file")
    put(drive, "Garmin/NewFiles/Course.fit", b"a course of Garmin Connect waiting")
    seen = courses.overview(device(), LocalStorage(drive))
    assert [(w.filename, w.size > 0, w.course, w.title) for w in seen.waiting] == [
        ("broken.gpx", True, None, "broken.gpx"),
        ("Morning_Loop.GPX", True, "Morning Loop", "Morning Loop")]
    assert seen.waiting[1].gpx.lines[0].points == 3


@pytest.mark.parametrize("files, expected", [
    ({}, 0),
    ({"Locations.fit": locations_fit(0)}, 0),
    ({"Locations.fit": locations_fit(3), "notes.txt": b"x"}, 3),
    ({"Locations.fit": locations_fit(3, cut=60)}, None),  # does not read whole: not known
])
def test_the_saved_locations_are_counted(drive, files, expected):
    for name, data in files.items():
        put(drive, f"Garmin/Locations/{name}", data)
    assert courses.overview(device(), LocalStorage(drive)).locations == expected


def test_a_device_that_declares_no_locations_has_none_known(drive):
    assert courses.overview(device(locations=None), LocalStorage(drive)).locations is None


# --- the plan of a copy --------------------------------------------------------------------------


def test_the_plan_names_the_file_after_the_course_as_the_device_declares_it(drive, tmp_path):
    local = a_gpx(tmp_path)
    plan = courses.plan_add(device(), LocalStorage(drive), local)
    assert (plan.course, plan.name, plan.path, plan.same_waiting) == (
        "Morning Loop", "Morning_Loop.GPX", "Garmin/NewFiles/Morning_Loop.GPX", None)
    assert plan.data == local.read_bytes() and plan.size == local.stat().st_size
    assert courses.plan_add(device(extension="gpx"), LocalStorage(drive), local).name == (
        "Morning_Loop.gpx")
    assert not (drive / "Garmin/NewFiles/Morning_Loop.GPX").exists()  # nothing written


def test_a_name_in_the_folder_is_never_taken(drive, tmp_path):
    put(drive, "Garmin/NewFiles/morning_loop.gpx", "another file")
    plan = courses.plan_add(device(), LocalStorage(drive), a_gpx(tmp_path))
    assert plan.name == "Morning_Loop_2.GPX" and plan.same_waiting is None


def test_the_same_file_waiting_already_is_said(drive, tmp_path):
    local = a_gpx(tmp_path)
    put(drive, "Garmin/NewFiles/Copied_Before.GPX", local.read_bytes())
    plan = courses.plan_add(device(), LocalStorage(drive), local)
    assert plan.same_waiting == "Copied_Before.GPX" and plan.name == "Morning_Loop.GPX"


def test_a_name_entered_is_written_into_the_copy_alone(drive, tmp_path):
    local = a_gpx(tmp_path)
    plan = courses.plan_add(device(), LocalStorage(drive), local, "Pętla nad jeziorem")
    assert (plan.course, plan.name) == ("Pętla nad jeziorem", "Petla_nad_jeziorem.GPX")
    original = local.read_bytes()
    assert plan.data == original.replace(b"Morning Loop", "Pętla nad jeziorem".encode())
    assert plan.courses == ["Pętla nad jeziorem"]


def test_a_track_without_a_name_gets_the_file_s_in_the_copy(drive, tmp_path):
    plan = courses.plan_add(device(), LocalStorage(drive), a_gpx(tmp_path, gpx_track(None)))
    assert plan.course == "morning-loop" and b"<name>morning-loop</name>" in plan.data


def test_a_file_of_several_courses_keeps_its_names(drive, tmp_path):
    body = gpx_track("First") + gpx_track("Second")
    plan = courses.plan_add(device(), LocalStorage(drive), a_gpx(tmp_path, body))
    assert (plan.course, plan.name, plan.courses) == (None, "morning-loop.GPX",
                                                     ["First", "Second"])
    with pytest.raises(CourseError, match="makes 2 courses; only a file with one track"):
        courses.plan_add(device(), LocalStorage(drive), a_gpx(tmp_path, body), "One Name")


def test_a_file_of_waypoints_takes_no_course_name(drive, tmp_path):
    local = a_gpx(tmp_path, gpx_waypoint() + gpx_waypoint("Shelter", 52.1, 13.1), "points.gpx")
    plan = courses.plan_add(device(), LocalStorage(drive), local)
    assert (plan.course, plan.name, plan.courses) == (None, "points.GPX", [])
    with pytest.raises(CourseError, match="has only waypoints"):
        courses.plan_add(device(), LocalStorage(drive), local, "A Name")


def test_what_is_refused_before_the_question(drive, tmp_path, monkeypatch):
    local = a_gpx(tmp_path)
    with pytest.raises(CourseError, match="does not make courses of GPX files"):
        courses.plan_add(device(gpx_folder=None), LocalStorage(drive), local)
    with pytest.raises(CourseFileError, match="is not a GPX file"):
        courses.plan_add(device(), LocalStorage(drive), a_gpx(tmp_path, "<trk>", "bad.gpx"))
    st = LocalStorage(drive)
    monkeypatch.setattr(st, "free_space", lambda: 1000)
    with pytest.raises(CourseError, match="Not enough space"):
        courses.plan_add(device(), st, local)
    (drive / "Garmin/NewFiles").rmdir()
    with pytest.raises(CourseError, match="no folder Garmin/NewFiles"):
        courses.plan_add(device(), LocalStorage(drive), local)


# --- the copy ------------------------------------------------------------------------------------


def test_the_copy_is_written_and_recorded(drive, tmp_path, clock):
    plan = copy_a_file(drive, tmp_path, name="Lake")
    assert (drive / "Garmin/NewFiles/Lake.GPX").read_bytes() == plan.data
    assert courses.recorded(UNIT) == [{"file": "Lake.GPX", "courses": ["Lake"],
                                       "size": plan.size, "md5": plan.md5, "copied": now()}]


def test_a_file_that_appeared_since_the_plan_is_not_overwritten(drive, tmp_path):
    st = LocalStorage(drive)
    plan = courses.plan_add(device(), st, a_gpx(tmp_path))
    put(drive, plan.path, "someone else's")
    with pytest.raises(CourseError, match="already on the device; nothing is overwritten"):
        courses.add(plan, device(), st)
    assert (drive / plan.path).read_text() == "someone else's"
    assert courses.recorded(UNIT) == []


def test_no_copy_while_a_sync_holds_the_lock(drive, tmp_path):
    st = LocalStorage(drive)
    plan = courses.plan_add(device(), st, a_gpx(tmp_path))
    with service.sync_lock(), pytest.raises(service.SyncBusy):
        courses.add(plan, device(), st)
    assert not (drive / plan.path).exists() and courses.recorded(UNIT) == []


def test_a_failed_copy_leaves_nothing(drive, tmp_path):
    class Breaks(LocalStorage):
        """Writes a part of the file, then fails, as a copy over MTP can; and cleans up after
        it as the storage over MTP does."""

        def _write(self, real_path, data):
            (self.root / real_path).write_bytes(data[:10])
            raise DeviceError("made-up failure")

        def _discard_partial(self, real_path):
            (self.root / real_path).unlink(missing_ok=True)

    st = Breaks(drive)
    plan = courses.plan_add(device(), st, a_gpx(tmp_path))
    with pytest.raises(CourseError, match="Writing Garmin/NewFiles/Morning_Loop.GPX failed"):
        courses.add(plan, device(), st)
    assert not (drive / plan.path).exists() and courses.recorded(UNIT) == []


def test_the_names_stay_out_of_the_log(drive, tmp_path, log_file):
    applog.setup("cli")
    copy_a_file(drive, tmp_path, name="Secret Hill")
    courses.overview(device(), LocalStorage(drive))
    log = log_file.read_text()
    assert "a GPX file copied" in log and "Secret" not in log and "morning-loop" not in log


# --- removing ------------------------------------------------------------------------------------


def test_a_course_is_removed_and_its_name_taken_off_the_record(drive, tmp_path, clock):
    copy_a_file(drive, tmp_path)
    (drive / "Garmin/NewFiles/Morning_Loop.GPX").unlink()  # the device made the course of it
    put(drive, "Garmin/Courses/Morning_Loop.fit", course_fit(made=now() + 60))
    st = LocalStorage(drive)
    (course,) = courses.overview(device(), st).courses
    plan = courses.plan_remove(device(), st, course)
    assert (plan.title, plan.waiting, plan.origin) == ("Morning Loop", False, "openExpress")
    courses.remove(plan, device(), st)
    assert not (drive / "Garmin/Courses/Morning_Loop.fit").exists()
    assert courses.recorded(UNIT) == []
    # A course of that name the device makes later of a file copied by hand is nobody's known.
    put(drive, "Garmin/Courses/Morning_Loop.fit", course_fit(made=now() + 3600))
    assert courses.overview(device(), st).courses[0].origin is None


def test_a_waiting_file_is_removed_with_its_record(drive, tmp_path):
    copy_a_file(drive, tmp_path)
    st = LocalStorage(drive)
    (waiting,) = courses.overview(device(), st).waiting
    plan = courses.plan_remove(device(), st, waiting)
    assert (plan.title, plan.waiting) == ("Morning Loop", True)
    courses.remove(plan, device(), st)
    assert not (drive / "Garmin/NewFiles/Morning_Loop.GPX").exists()
    assert courses.recorded(UNIT) == []


def test_a_file_changed_or_gone_since_the_list_is_not_removed(drive, clock):
    put(drive, "Garmin/Courses/A.fit", course_fit("A", made=now()))
    st = LocalStorage(drive)
    (course,) = courses.overview(device(), st).courses
    put(drive, "Garmin/Courses/A.fit", course_fit("A", made=now(), points=9))
    with pytest.raises(CourseError, match="has changed since the list was shown"):
        courses.plan_remove(device(), st, course)
    (course,) = courses.overview(device(), st).courses
    plan = courses.plan_remove(device(), st, course)
    put(drive, "Garmin/Courses/A.fit", course_fit("A", made=now(), points=20))
    with pytest.raises(CourseError, match="has changed since the list was shown"):
        courses.remove(plan, device(), st)
    assert (drive / "Garmin/Courses/A.fit").exists()
    (drive / "Garmin/Courses/A.fit").unlink()
    with pytest.raises(CourseError, match="no longer on the device"):
        courses.plan_remove(device(), st, course)


@pytest.mark.parametrize("shown", [
    courses.Course("../Locations/Locations.fit", "", 10, None, None, None, None, None),
    courses.Course("Locations.fit", "Garmin/Locations/Locations.fit", 10, None, None, None,
                   None, None),  # looked for in the courses folder only
    courses.Course("notes.txt", "Garmin/Courses/notes.txt", 3, None, None, None, None, None),
    courses.Course(".fit", "Garmin/Courses/.fit", 3, None, None, None, None, None),
    courses.Waiting("Course.fit", "Garmin/NewFiles/Course.fit", 3, None),
])
def test_only_a_course_s_file_or_a_waiting_gpx_file_is_ever_removed(drive, shown):
    put(drive, "Garmin/Locations/Locations.fit", locations_fit(2))
    put(drive, "Garmin/Courses/notes.txt", "abc")
    put(drive, "Garmin/Courses/.fit", "abc")
    put(drive, "Garmin/NewFiles/Course.fit", "abc")
    before = sorted(p.relative_to(drive) for p in drive.rglob("*"))
    with pytest.raises(CourseError, match="is not the file of a course|no longer on the device"):
        courses.plan_remove(device(), LocalStorage(drive), shown)
    assert sorted(p.relative_to(drive) for p in drive.rglob("*")) == before


def test_no_removal_while_a_sync_holds_the_lock(drive, clock):
    put(drive, "Garmin/Courses/A.fit", course_fit("A", made=now()))
    st = LocalStorage(drive)
    (course,) = courses.overview(device(), st).courses
    plan = courses.plan_remove(device(), st, course)
    with service.sync_lock(), pytest.raises(service.SyncBusy):
        courses.remove(plan, device(), st)
    assert (drive / "Garmin/Courses/A.fit").exists()
