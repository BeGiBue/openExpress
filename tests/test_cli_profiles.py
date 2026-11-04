"""The commands profiles and profiles show: the device's sport profiles and the data screens of
one, read only; what is not known said by its number. All profiles here are made up."""

import pytest
from fakes import ScreenRecord, sport_file

from openexpress.cli import main

SPORTS = ("<DataType><Name>FIT_TYPE_3</Name><File><Location><Path>Garmin/Sports</Path>"
          "<FileExtension>FIT</FileExtension></Location>"
          "<TransferDirection>OutputFromUnit</TransferDirection></File></DataType>")
RUN = (ScreenRecord(place=0, code=0, order=0, fields=(56, 6, 999, None), variant=2),
       ScreenRecord(place=1, code=110, order=1, variant=12),
       ScreenRecord(place=2, code=127, state=0, order=None, fields=(127,)),
       ScreenRecord(place=3, code=1, state=0, order=None, fields=(9,), variant=1))
ROAD = (ScreenRecord(place=0, code=0, order=0, fields=(48, 6), variant=1),
        ScreenRecord(place=1, code=104, order=1), ScreenRecord(place=2, code=35, hidden=1,
                                                               order=2),
        ScreenRecord(place=3, code=32, state=0))


@pytest.fixture
def profiles_root(device_root):
    xml = device_root / "GARMIN" / "GarminDevice.xml"
    text = xml.read_text()
    assert text.count("</MassStorageMode>") == 1
    xml.write_text(text.replace("</MassStorageMode>", SPORTS + "</MassStorageMode>"))
    sports = device_root / "GARMIN" / "Sports"
    sports.mkdir()
    (sports / "Run.fit").write_bytes(sport_file("Run", screens=RUN))
    (sports / "Road.fit").write_bytes(sport_file("Road", 2, screens=ROAD, shape="edge"))
    (sports / "Trail Run.fit").write_bytes(sport_file("Trail Run", screens=RUN[:1]))
    (sports / "Broken.fit").write_bytes(b"no FIT")
    return device_root


def tree(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file()}


def test_the_list(profiles_root, capsys):
    before = tree(profiles_root)
    assert main(["--path", str(profiles_root), "profiles"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[:4] == ["3 profiles:", "  Road · 1 data screen · 1 built-in screen",  # Compass is hidden
                       "  Run · 1 data screen · 1 built-in screen",
                       "  Trail Run · 1 data screen"]
    assert out[4].startswith("  Broken.fit: The file of this profile could not be read")
    assert tree(profiles_root) == before  # nothing is written


def test_a_watch_profile_s_screens(profiles_root, capsys):
    assert main(["--path", str(profiles_root), "profiles", "show", "run"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Run",
        "Data screens, in the order the device scrolls through them:",
        ("  1. Screen 1 · 4 fields · Layout “Stack”: Timer, Distance, Field 999, "
         "Empty field"),
        "  2. Built-in screen 110",
        "Built-in screens:",
        "  Built-in screen 110: on",
        "  Built-in screen 127: off",
        "Screens turned off:",
        "  Screen 2 · 1 field · Layout “No Labels”: Elevation",
        ("The fields are named as Garmin's Edge devices number them; the codes of some of this "
         "device's layouts and built-in screens are not known to openExpress yet."),
    ]


def test_an_edge_profile_s_screens(profiles_root, capsys):
    assert main(["--path", str(profiles_root), "profiles", "show", "ROAD"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Road",
        "Data screens, in the order the device scrolls through them:",
        "  1. Screen 1 · 2 fields · Layout B: Speed, Distance",
        "  2. ClimbPro",
        "Built-in screens:",
        "  Compass: hidden",
        "  ClimbPro: on",
    ]


@pytest.mark.parametrize("name, said", [
    ("trail", None), ("ru", "Profiles that match “ru”: Run, Trail Run"),
    ("swim", "No profile is named “swim”."),
])
def test_the_name_of_a_profile(profiles_root, capsys, name, said):
    code = main(["--path", str(profiles_root), "profiles", "show", name])
    captured = capsys.readouterr()
    if said is None:
        assert code == 0 and captured.out.startswith("Trail Run\n")
    else:
        assert code == 1 and said in captured.err


def test_a_device_without_profiles(device_root, capsys):
    assert main(["--path", str(device_root), "profiles"]) == 1
    assert "This device keeps no activity profiles." in capsys.readouterr().err
