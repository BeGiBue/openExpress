# Design: courses and points of interest from files, without the account

Status: accepted with the recommended options; at the attempt on the devices. Nothing is
implemented. The first step is an attempt by hand on a fēnix 8 and an Edge 1050 (section 10):
what it shows can change D2, D3, D7 and D13 before any code, for each device on its own. The texts of section
4.5 are drafts; their Polish is checked against Garmin's Polish manuals before they are written.

## 1. Scope

The user chooses a file on the computer and openExpress copies it to the connected device, with
no Garmin account and no network:

- **a GPX file** (`.gpx`): a track (`<trk>`), a route (`<rte>`) or waypoints (`<wpt>`), as route
  planners, other devices and phones export them;
- **a file of points of interest** (`.gpi`): Garmin's format of custom POIs, made by Garmin's
  POI Loader or by GPSBabel.

openExpress also shows, read only, what the device holds of them (its courses, the GPX files
waiting for it, its saved locations, its POI files), and removes a course, a waiting file or a
POI file it is asked to.

Not in scope (section 11): converting a GPX file into a FIT course, sending a course to the
Garmin account or from it (`docs/design/wyslij-na-urzadzenie.md`), FIT and TCX course files from
the computer, making a `.gpi` from waypoints, editing courses.

## 2. What the devices declare and do

### 2.1 Declared in `GarminDevice.xml`

What a fēnix 8 and an Edge 1050 declare for these files (their own `GarminDevice.xml`; Garmin
Express reads the same file to know where each type goes):

| Type | Direction | fēnix 8 | Edge 1050 |
|---|---|---|---|
| `GPSData` (GPX) | in | `Garmin/NewFiles`, `.gpx` | `Garmin/NewFiles`, `.gpx` |
| `CustomPOI` | in | `Garmin/POI`, `.gpi` | `Garmin/POI`, `.gpi` |
| `FIT_TYPE_6` (courses) | in / out | `Garmin/NewFiles` / `Garmin/Courses`, `.fit` | the same |
| `FIT_TYPE_8` (locations) | in / out | `Garmin/NewFiles` / `Garmin/Location`, `.fit` | `Garmin/NewFiles` / `Garmin/Locations`, `.fit` |
| `FitnessCourses` (TCX) | in | – | `Garmin/NewFiles`, `.tcx` |
| `Safety_Cameras_PROM_Provider_1` | in | – | `Garmin/POI`, `.gpi` |

- Neither declares a folder `Garmin/GPX`; other devices may (older Edge models, handhelds), and
  they are not offered the feature (D9). openExpress takes the folder from the declaration of
  each device, never a fixed one.
- A GPX file is declared only inward: the device takes it and keeps what it makes of it (a FIT
  course in `Garmin/Courses`, saved locations in `Garmin/Location`), not the file.
- The Edge 1050 keeps Garmin's own safety cameras in the same folder as custom POIs, with the same
  extension: the folder alone does not tell whose a `.gpi` file is (D7).

### 2.2 What Garmin documents, and what users report

**The manuals of the fēnix 8 and the Edge 1050 name no folder and no file type** for files copied
over USB. The Edge 1050's says only that "most file types have a named folder within the Garmin
folder"; both send courses from Garmin Connect or make them on the device; the fēnix 8's points
of interest are those of its maps. Neither mentions GPX, GPI or POI Loader.

Garmin documents it **for other devices**:

- eTrex SE (a handheld): GPX files copied to `NewFiles`; "GPX routes and tracks are converted to
  FIT courses", waypoints to FIT waypoints; its `GPX` folder is read only, for geocaches, up to
  30 files.
- eTrex Touch: "most file types are stored in the GARMIN\NewFiles folder", among them FIT
  courses and locations.
- Custom POIs: Garmin's page on POI Loader says current outdoor and car devices take them and
  sends to each model's specifications; an older tactix watch took GPI files. The only rule of
  names Garmin gives is for POI Loader's CSV files: no commas, no special characters.

**Users report** (Garmin's forums, not Garmin):

- Edge 1050: a GPX in `Garmin/NewFiles` becomes a FIT course in `Garmin/Courses`; a GPX copied
  to `Garmin/Courses` itself, or to a `GPX` folder, is never read. Whether a route alone (no
  track) works is disputed. POI Loader's files work on it (the icons small); on the Edge 1040
  they were said not to.
- fēnix 7: the waypoints of a GPX in `NewFiles` become saved locations, shown on the map; a FIT
  course in `NewFiles` became a course; a course has at most 200 course points, turns among them.
  fēnix 8: a FIT course copied to `NewFiles` by hand worked; no report on GPX. fēnix 5X: no GPI.
- The course takes its name from the GPX `<name>`, not the file's, cut on the device (about 15
  characters on an Edge 1030; the FIT field holds 50).
- An Edge holds 100 courses and 200 locations (shops' specifications; Garmin's for the Edge 1030).
- Edge 840 over MTP: a course a browser saved straight to `NewFiles` was never taken; copied from
  the computer, it was. A GPX of a recorded ride was not taken as a course on an Edge 830.
- Garmin Express and Garmin Connect put a course as a FIT file in `NewFiles`; the device moves
  it to `Courses` at the unplug or a restart.

### 2.3 What only the device can tell

Checked by hand on a fēnix 8 first (section 10), then on an Edge 1050:

1. A `.gpx` with one track in `Garmin/NewFiles`: does the device make a course of it, when (at
   the unplug, at a restart), under which name (the GPX `<name>` or the file's), and does the
   file leave `Garmin/NewFiles`?
2. A `.gpx` with a route (`<rte>`) instead of a track: the same, and whether the course follows
   roads or draws straight lines between the points.
3. A `.gpx` with waypoints only: saved locations, or nothing?
4. A `.gpx` with two tracks: one course or two?
5. A `.gpi` in `Garmin/POI`: where the device shows its points (the map, a search, a list of
   custom POIs).
6. A course's FIT file removed from `Garmin/Courses` over USB: is the course gone from the
   device's list after the unplug, with nothing else lost?
7. A long track (several thousand points): does the device take it whole, cut it, or refuse it?
8. A track with times (a recorded ride or walk) beside one without: is the first refused?
9. A file written over MTP (as openExpress writes, through gvfs): taken as a file copied in a
   file manager is?

## 3. What openExpress has

- The device's `GarminDevice.xml` read; for each type the folders it declares in and out
  (`GarminDevice.targets`, `sources`).
- Writes to the device that are checked: the free space before (`require_space`), the size on
  the device after (`write_file_checked`), a partial file removed; removals that never fail a
  task (`delete_quietly`); one write at a time in the window (`writes_to_device`, `WRITING`).
- **Own maps**, the nearest model: the file checked without the device, a plan made with it (the
  name it gets, the folder, the space), a question with the size and the free space after, the
  copy, its size checked; a name already on the device is never overwritten; what this
  installation copied is recorded per device, and removing a map it did not copy is asked about
  more strongly. On the command line `maps add FILE.img [--name NAME] [--apply]`.
- The FIT reader knows the messages `course` (its name) and `course_point`: the names of the
  courses on the device are read from their files, with no new format.
- `--path DIR`: a folder taken as a device (USB drives, tests).
- The second install of the same computer (the version from source and the Flatpak): the sync
  takes the other's lock too (`service.sync_lock`), and the version from source reads the
  Flatpak's records of a device, never writes them.
- In the Flatpak the window gets any file through the file chooser (the portal); the command line
  reads only the Downloads folder and `Documents/Garmin`.

## 4. The window and the command line

### 4.1 Where it is offered

A section of the device view, **Courses and Points** (D1), after Maps, for a device that declares
`GPSData` or `CustomPOI` inward to a folder of D9. Its header has **Add Course…** (a `.gpx`) and
**Add Points…** (a `.gpi`), each only when its type is declared. Its groups, read from the
device when the section is first shown and after each change:

- **Courses**: one row per FIT file of `Garmin/Courses`: the course's name from the file (else
  the file's name), "{distance} · {date}" when the file gives them; **Remove…** (D7).
- **Waiting for the Device**: the `.gpx` files in the folder of `GPSData`, with the description
  "The device takes these when you unplug it"; **Remove…**. Shown only when there is one.
- **Points of Interest**: the `.gpi` files of `Garmin/POI`, name and size; **Remove…** only for
  those openExpress copied (D7).
- **Saved Locations**: one row, "{count} locations" read from the device's locations file; no
  list and no removal (section 11).

An empty group says so in one row ("No Courses on the Device"), as Own Maps does.

### 4.2 The question before a copy

As for a map of one's own: the file is checked first (D3, D4, D5), then the device asked for its
space, then the question (`confirm()`, Cancel by default; Escape and closing are Cancel):

> **Copy This Course to the Device?**
> Morning Loop
>
> morning-loop.gpx
> A track of 12.4 km and 3 waypoints · 48 KB
> Free after copying: 7.4 GB of 8.0 GB
> The device makes a course of it when you unplug it.
>
> Cancel · **Copy**

- The first line is the GPX `<name>` (of the file's metadata, else of its first track or route),
  else the file's name without `.gpx`; the second the name the file gets on the device (D4). The
  device names the course after the GPX `<name>` and may cut it (2.2); openExpress never changes
  what is inside the file.
- The content line counts what the file holds: tracks and routes with their length, waypoints;
  a file with several tracks says how many (D3).
- The free space line is the maps' (`free_after_text`).
- The last line says what the device does; it is written after the attempt of section 10 (for a
  file of waypoints only it may be "saved locations").

**Add Points…** asks the same with "Copy These Points to the Device?", the file's name and size,
the free space, and "The device shows them after you unplug it."

### 4.3 The outcomes

- **Copied**: the toast "Copied to the device: {name}", the groups read again; the file is in
  "Waiting for the Device" until the unplug.
- **Refused before the question** (`inform()` with the reason, nothing written): not a GPX or
  GPI file, too large (D5), nothing in it to navigate, no folder for it on this device.
- **The same file already on the device** (the same size and content in the folder): said in the
  question, not refused.
- **No room**: the maps' message.
- **The copy failed**: the partial file removed, the reason shown, the groups read again.

**Remove…** asks (`confirm()`, Cancel by default) "Remove {name} from the Device?" with what is
removed; for a course openExpress did not copy, the stronger wording of a foreign map: "openExpress
did not copy this course. The device keeps no other copy of it; a course from Garmin Connect can
be sent again from there."

### 4.4 The command line

- `openexpress courses`: the device's courses, the files waiting for it, its POI files and the
  number of saved locations (D10).
- `openexpress courses add FILE.gpx [--name NAME] [--apply]`: without `--apply` what would be
  copied (the name on the device, the folder, what the file holds, the space); with it the copy.
- `openexpress courses remove NAME [--apply]`: a course or a waiting file, by its name or a part
  of it, as `profiles show` matches names; several matches list them and remove nothing.
- `openexpress points add FILE.gpi [--name NAME] [--apply]`, `openexpress points remove NAME
  [--apply]` (only POI files openExpress copied).
- Every one works with `--path DIR` and `--device-uri URI`, as the other commands that open a
  device. No new exit code: a refusal is 1, with its reason.

### 4.5 Texts (English, Polish)

| English | Polish |
|---|---|
| Courses and Points | Kursy i punkty |
| Add Course… | Dodaj kurs… |
| Add Points… | Dodaj punkty… |
| Courses · Waiting for the Device · Points of Interest · Saved Locations | Kursy · Czeka na urządzenie · Punkty POI · Zapisane lokalizacje |
| The device takes these when you unplug it | Urządzenie przejmie je po odłączeniu |
| No Courses on the Device | Brak kursów na urządzeniu |
| {count} locations | {count} lokalizacji (ngettext) |
| Copy This Course to the Device? | Skopiować ten kurs na urządzenie? |
| Copy These Points to the Device? | Skopiować te punkty na urządzenie? |
| A track of {distance} and {count} waypoints | Ślad {distance} i {count} punktów (ngettext) |
| The device makes a course of it when you unplug it. | Urządzenie zrobi z niego kurs po odłączeniu. |
| Copied to the device: {name} | Skopiowano na urządzenie: {name} |
| Remove {name} from the Device? | Usunąć {name} z urządzenia? |
| Choose a GPX File · Choose a POI File (.gpi) | Wybierz plik GPX · Wybierz plik punktów POI (.gpi) |

English labels in GNOME's header capitalization, the rest in sentences; Polish in sentence case.
The names of Garmin's things ("Kursy", "Zapisane lokalizacje", the name of custom POIs) are the
words of Garmin's Polish manuals of these devices.

### 4.6 Experimental

The window's buttons' tooltips and the commands' help say "experimental" until the attempts of
section 10 have succeeded on a fēnix 8 and an Edge 1050 (D12).

## 5. Safety

### 5.1 Where it writes and removes

- **Writes** only to the folder the device declares inward for the type (`GPSData` for `.gpx`,
  `CustomPOI` for `.gpi`), and only when that folder is `Garmin/NewFiles` or `Garmin/POI`, the
  folders both devices declare (compared without case, as the device's storage does) (D9). A device that declares
  another folder is not offered the feature; the log says which type and folder.
- **Removes** only one file at a time, never a folder: a `.fit` directly in the device's courses
  folder (`FIT_TYPE_6` outward, one of `Garmin/Courses`), a `.gpx` directly in the folder of
  `GPSData`, a
  `.gpi` directly in `Garmin/POI` that openExpress copied. Nothing in a subfolder, nothing by a
  pattern.
- Every path is made from a folder of the declaration and one name checked as below; no part of
  a path comes from the file's content.

### 5.2 The file

- **Size** (D5): a `.gpx` up to 25 MB, read whole only after its size is checked; a `.gpi` up to
  the free space only (it is copied, not parsed).
- **A GPX file** must be XML with no document type declaration and no entities (a `<!DOCTYPE`
  refuses it: no expansion of entities, no external file read), its root `gpx` in GPX 1.1's or
  1.0's namespace, and at least one track with points, route with points or waypoint; every
  latitude within ±90 and longitude within ±180. What it holds is counted for the question; its
  names and descriptions are only shown, never used in a path.
- **A GPI file** must start with the signature of the format as its public descriptions give it
  (checked on a file from POI Loader and one from GPSBabel before the code is written).
- **The name on the device** (D4): made from the file's name; letters with accents written
  without them ("Pętla" → "Petla"); only letters, digits, spaces and `. _ - ( )`; no name of a
  device of DOS (`CON`, `NUL`, `COM1`…), no dot or space at the end; up to 64 characters with the
  extension; the extension `.gpx` or `.gpi` in the case the device declares. A name already in
  the folder (without case) is never overwritten: " (2)", " (3)"… is added, and the question
  shows the name. `--name` sets it on the command line, under the same rules.

### 5.3 Two installs, one device

- A copy or a removal takes the sync's lock (`service.sync_lock`), which holds the other
  install's too: a sync and a copy never write to the device at once, in either install (D11).
- What openExpress copied is recorded per device, beside the own maps' record
  (`devices/<unit>/courses.json`: the folder, the name, the size, the MD5; no content). The
  version from source also reads the Flatpak's record, never writes it; a file either install
  copied counts as openExpress's (D7).
- The lists of 4.1 are read from the device, not from the records: both installs show the same.

### 5.4 The log and the tests

- The log names the type, the folder and the size (`applog.size`); the user's file names, the
  names inside the files and their places are hidden (`applog.hide`).
- The tests use made-up GPX and GPI files and the fake storages only; none reaches a device.

## 6. Decisions

### D1: where the window offers it — recommended: 1a

- **1a. A section of its own, Courses and Points, after Maps (recommended).**
  - \+ One place for what is navigated on the device; room for the lists, and later for the
    courses of the account (`docs/design/wyslij-na-urzadzenie.md`, its section Workouts and
    Courses would then hold only workouts and the calendar).
  - − One more section in the sidebar.
- **1b. A group of the Maps page, beside Own Maps.** + No new section. − Maps is long already;
  courses are no maps.
- **1c. A group of the Device page.** − Lists do not fit the device's summary.

### D2: what is copied for a GPX file — recommended: 2a

- **2a. The file as it is, to the folder of `GPSData`; the device makes the course
  (recommended)**, if section 10 shows a fēnix 8 does.
  - \+ What the device declares; nothing of Garmin's formats made by openExpress.
  - − The course is seen only after the unplug; how the device names it is its own.
- **2b. A FIT course made by openExpress, to the folder of `FIT_TYPE_6`.** + Works on a device
  that takes no GPX. − A course writer (laps, records, course points) to build and test; later
  (section 11), only if 2a fails.

### D3: what a GPX file may hold — recommended: 3a

- **3a. Any valid GPX with something to navigate; the question says what (recommended).** Tracks,
  routes and waypoints are counted; several tracks are said, and section 10 tells whether the
  device makes several courses.
- **3b. One track or one route only.** − Refuses files the device may take.
- **3c. Several tracks split into files by openExpress.** − Writes GPX of its own; later, if the
  device takes only the first.

### D4: the name on the device — recommended: 4a

- **4a. A safe name made from the file's name, shown in the question; a taken name gets
  " (2)" (recommended).**
  - \+ A file named in Polish or with spaces works without a question about its name.
- **4b. Refused unless safe, as an own map's.** − Most names of route planners have characters
  that would refuse them.

### D5: the largest file — recommended: 5a

- **5a. A `.gpx` up to 25 MB; a `.gpi` up to the free space (recommended).** The limit keeps the
  check of a GPX in memory small; a course of the device's own limits is learnt in section 10.
- **5b. No limit but the free space.** − A GPX of hundreds of MB read whole.

### D6: the lists — recommended: 6a

- **6a. Courses, waiting files, POI files and the count of saved locations, read from the device
  (recommended).** + What the device holds, whoever put it there; both installs show the same.
- **6b. Only what openExpress copied.** − The device's courses from Garmin Connect unseen.

### D7: what can be removed — recommended: 7a

- **7a. Any course and any waiting GPX file, those openExpress did not copy with the stronger
  question; POI files only those openExpress copied (recommended).**
  - \+ A course can be removed on the device too, so nothing new is allowed; Garmin's safety
    cameras share `Garmin/POI` and cannot be told apart by the folder.
  - − A POI file copied by another program stays (the device removes it, or a file manager).
- **7b. Only what openExpress copied.** − The courses from Garmin Connect cannot be tidied.
- **7c. No removal.** − Half of a tool.

Removing a course is offered only after section 10 has shown that the device takes it well.

### D8: which devices — recommended: 8a

- **8a. Those that declare `GPSData` or `CustomPOI` inward to a folder of D9; each button for
  its own type (recommended).**
- **8b. Every Garmin device, with a fixed `Garmin/NewFiles`.** − Writes where a device has not
  said it reads.

### D9: the folders — recommended: 9a

- **9a. Only the folders the devices declare: writes to `Garmin/NewFiles` and `Garmin/POI`;
  removals in `Garmin/Courses`, `Garmin/NewFiles` and `Garmin/POI` (recommended).** `Garmin/POI`
  is needed for the points: both devices declare it for `CustomPOI`. `Garmin/GPX`, which neither
  declares, is left out: a device that declares it for `GPSData` is not offered the feature.
- **9b. Without `Garmin/POI`.** − No points of interest.

### D10: the commands' names — recommended: 10a

- **10a. `courses` (list, `add`, `remove`) and `points` (`add`, `remove`) (recommended).** The
  postponed sending of the account's courses fits as `courses send NAME`.
- **10b. One command `navigation add FILE`, the type from the extension.** − One name for two
  lists.
- **10c. Under `maps`.** − Courses are no maps.

### D11: the lock — recommended: 11a

- **11a. The sync's lock, the other install's with it (recommended).** + No copy during a sync,
  in either install. − A copy waits for a sync to end (it is refused with the sync's message).
- **11b. The window's own lock only.** − The command line or the other install could write at
  the same time.

### D12: experimental — recommended: 12a

- **12a. Experimental until the attempts on a fēnix 8 and an Edge 1050 succeed (recommended).**

### D13: points of interest on a device that may not show them — recommended: 13a

A watch can declare `CustomPOI` and still show no custom points (2.2: the fēnix 8's manual knows
only the points of its maps; a fēnix 5X took none).

- **13a. Offered where declared (D8); the question adds "Not every device shows custom points of
  interest"; `docs/devices.md` says on which models they were seen (recommended).**
- **13b. Offered only on models where they were seen.** − A list of models to keep in the code.
- **13c. Not offered on watches until section 10 shows them on a fēnix 8.** + Nothing offered
  that does nothing; − how a watch is told from a bike computer is a guess.

If section 10 shows nothing on a fēnix 8, 13c is chosen again for review.

## 7. What can go wrong, and how it is found

| What | How it is prevented, and found |
|---|---|
| A file written outside the allowed folders | folders only from the declaration and D9; names checked (5.2); tests of each refusal |
| A file of the device overwritten | a taken name gets " (2)"; the folder read just before the copy |
| A GPX that is no GPX, or harmful XML | the checks of 5.2 before the question; no document type, no entities |
| The device takes no GPX, or only part of it | section 10 first; D2 and D3 follow what it shows |
| A course removed that was wanted | the question names it; a course not copied by openExpress asked about more strongly |
| Garmin's safety cameras removed | POI files removed only when openExpress copied them (D7) |
| A sync and a copy at once | the sync's lock (D11) |
| No room | the free space checked before the question and before the copy |
| The Flatpak cannot read the file | the window through the portal; the command line names the folders it reads |

## 8. Steps

Each step starts with tests that fail on the code before it, keeps its texts and their Polish in
the same commit, and passes the usual checks. Each waits for acceptance.

1. **The attempt on a fēnix 8** (section 10), by hand, before any code; this design corrected by
   what it shows.
2. **The checks** (a new module): GPX and GPI files, the name on the device, the counts for the
   question; tests with made-up files, harmful ones among them.
3. **Plan, copy, remove, lists** (beside `ownmaps`): the folders of D9, the record, the lock.
4. **The commands** `courses` and `points`; `docs/cli.md`.
5. **The window**: the section, the questions, the outcomes; the narrow window.
6. **The documents**: `docs/guide.md`, `docs/devices.md`, README.
7. **On an Edge 1050**: section 10 again; then "experimental" goes (D12).

## 9. Size

About 400 lines of code (the checks 120, plan and copy 110, the commands 70, the window 100),
about 600 lines of tests, about 35 texts with their Polish; 5 commits after the attempt.

## 10. The first attempt on the devices

Made by hand on the maintainer's own fēnix 8, then the Edge 1050, with `gio copy` through gvfs, as openExpress
writes over MTP (2.3, item 9), from commands prepared for it; no openExpress yet. Nothing else is
written to the device, and each file is removed at the end.

**Files** (made up, a short loop in a public park, nobody's place): `oe-test-track.gpx` (one
track "OE Test Track", 2 km, 200 points, no times), `oe-test-timed.gpx` (the same track with
times, "OE Test Timed"), `oe-test-route.gpx` (one route "OE Test Route", 5 points),
`oe-test-points.gpx` (3 waypoints "OE Test Point 1–3"), `oe-test-two.gpx` (two tracks),
`oe-test.gpi` (the 3 points, made by GPSBabel); for the Edge also `oe-test.tcx` (the track as a
TCX course "OE Test TCX"), as it declares `FitnessCourses`.

**Before:** the device connected; the folders `Garmin/NewFiles`, `Garmin/Courses`,
`Garmin/Location` and `Garmin/POI` listed (names and sizes, masked); on the watch the number of
courses (Navigation › Courses) and of saved locations written down.

**The attempt**, one file at a time, each followed by an unplug, a look at the watch and a plug
in again:

1. `oe-test-track.gpx` to `Garmin/NewFiles`. **Expected:** after the unplug "OE Test Track" in
   Navigation › Courses, its line on the map; plugged in again, the file gone from
   `Garmin/NewFiles` and one new `.fit` in `Garmin/Courses`. Its name in the FIT file and on the
   watch written down.
2. `oe-test-timed.gpx`: a course too, or refused as a recorded activity?
3. `oe-test-route.gpx`: the same as 1; does it follow roads or draw straight lines?
4. `oe-test-points.gpx`: three new saved locations (Navigation › Saved Locations, the map), or
   none?
5. `oe-test-two.gpx`: one course, two, or none?
6. `oe-test.gpi` to `Garmin/POI`: where the watch shows the three points, if anywhere (D13).
7. The new course's `.fit` removed from `Garmin/Courses` with `gio remove`; after the unplug,
   the course gone, the others as before. Saved locations of step 4 removed on the watch.

**If not:** a `.gpx` still in `Garmin/NewFiles` after the unplug and no course means the watch
takes no GPX over USB: D2 turns to 2b (or the feature is for the Edge only), and `docs/devices.md`
says so. A course named after the file means D4 names what the watch shows. A watch that
restarts or shows an error: the file removed at once, the attempt stopped, the device's crash
log kept for the report. Every file of the attempt removed at the end; the folders listed again
and compared with the listing before.

**Then** the same on an Edge 1050, with the TCX course as one more step. The results go here
for each device on its own, and D2 is decided for each: the watch and the Edge may differ.

## 11. Later, or not at all

- **A FIT course made by openExpress** from a GPX (D2, 2b): for devices that take no GPX, or to
  name the course and add course points.
- **The account**: a course imported to Garmin Connect from a file, and courses sent from the
  account (`docs/design/wyslij-na-urzadzenie.md`).
- **FIT and TCX course files** from the computer: the same copy to the folder of `FIT_TYPE_6` or
  `FitnessCourses`.
- **A `.gpi` made from waypoints**, saved locations written as FIT (`FIT_TYPE_8`), their list
  and removal.
- **Editing**: reversing, joining, renaming a course on the device.
- **A file dropped on the window.**
- **Named trails** (`NamedTrails`, `Garmin/SQL`): not offered.

## 12. Open questions

1. Does a fēnix 8 make a course of a `.gpx` in `Garmin/NewFiles` (section 10)? Everything else
   rests on it.
2. How the watch names the course (and how many characters it keeps), and whether a route
   follows roads.
3. Where custom POIs show on a fēnix 8, and whether it shows them at all (D13).
4. The limits: how many courses and saved locations a fēnix 8 holds, and what happens past them
   (an Edge: 100 and 200 by shops' specifications); whether the question should warn near them.
5. Whether removing a course's file over USB is safe on both devices.
6. A test `.gpi`: GPSBabel is not installed on the maintainer's computer; it can be installed
   from Fedora, or a file of POI Loader used.
7. The Polish of "custom POIs" and "Saved Locations" in Garmin's manuals of these devices.
