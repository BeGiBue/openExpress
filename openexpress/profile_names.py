"""The names of what a sport profile's data screens show (profiles.py): their data fields,
their built-in screens and the layouts of their own screens, in the window's language. The
names are Garmin's own words, from the Data Fields pages of its manuals (the Edge 1050's above
all; the fēnix 8's and the Edge 530's for a few fields the Edge 1050 has not), English as the
msgid and Polish in po/pl.po, a watch's in Polish as Garmin Connect shows them for a fēnix 8;
a number nobody has named is shown as a number.

The numbers of the data fields follow the table of Activity Profile Editor
(https://github.com/fullcarbonbike/Activity-Profile-Editor), which learnt them on Edge bike
computers; a watch's profiles give the same numbers to the same fields (a fēnix 8's profile set
to a dozen of them holds each under its number). The few fields of a watch the table has not
(pace, ambient pressure, its charts and gauges) have the numbers its profiles gave them, and a
watch names two numbers its own way (77, 97). Its notice:

    MIT License

    Copyright (c) 2026 Doug (fullcarbonbike)

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.

Garmin's manuals give one "Time in Zone" field for every zone; the table has one number for
each heart-rate and power zone, named here with its zone."""

from __future__ import annotations

from openexpress.i18n import _, pgettext

# The number of a Connect IQ data field: which app it shows is said elsewhere in the file.
CONNECT_IQ_FIELD = 216

# The fields of the time in one zone: (kind, zone).
_ZONES = {
    **{number: ("heart rate", zone) for zone, number in enumerate(range(199, 204), 1)},
    **{number: ("power", zone) for zone, number in enumerate(range(207, 214), 1)},
    418: ("power", 8), 419: ("power", 9),
}


def _field_names() -> dict[int, str]:
    """The names of the data fields by their numbers, in the window's language."""
    return {
        0: pgettext("data field", "Calories"),
        2: pgettext("data field", "Course Pt. Distance"),
        3: pgettext("data field", "Cadence"),
        4: pgettext("data field", "Avg Cadence"),
        5: pgettext("data field", "Lap Cadence"),
        6: pgettext("data field", "Distance"),
        7: pgettext("data field", "Lap Distance"),
        9: pgettext("data field", "Elevation"),
        11: pgettext("data field", "Grade"),
        12: pgettext("data field", "Heading"),
        13: pgettext("data field", "Heart Rate"),
        14: pgettext("data field", "Avg Heart Rate"),
        15: pgettext("data field", "Lap Heart Rate"),
        16: pgettext("data field", "%Max Heart Rate"),
        17: pgettext("data field", "Avg %Max Heart Rate"),
        18: pgettext("data field", "Lap %Max Heart Rate"),
        19: pgettext("data field", "%Heart Rate Reserve"),
        20: pgettext("data field", "Avg %HRR"),
        21: pgettext("data field", "Lap %HRR"),
        22: pgettext("data field", "Heart Rate Zone"),
        23: pgettext("data field", "HR Zone Bar"),
        24: pgettext("data field", "Laps"),
        27: pgettext("data field", "Distance to Destination"),
        28: pgettext("data field", "Time to Destination"),
        29: pgettext("data field", "Distance to Next"),
        30: pgettext("data field", "Time to Next"),
        31: pgettext("data field", "Destination Location"),
        32: pgettext("data field", "Next Waypoint"),
        33: pgettext("data field", "Pace"),
        34: pgettext("data field", "Average Pace"),
        35: pgettext("data field", "Lap Pace"),
        51: pgettext("data field", "SOG"),
        36: pgettext("data field", "Power"),
        37: pgettext("data field", "Avg Power"),
        38: pgettext("data field", "Kilojoules"),
        39: pgettext("data field", "Lap Power"),
        40: pgettext("data field", "Max. Power"),
        41: pgettext("data field", "Max. Lap Power"),
        42: pgettext("data field", "%FTP"),
        43: pgettext("data field", "Power Zone"),
        45: pgettext("data field", "Workout Step"),
        48: pgettext("data field", "Speed"),
        49: pgettext("data field", "Avg Speed"),
        50: pgettext("data field", "Lap Speed"),
        53: pgettext("data field", "Sunrise"),
        54: pgettext("data field", "Sunset"),
        55: pgettext("data field", "Elapsed Time"),
        56: pgettext("data field", "Timer"),
        57: pgettext("data field", "Avg Lap Time"),
        58: pgettext("data field", "Lap Time"),
        59: pgettext("data field", "Time of Day"),
        60: pgettext("data field", "Total Ascent"),
        61: pgettext("data field", "Total Descent"),
        62: pgettext("data field", "Distance Ahead"),
        63: pgettext("data field", "Time Ahead"),
        64: pgettext("data field", "Calories to Go"),
        65: pgettext("data field", "Distance to Go"),
        66: pgettext("data field", "Heart Rate to Go"),
        67: pgettext("data field", "Reps to Go"),
        68: pgettext("data field", "Time to Go"),
        77: pgettext("data field", "VAM"),
        78: pgettext("data field", "Temperature"),
        79: pgettext("data field", "3s Power"),
        80: pgettext("data field", "30s Power"),
        81: pgettext("data field", "Normalized Power"),
        82: pgettext("data field", "TSS"),
        83: pgettext("data field", "Intensity Factor"),
        84: pgettext("data field", "Last Lap Distance"),
        86: pgettext("data field", "Last Lap Speed"),
        87: pgettext("data field", "Last Lap Time"),
        88: pgettext("data field", "30s VAM"),
        91: pgettext("data field", "Max. Speed"),
        93: pgettext("data field", "ETA at Destination"),
        94: pgettext("data field", "ETA at Next"),
        95: pgettext("data field", "Odometer"),
        96: pgettext("data field", "Battery Level"),
        97: pgettext("data field", "GPS Signal Strength"),
        98: pgettext("data field", "Watts/kg"),
        99: pgettext("data field", "Aerobic Training Effect"),
        100: pgettext("data field", "Last Lap Power"),
        146: pgettext("data field", "10s Power"),
        147: pgettext("data field", "Lap NP"),
        148: pgettext("data field", "Last Lap NP"),
        149: pgettext("data field", "Balance"),
        150: pgettext("data field", "Avg Balance"),
        151: pgettext("data field", "Lap Balance"),
        159: pgettext("data field", "3s Balance"),
        160: pgettext("data field", "10s Balance"),
        161: pgettext("data field", "30s Balance"),
        165: pgettext("data field", "Last Lap Heart Rate"),
        176: pgettext("data field", "Pedal Smoothness"),
        177: pgettext("data field", "Torque Effectiveness"),
        178: pgettext("data field", "Gears"),
        179: pgettext("data field", "Front Gear"),
        180: pgettext("data field", "Rear Gear"),
        181: pgettext("data field", "Gear Battery"),
        182: pgettext("data field", "Gear Ratio"),
        205: pgettext("data field", "Stroke Rate"),
        214: pgettext("data field", "24-Hour Maximum Temperature"),
        215: pgettext("data field", "24-Hour Minimum Temperature"),
        220: pgettext("data field", "Avg. Vertical Descent Speed"),
        223: pgettext("data field", "Lap Ascent"),
        224: pgettext("data field", "Lap Descent"),
        228: pgettext("data field", "Maximum Elevation"),
        231: pgettext("data field", "Ambient Pressure"),
        240: pgettext("data field", "Location"),
        245: pgettext("data field", "Active Calories"),
        257: pgettext("data field", "Time Standing"),
        258: pgettext("data field", "Lap Time Standing"),
        259: pgettext("data field", "Time Seated"),
        260: pgettext("data field", "Lap Time Seated"),
        263: pgettext("data field", "Platform Center Offset"),
        264: pgettext("data field", "Avg PCO"),
        265: pgettext("data field", "Lap PCO"),
        266: pgettext("data field", "Right Power Phase"),
        267: pgettext("data field", "Avg Right Pwr Phase"),
        268: pgettext("data field", "Lap Right Pwr Phase"),
        269: pgettext("data field", "Right Peak Pwr Phase"),
        270: pgettext("data field", "Avg R. Peak Pwr Phase"),
        271: pgettext("data field", "Lap R. Peak Pwr Phase"),
        272: pgettext("data field", "Left Power Phase"),
        273: pgettext("data field", "Avg Left Pwr Phase"),
        274: pgettext("data field", "Lap Left Pwr Phase"),
        275: pgettext("data field", "Left Peak Pwr Phase"),
        276: pgettext("data field", "Avg L. Peak Pwr Phase"),
        277: pgettext("data field", "Lap L. Peak Pwr Phase"),
        294: pgettext("data field", "Trainer Resistance"),
        295: pgettext("data field", "Target Power"),
        302: pgettext("data field", "Step Distance"),
        316: pgettext("data field", "Lights Connected"),
        317: pgettext("data field", "Battery Status"),
        318: pgettext("data field", "Beam Angle Status"),
        319: pgettext("data field", "Light Mode"),
        320: pgettext("data field", "Performance Condition"),
        343: pgettext("data field", "Heart Rate Graph"),
        344: pgettext("data field", "Speed Graph"),
        345: pgettext("data field", "Cadence Graph"),
        346: pgettext("data field", "3s Power Graph"),
        347: pgettext("data field", "Heart Rate Bars"),
        348: pgettext("data field", "Speed Bars"),
        349: pgettext("data field", "Cadence Bars"),
        350: pgettext("data field", "3s Power Bar"),
        # Two values in one place, named as the table names them
        351: pgettext("data field", "Heart Rate (Avg/Max)"),
        352: pgettext("data field", "Speed (Avg/Max)"),
        353: pgettext("data field", "Cadence (Avg/Max)"),
        354: pgettext("data field", "Power (Avg/Max)"),
        358: pgettext("data field", "Elevation (Asc/Desc)"),
        368: pgettext("data field", "Elevation Graph"),
        371: pgettext("data field", "SOG"),
        395: pgettext("data field", "Battery Hours"),
        408: pgettext("data field", "Di2 Battery Level"),
        409: pgettext("data field", "Gear Combo"),
        411: pgettext("data field", "Di2 Shift Mode"),
        433: pgettext("data field", "Anaerobic Training Effect"),
        437: pgettext("data field", "Avg Watts/kg"),
        438: pgettext("data field", "Lap Watts/kg"),
        439: pgettext("data field", "3s Watts/kg"),
        440: pgettext("data field", "10s Watts/kg"),
        441: pgettext("data field", "30s Watts/kg"),
        442: pgettext("data field", "Lap VAM"),
        443: pgettext("data field", "Avg VAM"),
        444: pgettext("data field", "Ascent Remaining"),
        445: pgettext("data field", "Asc. to Next Course Pt."),
        452: pgettext("data field", "Respiration Rate"),
        478: pgettext("data field", "Load"),
        486: pgettext("data field", "Grit"),
        487: pgettext("data field", "Lap Grit"),
        488: pgettext("data field", "Flow"),
        489: pgettext("data field", "Lap Flow"),
        491: pgettext("data field", "Assist Mode"),
        492: pgettext("data field", "Shifting Advice"),
        493: pgettext("data field", "eBike Battery"),
        494: pgettext("data field", "Travel Range"),
        495: pgettext("data field", "60s Grit"),
        497: pgettext("data field", "60s Flow"),
        511: pgettext("data field", "Workout Comparison"),
        520: pgettext("data field", "Primary Target"),
        521: pgettext("data field", "Target"),
        522: pgettext("data field", "Duration"),
        523: pgettext("data field", "Step Time"),
        529: pgettext("data field", "Compass"),
        530: pgettext("data field", "Training Effect Gauge"),
        531: pgettext("data field", "Total Ascent/Descent Gauge"),
        578: pgettext("data field", "Secondary Target"),
        579: pgettext("data field", "Smart Travel Range"),
        580: pgettext("data field", "Potential"),
        581: pgettext("data field", "Stamina"),
        582: pgettext("data field", "Estimated Distance"),
        583: pgettext("data field", "Estimated Time"),
        586: pgettext("data field", "Elevation Chart"),
        588: pgettext("data field", "Heart Rate Chart"),
        590: pgettext("data field", "Speed Chart"),
        595: pgettext("data field", "Dist. to Point"),
        596: pgettext("data field", "Time to Point"),
        610: pgettext("data field", "Heart Rate Zones Ratio"),
        654: pgettext("data field", "Segment Time"),
        725: pgettext("data field", "Map"),
        786: pgettext("data field", "Vertical Descent Speed"),
        787: pgettext("data field", "30s Vertical Descent Speed"),
        788: pgettext("data field", "Lap Vertical Descent Speed"),
        847: pgettext("data field", "Avg Force"),
        848: pgettext("data field", "Lap Force"),
        849: pgettext("data field", "Max. Force"),
        850: pgettext("data field", "Max. Lap Force"),
        851: pgettext("data field", "3s Force"),
        852: pgettext("data field", "10s Force"),
        853: pgettext("data field", "30s Force"),
        854: pgettext("data field", "Last Lap Force"),
        856: pgettext("data field", "Normalized Force"),
        857: pgettext("data field", "Lap Norm. Force"),
        858: pgettext("data field", "Last Lap Norm. Force"),
        860: pgettext("data field", "Force"),
    }


# The numbers a watch gives a field of its own, named as the fēnix 8's manual and Garmin Connect
# name them on a watch.
def _watch_names() -> dict[int, str]:
    return {
        77: pgettext("data field", "Vertical Speed"),
        97: pgettext("data field", "GPS"),
    }


def known_field(number: int) -> bool:
    """Whether the field of this number has a name of Garmin's here."""
    return number in _field_names() or number in _ZONES or number == CONNECT_IQ_FIELD


def field_name(number: int | None, edge: bool = True) -> str:
    """The name of a data field, on an Edge or on a watch (`edge` False); an empty place of a
    screen and a number nobody has named are said as such."""
    if number is None:
        # TRANSLATORS: a place of a data screen with no data field in it
        return _("Empty field")
    if number == CONNECT_IQ_FIELD:
        return _("Connect IQ data field")
    zone = _ZONES.get(number)
    if zone is not None:
        kind, n = zone
        if kind == "heart rate":
            return _("Time in Heart Rate Zone {zone}").format(zone=n)
        return _("Time in Power Zone {zone}").format(zone=n)
    name = (None if edge else _watch_names().get(number)) or _field_names().get(number)
    if name is not None:
        return name
    # TRANSLATORS: a data field openExpress has no name for, by its number in the profile file
    return _("Field {number}").format(number=number)


# --- the screens of a profile ----------------------------------------------------------------


def edge_shaped(profile) -> bool:
    """Whether the file is in the shape of an Edge's (it says which screens are hidden): the
    codes and layouts of the Edge bike computers are known; of a watch's, some built-in screens
    and layouts."""
    return profile.has_hidden_flag


def own_titles(profile) -> dict[int, str]:
    """The titles of the screens of one's own, by their place in the table: "Screen 1, 2…" in
    the order the device scrolls through them, then those turned off."""
    own = [s for s in profile.carousel() if s.own]
    own += [s for s in profile.own_screens() if s not in own]
    # TRANSLATORS: a data screen of one's own, by its order on the device
    return {s.place: _("Screen {number}").format(number=n) for n, s in enumerate(own, 1)}


def screen_title(profile, screen) -> str:
    if screen.own:
        return own_titles(profile).get(screen.place, "")
    return built_in_name(screen, edge_shaped(profile))


# --- built-in screens and layouts -----------------------------------------------------------
#
# The codes of an Edge's built-in screens, as the two open projects learnt them on Edge bike
# computers; named with Garmin's words for them in its manuals where it has them (a compass,
# an elevation and a lap summary screen it names nowhere: by what they show). A watch's codes
# are not known: its built-in screens are said by their numbers.


def _edge_screen_names() -> dict[int, str]:
    return {
        25: pgettext("built-in screen", "Map"),
        26: pgettext("built-in screen", "Virtual Partner"),
        30: pgettext("built-in screen", "Music Controls"),
        35: pgettext("built-in screen", "Compass"),
        38: pgettext("built-in screen", "Workout"),
        44: pgettext("built-in screen", "Elevation"),
        56: pgettext("built-in screen", "Segment"),
        57: pgettext("built-in screen", "GroupTrack"),
        58: pgettext("built-in screen", "eBike"),
        63: pgettext("built-in screen", "Cycling Dynamics"),
        74: pgettext("built-in screen", "Lap Summary"),
        95: pgettext("built-in screen", "Shimano STEPS"),
        104: pgettext("built-in screen", "ClimbPro"),
        125: pgettext("built-in screen", "Power Guide"),
        127: pgettext("built-in screen", "Stamina"),
        128: pgettext("built-in screen", "Solar"),
        162: pgettext("built-in screen", "GroupRide"),
        223: pgettext("built-in screen", "Radar"),
    }


# A watch's built-in screens as Garmin Connect names them for a fēnix 8; in English as its manual
# does, and for the clocks, the gauge and a strength workout's set, which it does not name, in
# plain words.
def _watch_screen_names() -> dict[int, str]:
    return {
        21: pgettext("built-in screen", "Clock with Status Icons"),
        22: pgettext("built-in screen", "Heart Rate Zone Gauge"),
        25: pgettext("built-in screen", "Map"),
        35: pgettext("built-in screen", "Compass"),
        80: pgettext("built-in screen", "Set"),
        100: pgettext("built-in screen", "Regatta Timer"),
        101: pgettext("built-in screen", "Tack Assist"),
        221: pgettext("built-in screen", "Clock with Sun Info"),
    }


def _screen_names(edge: bool) -> dict[int, str]:
    return _edge_screen_names() if edge else _watch_screen_names()


def built_in_known(screen, edge: bool) -> bool:
    """Whether the built-in screen's code is known for a profile of this shape (an Edge's:
    `edge`)."""
    return screen.code in _screen_names(edge)


def built_in_name(screen, edge: bool) -> str:
    """The name of a built-in screen; its code when it is not known."""
    name = _screen_names(edge).get(screen.code)
    if name is not None:
        return name
    # TRANSLATORS: a built-in screen openExpress has no name for, by its code in the profile
    return _("Built-in screen {code}").format(code=screen.code)


# The variants of the layouts of an Edge's screens: the letters of its menu.
_EDGE_LAYOUTS = {0: "A", 1: "B", 2: "C"}


# The families of a watch's layouts, as Garmin Connect's pictures of a fēnix 8's screens show
# them: a stack of rows (two fields in two rows, three in three, four with the lower row split),
# one field without a label.
def _watch_layouts() -> dict[int, str]:
    return {
        1: pgettext("layout", "No Labels"),
        2: pgettext("layout", "Stack"),
    }


def layout_known(variant: int | None, edge: bool) -> bool:
    return variant in (_EDGE_LAYOUTS if edge else _watch_layouts())


def layout_name(variant: int | None, edge: bool) -> str:
    """The layout of a screen of one's own: its letter on an Edge, its family on a watch; its
    code when it is not known."""
    if variant is None:
        return _("Layout not given")
    if layout_known(variant, edge) and edge:
        # TRANSLATORS: the layout of a data screen by the letter of the device's menu
        return _("Layout {letter}").format(letter=_EDGE_LAYOUTS[variant])
    if layout_known(variant, edge):
        # TRANSLATORS: the layout of a watch's data screen by its family ("Stack")
        return _("Layout “{family}”").format(family=_watch_layouts()[variant])
    # TRANSLATORS: a layout openExpress has no name for, by its code in the profile
    return _("Layout code {code}, unknown").format(code=variant)
