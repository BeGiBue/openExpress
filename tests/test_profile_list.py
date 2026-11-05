"""The profiles of the open device (profiles.ProfileList): its Sports folder as its
GarminDevice.xml declares it, every file read once and kept by its path, size and time of change,
a file that cannot be read said as such, and the profiles of the newest activities first (the
name an activity file gives its profile). All files here are made up."""

import os

import pytest
from fakes import FitData, FitDefinition, ScreenRecord, backup_of_a_profile, fit_file, sport_file

from openexpress import fit, profiles
from openexpress.device.storage import DeviceError, LocalStorage
from openexpress.device.xmldevice import parse


def device(sports="Garmin/Sports"):
    """A made-up device; `sports`: the folder it declares for its sport profiles (None:
    none)."""
    types = [("FIT_TYPE_4", "Garmin/Activity", "OutputFromUnit")]
    if sports:
        types += [("FIT_TYPE_3", sports, "OutputFromUnit"),
                  ("FIT_TYPE_3", "Garmin/NewFiles", "InputToUnit")]
    files = "".join(
        f"<DataType><Name>{name}</Name><File><Location><Path>{path}</Path>"
        f"<FileExtension>FIT</FileExtension></Location>"
        f"<TransferDirection>{direction}</TransferDirection></File></DataType>"
        for name, path, direction in types)
    return parse(f"""<?xml version="1.0" encoding="UTF-8"?>
<Device xmlns="http://www.garmin.com/xmlschemas/GarminDevice/v2">
 <Model><PartNumber>006-B9999-00</PartNumber><SoftwareVersion>100</SoftwareVersion>
  <Description>Made-up watch</Description></Model>
 <Id>3000000071</Id>
 <MassStorageMode>{files}</MassStorageMode>
</Device>
""".encode())


SCREEN = (ScreenRecord(place=0, code=0, order=0, fields=(56, 6)),)


@pytest.fixture
def root(tmp_path):
    sports = tmp_path / "GARMIN" / "Sports"  # the device's own letter case
    sports.mkdir(parents=True)
    (sports / "Run.fit").write_bytes(sport_file("Run", screens=SCREEN))
    (sports / "Bike.fit").write_bytes(sport_file("Bike", 2, screens=SCREEN))
    (sports / "Hike.fit").write_bytes(sport_file("Hike", 17, screens=SCREEN))
    (sports / "notes.txt").write_text("no profile")
    return tmp_path


class Counting(LocalStorage):
    def __init__(self, root):
        super().__init__(root)
        self.reads = []

    def read_at(self, real_path):
        self.reads.append(real_path)
        return super().read_at(real_path)


def test_the_profiles_of_the_device_by_name(root):
    storage = Counting(root)
    found = profiles.ProfileList(device(), storage).read_all()
    assert [f.profile.name for f in found] == ["Bike", "Hike", "Run"]
    assert all(f.error is None for f in found) and len(storage.reads) == 3
    assert {f.name for f in found} == {"Bike.fit", "Hike.fit", "Run.fit"}


def test_the_profiles_are_sorted_with_letter_case_and_diacritics_aside(root):
    sports = root / "GARMIN" / "Sports"
    (sports / "C.fit").write_bytes(sport_file("Ćwiczenia siłowe", 10, screens=SCREEN))
    (sports / "L.fit").write_bytes(sport_file("łyżwy", 13, screens=SCREEN))
    found = profiles.ProfileList(device(), Counting(root)).read_all()
    assert [f.profile.name for f in found] == ["Bike", "Ćwiczenia siłowe", "Hike", "łyżwy",
                                               "Run"]
    assert profiles.sort_key("Ćwiczenia ŁYŻWY") == "cwiczenia lyzwy"


def test_each_file_is_read_once_and_again_when_it_changed(root):
    storage = Counting(root)
    listing = profiles.ProfileList(device(), storage)
    listing.read_all()
    listing.read_all()
    assert len(storage.reads) == 3
    run = root / "GARMIN" / "Sports" / "Run.fit"
    run.write_bytes(sport_file("Run again", screens=SCREEN))
    os.utime(run, (1_800_000_000, 1_800_000_000))
    names = [f.profile.name for f in listing.read_all()]
    assert len(storage.reads) == 4 and "Run again" in names


def test_a_file_that_is_no_profile_is_said_and_the_others_read(root):
    (root / "GARMIN" / "Sports" / "Broken.fit").write_bytes(b"not a FIT file")
    found = profiles.ProfileList(device(), Counting(root)).read_all()
    (broken,) = [f for f in found if f.profile is None]
    assert broken.name == "Broken.fit" and "could not be read" in broken.error
    assert len(found) == 4 and found[-1] is broken  # after the profiles


def test_the_device_s_own_backups_are_no_profiles(root):
    """An Edge keeps copies of its profiles in Sports/Backups (FIT type 57): they are neither
    profiles nor files that are no profile, and the list keeps only when the newest was made.
    The files of other folders below Sports are none of the profiles' either."""
    backups = root / "GARMIN" / "Sports" / "Backups"
    backups.mkdir()
    for name, when in (("Run.fit", 1_700_000_000), ("Bike.fit", 1_700_086_400)):
        (backups / name).write_bytes(backup_of_a_profile())
        os.utime(backups / name, (when, when))
    (root / "GARMIN" / "Sports" / "Other").mkdir()
    (root / "GARMIN" / "Sports" / "Other" / "Odd.fit").write_bytes(b"no profile")
    found = profiles.ProfileList(device(), LocalStorage(root))
    files = found.read_all()
    assert sorted(f.path.split("/", 2)[2] for f in files) == ["Bike.fit", "Hike.fit", "Run.fit"]
    assert found.backup_time == 1_700_086_400


def test_without_backups_the_list_says_none(root):
    found = profiles.ProfileList(device(), LocalStorage(root))
    found.read_all()
    assert found.backup_time is None


def test_the_steps_of_the_reading(root):
    steps = []
    profiles.ProfileList(device(), Counting(root)).read_all(progress=steps.append)
    assert steps == [f"Reading profiles\u00a0· {n} of 3" for n in (1, 2, 3)]


def test_a_device_without_profiles(root):
    assert not profiles.keeps_profiles(device(sports=None))
    assert profiles.keeps_profiles(device())
    assert profiles.ProfileList(device(sports=None), Counting(root)).read_all() == []


def test_an_error_of_the_device_stops_the_reading(root):
    class Failing(Counting):
        def read_at(self, real_path):
            raise DeviceError("made up")

    with pytest.raises(DeviceError):
        profiles.ProfileList(device(), Failing(root)).read_all()


def test_nothing_is_written(root):
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    profiles.ProfileList(device(), Counting(root)).read_all()
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


# --- the profiles of the newest activities ---------------------------------------------------


def activity(start, profile=None):
    """A made-up activity file with a session started at `start` (FIT time) and, when given,
    the name of its profile in its sport message."""
    msgs = [FitDefinition(0, 0, ((0, 0x00), (4, 0x86))), FitData(0, (4, start)),
            FitDefinition(1, 18, ((2, 0x86), (5, 0x00), (7, 0x86), (8, 0x86))),
            FitData(1, (start, 1, 600_000, 600_000))]
    if profile is not None:
        msgs += [FitDefinition(2, 12, ((3, 0x07, 32), (0, 0x00))), FitData(2, (profile, 1))]
    return fit_file(*msgs)


def test_an_activity_names_its_profile():
    assert fit.summary(activity(1_100_000_000, "Trail Run")).profile == "Trail Run"
    assert fit.summary(activity(1_100_000_000)).profile is None


def test_the_profiles_of_the_newest_activities_come_first():
    summaries = [fit.summary(activity(t, name)) for t, name in (
        (1_100_000_000, "Run"), (1_100_300_000, "Hike"), (1_100_200_000, "Run"),
        (1_100_100_000, None), (1_100_400_000, "Bike"))]
    assert profiles.recent_names(summaries) == ["Bike", "Hike", "Run"]
    assert profiles.recent_names(summaries, limit=2) == ["Bike", "Hike"]
    assert profiles.recent_names([None]) == []  # an activity that could not be read
