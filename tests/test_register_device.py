"""Adding a device to the account: one request, as an active device, and nothing of the answer
kept but whether it worked; a device Garmin keeps as retired made active. All IDs, keys and
tokens here are made up."""

import email.utils
import json
import logging
import time

import pytest
import requests
from fakes import DEVICE_UNIT, OTHER_UNIT, make_client, response

from openexpress.connect import (
    REGISTER_PATH,
    ApiError,
    ClockSkew,
    DeviceNotVerified,
    OtherOwner,
    Registration,
    RegistrationRefused,
    Unauthorized,
)

UNIT = DEVICE_UNIT
STATUS_PATH = f"device-service/deviceregistration/device/status/{UNIT}"
XML = b'<?xml version="1.0"?><Device><Id>1234567890</Id><Model>made up</Model></Device>'
# What Garmin sends back, with the device's own credentials in it.
SECRETS = ("ConsumerKey9f8e", "ConsumerSecret7d6c", "OauthToken5b4a", "OauthTokenSecret3928")
ANSWER = {"unitId": UNIT, "displayName": "made up", "newRegistration": True,
          "deviceStatus": "active", "registrationID": "RegistrationId1716",
          "consumer": SECRETS[0], "secret": SECRETS[1], "oAuthToken": SECRETS[2],
          "oAuthTokenSecret": SECRETS[3]}


def client_answering(answer, status_answer=None, **kw):
    """A client whose Garmin answers the registration (POST) with `answer` and a change of
    status (PUT) with `status_answer`; what it was sent, in `sent`."""
    client = make_client(**kw)
    sent = []

    def handler(method, request):
        sent.append({"method": method, "headers": request.get("headers") or {},
                     "data": request.get("data")})
        if method == "GET":
            return None  # the account's list (its path holds the registration's)
        reply = answer if method == "POST" else status_answer
        if isinstance(reply, Exception):
            raise reply
        return reply if reply is not None else response(404, b"")

    client.http.handlers[REGISTER_PATH] = handler
    return client, sent


def test_the_request_adds_the_device_as_active_without_a_verified_unit_id():
    client, sent = client_answering(response(body=ANSWER))
    assert client.verified_unit_id is None  # the account does not list the device yet
    assert client.register_device(XML, UNIT) == Registration(True, "active")
    assert len(sent) == 1 and client.http.paths() == [REGISTER_PATH]
    request = sent[0]
    assert request["method"] == "POST" and request["data"] == XML  # the file, byte for byte
    headers = request["headers"]
    assert headers["Content-Type"] == "application/xml" and headers["Override"] == "1"
    assert headers["Accept"] == "application/json"
    assert headers["Authorization"].startswith("OAuth ") and 'oauth_token="t"' in headers[
        "Authorization"]  # signed with the account's token
    # Adding the device does not verify it: other account requests for it are still refused.
    assert client.verified_unit_id is None
    with pytest.raises(DeviceNotVerified):
        client.device_messages(UNIT)
    assert len(client.http.sent) == 1


def test_the_request_goes_to_the_environment_set():
    client, _sent = client_answering(response(body=ANSWER))
    client.settings.environment = "china"
    client.register_device(XML, UNIT)
    assert client.http.sent[0]["url"].startswith("https://connectapi.garmin.cn/")


def test_the_device_credentials_in_the_answer_are_not_kept_or_logged(caplog):
    client, _sent = client_answering(response(body=ANSWER))
    with caplog.at_level(logging.DEBUG):
        result = client.register_device(XML, UNIT)
    kept = repr(result) + repr(vars(result)) + repr(vars(client)) + caplog.text
    for secret in (*SECRETS, "RegistrationId1716"):
        assert secret not in kept
    assert "deviceregistration/device -> 200" in caplog.text


@pytest.mark.parametrize("body, content_type", [
    ((b"<RegisterDeviceResponse><consumer>ConsumerKey9f8e</consumer>"
      b"<secret>ConsumerSecret7d6c</secret></RegisterDeviceResponse>"), "application/xml"),
    (json.dumps([ANSWER]).encode(), "application/json"),  # not an object
    (b"", None),
    (b"{not json", "application/json"),
])
def test_an_answer_that_cannot_be_read_still_means_accepted(body, content_type, caplog):
    answer = response(body=body)
    if content_type:
        answer.headers["Content-Type"] = content_type
    client, sent = client_answering(answer)
    with caplog.at_level(logging.DEBUG):
        assert client.register_device(XML, UNIT) == Registration(None, "")
    assert len(sent) == 1
    said = f"accepted, the answer not understood ({content_type or 'no content type'}, "
    assert said in caplog.text and f"{len(body)} B)" in caplog.text
    for secret in (*SECRETS, "RegistrationId1716"):
        assert secret not in caplog.text


def test_an_answer_about_another_device_asks_to_check_the_account():
    client, sent = client_answering(response(body={**ANSWER, "unitId": OTHER_UNIT}))
    with pytest.raises(ApiError, match="Check the devices of your account") as e:
        client.register_device(XML, UNIT)
    assert len(sent) == 1 and e.value.body == ""
    assert "Nothing was changed" not in str(e.value)
    assert not any(secret in str(e.value) for secret in SECRETS)


def test_an_answer_without_the_optional_fields_is_accepted():
    client, _sent = client_answering(response(body={}))
    assert client.register_device(XML, UNIT) == Registration(None, "")


def test_another_accounts_device_is_refused_once():
    client, sent = client_answering(response(409, {"error": {"code": 409}}))
    with pytest.raises(OtherOwner, match="registered to another Garmin account") as e:
        client.register_device(XML, UNIT)
    assert len(sent) == 1 and e.value.status == 409 and isinstance(e.value, RegistrationRefused)
    assert not e.value.subscription and "Nothing was changed." in str(e.value)
    assert e.value.body == ""


def test_another_accounts_subscription_is_said_as_such():
    client, sent = client_answering(response(409, {"error": {"code": 409, "subcode": 4091}}))
    with pytest.raises(OtherOwner, match="active subscription") as e:
        client.register_device(XML, UNIT)
    assert len(sent) == 1 and e.value.subscription and "Nothing was changed." in str(e.value)


@pytest.mark.parametrize("status, text", [
    (400, "did not accept the description of this device"),
    (403, "does not allow adding this device"),
])
def test_a_refusal_says_why_and_that_nothing_changed(status, text):
    client, sent = client_answering(response(status, {"error": "made up"}))
    with pytest.raises(RegistrationRefused, match=text) as e:
        client.register_device(XML, UNIT)
    assert len(sent) == 1 and "Nothing was changed." in str(e.value)
    assert not isinstance(e.value, OtherOwner) and e.value.body == ""


def test_a_403_from_a_wrong_clock_is_told_as_such():
    answer = response(403, b"")
    answer.headers["Date"] = email.utils.formatdate(time.time() - 3 * 3600, usegmt=True)
    client, _sent = client_answering(answer)
    with pytest.raises(ClockSkew):
        client.register_device(XML, UNIT)


@pytest.mark.parametrize("status, error", [(401, Unauthorized), (500, ApiError)])
def test_other_errors_are_the_usual_ones_without_the_body(status, error):
    client, sent = client_answering(response(status, {"consumer": SECRETS[0]}))
    with pytest.raises(error) as e:
        client.register_device(XML, UNIT)
    assert len(sent) == 1 and e.value.body == "" and SECRETS[0] not in str(e.value)


def test_no_network_is_an_error_and_is_not_tried_again():
    client, sent = client_answering(requests.ConnectionError("made up"))
    with pytest.raises(ApiError, match="network error"):
        client.register_device(XML, UNIT)
    assert len(sent) == 1


def test_nothing_is_sent_without_a_login():
    client, sent = client_answering(response(body=ANSWER), auth=False)
    with pytest.raises(Unauthorized):
        client.register_device(XML, UNIT)
    assert sent == [] and client.http.sent == []


# --- a retired device made active ----------------------------------------------------------


def test_a_device_this_client_added_is_made_active(caplog):
    retired = {**ANSWER, "deviceStatus": "retired", "newRegistration": False}
    client, sent = client_answering(response(body=retired), response(204, b""))
    assert client.register_device(XML, UNIT) == Registration(False, "retired")
    with caplog.at_level(logging.DEBUG):
        client.set_device_active(UNIT)
    assert [s["method"] for s in sent] == ["POST", "PUT"]
    assert client.http.paths()[-1] == STATUS_PATH
    put = sent[1]
    assert json.loads(put["data"]) == {"deviceStatus": "active"}
    assert put["headers"]["Content-Type"] == "application/json"
    assert put["headers"]["Authorization"].startswith("OAuth ")
    assert str(UNIT) not in caplog.text  # the path names the device: the log has the host


def test_no_other_device_is_made_active():
    client, sent = client_answering(response(body=ANSWER), response(204, b""))
    with pytest.raises(DeviceNotVerified):
        client.set_device_active(UNIT)  # not added by this client
    client.register_device(XML, UNIT)
    with pytest.raises(DeviceNotVerified):
        client.set_device_active(OTHER_UNIT)
    assert [s["method"] for s in sent] == ["POST"]


@pytest.mark.parametrize("status", [400, 403, 409, 500])
def test_a_refused_change_of_status_is_an_error(status):
    client, _sent = client_answering(response(body=ANSWER), response(status, {"x": SECRETS[0]}))
    client.register_device(XML, UNIT)
    with pytest.raises(ApiError) as e:
        client.set_device_active(UNIT)
    assert SECRETS[0] not in str(e.value)
