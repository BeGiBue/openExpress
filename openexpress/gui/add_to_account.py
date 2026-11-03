"""Add to Account… (experimental): a device the account's list does not hold added to the account
the window is logged in to (service.add_device), after a question that names the device and the
account; offered by the banner of the device view and by a row of the Device page. The account
is named as the window names it elsewhere, its e-mail address whole.

Has: no attribute of the window; the task keeps what it needs in its closures."""

from __future__ import annotations

import logging

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, GLib  # noqa: E402 - imports must follow gi.require_version

from openexpress import service  # noqa: E402
from openexpress.connect import NotAccountDevice, OtherOwner, RegistrationRefused  # noqa: E402
from openexpress.gui.navigation import Cause  # noqa: E402
from openexpress.gui.window_tasks import Answer, confirm, inform  # noqa: E402
from openexpress.i18n import _  # noqa: E402

log = logging.getLogger(__name__)


def offers_adding(s) -> bool:
    """Whether the window offers Add to Account…: a device the account's list does not hold
    (not a list that could not be read), while logged in, and not a USB drive openExpress
    does not sync."""
    return (s is not None and s.logged_in and isinstance(s.ownership_error, NotAccountDevice)
            and getattr(s, "drive_refusal", None) is None)


def _account(s) -> str:
    return s.client.auth.display


def _model(s) -> str:
    from openexpress.gui.device_page import device_name

    return device_name(s)


def add_to_account_row(win, s) -> Adw.ActionRow:
    """The row "On the account" of the group of the account on the Device page, with Add to
    Account…, for a device offers_adding allows."""
    row = Adw.ActionRow(title=_("On the account"), subtitle=GLib.markup_escape_text(
        _("Not on the account {account}").format(account=_account(s))))
    row.add_suffix(win._button(_("Add to Account…"),
                               lambda button: confirm_add_to_account(win, button),
                               with_button=True))
    return row


def confirm_add_to_account(win, button=None) -> None:
    """The question before adding the open device to the account; once Add to Account is
    chosen, the task runs from `button` (the row's), which spins meanwhile."""
    s = win.session
    if not offers_adding(s):
        return
    confirm(win, "add-to-account",
            _("Add {model} to your Garmin account?").format(model=_model(s)),
            _("openExpress sends Garmin the description of the device (its GarminDevice.xml, "
              "with its unit ID) and adds it to the account {account} as an active device. "
              "Then a sync uploads its activities and health data to this account.\n\n"
              "If the device is paired with the Garmin Connect app on a phone, check first "
              "that the app uses the same account. A device can be removed from an account "
              "only in Garmin Connect.\n\n"
              "This is an experimental feature.").format(account=_account(s)),
            Answer("add", _("Add to Account"), lambda: add_to_account(win, button),
                   look="suggested"),
            default="cancel")


def add_to_account(win, button=None) -> None:
    """Adds the open device to the account (service.add_device, an account task: the device
    is not touched), then says what came of it; the device is checked again, as by
    Refresh, unless Garmin refused it."""
    s = win.session
    if not offers_adding(s):
        return
    account, model = _account(s), _model(s)

    def done(result: service.DeviceAddition) -> None:
        if result.already:
            win.toast(_("{model} is on the account {account} already").format(
                model=model, account=account))
        elif result.listed is False:
            inform(win, "added-not-listed",
                   _("Garmin accepted the device, but the account's list does not show it yet"),
                   _("Refresh in a few minutes. If it is still missing, check the devices of "
                     "your account in Garmin Connect."))
        elif result.listed is None:
            inform(win, "added-not-checked", _("Garmin accepted the device"),
                   _("The account's list could not be read to check it. Refresh in a few "
                     "minutes; if the device is still refused, check the devices of your "
                     "account in Garmin Connect."))
        else:
            win.toast(_("{model} added to the account {account}").format(
                model=model, account=account))
        if win.session is s:
            win.refresh_device(cause=Cause.REFRESH_IN_VIEW)

    def refused(e) -> bool:
        if isinstance(e, OtherOwner):
            heading = (_("Another Garmin account has a subscription on this device")
                       if e.subscription else _("This device is on another Garmin account"))
        elif isinstance(e, RegistrationRefused):
            heading = _("This device was not added")
        else:
            return False  # the window's usual error
        inform(win, "add-to-account-refused", heading, str(e))
        return True

    win.run_task(_("Adding to the account {account}…").format(account=account),
                 lambda: service.add_device(s.client, s.device, apply=True), done, refused,
                 device=False, button=button)
