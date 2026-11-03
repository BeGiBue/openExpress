"""How openExpress names itself to the servers it asks: one User-Agent header for every
request (the Garmin Connect API, uploads and their status, product pictures, the files of
updates and maps). The Garmin Express client headers are sent too, so that the servers answer,
but the program does not hide that it is another one. The sign-in window, a web browser, has
its own header, and so have the map tiles of an activity's page: OpenStreetMap's tile policy
asks for a name that says where to reach the program (gui/activity_map.py)."""

from __future__ import annotations

import platform

import requests

from openexpress import __version__

USER_AGENT = f"openexpress/{__version__} ({platform.system()})"


def session(user_agent: str = USER_AGENT) -> requests.Session:
    """A session whose requests carry `user_agent` instead of the library's own header. The
    requests of the program name it themselves too, so a session made elsewhere does not
    bring the library's header back."""
    http = requests.Session()
    http.headers["User-Agent"] = user_agent
    return http
