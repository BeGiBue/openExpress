"""What an activity's page works out itself, on real files of a fēnix 8, against what Garmin
Connect shows for them: the moving time (from the speed of each record) and the average
temperature (from the records). The files and Connect's values are private: they are listed in
testdata/fenix8_expected.json, which is not in the repository, and without the list each test
is skipped. The list:

    {"moving time": [{"file": NAME, "ours": "H:MM:SS", "connect": "H:MM:SS"}, …],
     "temperature": [{"file": NAME, "said": "21.4 °C (18.0–26.0 °C)"}, …]}"""

import json
from pathlib import Path

import pytest

from openexpress import fit

TESTDATA = Path(__file__).resolve().parent.parent / "testdata"
EXPECTED = TESTDATA / "fenix8_expected.json"


def expected(kind: str) -> list[dict]:
    """The cases of the list (none without it)."""
    if not EXPECTED.is_file():
        return []
    return json.loads(EXPECTED.read_text(encoding="utf-8")).get(kind, [])


def ids(cases: list[dict]) -> list[str]:
    return [f"activity {i + 1}" for i in range(len(cases))]


def data_of(name: str):
    path = TESTDATA / name
    if not path.is_file():
        pytest.skip("a file of testdata/fenix8_expected.json is not in testdata/")
    return fit.activity_data(path.read_bytes())


def seconds(clock: str) -> int:
    total = 0
    for part in clock.split(":"):
        total = total * 60 + int(part)
    return total


MOVING, TEMPERATURE = expected("moving time"), expected("temperature")


@pytest.mark.parametrize("case", MOVING, ids=ids(MOVING))
def test_the_moving_time_is_garmin_connect_s(case):
    """Within 1% of Garmin Connect's, which does not say how it works it out; a slow steep
    climb the device records at no speed is no moving for Connect either."""
    from openexpress.gui.activity_chart import moving_time
    from openexpress.gui.words import activity_clock

    moving = moving_time(data_of(case["file"]))
    assert activity_clock(moving) == case["ours"]
    assert abs(moving - seconds(case["connect"])) <= 0.01 * seconds(case["connect"])


@pytest.mark.parametrize("case", TEMPERATURE, ids=ids(TEMPERATURE))
def test_the_temperature_is_garmin_connect_s(case):
    """The session keeps whole degrees; Garmin Connect's average is that of the records."""
    from openexpress.gui.words import activity_detail_kinds

    assert dict(activity_detail_kinds(data_of(case["file"])))["temperature"] == case["said"]
