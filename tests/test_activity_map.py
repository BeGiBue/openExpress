"""The map of an activity (gui/activity_map.py) without a screen: the track from the records with
positions (its time as the chart's), thinned for a long one, its bounds and the zoom that shows
it, where the chart's cursor is on it, the markers of its ends; the tiles a view shows and
where they are drawn (each edge on a pixel of the screen); the tiles of OpenStreetMap asked by
openExpress itself, with its User-Agent, kept in the program's cache as long as the server
allows, asked again with what the cache has, nothing said of a place in the log. No tile is
asked of a server here: the download is a stand-in. Every value is made up."""

import itertools
import time

import pytest

from openexpress import fit

START = 1_700_000_000  # a Unix time
PNG = b"\x89PNG made-up tile"


def amap():
    from openexpress.gui import activity_map
    return activity_map


def sample(second, lat=None, lon=None):
    return fit.Sample(START + second, latitude=lat, longitude=lon, heart_rate=100)


def activity(samples):
    return fit.ActivityData(fit.FileState.WHOLE, start=START, sport=11, samples=tuple(samples))


# --- the track -------------------------------------------------------------------------------


def test_the_track_has_the_records_with_positions_and_the_chart_s_time():
    """Its time since the first record of the activity, with a position or not."""
    track = amap().track_of(activity([sample(0), sample(5, 51.5, -0.16), sample(6, 51.501, -0.161),
                                      sample(9)]))
    assert track.times == (5, 6)
    assert track.points == ((51.5, -0.16), (51.501, -0.161))
    assert amap().track_of(activity([sample(0), sample(1)])) is None


def test_a_long_track_is_thinned_for_the_map_but_keeps_its_ends():
    points = [(51.5 + i * 1e-6, -0.16) for i in range(28_800)]
    thin = amap().thinned(points)
    assert len(thin) <= amap().PATH_POINTS + 1
    assert thin[0] == points[0] and thin[-1] == points[-1]
    assert amap().thinned(points[:10]) == points[:10]


def test_the_zoom_that_shows_the_whole_track():
    """A track of 0.02° by 0.01° at 51.5°N in a map of 600 by 300 pixels: zoom 14 (15 would
    be too high for it); one point alone: a close zoom, not the closest."""
    bounds = amap().bounds([(51.5, -0.17), (51.51, -0.15), (51.505, -0.16)])
    assert bounds == (51.5, -0.17, 51.51, -0.15)
    assert amap().fitting_zoom(bounds, 600, 300) == 14
    assert amap().fitting_zoom((51.5, -0.16, 51.5, -0.16), 600, 300) == amap().CLOSEST_FIT
    lat, lon = amap().center(bounds)
    assert lat == pytest.approx(51.505, abs=1e-3) and lon == pytest.approx(-0.16)


def test_where_the_chart_s_cursor_is_on_the_track():
    """The nearest record with a position; none in a gap or a pause."""
    track = amap().Track((0, 5, 10, 200), ((51.5, -0.1), (51.6, -0.2), (51.7, -0.3),
                                          (51.8, -0.4)))
    assert amap().position_at(track, 6) == (51.6, -0.2)
    assert amap().position_at(track, -3) == (51.5, -0.1)
    assert amap().position_at(track, 100) is None


def test_the_start_and_the_finish_one_marker_for_a_loop():
    """Apart: the start and the finish where they are; closer than 50 m (a loop): one marker
    for both, at the start."""
    line = amap().Track((0, 600), ((51.5, -0.16), (51.51, -0.16)))
    assert amap().ends_of(line) == [("start", (51.5, -0.16)), ("finish", (51.51, -0.16))]
    loop = amap().Track((0, 300, 600), ((51.5, -0.16), (51.51, -0.16), (51.5003, -0.16)))
    assert amap().ends_of(loop) == [("start-and-finish", (51.5, -0.16))]
    alone = amap().Track((0,), ((51.5, -0.16),))
    assert amap().ends_of(alone) == [("start-and-finish", (51.5, -0.16))]


# --- where the tiles are drawn ----------------------------------------------------------------


def test_the_tiles_of_a_view_in_the_order_they_are_drawn():
    """Rows from the top, each from the left, every tile touching the next: the whole view
    covered, nothing more than a tile around it."""
    places = amap().tile_places(15, 51.5065, -0.1665, 600, 300)
    rows = sorted({p.y for p in places})
    assert [p.y for p in places] == sorted(p.y for p in places)
    for y in rows:
        row = [p for p in places if p.y == y]
        assert [p.x for p in row] == sorted(p.x for p in row)
        assert all(a.x + a.width == b.x for a, b in itertools.pairwise(row))
        assert row[0].x <= 0 < row[0].x + row[0].width and row[-1].x + row[-1].width >= 600
    assert places[0].y <= 0 and places[-1].y + places[-1].height >= 300
    assert {p.key[0] for p in places} == {15}
    assert all(p.width == p.height == 256 for p in places)
    zoom, x, y = places[0].key
    assert (x, y) == (16367, 10895)  # the tile of OpenStreetMap at the view's top left


def test_tiles_across_the_antimeridian_are_those_of_the_other_side():
    keys = {p.key[1] for p in amap().tile_places(3, 0.0, 179.9, 600, 300)}
    assert 0 in keys and 7 in keys and max(keys) < 8


def test_the_tiles_land_on_the_pixels_of_the_screen():
    """Each edge on a pixel of a screen of this scale (the view's centre anywhere)."""
    for scale in (1, 1.25, 1.5, 2):
        for place in amap().tile_places(15, 51.50651234, -0.16653456, 600, 300, scale):
            for edge in (place.x, place.y, place.x + place.width, place.y + place.height):
                assert edge * scale == pytest.approx(round(edge * scale))


def test_between_two_zooms_the_tiles_of_the_zoom_below_drawn_larger():
    places = amap().tile_places(15.5, 51.5065, -0.1665, 600, 300)
    assert {p.key[0] for p in places} == {15}
    assert all(p.width == pytest.approx(256 * 2 ** 0.5, abs=1) for p in places)


# --- the tiles -------------------------------------------------------------------------------


@pytest.mark.parametrize(("header", "seconds"), [
    ("max-age=3473, stale-while-revalidate=604800, stale-if-error=604800", 3473),
    (None, 7 * 24 * 3600), ("no-cache", 0), ("public, max-age=0", 0)])
def test_how_long_a_tile_is_kept_before_it_is_asked_again(header, seconds):
    """As the server's caching header says; a week when it says nothing (the tile policy)."""
    assert amap().freshness(header) == seconds


def test_the_tile_server_is_told_who_asks_and_what_the_cache_has(monkeypatch):
    """openExpress's own User-Agent, and the tag of the tile it has, so that an unchanged one
    is not sent again."""
    asked = []

    class Session:
        def get(self, url, headers, timeout):
            asked.append((url, headers))
            return type("Answer", (), {"status_code": 304, "content": b"",
                                       "headers": {"Cache-Control": "max-age=60"}})()

    monkeypatch.setattr(amap(), "_session", Session)
    fetched = amap()._fetch("https://tile.example/1/2/3.png", '"tag"')
    ((url, headers),) = asked
    assert url == "https://tile.example/1/2/3.png"
    assert headers["User-Agent"] == amap().USER_AGENT
    assert amap().USER_AGENT.startswith("openExpress/") and amap().USER_AGENT.endswith(
        " (+https://github.com/TomaszBojanowski/openExpress)")
    assert headers["If-None-Match"] == '"tag"'
    assert (fetched.status, fetched.max_age) == (304, 60)


def test_the_session_of_the_tiles_is_named_as_the_map():
    """Its own session, never another one's header."""
    assert amap()._session().headers["User-Agent"] == amap().USER_AGENT


def needs_shumate():
    if amap().Shumate is None or not amap().can_ask():
        pytest.skip("libshumate 1.1 or later is not installed")


def asked(source, x=1, y=2, zoom=3):
    """A tile asked of the source as the map asks it; returns the request once it ends."""
    from gi.repository import GLib

    request = source.start_request(x, y, zoom, None)
    end = time.monotonic() + 5
    while not request.props.completed and request.get_error() is None \
            and time.monotonic() < end:
        GLib.MainContext.default().iteration(False)
    return request


def test_a_tile_is_downloaded_once_and_kept_in_the_program_s_cache(monkeypatch):
    from openexpress import paths

    needs_shumate()
    fetched = []

    def fetch(url, etag):
        fetched.append((url, etag))
        return amap().Fetched(200, PNG, '"t1"', 3600)

    monkeypatch.setattr(amap(), "_fetch", fetch)
    folder = paths.cache_dir() / amap().CACHE_FOLDER
    source = amap().TileSource()
    assert not folder.exists()  # nothing made before a tile is asked
    first = asked(source)
    assert first.get_data().get_data() == PNG
    assert fetched == [(amap().TILE_URL.format(z=3, x=1, y=2), None)]
    second = asked(amap().TileSource())
    assert second.get_data().get_data() == PNG and len(fetched) == 1  # from the cache
    assert folder.is_dir()


def test_an_old_tile_is_asked_again_with_its_tag(monkeypatch):
    needs_shumate()
    answers = [amap().Fetched(200, PNG, '"t1"', 0), amap().Fetched(304, None, '"t1"', 3600)]
    fetched = []

    def fetch(url, etag):
        fetched.append(etag)
        return answers.pop(0)

    monkeypatch.setattr(amap(), "_fetch", fetch)
    asked(amap().TileSource())
    again = asked(amap().TileSource())
    assert fetched == [None, '"t1"'] and again.get_data().get_data() == PNG


def test_a_tile_that_cannot_be_downloaded_is_an_error_and_the_log_names_no_place(
        monkeypatch, caplog):
    needs_shumate()
    monkeypatch.setattr(amap(), "_fetch", lambda url, etag: amap().Fetched(None, None, None, 0))
    request = asked(amap().TileSource(), x=4_321, y=2_718, zoom=13)
    assert request.get_error() is not None
    assert "4321" not in caplog.text and "2718" not in caplog.text
