"""The map of an activity's page: its track (the records with positions) drawn with libshumate,
GNOME's map widget, thick in a colour of its own with a dark edge, its start and finish marked,
and a marker where the chart's cursor is. Streets and terrain under it come from
OpenStreetMap's tile server only after a yes given once for the program (gui.json "map_tiles":
on the page or in Preferences, taken back there); until then the track is on a plain
background, with a note of what the server would learn and a button. The tiles are asked by
openExpress itself, with its own User-Agent, at most DOWNLOADS at a time and only those the map
shows (its view is set, never flown to), kept in the program's cache (cache.CATEGORIES "tiles")
as long as the server allows, at most CACHE_LIMIT, and drawn by openExpress (TileLayer: each
one a pixel past its edges, so that no seam is left where two meet between two pixels of a
screen at a fractional scale); the log names no place. Without a network the map says that
only the tiles downloaded before are shown, and asks again those that failed once it is back;
without libshumate the page says what is missing.
Has: no attribute of the window; the map's widgets keep their track and state themselves."""
from __future__ import annotations

import bisect
import logging
import math
import queue
import threading
import weakref
from collections import OrderedDict
from dataclasses import dataclass

import gi
import requests

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Graphene, Gtk  # noqa: E402 - imports must follow gi.require_version

try:
    gi.require_version("Shumate", "1.0")
    from gi.repository import Shumate
except (ValueError, ImportError):  # not installed (the version from source): no map
    Shumate = None

from openexpress import __version__, cache, paths, useragent  # noqa: E402
from openexpress.gui.activity_chart import ACCENT, GAP_S  # noqa: E402
from openexpress.gui.gui_settings import load_gui_settings, update_gui_settings  # noqa: E402
from openexpress.i18n import _  # noqa: E402

log = logging.getLogger(__name__)

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
COPYRIGHT_URL = "https://www.openstreetmap.org/copyright"
USER_AGENT = f"openExpress/{__version__} (+https://github.com/TomaszBojanowski/openExpress)"
CACHE_FOLDER = cache.CATEGORIES["tiles"][0]  # in the program's cache
CACHE_KEY = "openstreetmap"
CACHE_LIMIT = 100_000_000  # bytes; the less used tiles go first
PURGE_EVERY = 200  # tiles stored between two purges of the cache to its limit
FRESH_S = 7 * 24 * 3600  # a tile whose server says nothing of caching: a week (the tile policy)
DOWNLOADS = 2  # tiles downloaded at a time
TIMEOUT_S = 20
MAX_ZOOM = 19
TILE_SIZE = 256
CLOSEST_FIT = 17  # the zoom of a track of a single point
FIT_MARGIN = 24  # pixels around the track
MAP_HEIGHT = 300
PATH_POINTS = 5000  # a longer track is thinned for the map
SETTING = "map_tiles"  # in gui.json: the yes to OpenStreetMap's tiles
TRACK_COLOR = "#e5420e"  # orange-red: apart from the water, the green and the streets of the tiles
TRACK_EDGE = "#6b1d05"  # its dark edge, seen on the light streets
TRACK_WIDTH = 4  # pixels of the track's colour
EDGE_WIDTH = 1.5  # pixels of its dark edge on each side
START_COLOR = "#26a269"
END_SIZE = 18  # pixels: the marker of the start and the one of the finish
BOTH_SIZE = 20  # the one marker of a loop's start and finish
CURSOR_SIZE = 20  # the marker of the chart's cursor, above them
LOOP_M = 50  # a finish closer to the start: a loop, one marker for both
BLEED = 1  # pixels each tile is drawn past its right and bottom edge, under the next one
KEEP_TILES = 64  # tiles kept drawn in memory, the less used let go first
FALLBACK_ZOOMS = 3  # while a tile loads, one of up to so many zooms below, scaled


def available() -> bool:
    """Whether libshumate is installed (the Flatpak has it; from source, a package)."""
    return Shumate is not None


def can_ask() -> bool:
    """Whether this libshumate lets openExpress ask the tiles itself (libshumate 1.1 and
    later): its own User-Agent and cache. An older one keeps the track on a plain background."""
    return Shumate is not None and hasattr(Shumate, "DataSourceRequest")


def tiles_on() -> bool:
    """Whether the yes to OpenStreetMap's tiles is given (off until it is)."""
    return load_gui_settings().get(SETTING) is True


def set_tiles(on: bool) -> None:
    update_gui_settings(**{SETTING: bool(on)})
    log.info("activity map: the tiles of OpenStreetMap turned %s", "on" if on else "off")


# --- the track -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Track:
    """The records of an activity with a position: each one's time in seconds since the first
    record of the activity (as the chart's) and its (latitude, longitude)."""

    times: tuple[float, ...]
    points: tuple[tuple[float, float], ...]


def track_of(data) -> Track | None:
    """The track of an activity (fit.ActivityData); None without any position."""
    samples = data.samples
    if not samples:
        return None
    origin = samples[0].time
    found = [(s.time - origin, (s.latitude, s.longitude)) for s in samples
             if s.latitude is not None and s.longitude is not None]
    if not found:
        return None
    return Track(tuple(t for t, _p in found), tuple(p for _t, p in found))


def thinned(points, most: int = PATH_POINTS) -> list:
    """At most about `most` of the points, evenly, the last one kept."""
    if len(points) <= most:
        return list(points)
    out = list(points[::math.ceil(len(points) / most)])
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out


def bounds(points) -> tuple[float, float, float, float]:
    """(south, west, north, east) of the points."""
    lats = [lat for lat, _lon in points]
    lons = [lon for _lat, lon in points]
    return min(lats), min(lons), max(lats), max(lons)


def _mercator(lat: float) -> float:
    lat = max(min(lat, 85.0511), -85.0511)
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def fitting_zoom(box, width: float, height: float) -> int:
    """The closest whole zoom at which the bounds fit a map of this size, with a margin."""
    south, west, north, east = box
    zooms = [CLOSEST_FIT]
    for share, room in (((east - west) / 360, width),
                        ((_mercator(north) - _mercator(south)) / (2 * math.pi), height)):
        if share > 0:
            zooms.append(math.log2(max(room - 2 * FIT_MARGIN, 1) / (share * TILE_SIZE)))
    return max(1, min(CLOSEST_FIT, math.floor(min(zooms))))


def center(box) -> tuple[float, float]:
    """The middle of the bounds as the map draws them (Web Mercator)."""
    south, west, north, east = box
    y = (_mercator(south) + _mercator(north)) / 2
    return math.degrees(2 * math.atan(math.exp(y)) - math.pi / 2), (west + east) / 2


def position_at(track: Track, at: float) -> tuple[float, float] | None:
    """Where the record nearest to the time `at` is; None in a gap or a pause (no record
    within half of the chart's GAP_S)."""
    times = track.times
    at = min(max(at, times[0]), times[-1])
    i = bisect.bisect_left(times, at)
    nearest = min((j for j in (i - 1, i) if 0 <= j < len(times)), key=lambda j: abs(times[j] - at))
    if abs(times[nearest] - at) > GAP_S / 2:
        return None
    return track.points[nearest]


def _metres(a, b) -> float:
    """The distance between two (latitude, longitude) on the Earth (haversine)."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6_371_000 * math.asin(min(1.0, math.sqrt(h)))


def ends_of(track: Track) -> list[tuple[str, tuple[float, float]]]:
    """The markers of the track's ends, in the order they are drawn: the start and the finish,
    or one for both at the start when the finish is closer than LOOP_M (a loop)."""
    first, last = track.points[0], track.points[-1]
    if _metres(first, last) < LOOP_M:
        return [("start-and-finish", first)]
    return [("start", first), ("finish", last)]


# --- where the tiles are drawn ----------------------------------------------------------------


def world_xy(lat: float, lon: float, zoom: float) -> tuple[float, float]:
    """Where a place is on the whole map at this zoom, in pixels from its top left (Web
    Mercator, TILE_SIZE tiles)."""
    size = TILE_SIZE * 2 ** zoom
    return (lon + 180) / 360 * size, (1 - _mercator(lat) / math.pi) / 2 * size


@dataclass(frozen=True)
class Place:
    """A tile drawn: its (zoom, x, y) on the tile server, and where it is drawn on the map
    (without BLEED)."""

    key: tuple[int, int, int]
    x: float
    y: float
    width: float
    height: float


def tile_places(zoom: float, lat: float, lon: float, width: float, height: float,
                scale: float = 1.0, rotation: float = 0.0) -> list[Place]:
    """The tiles a map of this size shows around this centre, in the order they are drawn
    (rows from the top, each from the left), each edge on a pixel of a screen of this scale;
    between two zooms, those of the zoom below drawn larger. Turned by `rotation` (radians),
    those of the circle around the view."""
    whole = max(0, min(MAX_ZOOM, math.floor(zoom)))
    size = TILE_SIZE * 2 ** (zoom - whole)
    cx, cy = world_xy(lat, lon, zoom)
    left, top = cx - width / 2, cy - height / 2
    if rotation:
        reach = math.hypot(width, height) / 2
        columns = range(math.floor((cx - reach) / size), math.floor((cx + reach) / size) + 1)
        rows = range(math.floor((cy - reach) / size), math.floor((cy + reach) / size) + 1)
    else:
        columns = range(math.floor(left / size), math.floor((left + width) / size) + 1)
        rows = range(math.floor(top / size), math.floor((top + height) / size) + 1)
    count = 2 ** whole

    def on_pixel(value: float) -> float:
        return round(value * scale) / scale

    places = []
    for y in rows:
        if not 0 <= y < count:
            continue
        top_edge, bottom_edge = on_pixel(y * size - top), on_pixel((y + 1) * size - top)
        for x in columns:
            left_edge, right_edge = on_pixel(x * size - left), on_pixel((x + 1) * size - left)
            places.append(Place((whole, x % count, y), left_edge, top_edge,
                                right_edge - left_edge, bottom_edge - top_edge))
    return places


# --- the tiles -------------------------------------------------------------------------------


def freshness(cache_control: str | None) -> int:
    """How long a tile may be used before it is asked again, as the server's Cache-Control
    says (max-age; no-cache and no-store: at once); FRESH_S when it says nothing."""
    if not cache_control:
        return FRESH_S
    directives = [d.strip().lower() for d in cache_control.split(",")]
    if "no-cache" in directives or "no-store" in directives:
        return 0
    for directive in directives:
        if directive.startswith("max-age="):
            try:
                return max(0, int(directive.split("=", 1)[1]))
            except ValueError:
                break
    return FRESH_S


@dataclass(frozen=True)
class Fetched:
    """What the tile server answered: its status (None: not reached), the tile (with 200), its
    tag and how long it may be used."""

    status: int | None
    data: bytes | None
    etag: str | None
    max_age: int


_local = threading.local()


def _session() -> requests.Session:
    """The session of a downloading thread, named as openExpress."""
    session = getattr(_local, "session", None)
    if session is None:
        session = _local.session = useragent.session()
        session.headers["User-Agent"] = USER_AGENT
    return session


def _fetch(url: str, etag: str | None) -> Fetched:
    """A tile asked of the server (in a downloading thread), with the tag of the one the
    cache has, so that an unchanged one is not sent again."""
    headers = {"User-Agent": USER_AGENT}
    if etag:
        headers["If-None-Match"] = etag
    try:
        answer = _session().get(url, headers=headers, timeout=TIMEOUT_S)
    except requests.RequestException as e:
        _not_downloaded(type(e).__name__)
        return Fetched(None, None, None, 0)
    max_age = freshness(answer.headers.get("Cache-Control"))
    tag = answer.headers.get("ETag")
    if answer.status_code in (200, 304):
        _said.clear()
        return Fetched(answer.status_code, answer.content if answer.status_code == 200 else None,
                       tag, max_age)
    _not_downloaded(f"HTTP {answer.status_code}")
    return Fetched(answer.status_code, None, tag, max_age)


_said: set[str] = set()  # why tiles were not downloaded, each said once until one is


def _not_downloaded(why: str) -> None:
    if why not in _said:
        _said.add(why)
        log.info("activity map: tiles not downloaded (%s)", why)


_waiting: queue.Queue | None = None


def _download_later(url: str, etag: str | None, cancellable, done) -> None:
    """`done(fetched)` on the window's thread once the tile is fetched, by one of DOWNLOADS
    threads (daemons: the program does not wait for them when it ends); nothing for a tile no
    longer wanted."""
    global _waiting
    if _waiting is None:
        _waiting = queue.Queue()
        for _ in range(DOWNLOADS):
            threading.Thread(target=_downloading, args=(_waiting,), daemon=True,
                             name="tiles").start()
    _waiting.put((url, etag, cancellable, done))


def _downloading(waiting: queue.Queue) -> None:
    while True:
        url, etag, cancellable, done = waiting.get()
        if cancellable is not None and cancellable.is_cancelled():
            continue
        fetched = _fetch(url, etag)
        GLib.idle_add(lambda d=done, f=fetched: (d(f), False)[1])


def _tag(etag: str | None, max_age: int) -> str:
    """What the cache keeps with a tile: how long it may be used, and the server's tag."""
    return f"{max_age} {etag or ''}"


def _untag(tag: str | None) -> tuple[str | None, int]:
    if not tag:
        return None, FRESH_S
    max_age, _space, etag = tag.partition(" ")
    try:
        return etag or None, int(max_age)
    except ValueError:
        return None, FRESH_S


def _cached(cache_, result, request_and_cancellable) -> None:
    """The cache's answer for a tile: used while fresh; else shown meanwhile and asked
    again."""
    request, cancellable = request_and_cancellable
    try:
        found, tag, modified = cache_.get_tile_finish(result)
    except GLib.Error:
        found, tag, modified = None, None, None
    etag, max_age = _untag(tag)
    if found is not None and modified is not None:
        age = GLib.DateTime.new_now_utc().difference(modified) / 1_000_000
        if age < max_age:
            request.emit_data(found, True)
            return
        request.emit_data(found, False)
    url = TILE_URL.format(z=request.get_zoom_level(), x=request.get_x(), y=request.get_y())
    _download_later(url, etag if found is not None else None, cancellable,
                    lambda fetched: _downloaded(cache_, request, found, fetched))


def _downloaded(cache_, request, found, fetched: Fetched) -> None:
    """The server's answer: a new tile stored, an unchanged one kept again, or the old one
    when the server was not reached; an error without any."""
    x, y, zoom = request.get_x(), request.get_y(), request.get_zoom_level()
    if fetched.status == 200 and fetched.data:
        tile = GLib.Bytes.new(fetched.data)
    elif fetched.status == 304 and found is not None:
        tile = found
    elif found is not None:
        request.emit_data(found, True)
        return
    else:
        request.emit_error(GLib.Error.new_literal(Gio.io_error_quark(), "no tile",
                                                  Gio.IOErrorEnum.FAILED))
        return
    _stored_once_more(cache_)
    cache_.store_tile_async(x, y, zoom, tile, _tag(fetched.etag, fetched.max_age), None,
                            lambda c, result: _stored(c, result, request, tile))


def _stored(cache_, result, request, tile) -> None:
    try:
        cache_.store_tile_finish(result)
    except GLib.Error as e:
        log.info("activity map: a tile not kept in the cache (%s)", e.domain)
    request.emit_data(tile, True)


_stored_count = [0]


def _stored_once_more(cache_) -> None:
    """Every PURGE_EVERY tiles stored (and at the first), the cache brought to its limit."""
    if _stored_count[0] % PURGE_EVERY == 0:
        cache_.purge_cache_async(None, None)
    _stored_count[0] += 1


if can_ask():
    class TileSource(Shumate.DataSource):
        """The tiles of OpenStreetMap, asked by openExpress (_fetch) and kept in the program's
        cache, made with the first tile asked."""

        __gtype_name__ = "OpenExpressTileSource"

        def __init__(self):
            super().__init__(min_zoom_level=0, max_zoom_level=MAX_ZOOM)
            self.cache = None

        def do_start_request(self, x, y, zoom, cancellable):
            if self.cache is None:
                folder = paths.cache_dir() / CACHE_FOLDER
                self.cache = Shumate.FileCache.new_full(CACHE_LIMIT, CACHE_KEY, str(folder))
            request = Shumate.DataSourceRequest.new(x, y, zoom)
            self.cache.get_tile_async(x, y, zoom, cancellable, _cached, (request, cancellable))
            return request

    class TileLayer(Shumate.Layer):
        """The tiles under the track, drawn by openExpress (libshumate's own layer leaves a
        seam of the background where two tiles meet between two pixels of a screen at a
        fractional scale): in rows from the top, each from the left, each one BLEED past its
        right and bottom edge, under the next one; while a tile loads, the one of a zoom below
        scaled, if drawn before. Only the tiles in view are asked of the TileSource; those gone
        from it are let go, those that failed asked again by retry()."""

        __gtype_name__ = "OpenExpressTileLayer"

        def __init__(self, viewport):
            super().__init__(viewport=viewport)
            self.source = TileSource()
            self.textures: OrderedDict = OrderedDict()  # (zoom, x, y): Gdk.Texture
            self.asked: dict = {}  # (zoom, x, y): (its request, its cancellable)
            self.failed: set = set()
            self.handler = viewport.connect("notify", _view_changed, weakref.ref(self))

        def do_snapshot(self, snapshot) -> None:
            viewport = self.get_viewport()
            width, height = self.get_width(), self.get_height()
            if width <= 0 or height <= 0:
                return
            rotation = viewport.get_rotation()
            places = tile_places(viewport.get_zoom_level(), viewport.get_latitude(),
                                 viewport.get_longitude(), width, height, _screen_scale(self),
                                 rotation)
            snapshot.save()
            if rotation:
                middle = Graphene.Point().init(width / 2, height / 2)
                snapshot.translate(middle)
                snapshot.rotate(math.degrees(rotation))
                snapshot.translate(Graphene.Point().init(-width / 2, -height / 2))
            for place in places:
                texture = self.textures.get(place.key)
                if texture is not None:
                    self.textures.move_to_end(place.key)
                    snapshot.append_texture(texture, Graphene.Rect().init(
                        place.x, place.y, place.width + BLEED, place.height + BLEED))
                else:
                    self._ask(place.key)
                    self._draw_below(snapshot, place)
            snapshot.restore()
            wanted = {place.key for place in places}
            for key in [key for key in self.asked if key not in wanted]:
                self.asked.pop(key)[1].cancel()

        def _draw_below(self, snapshot, place: Place) -> None:
            """The part of a tile of a zoom below where the tile `place` will be."""
            zoom, x, y = place.key
            for k in range(1, FALLBACK_ZOOMS + 1):
                texture = self.textures.get((zoom - k, x >> k, y >> k))
                if texture is None:
                    continue
                n = 2 ** k
                snapshot.push_clip(Graphene.Rect().init(place.x, place.y, place.width + BLEED,
                                                        place.height + BLEED))
                snapshot.append_texture(texture, Graphene.Rect().init(
                    place.x - (x % n) * place.width, place.y - (y % n) * place.height,
                    n * place.width + BLEED, n * place.height + BLEED))
                snapshot.pop()
                return

        def _ask(self, key) -> None:
            if key in self.asked or key in self.failed:
                return
            zoom, x, y = key
            cancellable = Gio.Cancellable()
            request = self.source.start_request(x, y, zoom, cancellable)
            self.asked[key] = (request, cancellable)
            this = weakref.ref(self)
            request.connect("notify::data", _tile_data, this, key)
            request.connect("notify::completed", _tile_done, this, key)

        def keep(self, key, texture) -> None:
            self.textures[key] = texture
            self.textures.move_to_end(key)
            while len(self.textures) > KEEP_TILES:
                self.textures.popitem(last=False)
            self.queue_draw()

        def retry(self) -> None:
            """The tiles that failed asked again (the network is back)."""
            if self.failed:
                self.failed.clear()
                self.queue_draw()

        def let_go(self) -> None:
            """The tiles being asked no longer wanted (the map off the screen, or the tiles
            turned off); asked again when drawn."""
            for _request, cancellable in self.asked.values():
                cancellable.cancel()
            self.asked.clear()

        def stop(self) -> None:
            self.let_go()
            self.get_viewport().disconnect(self.handler)


def _view_changed(_viewport, _pspec, layer_ref) -> None:
    layer = layer_ref()
    if layer is not None:
        layer.queue_draw()


def _tile_data(request, _pspec, layer_ref, key) -> None:
    """A tile's data (the one in the cache meanwhile, then the server's): drawn."""
    layer, data = layer_ref(), request.get_data()
    if layer is None or data is None:
        return
    try:
        texture = Gdk.Texture.new_from_bytes(data)
    except GLib.Error as e:
        log.info("activity map: a tile that is not a picture (%s)", e.domain)
        return
    layer.keep(key, texture)


def _tile_done(request, _pspec, layer_ref, key) -> None:
    layer = layer_ref()
    if layer is None or layer.asked.get(key, (None,))[0] is not request:
        return
    del layer.asked[key]
    if request.get_error() is not None and key not in layer.textures:
        layer.failed.add(key)


def _screen_scale(widget) -> float:
    """The scale of the screen the widget is on (fractional: 1.25 at 125 %)."""
    native = widget.get_native()
    surface = native.get_surface() if native is not None else None
    return surface.get_scale() if surface is not None else widget.get_scale_factor()


if Shumate is not None:
    class NoTiles(Shumate.DataSource):
        """A source that is never asked: the reference of the map's view (its projection, its
        tile size and zooms); the tiles are drawn by TileLayer. libshumate's own sources would
        make its cache (~/.cache/shumate) as soon as they are made."""

        __gtype_name__ = "OpenExpressNoTiles"


def _map_source():
    """The reference of the map's view: OpenStreetMap's projection and zooms."""
    return Shumate.RasterRenderer.new_full(
        CACHE_KEY, "OpenStreetMap", _("© OpenStreetMap contributors"), COPYRIGHT_URL, 0,
        MAX_ZOOM, TILE_SIZE, Shumate.MapProjection.MERCATOR, NoTiles())


def _network_monitor():
    return Gio.NetworkMonitor.get_default()


# --- the widget ------------------------------------------------------------------------------


def _rgba(text: str) -> Gdk.RGBA:
    color = Gdk.RGBA()
    color.parse(text)
    return color


def cursor_color() -> Gdk.RGBA:
    """The accent colour of the desktop in its strong shade (libadwaita 1.6 and later), as the
    chart's cursor; else libadwaita's blue."""
    manager = Adw.StyleManager.get_default()
    if hasattr(manager, "get_accent_color_rgba"):
        return manager.get_accent_color_rgba()
    return _rgba(ACCENT)


def _disc(cr, width: int, height: int, ring: float) -> tuple[float, float, float]:
    """A marker's disc: a thin dark edge and a white ring `ring` wide; its middle (x, y,
    radius) left to fill."""
    x, y, radius = width / 2, height / 2, min(width, height) / 2 - 1
    cr.arc(x, y, radius, 0, 2 * math.pi)
    cr.set_source_rgba(0, 0, 0, 0.55)
    cr.fill()
    cr.arc(x, y, radius - 1, 0, 2 * math.pi)
    cr.set_source_rgba(1, 1, 1, 1)
    cr.fill()
    return x, y, radius - 1 - ring


def _draw_cursor(_area, cr, width: int, height: int) -> None:
    x, y, radius = _disc(cr, width, height, 3)
    color = cursor_color()
    cr.arc(x, y, radius, 0, 2 * math.pi)
    cr.set_source_rgba(color.red, color.green, color.blue, 1)
    cr.fill()


def _draw_end(_area, cr, width: int, height: int, kind: str) -> None:
    """The start green, the finish chequered; a loop's one marker half of each."""
    x, y, radius = _disc(cr, width, height, 2)
    cr.save()
    cr.arc(x, y, radius, 0, 2 * math.pi)
    cr.clip()
    if kind != "start":
        cr.set_source_rgba(0.12, 0.12, 0.12, 1)
        cr.paint()
        cr.set_source_rgba(1, 1, 1, 1)
        step = radius / 2
        for row in range(4):
            for column in range(row % 2, 4, 2):
                cr.rectangle(x - radius + column * step, y - radius + row * step, step, step)
        cr.fill()
    if kind != "finish":
        if kind == "start-and-finish":
            cr.rectangle(x - radius, y - radius, radius, 2 * radius)
            cr.clip()
        color = _rgba(START_COLOR)
        cr.set_source_rgba(color.red, color.green, color.blue, 1)
        cr.paint()
    cr.restore()


def _marker(size: int, draw, *data) -> Shumate.Marker:
    dot = Gtk.DrawingArea(content_width=size, content_height=size)
    dot.set_draw_func(draw, *data)
    return Shumate.Marker(child=dot)


def _turn_on(button) -> None:
    """Show the Map: the yes for the program, the tiles on this map."""
    shown = button.get_ancestor(ActivityMap)
    set_tiles(True)
    if shown is not None:
        shown.show_tiles(True)


def _fit(widget, _clock) -> bool:
    """Once the map has its size: the whole track in view (a tick before the map is drawn, so
    that no tile is asked for another view)."""
    width, height = widget.map.get_width(), widget.map.get_height()
    if width <= 0 or height <= 0:
        return GLib.SOURCE_CONTINUE
    widget.fit(width, height)
    return GLib.SOURCE_REMOVE


def _dim(text: str) -> Gtk.Label:
    label = Gtk.Label(label=text, wrap=True, xalign=0, visible=False)
    label.add_css_class("dim-label")
    return label


class ActivityMap(Gtk.Box):
    """The map of a track: the tiles (after the yes) under the track, the markers of its ends
    and of the chart's cursor above them, and the attribution; under it the note and its button
    before the yes, or what is missing. Its handlers reach it through the widget of their
    signal."""

    __gtype_name__ = "OpenExpressActivityMap"

    def __init__(self, track: Track):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.track = track
        self.map = Shumate.Map(height_request=MAP_HEIGHT, hexpand=True)
        self.accessible_name = _("Map of the track")
        self.map.update_property([Gtk.AccessibleProperty.LABEL], [self.accessible_name])
        viewport = self.map.get_viewport()
        self.source = _map_source()
        viewport.set_reference_map_source(self.source)
        viewport.set_min_zoom_level(1)
        viewport.set_max_zoom_level(MAX_ZOOM)
        self.path = Shumate.PathLayer.new(viewport)
        self.path.set_stroke_color(_rgba(TRACK_COLOR))
        self.path.set_outline_color(_rgba(TRACK_EDGE))
        self.path.set_outline_width(EDGE_WIDTH)
        # libshumate draws the edge inside the stroke's width, on both sides
        self.path.set_stroke_width(TRACK_WIDTH + 2 * EDGE_WIDTH)
        for lat, lon in thinned(track.points):
            self.path.add_node(Shumate.Coordinate.new_full(lat, lon))
        self.map.add_layer(self.path)
        ends = Shumate.MarkerLayer.new(viewport)
        self.ends = {}  # "start", "finish" or "start-and-finish": its marker
        for kind, (lat, lon) in ends_of(track):
            marker = _marker(BOTH_SIZE if kind == "start-and-finish" else END_SIZE, _draw_end,
                             kind)
            marker.set_location(lat, lon)
            ends.add_marker(marker)
            self.ends[kind] = marker
        self.map.add_layer(ends)
        cursor = Shumate.MarkerLayer.new(viewport)
        self.marker = _marker(CURSOR_SIZE, _draw_cursor)
        self.marker.set_visible(False)
        cursor.add_marker(self.marker)
        self.map.add_layer(cursor)
        self.tiles = None  # the tile layer, while the tiles are on
        self.online = None  # whether the network was there when last told
        self.fit(600, MAP_HEIGHT)  # near already; _fit sets it for the map's own size

        self.attribution = Gtk.Label(use_markup=True, halign=Gtk.Align.END,
                                     valign=Gtk.Align.END, margin_end=6, margin_bottom=6,
                                     visible=False)
        self.attribution.set_markup(f'<a href="{COPYRIGHT_URL}">'
                                    f'{GLib.markup_escape_text(_("© OpenStreetMap contributors"))}'
                                    "</a>")
        self.attribution.add_css_class("osd")
        self.attribution.add_css_class("caption")
        overlay = Gtk.Overlay(child=self.map)
        overlay.add_overlay(self.attribution)
        frame = Gtk.Frame(child=overlay)
        frame.set_overflow(Gtk.Overflow.HIDDEN)
        self.append(frame)

        self.note = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.note.append(Gtk.Label(label=_(
            "The map can show streets and terrain under the track, from OpenStreetMap. The "
            "OpenStreetMap server then learns the area of each activity you open. You can turn "
            "this off again in Preferences."), wrap=True, xalign=0))
        button = Gtk.Button(label=_("Show the Map"), halign=Gtk.Align.START)
        button.add_css_class("pill")
        button.connect("clicked", _turn_on)
        self.note.append(button)
        self.append(self.note)
        self.too_old = _dim(_("The map needs a newer libshumate library to show streets and "
                              "terrain"))
        self.append(self.too_old)
        self.offline = _dim(_("No internet connection: only the parts of the map downloaded "
                              "before are shown"))
        self.append(self.offline)
        self.monitor = self.monitor_handler = None
        self.add_tick_callback(_fit)
        self.show_tiles(tiles_on())

    def fit(self, width: float, height: float) -> None:
        """The whole track in view of a map of this size; set, not flown to."""
        box = bounds(self.track.points)
        self.map.get_viewport().set_zoom_level(fitting_zoom(box, width, height))
        self.map.center_on(*center(box))

    def show_tiles(self, on: bool) -> None:
        """The tiles under the track (with the attribution) or not (with the note)."""
        asks = can_ask()
        on = on and asks
        if on and self.tiles is None:
            self.tiles = TileLayer(self.map.get_viewport())
            self.map.insert_layer_behind(self.tiles, self.path)
        elif not on and self.tiles is not None:
            self.tiles.stop()
            self.map.remove_layer(self.tiles)
            self.tiles = None
        self.note.set_visible(asks and not on)
        self.too_old.set_visible(not asks)
        self.attribution.set_visible(on)
        self._show_network()

    def show_cursor(self, at: float) -> None:
        """The marker where the chart's cursor is; hidden where the track has no record."""
        point = position_at(self.track, at)
        if point is not None:
            self.marker.set_location(*point)
        self.marker.set_visible(point is not None)

    def _show_network(self, *_args) -> None:
        """Without a network, said under the map; once it is back, the tiles that failed asked
        again."""
        online = _network_monitor().get_network_available()
        self.offline.set_visible(self.tiles is not None and not online)
        if online and self.online is False and self.tiles is not None:
            self.tiles.retry()
        self.online = online

    def do_map(self) -> None:
        # Told of the network only while on the screen: the monitor lives on, the map not.
        Gtk.Box.do_map(self)
        if self.monitor_handler is None:
            self.monitor = _network_monitor()
            self.monitor_handler = self.monitor.connect("network-changed", self._show_network)
        self._show_network()

    def do_unmap(self) -> None:
        if self.monitor_handler is not None:
            self.monitor.disconnect(self.monitor_handler)
            self.monitor = self.monitor_handler = None
        if self.tiles is not None:
            self.tiles.let_go()
        Gtk.Box.do_unmap(self)


def _maps_in(widget):
    child = widget.get_first_child()
    while child is not None:
        if isinstance(child, ActivityMap):
            yield child
        else:
            yield from _maps_in(child)
        child = child.get_next_sibling()


def tiles_changed(win) -> None:
    """The yes given or taken back in Preferences: the map shown now follows it."""
    navigation = win.navigation
    page = navigation.get_visible_page() if navigation is not None else None
    if not isinstance(page, Adw.NavigationPage):
        return
    on = tiles_on()
    for shown in _maps_in(page):
        shown.show_tiles(on)
