"""The activities of a connected device and of its backups (activities.py): one list, the
device's files first and newest first, then those only in backups; read N at a time with the
steps of a long task; what each file says kept by its source, path, size and time of change.
A folder stands for the device; the backups are made-up folders as openExpress names them."""

import os

import pytest
from conftest import DEVICE_XML
from fakes import FitData, FitDefinition, fit_file

from openexpress.device.storage import LocalStorage
from openexpress.device.xmldevice import parse

UNIT = 1234567890  # the unit ID of DEVICE_XML
DAY = 86_400
CREATED = 1_100_000_000  # a made-up time, in seconds of the FIT protocol


class CountingStorage(LocalStorage):
    """A folder as a device that counts the files read from it."""

    def __init__(self, root):
        super().__init__(root)
        self.reads = 0

    def _read(self, real_path):
        self.reads += 1
        return super()._read(real_path)


def a_run(day: int, records: int = 1) -> bytes:
    """A made-up run of day `day`; more `records`, a bigger file."""
    return fit_file(
        FitDefinition(0, 0, ((0, 0x00), (4, 0x86))), FitData(0, (4, CREATED + day * DAY)),
        FitDefinition(1, 20, ((253, 0x86),)),
        *(FitData(1, (CREATED + day * DAY + n,)) for n in range(records)),
        FitDefinition(2, 18, ((2, 0x86), (5, 0x00), (9, 0x86))),
        FitData(2, (CREATED + day * DAY, 1, 1_000_000)))


@pytest.fixture
def device(tmp_path):
    """A device with no activity yet: (its folder, its storage, its GarminDevice.xml)."""
    root = tmp_path / "device"
    (root / "GARMIN" / "Activity").mkdir(parents=True)
    (root / "GARMIN" / "GarminDevice.xml").write_text(DEVICE_XML)
    storage = CountingStorage(root)
    xml = parse(storage.read("GARMIN/GarminDevice.xml"))
    storage.reads = 0  # only the activities counted
    return root, storage, xml


@pytest.fixture
def backups(tmp_path):
    return tmp_path / "Backups"


def on_device(root, name: str, data: bytes, changed: int):
    path = root / "GARMIN" / "Activity" / name
    path.write_bytes(data)
    os.utime(path, (changed, changed))
    return path


def in_backup(backups, stamp: str, name: str, data: bytes):
    folder = backups / str(UNIT) / stamp / "FIT_TYPE_4"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)
    return folder.parent


def listed(device, backups):
    from openexpress import activities

    _root, storage, xml = device
    found = activities.DeviceActivities(xml, storage, backups)
    found.list_files()
    return found


def where(found) -> list[tuple[str, str]]:
    return [(a.source.value, a.name) for a in found.listing]


def test_the_device_s_copy_comes_first_and_once(device, backups):
    root = device[0]
    on_device(root, "2026-10-02.fit", a_run(2), 2_000)
    in_backup(backups, "2026-10-03 (10.00.00)", "2026-10-02.fit", a_run(2))
    assert where(listed(device, backups)) == [("device", "2026-10-02.fit")]


def test_files_only_in_backups_come_after_those_on_the_device(device, backups):
    root = device[0]
    on_device(root, "2026-10-05.fit", a_run(5), 5_000)
    on_device(root, "2026-10-04.fit", a_run(4), 4_000)
    in_backup(backups, "2026-09-01 (10.00.00)", "2026-08-01.fit", a_run(-60))
    in_backup(backups, "2026-10-01 (10.00.00)", "2026-09-20.fit", a_run(-10))
    in_backup(backups, "2026-10-01 (10.00.00)", "2026-09-21.fit", a_run(-9))
    assert where(listed(device, backups)) == [
        ("device", "2026-10-05.fit"), ("device", "2026-10-04.fit"),
        # the newest backup first, and in it the newest name first
        ("backup", "2026-09-21.fit"), ("backup", "2026-09-20.fit"), ("backup", "2026-08-01.fit")]


def test_a_file_in_several_backups_is_listed_once_from_the_newest(device, backups):
    in_backup(backups, "2026-09-01 (10.00.00)", "2026-08-01.fit", a_run(-60))
    newest = in_backup(backups, "2026-10-01 (10.00.00)", "2026-08-01.fit", a_run(-60))
    found = listed(device, backups)
    assert where(found) == [("backup", "2026-08-01.fit")]
    assert found.listing[0].path == str(newest / "FIT_TYPE_4" / "2026-08-01.fit")
    assert found.listing[0].backup.strftime("%Y-%m-%d") == "2026-10-01"


def test_a_symbolic_link_to_a_backup_is_skipped(device, backups, tmp_path):
    elsewhere = in_backup(tmp_path / "elsewhere", "2026-10-01 (10.00.00)", "2026-09-20.fit",
                          a_run(-10))
    (backups / str(UNIT)).mkdir(parents=True)
    (backups / str(UNIT) / "2026-10-02 (10.00.00)").symlink_to(elsewhere, target_is_directory=True)
    # and a link to a file outside a backup, inside a real one
    real = in_backup(backups, "2026-10-03 (10.00.00)", "2026-09-22.fit", a_run(-8))
    (real / "FIT_TYPE_4" / "2026-09-23.fit").symlink_to(elsewhere / "FIT_TYPE_4" / "2026-09-20.fit")
    assert where(listed(device, backups)) == [("backup", "2026-09-22.fit")]


def test_the_same_name_with_another_size_is_one_activity_from_the_device(device, backups):
    root = device[0]
    on_device(root, "2026-10-02.fit", a_run(2, records=5), 2_000)
    in_backup(backups, "2026-10-03 (10.00.00)", "2026-10-02.FIT", a_run(2, records=1))
    found = listed(device, backups)
    assert where(found) == [("device", "2026-10-02.fit")]
    assert found.listing[0].size == len(a_run(2, records=5))


def test_the_same_name_in_two_backups_with_another_size_is_one_activity_from_the_newest(
        device, backups):
    in_backup(backups, "2026-09-01 (10.00.00)", "2026-08-01.fit", a_run(-60, records=1))
    newest = in_backup(backups, "2026-10-01 (10.00.00)", "2026-08-01.fit", a_run(-60, records=5))
    found = listed(device, backups)
    assert where(found) == [("backup", "2026-08-01.fit")]
    assert found.listing[0].path == str(newest / "FIT_TYPE_4" / "2026-08-01.fit")


def test_reading_tells_its_steps(device, backups):
    root = device[0]
    for day in (1, 2, 3):
        on_device(root, f"2026-10-0{day}.fit", a_run(day), day * 1_000)
    said = []
    read = listed(device, backups).read_next(progress=said.append)
    assert len(read) == 3
    assert "Reading activities · 2 of 3" in said
    assert said[-1] == "Reading activities · 3 of 3"


def test_what_was_read_is_not_read_again(device, backups):
    root, storage, _xml = device
    for day in (1, 2, 3):
        on_device(root, f"2026-10-0{day}.fit", a_run(day), day * 1_000)
    found = listed(device, backups)
    first = found.read_next()
    assert storage.reads == 3
    found.list_files()  # as Refresh does
    again = found.read_next()
    assert storage.reads == 3
    assert [r.summary for r in again] == [r.summary for r in first]
    # A file whose time of change is another is another file: read again.
    on_device(root, "2026-10-02.fit", a_run(2), 9_000)
    found.list_files()
    found.read_next()
    assert storage.reads == 4


def test_n_at_a_time(device, backups):
    root, storage, _xml = device
    for day in range(1, 6):
        on_device(root, f"2026-10-0{day}.fit", a_run(day), day * 1_000)
    found = listed(device, backups)
    batches = [[r.activity.name for r in found.read_next(count=2)] for _batch in range(4)]
    assert batches == [["2026-10-05.fit", "2026-10-04.fit"], ["2026-10-03.fit", "2026-10-02.fit"],
                       ["2026-10-01.fit"], []]
    assert storage.reads == 5
    assert [r.activity.name for r in found.read] == [f"2026-10-0{d}.fit" for d in (5, 4, 3, 2, 1)]
    assert found.left == 0


def test_thirty_at_a_time_unless_told(device, backups):
    from openexpress import activities

    root = device[0]
    for n in range(32):
        on_device(root, f"2026-09-{n:02}.fit", a_run(n), 1_000 + n)
    found = listed(device, backups)
    assert activities.PAGE == 30
    assert len(found.read_next()) == 30
    assert found.left == 2


def test_each_read_says_what_its_file_says(device, backups):
    from openexpress import fit

    root = device[0]
    on_device(root, "2026-10-02.fit", a_run(2), 2_000)
    on_device(root, "2026-10-01.fit", b"not a FIT file", 1_000)
    in_backup(backups, "2026-10-03 (10.00.00)", "2026-09-01.fit", a_run(-30)[:-20])
    read = listed(device, backups).read_next()
    assert [r.summary.sport if r.summary else None for r in read] == [1, None, None]
    assert read[1].summary is None  # no FIT file: nothing it says
    assert read[2].summary.state is fit.FileState.STILL_BEING_WRITTEN


def test_a_device_that_declares_no_activities_keeps_none(device):
    from openexpress import activities
    from openexpress.device.xmldevice import parse as parse_xml

    _root, _storage, xml = device
    assert activities.keeps_activities(xml)
    without = DEVICE_XML.replace("<Name>FIT_TYPE_4</Name>", "<Name>FIT_TYPE_999</Name>")
    assert not activities.keeps_activities(parse_xml(without.encode()))


def test_the_names_of_sports():
    from openexpress import activities

    assert activities.sport_name(1) == "Running"
    assert activities.sport_name(62) == "HIIT"
    assert activities.sport_name(0) == activities.sport_name(None) == "Activity"
    assert activities.sport_name(99) == "Sport 99"
