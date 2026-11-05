# Design: adding a device to the Garmin account

Status: implemented, steps 1 to 5 of section 7; the first attempt on a device succeeded (a
Venu 2, section 9.1); "experimental" stays until a second attempt succeeds, by another user
(4.7). Each decision of section 5 took its recommended option, marked "chosen", D3a with one
change: the window names the account as it does elsewhere (its user name, else its whole e-mail
address), the command line masks the account's name, its user name as well as an e-mail
address, since its output is pasted into reports (and so do its other commands).
The feature is marked experimental (section 4.7). One detail differs from 4.3 as first written:
the row "On the Account" is shown only for a device off the account, so a device added loses it
(its group then shows what any device of the account shows).

## 1. Scope

openExpress uses a device with Garmin Connect (sync, Connect IQ apps, the primary training
device) only when the account it is logged in to lists that device; otherwise it refuses, says
why, and changes nothing. A device the account does not list can today be added only elsewhere:
the Garmin Connect app on a phone, or Garmin Express on another computer. This design adds it to
openExpress:

1. **On request only**: a button in the window and a command, never on its own (D1).
2. **After a question** that names the device, the account and what follows (D3).
3. **One request** that adds the device, as Garmin Express makes it, and a second only for a
   device Garmin keeps as retired (D2, D6); then the account's list read anew decides whether it
   worked (D7).
4. **What Garmin refuses**, said plainly: a device on another account, with an active
   subscription of another account, a description Garmin does not accept, a device Garmin does
   not allow (D5).
5. **Marked experimental**, in the window and on the command line (4.7).

Not in the scope: everything else Garmin Express does when it adds a device (section 2), namely
writing the device's own Garmin Connect credentials, the user's profile, e-mail address or phone
number to the device, its nickname, Wi-Fi, time zone and preferred activity tracker (D4, D10);
comparing the account's GUID with the one the device keeps, and deleting files on a device that
was paired with another account (D5); removing a device from an account (only Garmin Connect
does).

An example of the case it solves: a fēnix 5X registered only as a product on garmin.com, not in
Garmin Connect ([#27](https://github.com/TomaszBojanowski/openExpress/issues/27)). The account's
list did not hold it, so openExpress refused it; once it was added in Garmin Connect, a sync
worked. With this feature it is added from openExpress, after the question.

## 2. What Garmin Express does

From the analysis of Garmin Express (Windows 7.29.1.0, macOS 7.29.3.0): facts about its use of
the servers, written down without its code.

**After every sign-in, for the device it signs in for**, in this order:

1. The ticket of the sign-in page exchanged for the account's token; the account's profile.
2. The privacy consents of Garmin Connect (and golf); none given: the token is dropped.
3. On an MTP device: the account's GUID compared with the one the device keeps (an MTP
   operation of Garmin's). A device paired with another account: the user is asked, and the
   device's files may be deleted.
4. **The registration**: `POST device-service/deviceregistration/device` on the Connect API
   host, the device's whole `GarminDevice.xml` as the body (`Content-Type: application/xml`),
   with the header `Override: 1` ("add as active") for devices that track activity
   (`Override: 2` means "add as inactive").
   - 409: the device belongs to another account; Express may offer a factory reset and try
     again, three times at most. 409 with `error.subcode` 4091: another account has an active
     subscription on it; Express stops.
   - 400: the description is not accepted (bad XML, no UDI); 403: registration not allowed.
   - 2xx: JSON with `unitId`, `displayName`, `partNumber`, `newRegistration`, `deviceStatus`
     and the device's own OAuth credentials (`consumer`, `secret`, `oAuthToken`,
     `oAuthTokenSecret`).
   - `deviceStatus` "retired": `PUT device-service/deviceregistration/device/status/{unitId}`
     with `{"deviceStatus":"active"}`.
5. The account's settings; the user's physiological profile, e-mail address, phone number and
   user name written to the device's settings.
6. The device's OAuth credentials written to the device (an encrypted settings file, or its
   Wi-Fi file), with which the device later uploads by itself over Wi-Fi.
7. For new accounts and Wi-Fi scales, the time zone; then the primary training device and the
   preferred activity tracker (a question "Do you want this to be your Preferred Activity
   Tracker?").
8. Any error in the chain: the device's token is dropped.

On macOS the same steps are a wizard: nickname, registration (e-mail, privacy consent), account
(Sign In / Create an Account), Wi-Fi, the device's settings, the Connect profile, a first sync,
and "Setup complete! This device is now registered to" the account.

**Garmin Express never reads the account's list** (`device-service/deviceregistration/devices`):
it learns the account's devices from `express-gateway/device-info/primary-training-device`
(`RegisteredDevices`), and whether a device is the account's from the registration's answer.
openExpress asks the list before every account operation and adds nothing; the registration is
the one request it has never made.

## 3. What openExpress has

- `service.require_account_device`: the list asked (kept five minutes, asked anew before a write
  or an upload, forgotten at every sign-in and sign-out); a device not on it raises
  `NotAccountDevice`, whose message says to sign in to the account the device belongs to, to add
  it in Garmin Connect, and to check that the phone's Garmin Connect app uses the same account;
  the log tells what the list holds (part numbers, states, how the unit IDs compare, the
  environment), never a unit ID.
- The window (before this feature): the banner "This device is not registered to your Garmin account" (no button), Sync
  off, the Apps page and the primary training device "Not available".
- The command line: account commands end with code 1 and the same message.

**The branch `dodaj-do-konta` and a stash on it** hold an earlier start of this feature, made on
a version of the program long before the present one:

- on the branch, one commit: `GarminClient.register_device(device_xml, unit_id)` with `Override:
  2` (inactive); 409, 400 and 403 as refusals (`OtherOwner`, `RegistrationRefused`); any 2xx as
  accepted; the answer's `unitId` compared with the device's; only `newRegistration` and
  `deviceStatus` kept (`Registration`), never the body (it carries the device's credentials),
  not even in an error; tests on a recorded session;
- in the stash: `service.add_device` (the list first; a dry run stops there; the request; the list
  again, which tells the result), the command `openexpress device add [--apply]` with the text of
  its dry run, and its tests.

Since then the program has changed where this code lands: errors for the user derive from
`errors.UserFacingError`, the account's answers go through `answers.ANSWERS`, the window's
questions through `confirm()`, the log through `applog`, and the translations moved on. D11
decides what becomes of the branch and the stash.

## 4. The window and the command line

The mockups are drawn from libadwaita widgets with a made-up device and account, wide (1000 px)
and narrow (360 px), light and dark, in Polish; the texts are in 4.4.

### 4.1 Where it is offered

Only for a device the account's list does not hold (`NotAccountDevice`, not a list that could
not be read), while logged in, and for a device that syncs (MTP, or a USB drive whose
`GarminDevice.xml` declares what it uploads; not a Varia, which Garmin Express does not register
either):

- the banner gets the button **Add to Account…**;
- the Device page gets a group **Garmin account**: the row "On the Account" – "Not on the account
  {account}" with the same button, above "Primary Training Device".

### 4.2 The question and the work

**Add to Account…** asks (`confirm()`, Cancel by default, Escape and closing are Cancel):

> **Add fēnix 5X to your Garmin account?**
> openExpress sends Garmin the description of the device (its GarminDevice.xml, with its unit
> ID) and adds it to the account {account} as an active device. Then a sync uploads its
> activities and health data to this account.
>
> If the device is paired with the Garmin Connect app on a phone, check first that the app uses
> the same account. A device can be removed from an account only in Garmin Connect.
>
> Cancel · **Add to Account**

{account} is the name the window already shows for the account (Preferences, "Logged in as"):
its user name, else its e-mail address. The command line masks it: a user name as `t…b`, an
e-mail address as `t…@b…` (D3). The question ends with "This is an experimental feature."
(4.7).

Then, as a task with the button busy (`run_task`), "Adding to the Account {account}…" in the
row: the list asked anew (the device may have been added meanwhile: then nothing is sent), the
request, the status changed for a retired device (D6), the list asked anew.

### 4.3 The outcomes

- **Added**: the toast "Added to your Garmin account" (one line, at 360 px too; the account is
  on the page); the device checked again, so
  the banner and the row "On the Account" go, Sync, Apps and the primary training device come
  back. Nothing is synced by itself.
- **Already on the account** (the list read before the request holds it): the same, without a
  request.
- **On another account (409)**: `inform()` "Device on Another Account": "Garmin
  refused: the device is registered to another account. If it is your other account, log in to
  it in openExpress. If it was someone else's, they have to remove it from their account in
  Garmin Connect; then add it here. Nothing was changed." The row: "On another Garmin account".
- **Another account's subscription (409, subcode 4091)**: "Subscription on Another Account":
  "…another Garmin account has an active subscription on this device; its owner has to end it
  first. Nothing was changed."
- **Not accepted (400)**, **not allowed (403)**: "Garmin did not accept the description of this
  device" / "Garmin does not allow adding this device to an account"; "Nothing was changed".
  A 403 with the computer's clock off: the clock's usual message.
- **Accepted, not on the list yet**: "Device Not Listed Yet": "Garmin accepted the device, but the
  account's list does not show it yet. Refresh in a few minutes; if it is still missing, check
  the account's devices in Garmin Connect."
- **Network error or no answer**: whether Garmin added it is not known; the list is asked again
  on Refresh, the request is never repeated by itself.

### 4.4 Texts (English, Polish)

| English | Polish |
|---|---|
| Add to Account… / Add to Account | Dodaj do konta… / Dodaj do konta |
| Garmin account / On the account | Konto Garmin / Na koncie |
| Not on the account {account} / Yes, on the account {account} | Nie ma go na koncie {account} / Tak, na koncie {account} |
| Adding to the account {account}… | Dodawanie do konta {account}… |
| Add {model} to your Garmin account? | Dodać {model} do konta Garmin? |
| (the body of 4.2) | openExpress wyśle do Garmina opis urządzenia (plik GarminDevice.xml z jego numerem Unit ID) i doda je do konta {account} jako aktywne. Potem synchronizacja wyśle na to konto jego aktywności i dane o zdrowiu. … |
| Added to your Garmin account / On your Garmin account already | Dodano do konta Garmin / Już na koncie Garmin |
| This device is on another Garmin account | To urządzenie jest na innym koncie Garmin |
| On another Garmin account | Na innym koncie Garmin |
| Garmin did not accept the description of this device | Garmin nie przyjął opisu tego urządzenia |
| Garmin does not allow adding this device to an account | Garmin nie pozwala dodać tego urządzenia do konta |
| Nothing was changed. | Nic nie zmieniono. |
| Garmin accepted the device, but the account's list does not show it yet. … | Garmin przyjął urządzenie, ale lista konta go jeszcze nie pokazuje. … |

### 4.5 The command line

`openexpress register` (D9), a trial run without `--apply`, as every command that changes
something:

```
$ openexpress register
fenix 5x (006-B2604-00, software 19.10) is not on the Garmin account t…b.
Would add it as an active device: POST connectapi.garmin.com/device-service/deviceregistration/device
with its GarminDevice.xml (2.1 KB; it holds the device's unit ID).
After that, a sync uploads its activities and health data to this account.
A device can be removed from an account only in Garmin Connect.
Dry run. Add --apply.
$ openexpress register --apply
Added fenix 5x to the Garmin account t…b.
```

A device on the account already: "fenix 5x is on the Garmin account t…b already." (code 0,
nothing sent). Refusals: the texts of 4.3, code 1. No new exit code. An account named by an
e-mail address shows as `t…@b…`; every command shows the account masked so.

### 4.6 How the request introduces itself

As every request of openExpress to the Garmin Connect API: signed (OAuth1) with Garmin Express's
application key, which the user's own copy of its installer gives at setup, and the account's
token; with the client headers of Garmin Express (`Garmin-Client-Name`, `-Version`, `-Platform`,
`-Platform-Version`, `-SessionId`, `X-garmin-client-id`), as for every other request; and with
openExpress's own User-Agent, `openexpress/<version> (Linux)`, the one every request of the
program sends. The body is the device's `GarminDevice.xml`, with `Override: 1`, as Garmin Express
sends it. Garmin Express's own client sends there the default User-Agent of its HTTP library,
known from the analysis only, not from its traffic: openExpress does not imitate it. Garmin
accepted the first attempt (section 9.1) with openExpress's own User-Agent.

### 4.7 Experimental

Adding a device is the first request of openExpress that Garmin's servers answer with a change
to the account's devices. A first device has been added this way (section 9.1); until a second
attempt succeeds, by a user other than the one of the first, on another account, the feature
says it is experimental: the question ends
with "This is an experimental feature.", the command's help reads "add the connected device to
your Garmin account (experimental; trial run without --apply)", its trial run ends with
"Experimental.", and the documentation calls it experimental.

## 5. Decisions

### D1: when a device is added — chosen: 1a

- **1a. Only when asked (recommended; chosen):** the button of 4.1 or `register --apply`; nothing at
  sign-in or when a device is plugged in.
  - \+ Writing to the account stays a choice made each time, as every other write of openExpress.
  - − One click more than Garmin Express, which registers at every sign-in.
- **1b. At sign-in, as Garmin Express.**
  - − The account changes without a question; a device of someone else, plugged in once, would
    be tried on the user's account (Garmin refuses it only if it is on another account).

### D2: active or inactive — chosen: 2a

- **2a. Active, `Override: 1` (recommended; chosen):** as Garmin Express adds a device that tracks
  activity, and as the phone app leaves a paired device.
  - \+ The state the device is known to sync in.
  - − Whether an active second device changes how Garmin Connect counts steps or which device it
    prefers is Garmin's rule; openExpress changes neither the primary training device nor the
    preferred activity tracker (D10).
- **2b. Inactive, `Override: 2`** (what the branch of section 3 chose).
  - \+ The least change to the account.
  - − What an inactive device may upload is not known; the device could be on the account and
    still not serve its purpose.
- **2c. No header** (the server's default, not known).

### D3: the question — chosen: 3a

- **3a. The device, the account, what is sent and what follows (recommended; chosen):** the text of
  4.2; the account named as the window names it; on the command line its name only masked
  (user name and e-mail address), since its output is pasted into reports.
  - \+ The account named is the check that the device goes where the user means; the advice
    about the phone's app catches the commonest mistake (two accounts) before a request.
- **3b. A short question** ("Add this device to your account?").
  - − Says neither where nor what follows.

### D4: the device's credentials in the answer — chosen: 4a

- **4a. Never kept, logged or written to the device (recommended; chosen):** only `newRegistration` and
  `deviceStatus` are read; the body is not kept, not even in an error or the log.
  - \+ Nothing new to protect; the device keeps uploading as before (through the phone's app,
    its Wi-Fi as set up there, or openExpress).
  - − A device that uploads by itself over Wi-Fi only with credentials written by Garmin Express
    gets none from openExpress.
- **4b. Written to the device as Garmin Express does.**
  - − An encrypted file of the device's whose format openExpress does not have and, by its
    clean-room rule, does not reconstruct.

### D5: a device on another account — chosen: 5a

- **5a. Refused, explained, nothing more (recommended; chosen):** 409 and 4091 as in 4.3; no GUID
  comparison, no factory reset, no deleting of files, no second try.
  - \+ openExpress never deletes on a device; the owner of the other account decides.
- **5b. As Garmin Express: offer a factory reset and try again.**
  - − A destructive step on a device that may be someone else's.

### D6: a device Garmin keeps as retired — chosen: 6a

- **6a. Made active, as Garmin Express does, within the same question (recommended; chosen):** the
  answer says `retired`: one `PUT …/device/status/{unitId}` `{"deviceStatus":"active"}`; the
  question said "as an active device", so no second question. The log says it.
  - \+ A device the account kept from before (and may not list while retired) becomes usable.
- **6b. Said, left to Garmin Connect.**
  - − The device stays unusable in openExpress until the user finds the setting there.

### D7: what says it worked — chosen: 7a

- **7a. The list asked anew (recommended; chosen):** before the request (already on it: nothing sent)
  and after it; the answer's `unitId`, when it gives one, must be the device's (else an error,
  nothing more sent). The device's check is then run as after Refresh.
  - \+ The same test that refused the device decides that it may be used.

### D8: where the window offers it — chosen: 8a

- **8a. The banner's button and a row of the Device page (recommended; chosen):** 4.1.
  - \+ Where the refusal is said, and where the device's account is described.
- **8b. The banner only.**
  - − Gone once the banner is closed.

### D9: the command's name — chosen: 9a

- **9a. `openexpress register [--apply]` (recommended; chosen):** the word of the message that refuses
  ("not registered to your Garmin account").
- **9b. `openexpress device add`** (the stash): a command `device` next to `devices`, which lists
  the devices this installation has seen: two commands one letter apart.
- **9c. `openexpress account add`:** a new command `account` for one action.

### D10: the rest of Garmin Express's chain — chosen: 10a

- **10a. Not done (recommended; chosen):** no profile, e-mail, phone, nickname, Wi-Fi or time zone written,
  no preferred activity tracker set; after adding, the row "Primary Training Device" offers Set
  as Primary as for any device of the account.
  - \+ Each of them is a change of its own, on the device or the account, with its own question
    where openExpress has it already.

### D11: the branch `dodaj-do-konta` and its stash — chosen: 11a

- **11a. Written anew on the present code, the branch and the stash read as its first draft
  (recommended; chosen):** the request (`register_device`), its errors, `Registration` and their tests
  taken over by hand into the present modules; the stash's `add_device` and its dry-run text
  likewise. When the feature is in, the stash is kept as a patch file with the private notes,
  and the user drops it and deletes the branch (openExpress's work does not touch them).
  - \+ The decisions above (active, retired, the question) differ from the branch's; the code
    lands where today's rules want it.
- **11b. The branch rebased and the stash applied.**
  - − Conflicts in every file they touch (the translations above all), and the old choices
    (inactive) carried along.
- **11c. Left as they are.**

## 6. What can go wrong, and how it is found

| What | How it is prevented, and found |
|---|---|
| A device added to the wrong account | the question names the account; the advice about the phone's app; Garmin refuses a device of another account (409) |
| Someone else's device added | it must be plugged in and the question accepted; on another account Garmin refuses |
| The device's credentials leak | the body never kept nor logged; a test that a made-up answer's credentials appear in no log, error or file |
| Two requests | one request a click, the button busy meanwhile, the device's writes locked (`WRITING`); never repeated by itself |
| Garmin accepts, the list lacks it | said (4.3); the list asked again on Refresh |
| Retired | made active (D6); a test with a made-up answer |
| An answer naming another device | an error, nothing more sent |
| No network, or no answer | not known whether it was added: the list on Refresh says |
| The China environment | the request goes to the host of the environment set (`setup --environment`), as every request |
| The tests | no network: the request on a recorded session only |

## 7. Steps

Each step starts with tests that fail on the code before it, keeps its texts and their Polish in
the same commit, and passes the usual checks (ruff, the tests with and without a display, the
program's folders unchanged by the tests). Each waits for acceptance.

1. **The request** (`connect.register_device`, `set_device_active`): from the branch, with
   `Override: 1`, 4091, the errors as `UserFacingError`; tests: the request's form (path, body,
   headers), each answer, the body never kept.
2. **Adding** (`service.add_device`): the list before, a trial run, the request, retired made
   active, the list after; the log's lines (part number, environment, outcome; no unit ID).
3. **The command** `register`: its trial run and its outcomes; `docs/cli.md`.
4. **The window**: the banner's button, the group of the Device page, the question, the task, the
   outcomes; the narrow window.
5. **The documents**: `docs/guide.md`, `docs/privacy.md` (what is sent, what is not kept),
   `docs/troubleshooting.md` (a device not on the account).
6. **On a device**: section 9.

## 8. Size

About 350 lines of code (the request 90, adding 70, the command 60, the window 130), about 600
lines of tests, about 25 texts with their Polish; 5 commits.

## 9. The first attempt on a device

The tests answer as Garmin's servers would, from the analysis; the first real request is the
proof. It is made once, by hand, with the log kept:

- **Who:** a tester whose device the account does not list and who asks for it (a reporter of
  such a refusal), or the maintainer with a device off the account, each time with that
  person's agreement for that account. Never a device of someone else's account.
- **Before:** `openexpress register` (the trial run) shows the device, the account and what is
  sent; the log has the line "account: the device (…) is not among the N devices of the account
  (…)", which says what the list holds.
- **The request:** `openexpress register --apply`, or Add to Account… in the window; then
  `openexpress report --log`.
- **What says it worked**, in the log, in this order: "register: … sent as an active device"
  with the part number, the size of the description and the environment; "HTTP POST
  …/deviceregistration/device -> 200"; "register: Garmin added it (new registration: …,
  status: …)"; for a retired device "register: … made active"; "register: on the account's list
  after adding it: yes"; and no line "account: the device (…) is not among …" after it. Then
  `openexpress sync` (a trial run) passes the account's check.
- **What says it did not:** a 409 ("on another Garmin account"), 400 or 403 with "Nothing was
  changed"; or "on the account's list after adding it: no", which waits a few minutes and a
  Refresh before anything else is tried.
- **Then:** the device in Garmin Connect's list of devices, as active; `docs/devices.md` and the
  README say what was checked; the word "experimental" stays until a second attempt succeeds,
  by another user on another account.

### 9.1 The first attempt

A Venu 2 not on the account was added from the window (Add to Account… on the banner, then the
question's Add to Account): Garmin's server answered 200 to the registration, with openExpress's
own User-Agent (4.6), and the device was on the account's list after it, as active. Nothing was
synced afterwards, and the account's primary devices were not changed.
