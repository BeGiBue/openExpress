# Design: a device that stops answering over MTP

Status: the decisions in section 4 are made (D1 1a, D2 2a, D3 3a, D4 4a, and D5 5a, D6 6a,
D7 7a, taken when step 1 began; marked "chosen"). Step 1 of section 7 is implemented: listings
and queries under the limit, the error, the device layer letting it through. Steps 2–6 are not.
Sections 2 and 3 describe the program before this work. The work goes step by step (section 7),
each step after a yes. The scope in section 1 is set once: what it does not list is not added
while it is implemented.

## 1. Scope

A device connected over MTP can stop answering in the middle of a read. Today the program then
waits for ever: the bar stands still, the window answers but the task never ends, and only
killing `gvfsd-mtp` and unplugging the device end it. This design puts a limit on every read
from the device through gvfs: after 30 s without any progress the read is given up, the user is
told that the device stopped responding and to unplug it and plug it in again, and nothing else
is tried on that device until it is.

In scope, for a device over MTP through gvfs (`GioStorage`):

1. **Every reading operation**: listing a folder, the information of a file, its contents, the
   start of a file, the free space and capacity (D1).
2. **What follows a stall**: the error and its words, the operations after it in the same
   session, the window (D4), the log lines that tell how long the device had been idle.

Not in scope:

- Writes to the device (copying, deleting, making a folder): no time limit of their own yet;
  after a stall they fail at once like any other operation (section 5).
- USB drives and folders: they read the file system.
- A periodic request that keeps the device busy (D3): left for later.
- PTP sessions of our own (`device/ptp.py`): they have the time limits of libusb.

## 2. The problem

Seen once, on 2 November 2026, on a fēnix 8 (software 23.39) over MTP through gvfs, Fedora 44,
in the Flatpak of 0.8.1 (from the program's log):

- 00:41:25–00:41:39: 30 activities read (10.1 MB in 8.0 s) and the music listed; the device
  answered as usual.
- 00:41:50: a sync starts. Its plan reads `GARMIN/Backup/Backups/settings_backup.bak`, a file
  of a single-file type, for its MD5 (`sync.plan_uploads`); the read never answers. The bar
  stands on "Looking for new files on the device…".
- `gio list` and `gio mount` on the device's address hang too; `lsusb` shows the device on USB;
  `dmesg` shows no error and no disconnect: not USB nor the driver, but the MTP session in the
  device.
- 00:49:50, after `gvfsd-mtp` was killed: the sync stops after 480.7 s with "Error in stream
  protocol: End of stream" for that file.
- 00:50:23–00:53: the window tries to mount the device every 32 s or so; each mount gives up at
  its limit of 30 s. Only unplugging the device and plugging it in again helps; the syncs
  after it run as usual.

Why everything hung, not only that file (gvfs-mtp 1.60.3, `daemon/gvfsbackendmtp.c`):

- The backend keeps one mutex for the whole mount and holds it across each libmtp call. A read
  (`do_read`: `LIBMTP_GetPartialObject`) that does not return blocks every later operation on
  that mount: listings, queries, the unmount, a new mount of the same backend.
- `do_read` does not look at the job's cancellable, and a libmtp call cannot be interrupted. A
  client that cancels stops waiting; the backend stays blocked until the device is unplugged
  (or the process is killed).
- A read is served by `LIBMTP_GetPartialObject` for as many bytes as the client asks, so a
  file read in chunks gives one answer a chunk.
- The backend already asks the device something every 900 s (`mtp_heartbeat`:
  `LIBMTP_Get_Friendlyname`, when the mutex is free), so a mounted device is never quite idle.

The free space reaches the device: `do_query_fs_info` calls `LIBMTP_Get_Storage` on each call,
and libmtp 1.1.14 (the version read) then sends `GetStorageIDs` and `GetStorageInfo` anew, with
nothing kept. The
information of a file does not: libmtp keeps it from the first time it is asked.

## 3. What exists today

### The reads of `GioStorage`

Each is synchronous and given no cancellable (`None`), so none has a time limit:

| Operation | Gio call | Used for |
|---|---|---|
| `_list` | `enumerate_children`, then `next_file` | `listdir`, `walk_files`, `resolve` (the case of a path), `exists` |
| `info`, `_size_now` | `query_info` | a file's size and time, the check after a write |
| `_read` | `load_contents` | `read`: every file read whole |
| `_read_start` | `read`, then `read_bytes` | `read_start`: the start of a file (headers) |
| `_fs_attr` | `query_filesystem_info` | `free_space`, `capacity` |

About a hundred places in fifteen modules read through them (the sync, the backup, activities,
diagnostics, Connect IQ, maps, own maps, music, updates, the command line); the limit belongs in
these operations, not in their callers. The window reads the device only in its tasks, off the
GTK thread.

### Waiting on Gio

`gio_storage._wait(start, timeout_s, what, name)` runs one asynchronous Gio operation to its end:
in a worker thread on a main context of its own, in the main thread on the default one. At
`timeout_s` it cancels it and waits `CANCEL_WAIT_S` (5 s) more for its answer, then raises
`GioTimedOut` ("…: the device did not answer in time") and logs what happened. Only the mount
(30 s), the unmount (30 s) and the eject (60 s) use it today.

### Measured

From the program's log, 13 October to 2 November 2026:

- Reads of activities: 13, at 1.26–1.37 MB/s each; none slower.
- Syncs: 78; the long ones (up to 40 s) mostly wait for TrueUp. No "End of stream" and no time
  limit reached outside a stress test, but on 2 November.
- The time of a single read is not logged, so a stall of a few seconds would not show.

## 4. Decisions

### D1: which operations have a limit — chosen: 1a

- **1a. Every reading operation of `GioStorage` (recommended; chosen):** `_list`, `info` and
  `_size_now`, `_read`, `_read_start`, `_fs_attr`.
  - \+ Every caller is covered at once, also those added later.
  - \+ The stall seen was in the plan of a sync, which a limit on file contents only would
    cover by chance; the listings and queries go through the same blocked mutex.
  - − Six operations change at once (section 7 splits them in two steps).
- **1b. Only reads of file contents** (`_read`, `_read_start`).
  - − A listing or a query blocked behind the same mutex still waits for ever.
- **1c. Reads and writes.**
  - − A write cut off leaves a part of a file, which the clean-up after a failed write
    (`_discard_partial`) must then handle with no answer from the device; in the Flatpak writes
    go through `gio copy` on the host. Left for a design of its own.

### D2: the limit — chosen: 2a

- **2a. 30 s without progress a step; files read in chunks of 256 KiB (recommended; chosen).** A
  step is one answer of Gio: opening a file, a chunk of it, closing it; opening a listing, a
  portion of it (`next_files_async`), closing it; one `query_info`; one
  `query_filesystem_info`. Each goes under `_wait` with the limit.
  - \+ No false alarm for a large file: the time counts from the last answer, not from the
    start. A chunk of 256 KiB takes about 0.2 s at the speed measured, so 30 s is a margin of
    more than a hundred times.
  - \+ The same limit as the mount and the unmount.
  - − Up to 35 s (with `CANCEL_WAIT_S`) before the user is told.
- **2b. 15 s a step.**
  - \+ Told sooner.
  - − Half the margin, with nothing measured of a slow device but its mount (up to 20 s until
    `GarminDevice.xml` can be seen).
- **2c. A limit on the whole file, from its size.**
  - − The size gvfs gives can be old (a file written while connected), and a whole-file wait
    needs a guess of the speed.

### D3: a request that keeps the device busy — chosen: 3a

- **3a. Not now (recommended; chosen).** Come back when the log lines of section 5 show stalls
  after a long time without a request.
  - \+ The one stall seen came a few seconds after the device had answered many reads, not
    after idleness; gvfs-mtp already asks the device something every 900 s; three weeks of
    logs show no shorter stalls.
- **3b. Now, in the window only.** While the device view is open and no task runs, ask the free
  space (`GetStorageInfo`, which reaches the device) every 5 minutes, under the same limit.
  - \+ A stall would be found before the user starts a sync.
  - − Not shown to prevent anything; another request queued on the same mutex as the tasks.

### D4: the window after a stall — chosen: 4a

- **4a. A lasting banner, and no more mounts at that place on USB (recommended; chosen).** The
  window's banner (`Adw.Banner`, as for the setup and the sign-in) says "The device stopped
  responding. Unplug it and plug it in again." until the device is unplugged. While the same
  device stays at the same place on USB (`usb_still_there`), the window does not try to mount
  it: each try would wait 30 s for the same blocked mutex. Once the place is gone (unplugged,
  restarted: a new device number) the banner goes and detection works as today.
- **4b. As today.** A try to mount every 32 s or so, each giving up after 30 s, without saying
  why.

### D5: when the error comes in — chosen: 5a

- **5a. In step 1, with its words (recommended; chosen):** `DeviceNotResponding` with its
  English and Polish text and `says_replug`, and the tests of its words, come with the first
  step that raises it.
  - \+ A step raises the error it is tested with; no text in between to change later.
  - − Step 3 no longer brings the error, only what follows it.
- **5b. In step 1 with the words of today's time limits** ("…: the device did not answer in
  time"), its own words in step 3.
  - − A text shown for two steps, then changed.

### D6: the handlers of the device layer — chosen: 6a

- **6a. `DeviceNotResponding` goes past the handlers of the device layer (recommended;
  chosen).** `Storage.resolve` and `Storage.sizes` take a listing that failed for a missing
  folder; `_remount` looks for `GarminDevice.xml` up to 20 times, a second apart, whatever
  fails; `_device_state` takes a failure for "between"; `refresh` takes one for "not
  refreshed". Each lets the error through and keeps its answer for any other failure.
  - \+ Without it a stall while a path is looked for reads as a missing file after 35 s ("File
    not found on the device", an empty listing), and a sync goes on, waiting 35 s at every next
    path; `_remount` waits up to 20 times 35 s.
  - − Five handlers more than section 5 had.
- **6b. Leave them to step 3.**
  - − Step 1 alone would turn a stall into missing files.

### D7: a write that meets a stall — chosen: 7a

- **7a. No clean-up after it (recommended; chosen):** `write` and `write_file` let
  `DeviceNotResponding` through as they let `CopyNotStarted`, without `_discard_partial`. A copy
  has no time limit (D1), so the error comes only before it: from the size of the file there
  (`_size_now`) or from finding its folder.
  - \+ Nothing was touched, and a clean-up would ask the same blocked device again.
- **7b. Clean up as after any failure.**
  - − Waits another 35 s for the same device, then fails the same way.

## 5. What changes

| Module | Change |
|---|---|
| `device/gio_storage.py` | The six reading operations asynchronous, each step under `_wait` with `STALL_S = 30`: `_list` with `enumerate_children_async` and `next_files_async` (portions of 100), all its steps on one main context (`_wait(context=…)`, section 6), `info` and `_size_now` with `query_info_async`, `_read` reading a stream in chunks of 256 KiB (`read_async`, `read_bytes_async`, `close_async`), `_read_start` the same up to its count, `_fs_attr` with `query_filesystem_info_async` (its action: "Cannot read the space on the device"). A step that reaches its limit raises `DeviceNotResponding`. |
| `device/storage.py` | `DeviceNotResponding(DeviceError)`, made by `DeviceNotResponding.during(action)`, with `says_replug = True` as `replug_text` reads it: "{action}: the device stopped responding. Unplug it and plug it in again." (Polish: "{action}: urządzenie przestało odpowiadać. Odłącz je i podłącz ponownie."). In step 1 (D5). |
| `device/storage.py` | `Storage.resolve` and `Storage.sizes` let it through (D6); `write` and `write_file` let it through without a clean-up (D7). |
| `device/gio_storage.py` | `_remount`, `_device_state` and `refresh` let it through (D6). |
| `device/gio_storage.py` | Fast failure: after a `DeviceNotResponding` the storage keeps it, and every later operation of it, writes too, raises it again at once instead of waiting 30 s each. A device plugged in again is a new mount and a new storage. |
| `sync.py`, `backup.py` | `DeviceNotResponding` stops the sync or the backup: it goes past the handlers that let one unreadable file not stop them, as a device not mounted again does. The backup leaves no partial folder. |
| `device/gio_storage.py` | Log lines, never with a path or a file name. A step that reached its limit: what it was (a read, a listing, a query, the free space), how long since the device last answered, how long since this process opened the storage (a mount older than the process is said to be so). A step that took more than 5 s (`SLOW_STEP_S`): what it was and how long. |
| `gui/` | D4: the window keeps the place on USB of a device that stopped responding, shows the banner with its own text (the window's words, not the command line's), and does not start a refresh of that device while it stays at that place. |
| `docs/guide.md` | What the message means and what to do. |

Left on purpose as they are in step 1, and looked at again in step 3: the 25 handlers of
`DeviceError` in other modules. Each turns the error into a line of a report, an answer of "not
known" or an item skipped; with fast failure (step 3) the later operations of the same device
fail at once, but what each then says is to be settled there:

- `ciq.py` (10): `_hides_app_files`, `prepare_app_dir`, `_install_hidden` (3), `_ptp_delete`,
  `_remove_hidden` (3), `save_app_list_copy`;
- `ownmaps.py` (4): `list_own`, `overview`, `add`, `_failed_text`;
- `diagnostics.py` (4): `read_errors` (2), `at_open` (2);
- `maps.py` (2): `cleanup_plan`, `_write_unlock`;
- `cli.py` (2): `_status_updates_online`, `_eject_drive`;
- `watch.py` (1): `_open_session`; `updates.py` (1): `presence`; `service.py` (1):
  `open_device_or_drive`.

The command line says the error once and ends with exit code 1, as for other errors of the
device. The background service logs it and tells it in its notification of a sync that failed;
its next sync comes with the next mount of the device.

## 6. Risks

1. **A device that is slow but not stalled.** A step of more than 30 s ends as a stall. Nothing
   of the kind has been seen in reads; the slowest waits measured are mounts, which keep their
   own limits.
2. **The speed of reads in chunks.** `load_contents` reads in its own way; chunks of 256 KiB
   under `_wait` (a main context and a timer a chunk) may be faster or slower. To measure on a
   device against today's 30 activities in 7.6–8.0 s; the chunk size can change.
3. **gvfs stays blocked.** A cancel ends only our wait; the backend of gvfs-mtp holds its mutex
   until the device is unplugged. That is why the advice is to unplug it, and why nothing is
   tried automatically: mounting the device again, as for a file read cut short, would wait on
   the same mutex (seen: a try every 32 s or so, each giving up after 30 s, until the device was
   unplugged).
4. **Writes after a stall** fail at once (fast failure). A write that stalls before any read has
   no limit yet (D1).
5. **The GTK thread.** `_wait` on the window's main thread would run a nested loop of the
   default context. The window reads the device only in its tasks today (its four reads in
   `gui/` run in background tasks); a new read in the window must stay so.
6. **The fake and the real gvfs.** Portions of a listing and chunks of a stream come from a fake
   of Gio in the tests; a listing of a large folder and a read of a large file are to be
   checked on a device.
7. **One main context for a listing.** gvfs gives the entries of a listing to its enumerator in
   the main context where the listing began (`client/gdaemonfileenumerator.c`: its D-Bus object
   is exported there, and `next_files_async` gets the entries through it). In a worker thread
   `_wait` makes a context of its own for each wait, so a portion waited for on a new context
   would never come and every listing would reach the limit. The steps of one listing therefore
   wait on one context (`_steps_context`); the fake gives portions only in that context, so a
   test fails if they do not. A listing that stalled is not closed: closing it would wait on the
   same blocked device; the enumerator is dropped.

## 7. Order of work

Each step starts with a test that fails on the code before it, keeps its texts and their Polish
in the same commit, and passes the usual gate before its commit: ruff without findings, the tests
with and without a display, and the program's folders unchanged by the tests. Each step waits for
a yes. The fake of Gio (`tests/gio_fake.py`: `GioOp`, `answer_as_gio`) gets asynchronous
listings in portions, streams read in chunks, queries and filesystem queries, each able to
answer late or never.

1. **Listings and queries under `_wait`, and the error.** Failing tests:
   - a listing in several portions gives every entry, as today, in the main thread and in a
     worker (every portion waited for on the context the listing began in);
   - a listing slower in all than the limit, each portion in time, ends well;
   - a step of a listing (opening it, a portion, closing it) with no answer:
     `DeviceNotResponding` at the limit (a short limit in the test), whatever the answer to the
     cancel; a listing that stalled is not closed;
   - `query_info` with no answer: the same; a file that is not there still gives None;
   - the free space with no answer: the same;
   - another error keeps today's words ("Cannot list …", "Cannot read …");
   - its words in English and Polish (`replug_text` does not add the advice twice) (D5);
   - it goes past `resolve`, `sizes`, `_remount`, `_device_state` and `refresh` (D6), and a
     write cleans nothing up after it (D7).

   A guard that passes before and after: a folder on the disk read through the real Gio (the
   calls as Gio takes them).
2. **Reads in chunks under `_wait`.** Failing tests:
   - a file of 0 B, of less than a chunk, of exactly two chunks and of several reads whole;
   - a read slow but steady, longer in all than the limit, ends well;
   - a chunk with no answer: `DeviceNotResponding`;
   - `read_start` reads its count only, and stops at a stall.
3. **Fast failure, the sync and the backup.** Failing tests:
   - after a stall the next operation of the same storage fails at once, a write too; a new
     storage works;
   - a sync stops with the message, what it uploaded before stays done;
   - a backup stops and leaves no partial folder;
   - the command line says it once and ends with exit code 1.

   To solve here: the 25 handlers left from step 1 (section 5); and `open_device_storage` with
   waiting, as the command line opens a device (unless `--no-wait`). A device that stalls while
   it is opened (its first listing, the look for `GarminDevice.xml`) is a `DeviceError` to its
   waiting loop, which opens it again, each try waiting 35 s for the same blocked device, until
   its time for waiting is over; then, the device being on USB, it adds the advice that another
   program may hold the device. The command line must stop at the first stall and say only
   that the device stopped responding.
4. **Log lines.** Failing tests:
   - a stall logs what it was and the times since the last answer and since opening, without
     a path or a name;
   - a step of more than 5 s logs one line; quick steps log nothing new.
5. **The window (D4).** Failing tests:
   - after a stall in a task the banner says it, and no refresh of that device starts while it
     stays at its place on USB;
   - once the place is gone the banner goes and the device is detected as usual;
   - a mount that reaches its limit with no stall before it keeps today's behaviour;
   - the banner's text wraps in the narrowest window.

   To solve here: the window opens a device through `open_device_storage` too, without
   waiting: one try each time, with no advice about another program, but each detection of
   the window opens the device again, and each such try waits 35 s on its first listing. After
   a stall no detection may open that device at its place on USB (D4), and nothing the window
   says may add the advice about another program.
6. **Documentation**: `docs/guide.md`, the status of this design.

On a device: the speed of reads in chunks against today's, and a listing of a large folder. A
stall cannot be made on purpose; the log lines of step 4 show when it has happened.

## 8. Size

About 250–350 lines of code (gio_storage about 180 for the six operations, fast failure and the
log lines; storage about 15; sync and backup about 10; the window about 60), about 450–550 lines
of tests with the fake of Gio, three texts with their Polish (the error, the action of the free
space, the banner), and 6 commits, one a step of section 7.
