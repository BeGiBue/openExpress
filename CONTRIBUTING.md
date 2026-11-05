# Contributing

## Development
```bash
python3 -m pytest
```

The tests need Python 3.11+, `pytest`, `requests` and PyGObject 3.46+ with GTK 4 and
libadwaita (even without a display, because the window modules are imported); the tests with
a display also need WebKitGTK 6.0. They start their own hidden X server (Xvfb:
`xorg-x11-server-Xvfb` on Fedora, `xvfb` on Debian/Ubuntu), so no window shows on the desktop
and `xvfb-run` is not needed; without Xvfb they use the display of the session.
`OPENEXPRESS_TESTS_NO_DISPLAY=1` runs them without any display (the tests that need one are
skipped), `OPENEXPRESS_TESTS_ON_SCREEN=1` on the display of the session.
`OPENEXPRESS_TESTS_STRESS=1` also runs the long stress tests (a short version of each is in
the ordinary run). They need GNU gettext (`msgfmt`): they build the translations for
themselves. Some tests are skipped quietly when something is missing: the PTP test without
libusb-1.0 and the window-width tests without the Adwaita Sans font (the widths are measured in
it). The tests never reach the network (one that tries fails) and need no device.

## Trying a USB drive without such a watch

For testing only, not for ordinary use. `OPENEXPRESS_TEST_DRIVE_USB=VVVV:PPPP` (the vendor
and product ID that `lsusb` shows) makes openExpress take the mounted USB drive with these IDs
for a Garmin device connected as a USB drive. A pendrive with a copy of a watch's
`GARMIN/GarminDevice.xml` then stands in for that watch: the same unit ID and account, so
`--apply` uploads to Garmin Connect as from that watch. Its sync leaves Garmin Connect's queue
and TrueUp to the watch (nothing is downloaded or acknowledged, and the sync says so in one
line), and its records are its own: what it uploaded and its last sync are kept apart from the
watch's (`devices/<unit ID>/test-drive/` in the data folder), so its first sync starts anew and
the watch's tile and records stay as they were. The log says so in a warning (on the command
line also in the terminal); a value in another form is ignored with a warning. A connected MTP
device still comes first, and a drive that is not mounted is not taken.

```bash
OPENEXPRESS_TEST_DRIVE_USB=0781:5581 python3 -m openexpress sync    # dry run
```


## Adding a translation

What to translate and how, trying it in the window and sending it:
[Translating openExpress](docs/translating.md).

The template `po/openexpress.pot` is made from the files `po/POTFILES` lists, the metainfo's
template among them, by `tools/update-template.sh`; it is committed with the code that changes
the texts. The compiled catalogs and the translated metainfo are built at the build
(`python3 -m openexpress.catalogs`), never committed.
