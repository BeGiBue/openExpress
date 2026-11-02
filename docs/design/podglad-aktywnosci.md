# Design: the full view of an activity (summary, map, chart, laps)

Status: a design; no decision of section 5 is taken and nothing is implemented. The work goes
step by step (section 8), each step after a yes. The scope in section 1 is set once: what it does
not list is not added while it is implemented.

## 1. Scope

The Activities page lists the activities of the open device and of its backups and exports one
as GPX. This design adds what a user sees of one activity, in the same window:

1. **Its page**, opened from its row: a back arrow and a GPX export in the header bar.
2. **A summary** on top: four tiles, chosen by what the activity has (D11).
3. **A map of the track**, for an activity with positions (D2–D4).
4. **A chart** of heart rate, elevation or pace/speed (only those the file has), with the value
   where the cursor is, and that place marked on the map (D5, D6).
5. **Its laps**, as the device recorded them; a lap chosen is highlighted on the map and on the
   chart, chosen again it is not (D7).

From the device (MTP or USB drive) and from a copy in a backup, the same way; in the window
only.

Not in scope (a closed list; each would be a project of its own):

- changing, renaming or deleting an activity, on the device or in a backup;
- comparing activities; segments, personal records, heart-rate zones, training effect, power,
  running dynamics, splits other than the device's own laps;
- the sets of a strength workout, the lengths and strokes of a swim, the transitions of a
  multisport activity beyond its sessions taken together;
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
    values recognised); compressed-timestamp headers are read, their time is not worked out.
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
to read it. How long Python takes to go through 28,800 records is to be measured in step 1;
the series are lists of numbers of a few MB.

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

The mockup accepted in the chat, weighed:

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
 ← Running · Tue 28 Oct, 07:12                       [GPX]
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

### D1: where the activity's page opens

- **1a. A page pushed onto the window's navigation (recommended):** after the start page and the
  device view, a third page, with its own header bar: the back arrow (Alt+Left and the mouse's
  back button too), the activity's sport and start as the title, the GPX button at the end.
  - \+ The navigation the window has already; the whole width for the map and the chart.
  - − On a wide window the sections on the side are hidden while it is open.
- **1b. A navigation of its own inside the Activities section** (as some panels of GNOME
  Settings have), the sections staying on the side.
  - − The content side has one header bar for every section (Refresh, Sync, the banner): a
    second one under it for the activity, or a back button added to the shared one by hand.

### D2: what draws the map

- **2a. libshumate (recommended):** the GTK 4 map widget of GNOME (GNOME Maps uses it): tiles,
  a path layer for the track, a marker layer for the cursor, its file cache.
  - \+ Panning, zooming, scaling and the attribution as GNOME has them.
  - − Not in the GNOME runtime: one module more in the Flatpak manifest; from source the
    distribution's package (Fedora: `libshumate`); without it the page has no map and says why.
- **2b. The track drawn by openExpress itself** (a `Gtk.DrawingArea`, no tiles).
  - \+ No new library, no network.
  - − A line without streets or terrain; panning and zooming written anew.
- **2c. A web map in WebKit** (as the sign-in window uses WebKit).
  - − A web page and JavaScript for a map; heavier than both.

### D3: the map's tiles and privacy

- **3a. Off until the user turns them on (recommended):** at the first map, a line over it:
  "The map loads its tiles from OpenStreetMap, which then learns the area of the activity"
  with "Show the map"; the choice kept (Preferences, Privacy, can be changed); meanwhile the
  track on a plain background, zoom and pan working.
  - \+ Nothing about an activity leaves the computer without a yes, as the diagnostics.
  - − One click before the first map.
- **3b. On, said in `docs/privacy.md`.**
  - − The area of every activity opened goes to the tile server without a question.
- **3c. Never: the track alone.**
  - − The map says little without streets.

### D4: where the tiles come from

- **4a. tile.openstreetmap.org (recommended):** the HTTPS URL of the policy, the User-Agent
  `openExpress/<version> (+https://github.com/TomaszBojanowski/openExpress)`, the attribution
  on the map, libshumate's cache in the program's cache folder (`~/.cache/openexpress/tiles`,
  in the Flatpak its own), kept as the headers say; only the tiles shown. The URL in one
  constant, so that it can change without other code.
  - \+ Free, no key, within the policy for an occasional use.
  - − It may be blocked without notice; no guarantee.
- **4b. A provider with a key** (MapTiler, Thunderforest…).
  - − A key in the program or for the user to get; a contract.
- **4c. A URL the user sets.**
  - − A setting few need; the policy of each server is the user's to read.

### D5: the chart's axis

- **5a. The time since the start (recommended):** pauses as gaps in the line.
  - \+ The same for every activity, with or without a distance; laps and pauses fall where
    they happened.
- **5b. The distance when the activity has one, the time otherwise.**
  - \+ What runners and riders often look at.
  - − Two axes to draw and to test; a lap or a pause looks different in each.

### D6: what draws the chart

- **6a. Own drawing in a `Gtk.DrawingArea` with Cairo (recommended):** the line, the axes with
  round values, the cursor and its value, the highlighted lap; the points brought down to about
  two per pixel column (the lowest and the highest of each, so that peaks stay).
  - \+ No new library; the look of the window; the numbers testable without a screen.
  - − About 250 lines of our own.
- **6b. A plotting library** (matplotlib with its GTK 4 backend).
  - − Large, not in the GNOME runtime, a look of its own.

### D7: the laps

- **7a. A list of rows that wrap (recommended):** "Lap 1" and "1.00 km · 5:02 · 5:02 /km · 141
  bpm"; a click highlights it on the map and the chart, a second click takes it off; one lap at
  a time; no laps (or one, the whole activity): no list.
  - \+ Fits 360 px; the rows of the window.
- **7b. A table** (`Gtk.ColumnView`, a column each).
  - − Columns cut or scrolled in a narrow window.

### D8: where the data comes from

- **8a. The file read again at each opening, from the device or from its copy in a backup;
  nothing new kept (recommended):** a task with its progress (bytes), as every reading; the page
  gone before it ends, its result is dropped.
  - \+ "Activities are read, not kept" stays true; nothing to clean up.
  - − 1–2 s over MTP for a long activity, each time.
- **8b. A copy of each activity opened in the program's cache.**
  - \+ The second opening at once, also without the device.
  - − Tracks with positions on the disk in one more place; it overlaps with the backups.

### D9: a wide window

- **9a. One column at every width (recommended for the first version),** in a clamp (about
  1000 px).
  - \+ One layout to build and to test.
- **9b. The map and the chart side by side above a breakpoint.**
  - − A second layout; the chart is better wide, the map tall.

### D10: units

- **10a. Metric only, as the list (recommended).**
- **10b. The unit system of the Garmin Connect profile** (asked of the account).
  - − A question to the account for a page that otherwise asks nothing; every text twice.

### D11: the summary tiles

- **11a. By what the activity has (recommended):** with a distance: distance, time, pace or
  speed, average heart rate; without: time, average heart rate, maximum heart rate, calories;
  a value the file does not give: its tile left out, the others taking the row.
- **11b. Always the four of the mockup,** "–" where a value is not given.
  - − A workout shows two dashes of four.

### D12: pace or speed

- **12a. By sport (recommended):** running, walking, hiking: pace per km; swimming: pace per
  100 m; cycling and others with a distance: speed in km/h.
- **12b. Speed always.**
  - − Runners read pace.

## 6. What changes

| Module | Change |
|---|---|
| `fit.py` | `activity_data(data)`: the series (time, distance, speed, heart rate, altitude, position), the laps and the session's extras (Appendix A); compressed timestamps worked out. FitError where the file breaks off, after what was read. |
| `activities.py` | The data of one activity (`Read`), from the device or from its backup copy, as a task with progress. |
| `gui/activity_page.py` (new) | The page: header bar (back, GPX), tiles, map, chart, laps; reading, errors, the narrow window. |
| `gui/activity_chart.py` (new) | The chart widget (D5, D6): series, axes, cursor, keyboard, highlighted lap. |
| `gui/activity_map.py` (new) | libshumate around the track (D2–D4): tiles or not, the marker, the highlighted lap, the attribution, the User-Agent, the cache folder. |
| `gui/activities_page.py` | Rows activatable; a click opens the page. |
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
   whether that needs a yes. Tests must ask no tile (the tests' network guard fails any): the
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
waits for a yes.

1. **The data of an activity (`fit.activity_data`).** Failing tests on made-up FIT files: the
   series of a run (time, distance, speed, heart rate, altitude, position); a workout without
   positions or distance; pauses; compressed timestamps; laps and the session's extras; a file
   cut short (what reads, then FitError); a long activity read within a time measured here.
2. **The words.** Failing tests: durations, distances, pace by sport and speed (D12), heart
   rate, calories, the tiles' names, a lap's line; English and Polish, hard spaces.
3. **The page.** Failing tests: a click on a row opens it (D1), the back arrow returns to the
   list where it was, the GPX button exports as the row does; the tiles by what the activity has
   (D11); read from the device and from a backup copy (D8), with progress; unplugged meanwhile
   (a message, the back arrow); a stall (the banner, the page closed with the device); the
   narrow window.
4. **The chart.** Failing tests: the series the file has, and only those, in the switch; the
   axis (D5) with round values; the points brought down without losing a peak; the value at a
   place; the cursor by click, drag and arrow keys; pace smoothed; a gap where a value is
   missing; the narrow window.
5. **The map.** Failing tests: no map without positions; the track and its bounds; the marker
   follows the chart's cursor; tiles only after the yes of D3, the User-Agent and the cache
   folder of D4, the attribution shown; without libshumate a line instead; no tile asked in the
   tests. The Flatpak manifest with libshumate, `docs/privacy.md`.
6. **The laps.** Failing tests: the rows (D7), a click highlights the lap on the chart and on
   the map, a second click takes it off, another lap moves it; no list for one lap.
7. **Documentation**: `docs/guide.md`, `README.md`, the status of this design.

On a device: a run and a ride with positions, a workout without, a long hike (the time to read
and to draw), an activity from a backup with the device unplugged, the map with and without the
network.

## 9. Size

About 950 lines of code (fit about 150, the words about 80, the page about 180, the chart about
250, the map about 200, the laps about 90), about 900 lines of tests on made-up files, about
40 texts with their Polish, 7 commits, one a step of section 8; with 2a, one module in the
Flatpak manifest.

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
| session (18) | sub_sport | 6 | enum |
| | total_elapsed_time | 7 | s (scale 1000) |
| | total_calories | 11 | kcal |
| | avg_speed, enhanced_avg_speed | 14, 124 | m/s (scale 1000) |
| | avg_heart_rate, max_heart_rate | 16, 17 | bpm |
| (any) | compressed timestamp header | – | the 5 low bits of the time, from the last timestamp |
