"""The look of a sport on an activity's page: its group (on foot, cycling, water, winter,
training, others) by the sport of the FIT profile, and the group's colour, which an icon needs
to read with a contrast of 3:1 at least on the cards of the light style and of the dark one
alike. The program's style (gui/start.py) gets a class for each group: the colour of an icon,
and of the dot before the title of an activity's page.
Has: nothing of the window."""
from __future__ import annotations

# The sports of the FIT profile in each group; the rest is "others".
GROUPS = {
    "foot": (1, 11, 16, 17, 31, 48, 65, 66, 87),  # running, walking, mountaineering, hiking,
    # rock and floor climbing, the wheelchair's push walk and run, geocaching
    "cycling": (2, 21),  # cycling, e-biking
    "water": (5, 15, 19, 23, 29, 32, 37, 38, 39, 40, 41, 42, 43, 44, 53, 76, 77, 78, 82, 85,
              88),  # swimming, rowing, paddling, boating, fishing, sailing, …, canoeing
    "winter": (12, 13, 14, 33, 35, 36, 58),  # skiing, snowboarding, skating, snowshoeing, …
    "training": (4, 10, 47, 62, 67, 80, 83, 84, 86),  # fitness equipment, training, boxing,
    # HIIT, meditation, mixed martial arts, dance, jump rope, mobility
}
COLORS = {"foot": "#26a269", "cycling": "#3584e4", "water": "#2190a4", "winter": "#6f8396",
          "training": "#c061cb", "others": "#8a898e"}


def sport_group(sport: int | None) -> str:
    """The group of a sport of the FIT profile; "others" for any other, or none."""
    for group, members in GROUPS.items():
        if sport in members:
            return group
    return "others"


def css() -> str:
    """The rules of the program's style: a class for each group (an icon's colour; the dot's,
    with the class oe-sport-dot)."""
    rules = [".oe-sport-dot {\n  min-width: 12px;\n  min-height: 12px;\n  border-radius: 999px;\n}"]
    for group, color in COLORS.items():
        rules.append(f".oe-sport-{group} {{ color: {color}; }}")
        rules.append(f".oe-sport-dot.oe-sport-{group} {{ background-color: {color}; }}")
    return "\n".join(rules) + "\n"
