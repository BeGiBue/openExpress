# Design: the data screens of sport profiles

Status: stage 1 (read only) implemented, steps 1 to 5 of section 7; stage 2 (editing) waits for
the facts that section 2.4 lists as not known, learnt from copies of the device's own files. The
decisions of section 5 are made: each took its recommended option, marked "chosen" (13a, the
only one, included). As implemented, stage 1 differs from sections 4 and 5 in four points:

- The drawing of a screen shows its fields one under another, in their order, not where each
  stands: the places of the fields in each layout are not known for any device yet (D5).
- A watch's built-in screens and layouts have names of their own where they are known
  (Garmin Connect's names for a fēnix 8's screens, the families of its layouts), else their
  codes ("Built-in screen 127", "Layout code 12, unknown"); the Edge's names and letters are
  not taken for them. A watch's fields have the Edge's numbers (checked on a fēnix 8 with a
  profile set to a dozen of them), with a few of its own, the profile's page saying it.
- Message 13 is not read at all: no toggle of it is needed to show a profile (D13).
- The names of the fields are Garmin's words from the Data Fields pages of its manuals, by the
  numbers of Activity Profile Editor's table (D4a); a field without a name there is shown by its
  number, and so are the categories, left for stage 2.

## 1. Scope

A sport profile ("activity profile": Run, Hike, Road Bike…) keeps, among its settings, the data
screens the device scrolls through during an activity: screens of the user's own with one to ten
data fields each, and built-in screens (Map, Compass, ClimbPro, Stamina…). Garmin Express does
not show them; Garmin Connect shows and edits them for some devices through the phone. This
design adds them to openExpress in two stages.

**Stage 1, read only:**

1. A section "Activity Profiles" in the device view: every profile of the device, the recently
   used first, with a search (D1, D2).
2. A profile's page: its data screens in the order the device scrolls through them, each drawn in
   the shape of the device's screen (round for a watch, a rectangle for an Edge) with its fields
   named as Garmin Connect names them, in English or Polish (D4, D5); the built-in screens, on or
   off.
3. A screen's page: its layout and its fields, one by one.
4. The command line: `openexpress profiles` and `openexpress profiles show` (D14).

**Stage 2, editing (experimental, D11):**

5. On a screen: the number of fields, the layout's variant, each field from a list with a search
   and categories.
6. On a profile: add, duplicate, delete and move screens; turn built-in screens on and off.
7. Changes stay in the window until "Save to Device"; before every save a copy of the profile on
   the computer; the file checked before and after it is written; "Restore Previous Version"
   (D6–D8); what the device has to do to load the change, and whether it did (D12).

Not in the scope: Connect IQ data fields (shown, not changed: D10); every other setting of a
profile (alerts, GPS, zones, auto lap…): never read, since some of them are personal values
(D13); adding, deleting, renaming or copying profiles; the order of the profiles in the device's
own list. Editing comes to a model only when its files have been measured (D9); the two measured
are the fēnix 8 and the Edge 1050.

## 2. The files

### 2.1 Where they are

Each profile is one FIT file of type 3 (sport): `GARMIN/Sports/*.fit` on a watch,
`Garmin/Sports/*.fit` on an Edge (the folder's letter case differs; `GarminDevice.xml` declares
both the place of the files and the folder for new ones). The file's name is the device's, not the
profile's: the name is inside. A changed profile is not written over the file: it goes into the
device's folder for new files (`NewFiles`), and the device takes it in when it restarts, under a
name of its own; a file copied straight into `Sports` is taken once and then no more (D6).

### 2.2 The messages

| Message | What it holds | What openExpress reads |
|---|---|---|
| 12 `sport` (public FIT profile) | the profile's name (field 3), sport and sub-sport (0, 1), colour (10) | name, sport, colour |
| 13 `training_settings` (public) | the profile's other settings, among them toggles of built-in screens on some models, and personal values | only the toggles listed in a table per model (D13) |
| 14 (not in the public profile) | the table of screens: one record a place, about 31 places allotted in advance | every record (below) |
| 170 (not in the public profile, Edge) | which Connect IQ app a Connect IQ field shows | its records, to name the app (D10) |

The fields of message 14, as the two sources describe them and the files of both devices show:

- 254 `message_index`: the place of the record in the file, not the screen's identity: the device
  numbers the places anew when it takes a file in and when a screen is deleted.
- 1 state: 0xFF a place unused, 1 a screen, 0 a screen deleted (cleared at the next import).
- 3 the number of fields: how many of field 7 count.
- 7 the data fields' IDs, an array of `uint16` (0xFFFF empty); the places past field 3 keep old
  IDs, which the device does not clear.
- 8 the layout's variant (section 2.3).
- 9 the screen's place in the carousel, rising, unique among the screens shown; a duplicate
  silently loses a screen at the next import.
- 10 the screen's type and identity: a code for a built-in screen; for a screen of the user's own
  a counter (0, 1, 2… shown as "Screen 1, 2, 3…"), not its place.
- 12 (Edge) shown or hidden; 4, 6, 11, 14: not known.

Writing (both sources): the bytes changed in place, the file's length the same, the CRC of the
file (its last two bytes) computed anew; the header's CRC stays, since the length of the data
does not change. A file taken in unchanged comes back byte for byte, but for `file_id.number`.

### 2.3 Three devices compared

| | fēnix 8 (measured) | Edge 1050 (measured) | Edge 840 / 1040 (the sources) |
|---|---|---|---|
| Profiles | 113, each 5,735 bytes | 4, each 5,250 bytes | – |
| Message 14 | 31 records, 8 fields: 4, 7, 254, 1, 3, 8, 9, 10 | 31 records, 12 fields: also 6, 11, 12, 14 | as the Edge 1050 |
| Field 7 | 8 IDs (`uint16[8]`) | 10 IDs (`uint16[10]`) | 10 IDs |
| Field 12 (shown/hidden) | none | yes | yes |
| Message 170 (Connect IQ) | none | none in these files | yes |
| Screens of one's own | up to 5 in a profile, 0–6 fields | 1–3, 4–9 fields | up to 10, 1–10 fields |
| Field 8 (variant) | 0, 1, 2, 3 and 12, not by the rule of the Edge | 0 or 1 | A=0, B=1, C=2 whatever the count; 1 for one field |
| Built-in codes | 25 (Map), 32 (reserved), 35, 127 (Stamina) and about 60 codes the sources do not know (77–225) | those of the sources: 25, 30, 32, 35, 38, 44, 56, 57, 58, 63, 74, 95, 104, 125, 127, 162 | 25 Map, 26 Virtual Partner, 30 music, 32 reserved, 35 Compass, 38 Workout, 44 Elevation, 56 Segment, 57 GroupTrack, 58 eBike, 63 cycling dynamics, 74 lap summary, 95 Shimano STEPS, 104 ClimbPro, 125 Power Guide, 127 Stamina, 128 Solar, 162 GroupRide, 223 Radar |
| Message 13 | 124 fields, no field 99 | 60 fields, field 99 (Stamina) | 99 Stamina, 63 ClimbPro |

The Edge 1050 matches the description of the Edge 1040 of the issue that asked for this
feature: message 14 as the table of screens, its fields 1, 3, 7, 8, 9, 10 and 12, the built-in
codes. The fēnix 8 has the same table with other details: eight fields a screen, no field 12 and
no message 170, other variants and other built-in screens, and no toggle of Stamina in message 13
(Stamina is a screen of message 14 there).

Activity files of the fēnix 8 carry message 12 too, with the name of the profile the activity was
recorded with, near the start of the file (D2).

### 2.4 Not known yet

Learnt from the device's own files, each copied after one change made on the device (section 7,
step 0); nothing written to the device for it:

1. The fēnix 8's variants: which value of field 8 is which layout, for 1 to 6 fields (and what 12
   is).
2. The names of the fēnix 8's built-in codes, and how such a screen is turned off (field 1 or 9,
   with no field 12).
3. Whether an ID 0 in field 7 is an empty field or a field of its own (ten screens have it).
4. Field 4 of message 14 (eight bytes on the fēnix, ten on the Edge).
5. Whether the fēnix 8 takes a file from `NewFiles` over MTP at its restart, as the Edges do (the
   first write of stage 2, an unchanged file: section 7, step 10).

### 2.5 Personal values

Message 13 holds personal values (heart rate and power zones, FTP, weight and more, as settings
of a profile). openExpress never reads them: the reader asks message 13 for the listed toggles
only and skips every other field without decoding it (D13). The log names counts and kinds, never
a value; the tests use made-up files; a test on real files reads its expected values from the
private list of expected values, as the tests of activities do.

## 3. Sources and licences

openExpress takes facts from two open projects, which learnt the format by changing a setting on
a device and reading the file again (message and field numbers, codes, the rules of section
2.2); the README thanks both:

- **Sommet** (by skinnie, GPL-3.0-only): a desktop editor of Edge 1040 data screens over MTP; the
  field and built-in codes of the Edge 1040, field 99 of message 13. Its code is not copied:
  openExpress (GPL-3.0-or-later) writes its own from the description of the format.
- **Activity Profile Editor** (by Doug, fullcarbonbike; MIT): an editor for the Edge 530 and
  840; the most complete description of message 14 (the states of field 1, field 10 as identity,
  the rules of field 9, message 170), the known failures (section 6) and a table of about 210
  field IDs with their English names. Its code and data may be used: what is taken from it (the
  table of IDs of D4, for one) keeps its MIT notice and its author's name in the file that holds
  it.

The issue that asked for this feature called the Activity Profile Editor GPL-licensed; its
licence is MIT.

## 4. The window

The mockups are drawn from libadwaita widgets with made-up profiles and fields, wide (1000 px)
and narrow (360 px), light and dark, in Polish; the texts are in section 4.8.

### 4.1 Where it opens

A section of the device view, after Activities: "Activity Profiles", an icon of a grid. Like the
other sections it reads when it is first opened, keeps what it read, and Refresh reads again
(D1, D3). Devices without a `Sports` folder do not show it.

### 4.2 The list of profiles

- On top a search ("Search 113 profiles"): by name, letter case and diacritics aside.
- **Used Recently**: the profiles of the newest activities on the device, newest first, at most
  five (D2); none read yet: the group is not shown.
- **All Profiles**, A to Z.
- A row: the profile's colour as a dot (from message 12), its name, and "3 data screens · Map,
  Compass" (the built-in screens shown, at most two named, "+2" after them).
- 113 rows are one `Gtk.ListBox` with a filter; no paging.

### 4.3 A profile's page

Pushed onto the window's navigation, as an activity's page: the back arrow, the profile's name
and the device as the title.

- **Data Screens**, "In the order they scroll on the watch": a card for every screen shown, in
  the carousel's order, built-in screens among them (a card with the screen's sign and "Built-in
  screen"). A card of one's own draws the screen in the device's shape with its fields in their
  places (D5), "4 fields · layout A" under it. Two cards a row on a narrow window, four on a wide
  one.
- **Built-in screens**: a row for each, with a switch in stage 2 (a label "On"/"Off" in stage 1);
  one the device does not let hide (Map and ClimbPro on the Edges the sources describe): "Always
  shown on the device", no switch; one openExpress has no name for: "Built-in screen 221 –
  unknown to openExpress, read only".
- Stage 2 adds: the banner "Experimental: changes reach the device only when saved"; on each card
  a menu (Move Earlier, Move Later, Duplicate, Delete), and on a wide window cards that can be
  dragged; a card "Add Screen" at the end; the group **Copies on this computer** with "Restore
  Previous Version"; at the bottom, once something changed, the bar "2 changes, in this window
  only" with Discard and Save to Device (on a narrow window the two buttons alone, "Save (2)").

### 4.4 A screen's page

Pushed from a card. The screen drawn large, the chosen field in the accent colour. **Layout**:
"Number of Fields" (a spin button from 1 to what the model allows) and "Variant" (toggle buttons
with a small drawing of each variant, A, B, C, only those the model has for that number).
**Fields**, "Top to bottom, left to right": a row a field, "Place 1" under its name. Changes go
straight into the window's copy of the profile; the back arrow returns to the profile, where the
bar counts them. In stage 1 the same page without the controls.

### 4.5 Choosing a field

Pushed from a field's row. A search ("Search fields", matching the English name too in a Polish
window) and the **Categories** as expander rows ("Heart Rate – 14 fields"), the field's own
category open, its current field marked. A search shows the matching fields with their category
under each. Categories and names as the device's manual and Garmin Connect give them (D4). A
field unknown to openExpress is shown as "Field 588" and cannot be chosen; a screen keeping one
keeps it as it is.

### 4.6 Saving and restoring

- **Save to Device** asks first (`confirm()`): "Save the changes to the watch?" – "Run: 2
  changes on the data screens. Before saving, openExpress keeps a copy of the profile on this
  computer. The watch loads the changes when it restarts. This is an experimental feature."
  Cancel / Save.
- Then, as a task that writes to the device (`writes_to_device`), with progress: the copy (D7),
  the file made and checked (D8), written to `NewFiles` and read back.
- After it the banner "Saved. The watch loads the changes when it restarts" with "How?" (a
  dialog: unplug the device and restart it; do not change this profile on the device before
  that, or the import overwrites the change). The profile stays "waiting for the restart" until a
  later read shows the change ("The changes are on the watch") or not ("The watch did not load
  the changes", with Restore Previous Version) (D12).
- **Restore Previous Version** lists the copies of the profile, newest first, with their time;
  the one chosen is written back the same way, after a copy of the present file.
- An Edge 1050 keeps copies of its profiles itself, in `Sports/Backups` (FIT type 57, written by
  the device; the list of profiles leaves them out and says the day of the newest). A restore may
  offer them besides the copies on this computer: to be decided with the rest of stage 2.
- Leaving the page or the device with changes not saved asks: "Discard the changes to Run?".

### 4.7 The narrow window

Everything at 360 px, both languages: two cards a row, the bar's two buttons alone, the banner
on two lines, the variants' buttons in one row (three at most). The texts wrap.

### 4.8 Texts (English, Polish)

| English | Polish |
|---|---|
| Activity profiles | Profile aktywności |
| Search {n} profiles | Szukaj wśród {n} profili (ngettext) |
| Used recently / From the latest activities on the watch | Ostatnio używane / Z ostatnich aktywności na zegarku |
| All profiles | Wszystkie profile |
| {n} data screens | {n} ekrany danych (ngettext) |
| Data screens / In the order they scroll on the watch | Ekrany danych / W kolejności przewijania na zegarku |
| Screen {n} / Built-in screen | Ekran {n} / Ekran wbudowany |
| {n} fields · layout {letter} | {n} pola · układ {letter} (ngettext) |
| Built-in screens / On / Off | Ekrany wbudowane / Włączony / Wyłączony |
| Always shown on the device | Zawsze widoczny na urządzeniu |
| Built-in screen {code} / Unknown to openExpress, read only | Ekran wbudowany {code} / Nieznany openExpressowi, tylko do odczytu |
| Add Screen / Move Earlier / Move Later / Duplicate / Delete | Dodaj ekran / Przesuń wcześniej / Przesuń dalej / Powiel / Usuń |
| Layout / Number of fields / Variant | Układ / Liczba pól / Wariant |
| Fields / Top to bottom, left to right / Field {n} | Pola / Od góry, od lewej / Pole {n} |
| Search fields / Categories / {n} fields | Szukaj pola / Kategorie / {n} pól (ngettext) |
| Experimental: changes reach the device only when saved | Eksperymentalne: zmiany trafią na urządzenie dopiero po zapisie |
| {n} changes, in this window only / Discard / Save to Device | {n} zmiany, jeszcze tylko w oknie / Odrzuć / Zapisz na urządzenie |
| Save the changes to the watch? | Zapisać zmiany na zegarek? |
| Saved. The watch loads the changes when it restarts / How? | Zapisano. Zegarek wczyta zmiany po ponownym uruchomieniu / Jak? |
| The watch did not load the changes | Zegarek nie wczytał zmian |
| Copies on this computer / Made before every save of the profile | Kopie na komputerze / Robione przed każdym zapisem profilu |
| Restore Previous Version | Przywróć poprzednią wersję |
| Editing data screens (experimental) | Edycja ekranów danych (eksperymentalne) |
| Editing is not checked on this device yet | Edycja na tym urządzeniu nie jest jeszcze sprawdzona |

"Watch" and "device" follow the device's kind, as the other texts of the window (`gui/words.py`).
The names of the fields and categories are about 350 more texts (D4).

## 5. Decisions

### D1: where the profiles open — chosen: 1a

- **1a. A section of the device view (recommended; chosen):** "Activity Profiles" in the sidebar after
  Activities; a profile's page and a screen's page pushed onto the navigation, as an activity's
  page.
  - \+ The place of every other kind of thing on the device; Refresh and Sync as elsewhere.
  - − One section more in the sidebar (seven).
- **1b. A row on the Device page** ("Activity Profiles", with a count) that pushes the list.
  - \+ The sidebar stays as it is.
  - − A list of 113 behind a row, one level deeper than everything else.

### D2: which profiles come first — chosen: 2a

- **2a. Those of the newest activities (recommended; chosen):** the name of the profile is in message 12
  of an activity file, near its start; the names come from the activities whose summaries the
  Activities section has read, else from the newest ten activity files, read after the list is
  shown. Then all A to Z, and the search.
  - \+ The few profiles one uses are on top without a setting.
  - − Reading ten activity files (a few seconds over MTP) the first time.
- **2b. A to Z and the search only.**
  - − 113 rows, most never used.
- **2c. The device's own order** (its favourites): where the device keeps it is not known.

### D3: when the files are read — chosen: 3a

- **3a. All of them when the section opens (recommended; chosen):** the `Sports` folder listed, every file
  read (113 × 5.7 KB ≈ 650 KB), kept by name, size and time of change, as the activities'
  summaries; progress "Reading Profiles… 40 of 113".
  - \+ The list shows the count of screens; the search and the pages need nothing more.
  - − The time of 113 small reads over MTP, to be measured (expected below ten seconds).
- **3b. One file when its profile opens:** the list needs the names, which are inside the files,
  so each file is read anyway.

### D4: the names of the fields — chosen: 4a

- **4a. A table of openExpress (recommended; chosen):** ID → category, English name, Polish name. The
  names and categories are those of the device's manual in English and Polish (the words Garmin
  Connect uses); the IDs from the sources' published tables (the MIT one with its notice) and from
  files of the device, each ID checked on a device before editing allows choosing it. The names
  go through gettext with the context "data field", so the Polish is in `po/pl.po` like every
  text. A model's own set: the fields its manual lists.
  - \+ The names a user knows from the device and Connect, in both languages.
  - − About 350 names to map and translate; the Polish manuals call the elevation fields
    "distance fields" in one heading, to be corrected by hand.
- **4b. English names only, from the MIT table.**
  - − No Polish; names of the Edge for the watch.

### D5: the drawing of a screen — chosen: 5a

- **5a. The device's shape with its fields (recommended; chosen):** round for a watch, a rounded rectangle
  for an Edge (by the model's kind); the fields in rows by a table per model (count and variant →
  fields a row); a variant not in the table: the fields as a list, "Layout unknown".
  - \+ One look tells the screen apart; the variants are seen before they are chosen.
  - − A table per model, learnt from its files (2.4).
- **5b. Lists only.**
  - − Variants A, B, C mean nothing without a picture.

### D6: how a change is written — chosen: 6a

- **6a. The bytes changed in place and the file put in `NewFiles` (recommended; chosen):** the same
  length and records, only the changed fields' bytes, the file's CRC anew; the device takes it
  at its restart.
  - \+ What both sources do and the devices accept; everything unknown in the file stays as it
    was.
- **6b. The file written anew by a FIT encoder.**
  - − Unknown fields and their order could change; no source tried it.
- **6c. Written over the file in `Sports`.**
  - − Taken once, then no more (Activity Profile Editor).

### D7: the copies — chosen: 7a

- **7a. A copy of the profile before each save, and of the whole `Sports` folder before the first
  save of a session (recommended; chosen):** in the device's backup folder, as the copies of the app list
  (a folder named after the kind and the time), the last ten of a profile kept; Restore Previous
  Version writes a copy back as any change, after a copy of the present file.
  - \+ Every save can be undone from the computer; a whole folder covers a device that loses
    more than the profile written.
  - − About 650 KB a session that writes.
- **7b. A copy of the profile only.**

### D8: the checks — chosen: 8a

- **8a. Before, during and after (recommended; chosen):** before writing, the new bytes are read by
  openExpress's own reader and compared with what was meant: the changed fields as meant, every
  other byte the same, the CRC right; the file written by `Storage.write_file_checked` (read back
  and compared); after the restart, the next read of `Sports` compares the profile with what was
  saved (by the screens' identity, field 10, not by place) and says whether it is there.
  - \+ A wrong file never reaches the device; a change lost is said, not guessed.
- **8b. The CRC only.**

### D9: on which devices editing is allowed — chosen: 9a

- **9a. Only on models whose files are measured and whose variants and codes are known
  (recommended; chosen):** a list in the code (the Edge 1050; the fēnix 8 after 2.4); other devices are
  shown read only, with "Editing is not checked on this device yet". The reader checks that a
  file has the shape known for its model (fields, array lengths); another shape: read only.
  - \+ A change is written only where it is known how the device reads it.
- **9b. Every device with the same messages.**
  - − A variant or a code meaning something else on another model.

### D10: Connect IQ data fields — chosen: 10a

- **10a. Shown, not changed (recommended; chosen):** named by the app's name when message 170 and the
  device's app list say which app it is, else "Connect IQ field"; a screen with one shows it but
  cannot be changed (changing a screen's fields means moving the records of message 170 too,
  which neither source does reliably).
- **10b. Editable, message 170 rewritten.**
  - − The known failure: a field shows "Timer" instead of the app.

### D11: marking it experimental — chosen: 11a

- **11a. Editing off until turned on (recommended; chosen):** Preferences, "Editing data screens
  (experimental)"; until then the pages are those of stage 1; when on, the banner on every
  profile's page, the word in the question before saving, "(experimental)" in the help of the
  command line.
  - \+ Nobody changes a device's files without having chosen to.
- **11b. On for everyone, marked by the banner.**

### D12: the restart — chosen: 12a

- **12a. Said, then checked (recommended; chosen):** the banner and "How?" of 4.6; the profile waits for
  the restart until a read shows the change; the device view's other pages work meanwhile.
  - \+ The user knows what is left to do and learns whether it worked.
- **12b. openExpress restarts the device:** no way is known over MTP or as a USB drive.

### D13: personal values — chosen: 13a

- **13a (the only option; chosen):** the reader of profiles takes from message 13 only the
  fields of a table per model (the toggles of built-in screens) and skips the rest without
  decoding it;
  nothing of message 13 reaches the log, the window or a test of real files but those toggles;
  written back, message 13's bytes change only in those toggles.

### D14: the command line — chosen: 14a

- **14a. Read, and restore (recommended; chosen):** `openexpress profiles` (the list: name, screens),
  `openexpress profiles show NAME` (each screen with its fields, as text), and in stage 2
  `openexpress profiles restore NAME [--copy WHEN]`, a trial run without `--apply`, marked
  experimental. Editing stays in the window.
  - \+ A way back from the command line if the window cannot open.
- **14b. No command.**

### D15: the built-in screens in the order — chosen: 15a

- **15a. Cards in the carousel's order, switches below (recommended; chosen):** a built-in screen shown
  has its card among the others, where the device shows it, and moves like them; the list of
  built-in screens turns them on and off.
  - \+ The page shows the order the device has; field 9 is shared by both kinds.
- **15b. Only one's own screens as cards; the built-in ones in their list.**
  - − Where a built-in screen falls between them is not seen, and moving one's own screens
    must keep the built-in ones' places.

## 6. What can go wrong, and how it is found

| What | How it is prevented, and found |
|---|---|
| A wrong variant code: another layout, or a file not taken | only codes learnt from the model's files (D9); the check after the restart (D8) |
| A new screen with a field 10 another record has: the device merges it and destroys another screen (a failure the sources saw) | field 10 of a new screen is a counter no record of the file uses, deleted ones included; a test |
| Two screens with the same field 9: one lost at the import | field 9 numbered anew 0, 1, 2… over every screen shown after each change; a test |
| More screens or fields than the device takes: the device rewrites the file | the limits read from the file (the length of field 7, the places of message 14) and the model's table; "Add Screen" off at the limit |
| A Connect IQ field moved: it shows "Timer" | screens with one are not changed (D10) |
| A wrong CRC | the file read by openExpress's reader before it is written (D8); tests with files whose CRC is known |
| The fēnix does not take files from `NewFiles` over MTP | the first write is an unchanged file on the fēnix 8 (step 10); the check after the restart says so; nothing is written to `Sports` |
| The device unplugged or not responding while writing | `write_file_checked` removes a partial file; the device's own `Sports` file is never written; a stall as everywhere (the banner, unplug) |
| The profile changed on the device after the save and before the restart | the import overwrites it: "How?" says not to; the check after the restart shows what the device kept |
| A firmware that changes the file | the shape checked against the model's (D9): read only, and the log says what differs (numbers only) |
| A personal value in the log, a test or the window | D13; a test that a made-up file's message 13 values never reach the model |
| The window and the command line writing at once | the lock of the device's writes (`writes_to_device`, `WRITING`) |

## 7. Steps

Each step starts with tests that fail on the code before it, keeps its texts and their Polish in
the same commit, and passes the usual checks before its commit (ruff, the tests with and without
a display, the program's folders unchanged by the tests). Each waits for acceptance.

**Stage 1**

0. **Facts from the device (by the user, read only):** copies of the fēnix 8's `Sports` folder,
   each after one change made on the watch: each variant for one to six fields; each built-in
   screen turned on and off; a screen with a field known to be empty. Measured with a script that
   prints structure only.
1. **The reader** (`openexpress/profiles.py`): a profile from a file: name, colour, sport;
   screens (place, identity, order, fields, variant, shown); built-in toggles of message 13 by the
   table; Connect IQ fields. Made-up files built by a test helper in the shapes of the fēnix 8 and
   the Edge 1050; damaged and cut files; another shape (read only); message 13's other fields
   never decoded.
2. **The tables**: field IDs (category, English, Polish), built-in codes, variants per model.
   Tests: IDs unique, every name translated, an unknown ID named "Field {n}".
3. **Reading from the device**: the folder from `GarminDevice.xml`, all files with progress, kept
   by name, size and time of change (D3); the names of the newest activities' profiles (D2).
   Fake storages: MTP and a USB drive, unplugged, a stall.
4. **The window, read only**: the section, the list and its search, the profile's page with the
   drawings, the screen's page; narrow window; light and dark.
5. **The command line and the documents**: `profiles`, `profiles show`, `docs/cli.md`,
   `docs/guide.md`, the README's features.

**Stage 2**

6. **Changing a file**: the model to bytes, only the fields changed; the CRC. Tests: an unchanged
   profile gives the same bytes; each kind of change touches only its bytes; field 10 and field 9
   by the rules of section 6; the limits.
7. **Saving and restoring**: the copies (D7), `NewFiles`, the checks (D8), the state waiting for
   the restart and its end; Restore Previous Version. Fake storages.
8. **The window, editing**: the preference (D11), the screen's controls, choosing a field, the
   cards' menu and dragging, the switches, the bar, the question, the banners; narrow window.
9. **The command line and the documents**: `profiles restore`, the experimental marks.
10. **On the device (by the user):** on the fēnix 8, first an unchanged profile through
    `NewFiles` and a restart (compared byte for byte, but `file_id.number`); then one field
    changed; a variant; the order; a built-in screen off; Restore Previous Version.

## 8. Size

Stage 1: about 1,100 lines of code (the reader 300, the tables 250 as data, reading from the
device 150, the window 350, the command line 80), about 1,000 lines of tests, about 30 texts and
350 names of fields with their Polish; 6 commits. Stage 2: about 1,200 lines of code (changing a
file 250, saving and restoring 300, the window 550, the command line 100), about 1,300 lines of
tests, about 40 texts; 5 commits. The facts of step 0 and the checks of step 10 are the user's
time on the device: about an hour each.
