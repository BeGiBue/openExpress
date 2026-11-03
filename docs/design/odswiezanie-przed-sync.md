# Design: reading a cut-short file again after a fresh mount

Status: the decisions in section 4 are made (D1 1a, D2 2a, D3 3b, D4 4a, marked "chosen");
the implementation is done (steps 1–5 of section 7), as section 5 describes it. Not seen on a
device yet: a cut-short file cannot be made on purpose, and the log tells when it has happened
("upload: a … file read again after the device was mounted again", "backup: …"). The scope in
section 1 is set once: what it does not list is not added while it is implemented.

## 1. Scope

A FIT file that the device writes while it is connected over MTP can be read cut short: gvfs
gives the size the file had when it was first looked at. Today the sync and the backup find such
a file and leave it out; the sync reads it again at the next sync, which in practice means after
the device has been unplugged and plugged in again. This design lets them get the whole file
without unplugging: gvfs mounts the device again, which gives fresh sizes, and the file is read
once more.

In scope, for a device over MTP through gvfs:

1. **The sync**, in all three places that run it (the window, the command line, the background
   service; all through `service.run_sync`).
2. **The backup**, in the window and on the command line (`backup.run_backup`).

Not in scope:

- USB drives and folders: they read the file system, whose sizes are current.
- The diagnostic files and the app list, which read device files the same way.
- Files other than FIT: there is no check of their wholeness to start from.

## 2. The problem

- gvfs-mtp opens one libmtp session when it mounts the device and keeps it. libmtp keeps what it
  learnt of each object, its size among it, from the first time it is asked: `ptp_object_want`
  (libmtp 1.1.14, `src/ptp.c:6659`) returns the kept object info without asking the device, and
  `LIBMTP_Get_Filemetadata` goes that way.
- The device announces a changed object with the PTP event `ObjectInfoChanged`. libmtp ignores
  it ("TODO: rescan object cache", `src/libmtp.c:2224`) and has no `LIBMTP_EVENT_*` for it, so
  gvfs never hears of it. libmtp 1.1.22 with gvfs-mtp 1.60.3 behaves the same.
- So `query_info` through Gio gives the old size, and a read ends at it. Asking Gio again
  changes nothing: the same kept info answers.
- Seen once: a fēnix 8 rewrote `Garmin/Coach/schedule.fit` while it was connected. The sync read
  14 233 B of 20 625 B, and Garmin's server refused the file (415). After the device was
  unplugged and plugged in again, the same file had 20 625 B and a right CRC. When the device
  wrote it is not known.
- Fresh sizes without unplugging come from a new libmtp session, that is gvfs unmounting the
  device and mounting it again; or from a PTP session of our own (`device/ptp.py`, a fresh
  `GetObjectInfo`), which needs the unmount too. This design uses the first: in the Flatpak it
  needs no USB permission.

## 3. What exists today

### The sync

1. **The device is found.** In the window and the background service by the mounts of
   `Gio.VolumeMonitor` (the background service starts a sync 5 s after a mount appears); on the
   command line by `gio_storage.open_device_storage`. A `GioStorage` on its `mtp://` address,
   then a `service.DeviceSession`.
2. **`service.run_sync`**, the one entry of all three places, takes `sync_lock` (one sync at a
   time across processes), plans (`plan_sync`) and applies (`apply_sync`).
3. **The plan** (`sync.plan_uploads`) lists the device's folders with the sizes gvfs gives. A
   file of a single-file type (rewritten in place, as `schedule.fit`) is read already here, for
   its MD5 against the one kept from its last upload; its data stays on the candidate
   (`UploadCandidate.data`).
4. **The uploads** (`sync._run_uploads`) read each file (`_read_candidate`: the data the plan
   kept, or `storage.read`). `still_being_written` checks each FIT file that is not a ZIP with
   `fit.incompleteness`; a cut-short one is left out (`_skip_incomplete`), in both passes: the
   match of activities Garmin Connect already has, and the upload. For the types that must
   arrive in order (monitoring, sleep) the later files of the type wait. The summary gets the
   step `still_written`.
5. Then Garmin Connect's queue, TrueUp and Connect IQ.

### The backup

`backup._copy_files` lists every file of the backup first, then reads them one by one with
`storage.read`. A FIT file is checked with `fit.not_whole`, the check behind
`still_being_written`: one cut short is left out (counted, `incomplete_text`); one not whole
otherwise is copied as it is. The bytes of the backup are counted from the listed size
(`entry.size`).

### Mounting again

It exists already, for the PTP sessions that reach files gvfs does not show
(`gio_storage._exclusive`):

- `_unmount`: `Gio.Mount.unmount_with_operation`. gvfs closes its libmtp session; the device
  stays on USB.
- `_remount`: `mount_enclosing_volume` on the same `mtp://` address, then a wait until
  `GARMIN/GarminDevice.xml` can be seen (up to 20 s, once a second).
- Time limits: 30 s for each. An unmount cancelled at its limit is followed by `_mount_back`:
  the state is watched until it settles (2 s the same, at most 15 s), up to 3 tries.
- `own_remount`: for 15 s after our own unmount and mount, the window and the background service
  do not take them for a device unplugged and plugged in; only within the process that did them.
- The address stays the same, so the `GioStorage` goes on working afterwards.

Measured (three weeks of the developer's program log, fēnix 8):

- 60 PTP sessions, each an unmount, the session and the mount until `GarminDevice.xml` was seen:
  0.2–0.5 s in all, mostly 0.2 s; 5 of them in the Flatpak, 0.2–0.4 s. The unmount itself took
  about 0.0 s.
- 13 of 83 unmounts went over their time limit, all in a stress test with a deliberately short
  limit; in ordinary use none of 70.
- An Edge 1050 went through 10 unmount and mount cycles of the stress test without an error.
- Not measured: how long the first listing of the folders takes after a mount.

## 4. Decisions

### D1: when the device is mounted again — chosen: 1a

- **1a. After a cut-short FIT file is found, at most once a sync or a backup (recommended;
  chosen).**
  - \+ Costs nothing in a sync without such a file, that is nearly every sync; 0.2–0.5 s when it
    happens.
  - \+ Catches a file the device wrote at any time before it was read, also during the sync.
  - \+ The new risks (section 6) come only where the file would wait for the next replug anyway.
  - − More code than 1b: the data the plan kept of a single-file type must be read again, and the
    order of monitoring and sleep must hold.
- **1b. Before every sync.**
  - \+ Least code: one call in `run_sync`, under the lock, before the plan.
  - − 0.2–0.5 s and a new listing of every folder in every sync; a new point of failure in every
    sync; the file manager loses the device at every sync; another process (section 6, risk 3)
    sees an unplug at every sync of the command line or the background service.
  - − Catches only what the device wrote before the sync began.
- **1c. Before a sync, only when the device was connected less than X seconds ago.**
  - − The command line does not know when the device was connected (another process, no
    signals).
  - − The background service syncs 5 s after the device appears, so for it this is always 1b.
  - − Nothing tells X: when the device writes is not known (a phone that syncs the watch over
    Bluetooth while the cable is in could write at any time; not checked).

### D2: when in the uploads — chosen: 2a

- **2a. At the first cut-short file, then that file read again (recommended; chosen).**
  - \+ Files of a type that must arrive in order keep their order; later cut-short files of the
    same sync are read again without another mount.
  - − A mount that fails stops the rest of the sync (the device is not there to read), with
    today's message to unplug and plug in. In ordinary use no mount has failed (section 3).
- **2b. After all uploads, the cut-short files read again in one pass.**
  - \+ A failed mount cannot touch the uploads before it.
  - − Monitoring and sleep files held back behind a cut-short one must join the pass in order;
    Garmin Connect's queue, which follows, needs the device mounted all the same.

The backup does as 2a: at its first cut-short FIT file, then that file read again; its files
have no order to keep.

### D3: what else reads again — chosen: 3b

- **3a. Only the sync** (the recommendation of the first draft): the sync is where a cut-short
  file matters most, since Garmin Connect gets it only after the next replug.
- **3b. Also the backup (chosen)**, which has the same check: the same mechanism, at most once
  a backup, in this design rather than later.
  - \+ A backup taken while the device writes a file holds the whole file instead of leaving it
    out.
  - − More to test now; the diagnostic files and the app list still do not have it.

### D4: what the user is told — chosen: 4a

- **4a. A step of the progress and a line of the log (recommended; chosen).** The step:
  "Refreshing the device's files…" (Polish: "Odświeżanie plików urządzenia…"). A file read
  whole after the refresh is uploaded or copied as any other; one still cut short gives today's
  step `still_written` in the sync and today's count of files left out in the backup. The row
  "Last sync" does not change, so no new pattern in `tests/data/last_sync/`.
- **4b. Also a line of the summary**, e.g. "1 file read again after the device was mounted
  again".
  - − A new pattern of the row, with its words in English and Polish.

## 5. What changes in existing modules

As implemented:

| Module | Change |
|---|---|
| `device/storage.py` | `Storage.refresh(progress=None) -> bool`: by default does nothing and returns False (a folder, a USB drive). `replug_text`: a device not mounted again, its error and what to do (unplug and plug in), unless the error says that itself. `refresh_to_read_again`: the refresh as the sync and the backup ask it, a device not mounted again raised with that text. |
| `device/gio_storage.py` | `_unmounted`: the shared part, taken out of `_exclusive` with no change of behaviour (the quiet time for `own_remount`, the unmount with `_mount_back` after a time limit or Ctrl+C, the mount again, also after an error). `GioStorage.refresh(progress)`: says its step, then unmounts and mounts again without a PTP session; True once the device is mounted again. False, the device left as it is, when its place on USB is not known (our own unmount would be taken for an unplug) and when the unmount is refused or does not finish in time (then whether gvfs has fresh sizes is not known). |
| `sync.py` | `_WholeReads`, in both passes of `_run_uploads`: at the first cut-short FIT file one refresh; the candidate's kept data dropped and the file read from the device again; a later cut-short file of the same sync read again without another refresh; still cut short: left out. A device not mounted again stops the sync. |
| `backup.py` | `_copy_files`: the same, at most once a backup; the bytes counted from what was read (`len(data)`) rather than from the listed size. |
| `progress.py` | `refreshing_text()`: the text of the step, next to `downloading_text` and `copying_text`; its Polish. `GioStorage.refresh` says it where a refresh is done, so a folder and a USB drive never show it. |
| `ciq.py` | Its own text of a device not mounted again replaced by `replug_text`, with the same words. |
| `sync.py`, `backup.py`, `gio_storage.py` | Lines of the log: the refresh, each file read again, a refresh not done; the type and the sizes, never the name of the file. |
| `watch.py`, `gui/`, `service.py` | Nothing: they go through `run_sync` and `run_backup`, and `own_remount` already hides our own mount. |
| `docs/guide.md` | "Sync details", and the backup in "The start page and the device page": a cut-short file is read again after the device is mounted again; only one still cut short is left out, with today's advice to disconnect and reconnect the device. |

The dry run of the command line does not refresh: it only plans. A single-file type is read
there for its MD5, so its count may include a cut-short file, as today.

## 6. Risks

1. **The device during the refresh.** Closing the MTP session is not unplugging: changes written
   to the device still take effect only once it is unplugged, as after the PTP sessions of
   today. An Edge 1050 restarts when it is unplugged, not when a session closes. A file still
   being written when it is read again is still cut short and is left out as today.
2. **A mount that fails.** The sync or the backup stops with today's message (unplug and plug
   in). What the sync uploaded before is kept; a backup stopped this way leaves no partial
   folder, as any stopped backup. In ordinary use none of 70 mounts has failed.
3. **Other processes.** `own_remount` knows only its own process's mounts, a risk known before
   this design and the same as for the PTP sessions of today.
   - The background service, run by another process, takes the refresh for a device plugged in
     and tries a sync 5 s later: `SyncBusy` while the first sync runs, or a second sync
     (harmless, with its notification) when the first has ended.
   - A window open in another process sees it as it sees a PTP session of another process today.
   - With 1a this is rare; with 1b it would happen at every sync.
4. **The file manager.** The device leaves GNOME Files for a moment, as with a PTP session today.
5. **KDE.** openExpress needs gvfs-mtp there too. KDE's MTP service (kmtpd, in kio-extras) opens
   devices when it starts and when one is plugged in; a mount of gvfs is no USB event, so it
   should not take the device in the gap. Not checked on KDE.
6. **Flatpak.** The unmount and the mount go to gvfs over D-Bus, as for the PTP sessions of the
   Flatpak today; no USB permission is needed.
7. **Threads.** `Gio.VolumeMonitor` is used from the thread of a task, as for the PTP sessions of
   today (GIO documents it for the main thread; it has worked so far).
8. **Other tasks of the window** that read the device during a sync or a backup could meet the
   moment it is unmounted: to be checked when it is implemented.

## 7. Order of work

Each step starts with a test that fails on the code before it, keeps its texts and their Polish
in the same commit, and passes the usual gate before its commit: ruff without findings, the tests
with and without a display, and the program's folders unchanged by the tests. Each step waits for
acceptance.

1. **The shared part of `_exclusive` taken out**, with no change of behaviour: the tests of PTP
   sessions and of the unmount race unchanged, the syntax trees compared before and after.
2. **`Storage.refresh` and `GioStorage.refresh`**, on the gvfs fake (`tests/gio_fake.GvfsDevice`):
   unmounted and mounted again, `own_remount` true meanwhile, `_mount_back` after a time limit;
   a folder and a USB drive return False.
3. **The sync reads again.** A small fake storage that gives cut-short data until `refresh()`
   (in `tests/fakes.py`). Failing tests:
   - a cut-short file of a multi-file type: one refresh, uploaded whole;
   - a cut-short file of a single-file type, its data kept by the plan: read again, uploaded,
     the MD5 of the whole file kept;
   - still cut short after the refresh: left out, one refresh only;
   - two cut-short files: one refresh a sync;
   - monitoring keeps its order;
   - a folder and a USB drive (`refresh` does nothing): as today;
   - a mount that fails: the sync stops with today's message (unplug and plug in), the earlier
     uploads kept.

   The step of the progress (`progress.refreshing_text`), its text and its Polish.
4. **The backup reads again.** The same cases as the sync, as far as they apply: a cut-short
   file read whole after one refresh and copied; still cut short: left out and counted; two
   files: one refresh a backup; a folder and a USB drive: as today; a mount that fails: the
   backup stops, no partial folder left; the bytes counted from what was read.
5. **Documentation**: `docs/guide.md` (as in section 5).

On a device: the mount itself is what the PTP sessions do today. A cut-short file cannot be made
on purpose; the log line of the refresh shows when it has happened.

## 8. Size

About 150–200 lines of code (storage about 10, gio_storage 40–60 with the shared part, sync about
40, backup about 30, progress and the log lines about 10), 250–300 lines of tests, one small
fake, one text with its Polish, and 5 commits, one a step of section 7.

As implemented: 150 lines of code added and 34 taken out, 375 lines of tests added and 15
taken out (one fake, `fakes.stale_sizes`, which also lists a file at its old size), one text
with its Polish, and 5 commits.
