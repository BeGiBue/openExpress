# Design: the full view of an activity (summary, map, chart, laps)

Status: the decisions of section 5 are made (each took its option a, marked "chosen"; D3a with what
section 5 adds to it; 10b kept as an idea for later; D11 with the tile of the ascent and every tile
that applies, up to five). Steps 1 to 5 of section 8 are implemented (the data of an activity,
`fit.activity_data`; the words of its page, `gui/words.py`; the page with its tiles,
`gui/activity_page.py`; the chart, `gui/activity_chart.py`; the map, `gui/activity_map.py`).
The work goes step by step, each step once accepted. The scope in section 1 is set once: what it
does not list is not added while it is implemented. After step 5 the page was found correct but
plain: section 10 adds to the scope (items 6–10 of section 1), designed together with the laps.
Its decisions are made: 13a, 14a, 15a, 16b, 17a with moving time from the records, 18a, 19b,
20a, 21a, 22a; 19a (the sets of a strength workout) is put off, an idea for later. Its steps
(10.5) replace steps 6–7 of section 8; steps 6 to 12 are implemented (the laps, the look, the
heart-rate zones, the training effect, the colours of the track, the details, the
documentation).

## 1. Scope

The Activities page lists the activities of the open device and of its backups and exports one
as GPX. This design adds what a user sees of one activity, in the same window:

1. **Its page**, opened from its row: a back arrow and a GPX export in the header bar.
2. **A summary** on top: four tiles, chosen by what the activity has (D11).
3. **A map of the track**, for an activity with positions (D2–D4).
4. **A chart** of heart rate, elevation or pace/speed (only those the file has), with the value
   where the cursor is, and that place marked on the map (D5, D6).
5. **Its laps**, as the device recorded them; a lap chosen is highlighted on the map and on the
   chart, chosen again it is not (D7, D20); kilometres from the records where the device kept no
   laps (D16).
6. **Its heart-rate zones**, as the device worked them out, and their bounds behind the chart of
   heart rate (D14, D19b).
7. **Its training effect and load** (D15).
8. **Its details**, in a row that opens (D17).
9. **The track coloured** by the series of the chart (D13); the sport's colour and the tiles'
   icons (D18).
10. **The mouse wheel over the map** scrolls the page; Ctrl and the wheel zoom it (D21).

From the device (MTP or USB drive) and from a copy in a backup, the same way; in the window
only.

Not in scope (a closed list; each would be a project of its own):

- changing, renaming or deleting an activity, on the device or in a backup;
- comparing activities; segments, personal records, power, running dynamics, splits other than
  the device's own laps and the kilometres of D16; recovery time and primary benefit (not in the
  public FIT profile, D15);
- the sets of a strength workout (D19a, put off: the watch often names an exercise wrongly, the
  user corrects it in Garmin Connect, and the file keeps the watch's names), the lengths and
  strokes of a swim, the transitions of a multisport activity beyond its sessions taken
  together;
- exports other than the GPX that exists; sharing, uploading to other services;
- a local archive of activities beyond the backups (the backups are the archive);
- map tiles for offline use (OpenStreetMap's tile policy forbids it, section 3), satellite or
  terrain maps, 3D;
- photos and films along the track (gpxfoto, gpxfilm take the GPX that is exported already);
- statute units (D10 keeps metric);
- activities of a remembered device that is not connected, beyond those its backups hold;
  activities of the Garmin Connect account;
- the command line: `openexpress activities` and `fit inspect` stay as they are.

## 2. What exists today

- `openexpress/fit.py`, own code from the public FIT protocol (Appendix A):
  - `iter_messages(data, wanted)` with the base types of the fields (signed values, invalid
    values recognised); a message after a compressed-timestamp header gets the time it gives.
  - `summary(data)`: from the sessions the start, the sport (several: multisport), the timer
    time (pauses left out), the distance and the ascent, and whether a position is there.
  - `points(data)`: of each record that has a position, latitude, longitude, altitude and time;
    the GPX export uses it.
  - Not read: a record's heart rate, cadence, distance, speed, power and temperature; the laps;
    of a session its average and maximum heart rate, average speed, calories, elapsed time and
    sub-sport.
- `openexpress/activities.py`: lists the activity files of the device and of its backups and
  reads 30 at a time, each file whole, for its summary; the summaries are kept in memory by
  file (path, size, time of change), the files are not. `gpx.track` makes the GPX.
- `gui/activities_page.py`: a row for each activity (sport; start, time, distance in km, ascent
  in m, source) with an export button; a row is not activatable.
- The window: `Adw.NavigationView` (the start page, then the device view); the device view is an
  `Adw.NavigationSplitView` (the sections on the side; on the content side one header bar with
  Refresh and Sync, the banner, the stack of the section pages). It works from 360 px.
- Units: metric only (km, m).
- `docs/privacy.md`: "Activities are read, not kept"; the program talks to Garmin's servers
  only.
- A map in GTK 4: libshumate is packaged by Fedora (1.7.0 on the computer this design was
  written on, with its `Shumate-1.0` typelib), but it is not in the GNOME runtime (the platform
  of `gnome-build-meta`, `sdk-platform.bst`, does not list it): the Flatpak would build it as a
  module, as GNOME Maps on Flathub does.
- Garmin Express has no view of an activity: nothing to match.

## 3. What is needed

**From the file.** A series of the records: the time (from the start), the distance, the speed
(the enhanced field first), the heart rate, the altitude (enhanced first) and the position; the
laps: start, elapsed and timer time, distance, average speed, average and maximum heart rate,
ascent; of the sessions: the elapsed time, the average and maximum heart rate, the average
speed, the calories and the sub-sport (Appendix A). A record with a compressed timestamp takes
its time from the last full timestamp, as the protocol says; a field not given is a gap, not a
zero.

**Sizes.** A hike of 8 h with a record every second is about 28,800 records, a file of about
1–2 MB; over MTP the device gives about 1.3 MB/s (30 activities, 10 MB, in 7.4–8.0 s), so 1–2 s
to read it. Python goes through such a file (28,800 records with position, altitude, heart
rate, distance and speed, 0.75 MB) in about 0.2 s (measured in step 1); the samples take a
few MB.

**The map's tiles.** OpenStreetMap's tile policy (operations.osmfoundation.org/policies/tiles)
asks of an application: the HTTPS URL `https://tile.openstreetmap.org/{z}/{x}/{y}.png`, best
configurable; a User-Agent of its own, stable, naming it (never a library's default); the
attribution shown, not hidden; the cache headers honoured, else each tile kept at least 7
days; only the tiles of what is shown, with a modest look-ahead; no download for offline use,
no prefetching. Heavy use may be blocked without notice; no personal data is to be sent.
libshumate sets one User-Agent for the process (`Shumate.set_user_agent`) and keeps tiles in a
file cache of its own.

**Privacy.** Asking for tiles tells the tile server (and the network) which area the activity
is in, often where the user lives. Today the program sends nothing about activities anywhere.

## 4. The look and the flow

The accepted mockup, weighed:

- *A click on a row opens the activity in the same window, a back arrow and a GPX icon in the
  header bar*: kept. The row becomes activatable (a chevron), its export button stays.
- *Four tiles: distance, time, average pace, average heart rate*: kept for an activity with a
  distance. Most activities of some users are workouts without one: their tiles are time,
  average and maximum heart rate and calories (D11), not four dashes.
- *The map, then the chart with Heart rate / Elevation / Pace and the value at the cursor*:
  kept. The map only for an activity with positions (no empty map for a treadmill, a pool, a
  trainer or a workout); the switch only lists what the file has; "Pace" is "Speed" for a ride
  (D12).
- *Clicking or dragging on the chart moves a marker on the map*: kept, and the arrow keys move
  the cursor too (the chart takes the focus), so that it works without a mouse.
- *The laps: no., distance, pace, heart rate; a click highlights the lap, a second click takes it
  off*: kept, as a list of rows that wrap (D7), with the time of each lap too.

```
 ← Running · Tue 28 Oct, 07:00                       [GPX]
 ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
 │ 10.2 km  │ │ 52:41    │ │ 5:10 /km │ │ 148 bpm  │       wide: four in a row
 │ Distance │ │ Time     │ │ Pace     │ │ Heart r. │       narrow: two by two
 └──────────┘ └──────────┘ └──────────┘ └──────────┘
 ┌──────────────────────────────────────────────────┐
 │  map with the track, the marker at the cursor     │       only with positions
 │                         © OpenStreetMap contributors│
 └──────────────────────────────────────────────────┘
 [ Heart rate | Elevation | Pace ]         31:20 · 152 bpm
 ┌──────────────────────────────────────────────────┐
 │  chart over time, the cursor line                 │
 └──────────────────────────────────────────────────┘
 Laps
   Lap 1    1.00 km · 5:02 · 5:02 /km · 141 bpm
   Lap 2    1.00 km · 5:08 · 5:08 /km · 147 bpm       chosen: highlighted
   …
```

A workout without positions: the tiles (time, heart rate average and maximum, calories), the
chart of heart rate, its laps; no map, no space for one.

In a narrow window (from 360 px) everything is one column; the tiles two by two; the chart keeps
its height and narrows; the lap rows wrap.

## 5. Decisions

### D1: where the activity's page opens — chosen: 1a

- **1a. A page pushed onto the window's navigation (recommended; chosen):** after the start page and
  the device view, a third page, with its own header bar: the back arrow (Alt+Left and the mouse's
  back button too), the activity's sport and start as the title, the GPX button at the end.
  - \+ The navigation the window has already; the whole width for the map and the chart.
  - − On a wide window the sections on the side are hidden while it is open.
  - What follows from it, found when step 3 was implemented: the page lies over the whole
    device view, its Refresh and Sync and its bar at the bottom too. Refresh and Sync from the
    keyboard (F5, Ctrl+R, Ctrl+S) go back to the device view first, where their bar is; the
    pages of the device drawn anew (opened again, Refresh) close the page as well, the device
    view staying on its Activities page.
- **1b. A navigation of its own inside the Activities section** (as some panels of GNOME
  Settings have), the sections staying on the side.
  - − The content side has one header bar for every section (Refresh, Sync, the banner): a
    second one under it for the activity, or a back button added to the shared one by hand.

### D2: what draws the map — chosen: 2a

- **2a. libshumate (recommended; chosen):** the GTK 4 map widget of GNOME (GNOME Maps uses it):
  tiles, a path layer for the track, a marker layer for the cursor, its file cache.
  - \+ Panning, zooming, scaling and the attribution as GNOME has them.
  - − Not in the GNOME runtime: one module more in the Flatpak manifest; from source the
    distribution's package (Fedora: `libshumate`); without it the page has no map and says why.
- As corrected after step 5 was tried on a screen: the track thick in a colour of its own,
  orange-red (`#e5420e`, 4 px) with a dark edge (`#6b1d05`, 1.5 px on each side), seen on the
  water, the green and the streets of the tiles and on the plain background, whatever the accent
  colour of the desktop; its start a green disc, its finish a chequered one, a loop's (a finish
  closer than 50 m) one disc half of each; the marker of the cursor in the accent colour of the
  chart's cursor (libadwaita's shade for a line or a mark on the window), 20 px with a white
  ring, above them. The tiles are drawn by openExpress (a layer of its own), not by
  libshumate's: libshumate places its tiles on whole pixels of the widget's whole scale, so on
  a screen at a fractional scale (125 %) two tiles meet between two pixels and the background
  shows through as a thin line. Each tile is drawn a pixel past its right and bottom edges,
  under the next one (at 100 % and 200 % nothing changes); while one loads, the tiles drawn
  before in its place, of a zoom below or above, are shown scaled (zoomed in or out with the
  mouse wheel, every tile of the next zoom is new: without them the map was empty for a few
  frames, even with the tiles in the cache), and once the view has all its own tiles those of
  other zooms are let go; those that failed are asked again when the network is back.
- Corrected after the pictures of step 12: the track fills its map but a tenth of it on each
  side, at the zoom where it falls between two whole zooms; the whole zoom below left up to
  half of the map empty (a hike from north to south took half of the map's height). Between two
  zooms the tiles are those of the nearest whole zoom, scaled from 0.71 to 1.41 of their size,
  as web maps do, not those of the zoom below, which would be up to twice as large and blurred:
  the map stays sharp and shows more, its words as small as 71 % of their size when the zoom
  falls just under a half. Checked on the screen at both styles, wide and narrow: no seam
  between tiles, the map full a tenth of a second after it opens (from the cache), the buttons
  and the wheel's steps without an empty frame but the edges of a zoom out for a frame.
- **2b. The track drawn by openExpress itself** (a `Gtk.DrawingArea`, no tiles).
  - \+ No new library, no network.
  - − A line without streets or terrain; panning and zooming written anew.
- **2c. A web map in WebKit** (as the sign-in window uses WebKit).
  - − A web page and JavaScript for a map; heavier than both.

### D3: the map's tiles and privacy — chosen: 3a

- **3a. Off until the user turns them on (recommended; chosen):** at the first map, a line over it:
  "The map loads its tiles from OpenStreetMap, which then learns the area of the activity" with
  "Show the map"; the choice kept (Preferences, Privacy, can be changed); meanwhile the track on a
  plain background, zoom and pan working.
  - \+ Nothing about an activity leaves the computer without consent, as the diagnostics.
  - − One click before the first map.
  - As chosen: the yes is given once for the whole program, kept in its settings, and can be
    taken back at any time (Preferences); until then every map shows the track on a plain
    background and, in the map's place, a short note of what turning the tiles on does (the
    OpenStreetMap server learns the area of the activity) with a button that turns them on.
    `docs/privacy.md` says it in the step that brings the tiles (step 5); the exact texts of the
    note, the button, the preference and the privacy page, in English and Polish, are shown for
    acceptance before that step.
- **3b. On, said in `docs/privacy.md`.**
  - − The area of every activity opened goes to the tile server without a question.
- **3c. Never: the track alone.**
  - − The map says little without streets.

### D4: where the tiles come from — chosen: 4a

- **4a. tile.openstreetmap.org (recommended; chosen):** the HTTPS URL of the policy, the User-Agent
  `openExpress/<version> (+https://github.com/TomaszBojanowski/openExpress)`, the attribution on the
  map, libshumate's cache in the program's cache folder (`~/.cache/openexpress/tiles`, in the
  Flatpak its own), kept as the headers say; only the tiles shown. The URL in one constant, so that
  it can change without other code.
  - \+ Free, no key, within the policy for an occasional use.
  - − It may be blocked without notice; no guarantee.
- As implemented in step 5: libshumate's own downloader keeps its tiles in `~/.cache/shumate`
  whatever the program asks, so openExpress gives libshumate a tile source of its own (libshumate
  1.1 and later): each tile asked with `requests` and the User-Agent above, at most two at a
  time, kept in `~/.cache/openexpress/tiles` (a part of the cache, `tiles`, cleared in
  Preferences → Storage and by `openexpress cache`) with how long the server's Cache-Control
  lets it be used (a week when it says nothing), asked again then with its tag, the cache
  brought to 100 MB from time to time; the log names no tile. The map's view is set to the
  track, never flown to, so that only the tiles shown are asked. The yes is kept in `gui.json`
  (`map_tiles`). Without a network (Gio.NetworkMonitor) a line under the map says that only the
  tiles downloaded before are shown; with a libshumate older than 1.1 the track stays on a plain
  background and a line says why. The Flatpak builds libshumate 1.7.0 and protobuf-c 1.5.2 (its
  vector renderer needs it; not used here).
- **4b. A provider with a key** (MapTiler, Thunderforest…).
  - − A key in the program or for the user to get; a contract.
- **4c. A URL the user sets.**
  - − A setting few need; the policy of each server is the user's to read.

### D5: the chart's axis — chosen: 5a

- **5a. The time since the start (recommended; chosen):** pauses as gaps in the line.
  - \+ The same for every activity, with or without a distance; laps and pauses fall where
    they happened.
- **5b. The distance when the activity has one, the time otherwise.**
  - \+ What runners and riders often look at.
  - − Two axes to draw and to test; a lap or a pause looks different in each.
- As implemented in step 4: the time since the first record; records more than 60 s apart (a
  pause) and a value not given leave a gap. The cursor goes to the nearest record, its value
  beside the switch ("31:20 · 152 bpm"; under the switch in a narrow window); with no record
  within 30 s, "no reading". The arrow keys move it by a hundredth of the activity, to the next
  record at least that far (never stuck at a pause); Home and End to the first and the last.
  The series: heart rate first (chosen when the page opens), elevation, then pace or speed (D12)
  for an activity with a distance; pace drawn with the faster on top, speed as recorded.
- Changed after the chart was tried on a walk with many stops (each stop pulled the line down to
  the end of the axis, a "comb", and squeezed the walking into a strip): a stop is a gap in the
  pace. A stop: over 10 s, slower than 0.2 m/s or than a quarter of the activity's typical speed
  (the median of its moving records), whichever is more, and not climbing or descending 0.05 m/s
  (180 m an hour, over 20 s): a climb slow forward, on a mountain hike, is no stop. Pace is the
  mean of the middle half of the speeds of moving records over 30 s around each record (the zeros
  of a stop and the slowing down before it do not pull it); its axis spans the pace of 5% to 95%
  of the moving records with a tenth of that more on each side, never from 0:00, and a pace
  beyond it (a very steep climb, a minute walked in a run) is drawn at its edge, not lost. The
  cursor on a stop says "no reading". One series: its name in place of the switch; none: the line "No heart rate,
  elevation or speed in this activity".

### D6: what draws the chart — chosen: 6a

- **6a. Own drawing in a `Gtk.DrawingArea` with Cairo (recommended; chosen):** the line, the axes
  with round values, the cursor and its value, the highlighted lap; the points brought down to about
  two per pixel column (the lowest and the highest of each, so that peaks stay).
  - \+ No new library; the look of the window; the numbers testable without a screen.
  - − About 250 lines of our own.
- **6b. A plotting library** (matplotlib with its GTK 4 backend).
  - − Large, not in the GNOME runtime, a look of its own.

### D7: the laps — chosen: 7a

- **7a. A list of rows that wrap (recommended; chosen):** "Lap 1" and "1.00 km · 5:02 · 5:02 /km ·
  141 bpm"; a click highlights it on the map and the chart, a second click takes it off; one lap at
  a time; no laps (or one, the whole activity): no list.
  - \+ Fits 360 px; the rows of the window.
- **7b. A table** (`Gtk.ColumnView`, a column each).
  - − Columns cut or scrolled in a narrow window.

### D8: where the data comes from — chosen: 8a

- **8a. The file read again at each opening, from the device or from its copy in a backup;
  nothing new kept (recommended; chosen):** a task with its progress (bytes), as every reading; the
  page
  gone before it ends, its result is dropped.
  - \+ "Activities are read, not kept" stays true; nothing to clean up.
  - − 1–2 s over MTP for a long activity, each time.
  - Its progress, as implemented in step 3: reading a file again tells no bytes, so the page
    shows a spinner with "Reading the activity…" in its place until the file is read (1–2 s over
    MTP); a file that cannot be read is said there, without an error dialog.
  - What follows from it: an activity's page is seen only while its device is connected, as the
    list today: it opens from the Activities page of the open device, which also lists the
    copies in that device's backups (read from this computer then); a device unplugged while
    the page is open closes it with the device view.
- **8b. A copy of each activity opened in the program's cache.**
  - \+ The second opening at once, also without the device.
  - − Tracks with positions on the disk in one more place; it overlaps with the backups.

### D9: a wide window — chosen: 9a

- **9a. One column at every width (recommended for the first version; chosen),** in a clamp (about
  1000 px).
  - \+ One layout to build and to test.
- **9b. The map and the chart side by side above a breakpoint.**
  - − A second layout; the chart is better wide, the map tall.

### D10: units — chosen: 10a

- **10a. Metric only, as the list (recommended; chosen).**
- **10b. The unit system of the Garmin Connect profile** (asked of the account).
  - − A question to the account for a page that otherwise asks nothing; every text twice.
  - Kept as an idea for later, of its own, for the list and the page together.

### D11: the summary tiles — chosen: 11a

- **11a. By what the activity has (recommended; chosen):** with a distance: distance, time, pace or
  speed, average heart rate; without: time, average heart rate, maximum heart rate, calories; a
  value the file does not give: its tile left out, the others taking the row.
- **11b. Always the four of the mockup,** "–" where a value is not given.
  - − A workout shows two dashes of four.
- Added when step 2 began: a tile of the total ascent ("Total ascent", "Całkowity wznios" as Garmin
  Connect in Polish says it, as its "Całkowity spadek"), in whole metres ("740 m"), only for an
  activity whose ascent is above zero, as the column of the list. A
  distance of 0 m counts as none (workouts may record one). Which tiles there are when more
  apply than the four places of the mockup (a hike with distance, time, pace, heart rate and
  ascent) was decided when step 3 began: B; the lap's line keeps no ascent. The options, in the
  order of the tiles (with a distance: distance, time, pace or speed,
  average heart rate, ascent; without: time, average heart rate, maximum heart rate, calories,
  ascent):
  - **A. Four places, the first four that apply:** a hike with a heart rate shows no ascent.
  - **B. Every tile that applies, up to five, flowing (recommended; chosen):** five in a row
    on a wide window, two by two and one in a narrow one; nothing left out.
  - **C. Four places, the ascent in place of the average heart rate for mountain sports**
    (hiking, mountaineering, snowshoeing, skiing): a rule by sport to keep.

### D12: pace or speed — chosen: 12a

- **12a. By sport (recommended; chosen):** running, walking, hiking: pace per km; swimming: pace per
  100 m; cycling and others with a distance: speed in km/h.
- **12b. Speed always.**
  - − Runners read pace.

## 6. What changes

| Module | Change |
|---|---|
| `fit.py` | `activity_data(data)`: the samples of the records (time, distance, speed, heart rate, altitude, position; a value not given is a gap), the laps and what the sessions say together (Appendix A). Of a file cut short or damaged, what reads with its state, as `summary`; FitError for what is no FIT file. |
| `activities.py` | Nothing: `read_file` reads the file again, from the device or from its backup copy, in the page's task. |
| `gui/activity_page.py` (new) | The page: header bar (back, GPX), tiles, map, chart, laps; reading, errors, the narrow window. |
| `gui/activity_chart.py` (new) | The chart widget (D5, D6): series, axes, cursor, keyboard, highlighted lap. |
| `gui/activity_map.py` (new) | libshumate around the track (D2–D4): tiles or not, the marker, the highlighted lap, the attribution, the User-Agent, the cache folder. |
| `gui/activity_laps.py` (new, step 6 of 10.5) | The laps' rows, the kilometres of D16, the lap chosen told to the chart and the map. |
| `gui/activity_zones.py` (new, step 8 of 10.5) | The section of the heart-rate zones (D14): its rows and bars, the zones' colours. |
| `gui/activity_effect.py` (new, step 9 of 10.5) | The section of the training effect and load (D15): its rows, the effects' bars. |
| `gui/activity_colours.py` (new, step 10 of 10.5) | The track's colours by the chart's series (D13): the scale, its ends, each point's colour, the legend and its switch. |
| `gui/activity_details.py` (new, step 11 of 10.5) | The closed row of the details (D17) and its rows. |
| `gui/activities_page.py` | Rows of FIT files activatable (an arrow at their end); a click opens the page; the export button shared with the page. |
| `gui/device_page.py`, `gui/app.py` | The page closed when the pages of the device are drawn anew, and before Refresh and Sync from the keyboard. |
| `gui/words.py` | Durations, distances, pace and speed by sport, heart rate, the tiles' names, the laps' lines; English and Polish. |
| `gui_settings` | The choice of D3 (tiles on or off). |
| `packaging/flatpak/` | libshumate as a module (if 2a), without its vector renderer. |
| `docs/guide.md`, `docs/privacy.md`, `README.md` | The page; the tiles and what they tell (D3, D4). |

The window's rules hold: a new module begins with what it holds ("Has:"); its attributes made
by `MainWindow._init_state`; its texts wrap and fit 360 px; no device read on the GTK thread; a
stall of the device while the activity is read is told as every stall (the banner, the device
closed, this page with it), a device unplugged meanwhile as an activity that cannot be read.

## 7. Risks

1. **libshumate.** Not in the GNOME runtime: the Flatpak builds it (a module to keep up to
   date); from source each distribution has its own version (Fedora 1.7; older systems may lack
   `Shumate.set_user_agent` or the package): without it, no map and a line saying what to
   install. The first step of the map checks what is there.
2. **The tile server.** It may block an application without notice; the User-Agent and the
   cache are what it asks for; the URL in one place.
3. **Privacy.** The area of an activity goes to the tile server when tiles are on; D3 decides
   whether that needs consent. Tests must ask no tile (the tests' network guard fails any): the
   map gets no tile source in the tests.
4. **Long activities.** 28,800 records to read and to draw: the reading measured in step 1, the
   chart drawn from the points brought down to the width; the path layer of libshumate with
   tens of thousands of points to be measured in step 5 (thinned if slow).
5. **What a file holds.** Pauses (timer time against elapsed time), several sessions, laps with
   no position, compressed timestamps, a heart rate missing for minutes, positions that jump: each
   a case in the tests of step 1, on made-up files.
6. **Noise.** Pace from speed jumps: smoothed over about 30 s; heart rate and elevation drawn as
   they are.
7. **The narrow window.** Tiles, chart and lap rows measured at 360 px, in both languages.

## 8. Order of work

Each step starts with a test that fails on the code before it, keeps its texts and their Polish
in the same commit, and passes the usual gate before its commit: ruff without findings, the
tests with and without a display, and the program's folders unchanged by the tests. Each step
waits for acceptance.

1. **The data of an activity (`fit.activity_data`).** Failing tests on made-up FIT files: the
   series of a run (time, distance, speed, heart rate, altitude, position); a workout without
   positions or distance; pauses; compressed timestamps; laps and the session's extras; a file
   cut short or damaged (what reads, with its state); a long activity read within a time
   measured here.
2. **The words.** Failing tests: durations with seconds ("52:41"), distances (km with two
   decimals, swimming in metres, 0 m none), pace by sport and speed (D12), heart rate ("148
   bpm", "148 ud./min"), calories, ascent, the tiles' names (their own texts, not those of the
   command line), a lap's line; English and Polish, hard spaces.
3. **The page.** Failing tests: a click on a row opens it (D1), the back arrow returns to the
   list where it was, the GPX button exports as the row does; the tiles by what the activity has
   (D11); read from the device and from a backup copy (D8), with progress; unplugged meanwhile
   (a message, the back arrow); a stall (the banner, the page closed with the device); the
   narrow window.
4. **The chart.** Failing tests: the series the file has, and only those, in the switch; the
   axis (D5) with round values; the points brought down without losing a peak; the value at a
   place; the cursor by click, drag and arrow keys; pace smoothed; a gap where a value is
   missing; the narrow window.
5. **The map.** Before it, the exact texts of D3 (the note, the button, the preference, the
   privacy page; English and Polish) for acceptance. Failing tests: no map without positions; the
   track and its bounds; the marker follows the chart's cursor; tiles only after the yes of D3,
   kept for the program and taken back in Preferences, the note and the button meanwhile; the
   User-Agent and the cache folder of D4, the attribution shown; without libshumate a line
   instead; no tile asked in the tests. The Flatpak manifest with libshumate, `docs/privacy.md`.
6. **The laps.** Failing tests: the rows (D7), a click highlights the lap on the chart and on
   the map, a second click takes it off, another lap moves it; no list for one lap. Designed
   anew with the additions: step 6 of section 10.5.
7. **Documentation**: `docs/guide.md`, `README.md`, the status of this design. With the
   additions: step 12 of section 10.5, after its steps 7–11.

On a device: a run and a ride with positions, a workout without, a long hike (the time to read
and to draw), an activity from a backup with the device unplugged, the map with and without the
network.

## 9. Size

About 950 lines of code (fit about 150, the words about 80, the page about 180, the chart about
250, the map about 200, the laps about 90), about 900 lines of tests on made-up files, about
40 texts with their Polish, 7 commits, one a step of section 8; with 2a, one module in the
Flatpak manifest. The additions of section 10: about 860 lines of code, 920 of tests and 50 texts
more (10.5).

## 10. Additions, designed with the laps (proposed after step 5)

The page of step 5 is right but plain: tiles, a map, a chart. This section weighs what more the
files of a watch hold, designs it together with the laps of step 6, so that the page is built
step by step without being patched later, and leaves each choice open (D13–D22) until accepted.
Mockups of whole pages (a walk with GPS and a strength workout without, wide and at 360 px, in
Polish) were drawn on the hidden display with made-up data for review; they are not in the
repository.

### 10.1 What the files hold

Looked at on the activity files of a fēnix 8 (walks, hikes and strength workouts); only which
messages and fields are there, never a value that names a person or a place. From the public
FIT profile (FIT SDK 21.218); a field it does not describe is not used.

| Candidate | Where in the file | In the fēnix 8's files |
|---|---|---|
| Colours of the track by a series | records: heart rate, altitude, speed | heart rate in all; the others with GPS |
| Heart-rate zones | `time_in_zone` (216) for the session: time in each zone, the zones' high bounds, how they are worked out (% of max, of reserve, of threshold), the max, resting and threshold heart rate | in all; 7 times and 6 bounds (below zone 1, zones 1–5, above the top bound); the times add up to the timer time |
| Training effect | session: aerobic (24) and anaerobic (137), scale 10, 0.0–5.0 | in all |
| Training load | session: `training_load_peak` (168), scale 65536 | in all |
| Recovery time, primary benefit | not in the public profile (fields it does not describe) | – |
| Kilometres | laps (19) with `lap_trigger` (24) | every lap of a walk or hike is a distance lap of 1000 m (the watch's auto lap); a strength workout has no laps |
| Descent, min and max altitude | session 23, 127, 128 | with GPS |
| Cadence | session 18, 19 (+ fractional 92, 93), strides a minute on foot | walks and hikes |
| Steps | session `total_cycles` (10): strides on foot | all on foot |
| Maximum speed | session 125 (15) | with GPS |
| Minimum heart rate | session 64 | in all |
| Temperature | session 57, 58, 150 | nearly all (the watch's sensor, warmed by the wrist) |
| Breathing | session 169, 170, 180, scale 100 | strength workouts only |
| Moving time | session `total_moving_time` (59) | none: worked out from the records, or left out (D17) |
| Active time | session 78 | strength workouts |
| Sets | `set` (225): duration, repetitions, weight (scale 16), set type (active, rest), category (53 in the profile), category subtype (1,846 names) | every strength workout, about 60 sets with rests |

On the walks of these files most of the time is below zone 1: zones as the colours of the
track would paint a walk in one colour (D13).

### 10.2 The page, from top to bottom

The header bar (back, a dot of the sport's colour before the title, GPX), the tiles with their
icons, the map with its legend under it (with positions), the chart, the laps (or kilometres),
the heart-rate zones, the training effect and load, the details
(closed). Each part only when the file has its data; a section without data is not shown, not
empty.

```
 ← ● Walk · Sat 7 Mar, 10:12                                [GPX]
 ┌ ⌖ 3.25 km ┐ ┌ ◷ 40:00 ┐ ┌ ◔ 12:17 /km ┐ ┌ ♥ 108 bpm ┐ ┌ ˄ 12 m ┐
 ┌──────────────────────────────────────── [+] ┐
 │ the track coloured by heart rate, a lap      │
 │ chosen: thick, the rest thin and faded  [−]  │
 └──────────────────────────────────────────────┘
 Track colour: heart rate  94 ▬▬▬▬▬ 118 bpm        Colours [on]
 [ Heart rate | Elevation | Pace ]          15:00 · 101 bpm
 ┌ the chart, the chosen lap a band behind it ┐
 Laps
   Lap 1   1.00 km · 12:42 · 12:41 /km · 110 bpm
   Lap 2   1.00 km · 12:20 · 12:20 /km · 101 bpm         ✓
 Heart-rate zones        Bounds from the device: % of lactate threshold (… bpm)
   Zone 5  above … bpm                              0:00 · 0%
   ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
   …
   Below zone 1  below … bpm                      38:24 · 96%
 Training effect
   Aerobic                                  1.6 · Minor benefit
   Anaerobic                                    0.0 · No benefit
   Training load                                              28
 Details ▾
```

### 10.3 Decisions

#### D13: the colours of the track — chosen: 13a

- **13a. By the series chosen on the chart (recommended; chosen):** heart rate, elevation, pace or
  speed, on a scale from blue to red over the activity's own range (its 5th to 95th percentile;
  faster pace is red), a dark edge under it as today; a legend under the map with the two ends
  and the series' name; a switch "Colours" beside it, kept for the program in `gui.json`, on at
  first; off, the track is `#e5420e` as today. The track becomes a layer of openExpress (as the
  tiles' layer), needed by the laps (D20) anyway.
  - \+ Where the effort, the climb or the pace changed, on the map; follows the chart.
  - − Colours that mean something else for each series; the legend says which.
- As implemented in step 10 (`gui/activity_colours.py`): the scale is 64 steps of OKLCH from
  blue `#017dd6` through purple to red-orange `#f75e1c` (hue 250° rising to 40°, chroma 0.17 to
  0.20, lightness rising from 0.58 to 0.675), with no green and no yellow. Every colour stands
  out at 3:1 at least from the map without tiles, the window's background (3.06 on `#fafafb`,
  3.68 on `#222226`); on the tiles a coloured track has a neutral dark edge `#241f31` (6.9 on
  the motorways of OpenStreetMap, 10.0 on its water, 13.9 on its land), as the colour alone
  is 1.4–3.8 there. The ends are the activity's 5th and 95th percentile (nearest rank); a
  point takes the value of the record at its time or the last before it, beyond an end the
  colour of that end, without a value grey `#8a898e`; a series of one value is the middle.
  The legend is under the map, before the note of the tiles: "Track colour: heart rate", the
  two ends with their unit around the scale, and the switch "Colours" (gui.json
  `track_colours`, on until turned off); off, the track is as before (`#e5420e` on
  `#6b1d05`) and the legend its switch alone. A lap chosen fades the rest of the track in its
  colours. The series is the chart's: another chosen there, the track and the legend follow.
- **A limit of the scale:** with deuteranopia or protanopia its blue and its purple (the
  lower half) look alike and its upper half turns olive; its ends stay apart (33 and 26 in
  OKLab ×100, Machado 2009 at full severity) and its order is seen by its lightness and said
  by the legend. Every scale from blue to red has it; one that keeps the order for them
  (light to dark in one hue, or blue to yellow) would lose the track on the light tiles or
  the dark background.
- **13b. Heart rate by its zones (the zones' colours).**
  - − A walk mostly below zone 1 is one colour (10.1).
- **13c. One colour always.**
- Corrected after the pictures of step 12: each piece of one colour ends flat where the next one
  begins, and starts a pixel back along the stretch before, so that its round join fills a bend
  and no gap opens there; a round end stuck out over the pieces next to it, and a short piece (a
  heart rate a moment higher) showed as a dot of its colour. Only the track's own ends are round.
  Each stretch between two points is in the colour of the point it starts at, and a faded track
  (the rest of a lap chosen) has its colours laid on together, blended once.

#### D14: heart-rate zones — chosen: 14a

- **14a. As the device worked them out, from the file (recommended; chosen):** a section "Heart-rate
  zones": zone 5 on top, then 4–1 and "Below zone 1", each with its bounds in bpm, its time and
  share, and a bar in the zone's colour (grey, blue, green, yellow, orange, red; the time above
  the top bound counted in zone 5); under the title how the bounds are worked out and from what
  ("% of lactate threshold (… bpm)", "% of maximum heart rate (… bpm)", "% of heart rate reserve",
  "custom"). No section when the file has none.
  - \+ The zones the watch showed during the activity, even if they were changed later.
- Corrected when step 8 began (the colours drawn on the cards of both styles): the yellow had
  less than the contrast of 3:1 that a bar needs on the light cards (`#f6d32d`, 1.5), and so
  had the orange (`#ffa348`, 2.0); a red of the GNOME palette had it on the light cards only
  (`#e01b24`, 4.8 light, 2.6 dark). One colour each, of at least 3:1 on both: below zone 1
  `#8a898e` (3.5 light, 3.6 dark), zone 1 `#3584e4` (3.8, 3.3), zone 2 `#26a269` (3.3, 3.8),
  zone 3 `#bd8100` (3.3, 3.7; `#c88800` had 3.0 on the light cards, with no margin), zone 4
  `#e66100` (3.5, 3.6), zone 5 `#f0384a` (3.9, 3.2): each at 3.15 at least, which a test keeps.
  The bar's track under it is the text's colour, faint.
- Corrected when step 8 was tried on a watch (its times in the zones the same as Garmin
  Connect's to the second, its bounds a beat off): a device keeps as the bound of a zone the
  first beat of the zone above it, and Garmin Connect shows them so. Made-up bounds 118, 141, 158,
  170, 183, 195 are below zone 1 "below 118 bpm", zone 1 "118–140 bpm", zone 2 "141–157 bpm",
  zone 3 "158–169 bpm", zone 4 "170–182 bpm", zone 5 "above 182 bpm" (no top: the last bound
  is not shown, the time above it is zone 5's). The bands of D19b run from bound to bound as
  before. The bounds are always the activity's file's own. A row's bounds break onto a new
  line between words only (never in "ud./min"; Pango still may after the dash of a range,
  which fits the narrowest window on one line).
- **14b. 14a, and where the file has no zone times, worked out from the records with the
  bounds of its settings (`zones_target`, 7).**
  - − More code for files that are rare among those looked at.
- **14c. Worked out from the records with % of an assumed maximum.**
  - − A guess shown as a fact.

#### D15: training effect and load — chosen: 15a

- **15a. The values with a word (recommended; chosen):** "Aerobic 3.2 · Improving", "Anaerobic 2.0 ·
  Maintaining", each with a bar over 0–5; the word from the public scale (below 1 no benefit, 1
  minor benefit, 2 maintaining, 3 improving, 4 highly improving, 5 overreaching); "Training
  load" as its number. Recovery time and primary benefit are left out: the public profile does
  not describe where the file keeps them, and working that out would be undocumented Garmin data
  (the project's rule stops there).
- As implemented in step 9: the bars as those of the zones (D14), in the desktop's accent colour
  (as the chart's line); the load a whole number (a half up), with no bar, as it has no fixed
  top; a row the file does not give is left out, with none of the three no section; 0.0 is
  shown ("0.0 · No benefit"). The values are the session's fields 24, 137 and 168 (Appendix A).
- Corrected when step 9 was tried on a watch: the Polish words are Garmin's own, those of Garmin
  Connect, with which the page is compared. "Efekt treningu", "Aerobowy", "Beztlenowy" and
  "Obciążenie wysiłkowe" as Garmin Connect in Polish says them; the words of the scale as the
  help of Garmin Connect in Polish has them: 0.0–0.9 "Brak korzyści", 1.0–1.9 "Umiarkowana
  korzyść", 2.0–2.9 "Utrzymanie", 3.0–3.9 "Poprawa", 4.0–4.9 "Duża poprawa", 5.0
  "Przeciążenie". Other Polish texts of Garmin's say the scale otherwise: the manual of the
  fēnix 8 "Niewielka korzyść" and sentences ("Utrzymanie sprawności aerobowej", "Wpływ na
  sprawność aerobową", "Znaczny wpływ…", "Ponad siły…"), Garmin's Polish page on the aerobic
  training effect "Nieznaczna korzyść", "Wzrost" and "Znaczna poprawa"; the page keeps
  Connect's. The English words were Garmin's already.
- **An assumption to check:** of several sessions (a multisport activity) each of the three is
  the highest of the sessions. No such file was looked at; when one comes, compare with Garmin
  Connect (whether the device adds up the legs, or keeps each leg's own).
- **15b. The values only.**
- **15c. Left out.**

#### D16: kilometres — chosen: 16b

- **16a. The device's laps only:** the fēnix 8 already keeps a lap each kilometre (10.1).
- **16b. Kilometres from the records where the device kept no laps (recommended; chosen):** an activity
  with one lap (the whole of it) and at least 2 km gets "Kilometres" in place of "Laps", worked
  out from the records' distance, the last one shorter; the rows and highlighting as the laps.
  - \+ The same page for a device without auto lap; no switch.
- **16c. Laps and kilometres always, with a switch.**
  - − Twice the same list on a watch with auto lap at 1 km.

#### D17: details — chosen: 17a, moving time (1)

- **17a. A closed "Details" row that opens (recommended; chosen):** in this order, only what the file
  has: total time (with pauses), moving time, active time (strength), descent, elevation (min–
  max), maximum pace or speed, cadence (average, max; steps a minute on foot, rpm on a bike),
  steps, heart rate (min–max), calories (when not a tile), temperature (average, min–max),
  breathing (average, min–max). What a tile shows already is not repeated.
  - Moving time, sub-choice: **(1) worked out from the records with the chart's rule of a stop
    (recommended; chosen):** the same stops as the gaps of the pace; it may differ from Garmin Connect's;
    **(2) only from the file:** none on the fēnix 8. Corrected when step 11 was tried on a
    watch: worked out from the records, but by a rule of its own, as Garmin Connect counts it
    (below).
  - Steps: two a stride; checked against Garmin Connect on one walk in the step's test on a
    device.
- As implemented in step 11 (`gui/activity_details.py`, the words in `gui/words.py`): an
  `Adw.ExpanderRow` "Details" after the training effect, closed each time the page opens; each
  detail a row, its name (wrapping in a narrow window) and its value on one line. The names are
  Garmin Connect's, as Garmin Connect in Polish shows them: "Upływ czasu", "Czas ruchu", "Średnie tempo ruchu" (Connect shows it: the
  distance over the moving time; "Średnia prędkość ruchu" for a speed by analogy, not seen in
  Connect yet), "Czas ćwiczeń" and "Czas odpoczynku" (strength), "Całkowity spadek",
  "Minimalna wysokość" and "Maksymalna wysokość" (two rows as in Connect rather than one
  range), "Najlepsze tempo", "Średnia kadencja" (with its maximum), "Kroki"; "Tętno",
  "Kalorie", "Temperatura" and "Częstotliwość oddechu" as before. In English Connect's own
  words; "Work time" and "Rest time" as Garmin's forums quote Connect's strength workouts.
  The order: elapsed time, moving time, work time, rest time, descent, minimum and maximum
  elevation, average moving pace (speed), best pace (maximum speed), cadence, steps, heart rate
  (minimum–maximum), calories, temperature (average, minimum–maximum), respiration rate (the
  same).
  - What a tile shows is not repeated: an elapsed, moving or work time the same as the tile's
    time, a moving pace the same as the tile's pace, calories when they are a tile (a workout).
    A value of 0 (descent, steps, cadence) is left out, as the ascent's tile is.
  - Moving time and its pace only for an activity with a distance. Corrected when step 11 was
    tried on a watch (the chart's rule gave a walk over a minute more than Garmin Connect): the
    file has no moving time (`total_moving_time` empty in every file of the fēnix 8 looked at),
    so it is worked out as Garmin Connect does: the time from each record whose own speed is
    0.2 m/s or more to the next one, but between records more than a minute apart (a pause).
    The fēnix 8 writes a speed of exactly 0 when it finds you stopped (no value between 0 and
    0.2 m/s in its files), and so does it on a slow steep climb: such a climb is no moving, as
    in Garmin Connect, which leaves it out too (keeping such a climb as moving parted far from Connect on a mountain hike).
    The chart keeps its own rule of a stop (a window of 10 s, a climb no stop): its gaps of the
    pace are for the eye, a few seconds wider or narrower around a stop.
    Checked against Garmin Connect on three activities of the fēnix 8 (two walks, one with a
    pause of its timer, and a mountain hike): within 1%. The tests that compare them read the
    activities and Connect's values from a list in `testdata/`, which is not in the
    repository.
  - Temperature, corrected when step 11 was tried on a watch: the session keeps whole degrees
    (Garmin Connect shows them with a decimal); the average and the range are those of the
    records' temperatures, with one decimal as Garmin Connect shows them ("21.4 °C
    (18.0–26.0 °C)"), checked against Connect on a walk and a strength workout.
  - Work time is the session's `active_time` (78); rest time the rest sets (`set`, 225, set
    type 0) added up, as the session has no field of it.
  - Cadence and steps on foot (running, walking, mountaineering, hiking, snowshoeing) in steps:
    two a stride, the fractional fields added; on a bike (cycling, e-biking) cadence in
    revolutions a minute; in other sports neither.
  - Numbers up to 9999 as they are, from 10 000 with the thousands apart: a hard space in
    Polish (Polish typography), a comma in English; also on the tiles
    (calories, ascent, a swim's metres). A minus sign (U+2212) below zero.
  - Several sessions: descent, strides and active time added up, the lowest minimum and the
    highest maximum, averages weighted by the timer time (as the average heart rate).
- **17b. Always open, as a group.**
  - − Long on a narrow window.
- **17c. More tiles.**
  - − Ten tiles say nothing first.

#### D18: the look — chosen: 18a

- **18a. The sport's colour and the tiles' icons (recommended; chosen):** a dot of the sport's colour
  before the title in the header bar and the tiles' icons in it (foot `#26a269`, cycling
  `#1c71d8`, swimming and water `#62a0ea`, winter `#99c1f1`, training and strength `#9141ac`,
  others `#77767b`; the GNOME palette); the icons from the GNOME icon theme already in the
  runtime: distance `mark-location`, time `preferences-system-time`, pace and speed
  `power-profile-performance`, heart rate `emote-love`, ascent `go-up`, calories `emoji-food`.
  The colour says nothing the title does not (it is no carrier of meaning alone).
  - \+ No new dependency, no picture to draw.
- Corrected when step 7 began (the colours above drawn on the cards of both styles): five of
  the six had less than the contrast of 3:1 that an icon needs, on the light cards (water,
  winter) or on the dark ones (training, cycling, others). One colour each, of at least 3:1 on
  both: on foot `#26a269` (3.3 light, 3.8 dark), cycling `#3584e4` (3.8, 3.3), water `#2190a4`
  (3.8, 3.3), winter `#6f8396` (3.9, 3.2), training `#c061cb` (3.6, 3.4), others `#8a898e`
  (3.5, 3.6). The groups, by the sport of the FIT profile: on foot running, walking, hiking,
  mountaineering, rock climbing, floor climbing, the wheelchair's push walk and run, geocaching;
  cycling, e-biking; water: swimming, rowing, paddling, boating, fishing, sailing, stand-up
  paddleboarding, surfing, wakeboarding, water skiing, kayaking, rafting, windsurfing,
  kitesurfing, diving, water tubing, wakesurfing, water sport, snorkeling, pool apnea,
  canoeing; winter: cross-country and alpine skiing, snowboarding, ice skating, snowshoeing,
  snowmobiling, winter sport; training: fitness equipment, training, boxing, HIIT, meditation,
  mixed martial arts, dance, jump rope, mobility; others the rest. The dot is not shown in a
  narrow window (up to 450 sp): it would cut the start under the title; the icons keep the
  colour there.
- **18b. Icons of the sports in the header** (walking, running, cycling…): the GNOME theme has
  none; about eight of our own (drawn for the project, or taken with a compatible licence).
  - − Drawing and a licence to check; could come after 18a.
- **18c. No colour; icons on the tiles only.**

#### D19: own proposals — chosen: 19b; 19a put off

- **19a. The sets of a strength workout (recommended; put off):** a section "Sets" after the chart: the
  sets of one exercise in a row ("Squat", "3 sets · 10 × 60 kg, 10 × 60 kg, 8 × 65 kg"; a set
  without repetitions by its time, "1:00"); the rests left out. The names of the 53 categories of
  the profile in English and Polish, not the 1,846 names of its exercises. About half the
  activities looked at are strength workouts, now a page of a chart only.
  - Put off: the watch often names an exercise wrongly and it is corrected in Garmin
    Connect; the file on the watch keeps the wrong names. An idea for later: the sets as Garmin
    Connect keeps them, corrected. Until then nothing stands in their place on the page.
- **19b. The bounds of the heart-rate zones as faint bands behind the heart-rate chart
  (recommended; chosen):** with D14; the zone of each part of the line seen at once.
- As implemented in step 8: bands of zones 1–5 only, in the zones' colours of D14 at about an
  eighth of their strength; none below zone 1, which is no zone (a walk's chart stays mostly
  bare, as its time is); above the top bound in the colour of zone 5, as its time.
- **19c. The fastest lap marked:** not recommended (one more sign on each row).

#### D20: the laps (the questions of step 6) — chosen: 20a

- **20a. As drawn (recommended; chosen):** a section "Laps" (or "Kilometres", D16) of rows: the line
  large ("1.00 km · 12:20 · 12:20 /km · 101 bpm"), "Lap 2" small above it; a row chosen is
  tinted with a check mark, chosen again it is not, another moves it; Enter and Space as a click.
  On the chart a band behind the lap's time; on the map the lap thick with its edge, the rest
  thin and half transparent; the map's view stays (no new tiles); the chart's cursor stays where
  it was. One lap (the whole activity): no section, or kilometres (D16b); no laps (a strength
  workout): no section; the last lap, shorter, as it is.
- As implemented in step 6 (`gui/activity_laps.py`): the track is drawn by a layer of
  openExpress in place of libshumate's path layer, placed as libshumate places its markers;
  the rest of the track at half strength; a kilometre worked out from the records runs from the
  record that ends the one before to the record that reaches it, its timer time without the
  gaps of more than 60 s, a last part under 10 m left out.
- As implemented in step 8: a lap shown as 1.00 km with a pace a kilometre, or as 100 m with a
  pace of 100 m (a swim), leaves out its pace: it would repeat its time ("1.00 km · 12:20 ·
  101 bpm"); a ride keeps its speed. The chart's switch of series has no background under the
  pointer around its buttons (libadwaita gives one to a flow box's child that can be
  activated); only the buttons show it.
- **20b. 20a with the map's view fitted to the chosen lap.**
  - − New tiles at each click; the place of the lap in the whole is lost.

#### D21: the mouse wheel over the map — chosen: 21a

- **21a. The wheel scrolls the page; Ctrl + wheel zooms the map (recommended; chosen):** buttons + and
  − on the map (its top right), double click and pinch zoom too, dragging moves it; a wheel
  without Ctrl over the map shows "Ctrl + scroll to zoom" on it for a moment.
  - \+ Scrolling the page never stops at the map (today it zooms the map instead).
- As implemented in step 6: a wheel's notch scrolls the page as GTK does (the page's height to
  the power of two thirds), a touchpad by its pixels; the buttons go to the next whole zoom
  (libshumate's own step is a fifth of a level, a notch of the wheel); the hint stays 1.5 s.
- **21b. As today:** the wheel zooms the map.
- **21c. The map takes the wheel only after a click on it,** until the pointer leaves.
  - − A state the user does not see.

#### D22: the order of the page — chosen: 22a

- **22a. As 10.2 (recommended; chosen):** what the activity was first (tiles, map, chart, laps),
  how hard it was after (zones, effect), the rest last and closed.
- **22b. Zones and effect before the map.**

### 10.4 New texts (English, Polish)

Accepted, but for those of the sets (D19a put off), which are not added.

| English | Polish |
|---|---|
| Laps / Kilometres | Okrążenia / Kilometry |
| Kilometre {number} | Kilometr {number} |
| Heart-rate zones | Strefy tętna |
| Zone {number} / Below zone 1 | Strefa {number} / Poniżej strefy 1 |
| {low}–{high} bpm / below {rate} bpm / above {rate} bpm (corrected in step 8: a zone's bounds as Garmin Connect shows them, D14) | {low}–{high} ud./min / poniżej {rate} ud./min / powyżej {rate} ud./min |
| {time} · {percent}% | {time} · {percent}% |
| Bounds from the device: % of maximum heart rate ({bpm}) | Granice z urządzenia: % tętna maksymalnego ({bpm}) |
| Bounds from the device: % of heart rate reserve | Granice z urządzenia: % rezerwy tętna |
| Bounds from the device: % of lactate threshold ({bpm}) | Granice z urządzenia: % progu mleczanowego ({bpm}) |
| Bounds from the device: your own | Granice z urządzenia: własne |
| Training effect / Aerobic / Anaerobic / Training load | Efekt treningu / Aerobowy / Beztlenowy / Obciążenie wysiłkowe (corrected in step 9: Garmin's words, D15) |
| No benefit / Minor benefit / Maintaining / Improving / Highly improving / Overreaching (0.0–0.9, 1.0–1.9, 2.0–2.9, 3.0–3.9, 4.0–4.9, 5.0) | Brak korzyści / Umiarkowana korzyść / Utrzymanie / Poprawa / Duża poprawa / Przeciążenie (Garmin Connect's help on the training effect, D15) |
| Details | Szczegóły |
| Elapsed time / Moving time / Work time / Rest time (corrected in step 11: Garmin Connect's words, D17) | Upływ czasu / Czas ruchu / Czas ćwiczeń / Czas odpoczynku |
| Total ascent (the tile of step 2; Garmin Connect's word) | Całkowity wznios |
| Total descent / Minimum elevation / Maximum elevation (step 11: two rows, not a range) | Całkowity spadek / Minimalna wysokość / Maksymalna wysokość |
| Average moving pace / Average moving speed / Best pace / Maximum speed (step 11) | Średnie tempo ruchu / Średnia prędkość ruchu / Najlepsze tempo / Maksymalna prędkość |
| Average cadence / Steps / Heart rate / Calories / Temperature / Respiration rate (step 11) | Średnia kadencja / Kroki / Tętno / Kalorie / Temperatura / Częstotliwość oddechu |
| {average} spm (max {max}) / {average} rpm (max {max}); without a maximum {cadence} spm / {cadence} rpm | {average} kr./min (maks. {max}) / {average} obr./min (maks. {max}); {cadence} kr./min / {cadence} obr./min |
| {average} °C ({low}–{high} °C); without a range {temperature} °C | {average} °C ({low}–{high} °C); {temperature} °C |
| {average} brpm ({low}–{high}); without a range {rate} brpm | {average} odd./min ({low}–{high}); {rate} odd./min |
| (step 11) the separator of the thousands from 10 000: "," | a hard space (U+00A0) |
| Track colour: {series} | Kolor trasy: {series} |
| (step 10) heart rate / elevation / pace / speed, after "Track colour:" (lower case) | tętno / wysokość / tempo / prędkość |
| Colours | Kolory |
| Zoom in / Zoom out | Przybliż / Oddal |
| Ctrl + scroll to zoom | Ctrl + kółko przybliża |
| (put off with D19a) Sets; {count} set · {sets}; {repetitions} × {weight} kg; 53 exercise categories | Serie; {count} seria · {sets}; {repetitions} × {weight} kg; Przysiad, … |

The names of the tiles, the laps' rows ("Lap {number}", their line) and the chart's series are
those of steps 2–4. Hard spaces after one-letter Polish words as everywhere; every row fits 360
px (measured in the mockups).

### 10.5 Steps

Each starts with a test that fails on the code before it, keeps its texts and their Polish in
the same commit, passes the gate (ruff, the tests with and without a display, the program's
folders unchanged) and waits for acceptance; each ends with what to try on the watch. Sizes are
lines of code and of tests.

6. **The laps (D20, D16, D21).** The track drawn by a layer of openExpress (`#e5420e`, its edge,
   as today), the laps' rows, a lap chosen: the band on the chart, the lap thick on the map;
   kilometres from the records (D16b); the wheel and the zoom buttons (D21). Failing tests: the
   rows and their order, choose, choose again, another; Enter; the chart's band where the lap
   is; the map's drawing of the lap (pixels as in the tiles' tests); kilometres of a run without
   laps, not of one with laps nor of a workout; the wheel without Ctrl leaves the zoom and
   scrolls the page, with Ctrl zooms; the narrow window. About 260 and 260; 8 texts.
7. **The look (D18).** The sport's colour (a dot before the title, the tiles' icons) and the
   icons. Failing tests: the colour by sport, the icon by tile, the narrow window. About 60 and
   50; no text.
8. **Heart-rate zones (D14, D19b).** `fit`: the `time_in_zone` of the session (its arrays: today
   `fit` reads an array field as missing), the zones' bands behind the chart. Failing tests: a
   made-up file with zones (each way of working them out), one without (no section), the time
   above the top bound in zone 5, the words, the bands where the bounds are. About 180 and 200;
   12 texts.
9. **Training effect and load (D15).** `fit`: the two effects and the load; the words of the
   scale at its edges (0.9, 1.0, 4.9, 5.0). About 80 and 90; 10 texts.
10. **The colours of the track (D13).** The scale, the percentiles, the legend, the switch kept
    in `gui.json`; the chosen lap still faded over the colours. Failing tests: the colour of a
    value at both ends and in the middle, the pace's direction, a series with gaps, off: one
    colour, the switch kept. About 150 and 150; 3 texts.
11. **The details (D17).** `fit`: the fields of 10.1; moving time from the records; the words.
    Failing tests: each row only with its field, the order, nothing a tile shows, steps from
    strides, cadence by sport, the narrow window. About 150 and 160; 18 texts.
12. **Documentation:** `docs/guide.md`, `README.md`, the status of this design.

On a device: the same walk and a strength workout after each step; a ride
for the speed, cadence in rpm and the colours of speed; steps against Garmin Connect (D17).
In all about 860 lines of code, 920 of tests, 50 texts, 7 commits, one a step.

## Appendix A: the FIT facts used

From the public FIT profile (the FIT SDK), message and field numbers; scales as the profile
gives them.

| Message | Field | Number | Unit |
|---|---|---|---|
| record (20) | position_lat, position_long | 0, 1 | semicircles |
| | altitude, enhanced_altitude | 2, 78 | m (scale 5, offset 500) |
| | heart_rate | 3 | bpm |
| | cadence | 4 | rpm |
| | distance | 5 | m (scale 100) |
| | speed, enhanced_speed | 6, 73 | m/s (scale 1000) |
| | timestamp | 253 | s since 1989-12-31 |
| lap (19) | start_time | 2 | s since 1989-12-31 |
| | total_elapsed_time, total_timer_time | 7, 8 | s (scale 1000) |
| | total_distance | 9 | m (scale 100) |
| | total_calories | 11 | kcal |
| | avg_speed, enhanced_avg_speed | 13, 110 | m/s (scale 1000) |
| | avg_heart_rate, max_heart_rate | 15, 16 | bpm |
| | total_ascent | 21 | m |
| session (18) | total_elapsed_time | 7 | s (scale 1000) |
| | total_calories | 11 | kcal |
| | avg_speed, enhanced_avg_speed | 14, 124 | m/s (scale 1000) |
| | avg_heart_rate, max_heart_rate | 16, 17 | bpm |
| (any) | compressed timestamp header | – | the 5 low bits of the time, from the last timestamp |

With the additions of section 10 (their steps):

| Message | Field | Number | Unit |
|---|---|---|---|
| lap (19) | lap_trigger | 24 | enum: manual 0, time 1, distance 2, …, session_end 7 |
| session (18) | total_cycles (strides on foot) | 10 | cycles |
| | max_speed, enhanced_max_speed | 15, 125 | m/s (scale 1000) |
| | avg_cadence, max_cadence; avg_, max_fractional_cadence | 18, 19; 92, 93 | rpm; rpm (scale 128) |
| | total_fractional_cycles | 94 | cycles (scale 128) |
| | max_altitude, min_altitude (where the enhanced fields are not given) | 50, 71 | m (scale 5, offset 500) |
| | total_descent | 23 | m |
| | total_training_effect, total_anaerobic_training_effect | 24, 137 | scale 10 (0.0–5.0) |
| | avg_temperature, max_temperature, min_temperature | 57, 58, 150 | °C |
| | total_moving_time | 59 | s (scale 1000) |
| | min_heart_rate | 64 | bpm |
| | active_time | 78 | s (scale 1000) |
| | enhanced_min_altitude, enhanced_max_altitude | 127, 128 | m (scale 5, offset 500) |
| | training_load_peak | 168 | scale 65536 |
| | enhanced_avg_, max_, min_respiration_rate | 169, 170, 180 | breaths a minute (scale 100) |
| time_in_zone (216) | reference_mesg, reference_index | 0, 1 | the session (18) and its index |
| | time_in_hr_zone | 2 | s (scale 1000), an array: below zone 1, zones 1–5, above |
| | hr_zone_high_boundary | 6 | bpm, an array |
| | hr_calc_type | 10 | enum: custom 0, % of max 1, % of reserve 2, % of threshold 3 |
| | max_heart_rate, threshold_heart_rate | 11, 13 | bpm |
| set (225): duration and set_type for the rest time (step 11); the rest put off with D19a | duration | 0 | s (scale 1000) |
| | repetitions | 3 | |
| | weight | 4 | kg (scale 16) |
| | set_type | 5 | enum: rest 0, active 1 |
| | start_time | 6 | s since 1989-12-31 |
| | category | 7 | enum exercise_category (53), an array |
