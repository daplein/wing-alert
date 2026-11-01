import httpx
import pytest
import respx

from wing_alert.whatsapp import CallMeBotSender, DeliveryError, Recipient, parse_recipients

URL = CallMeBotSender.URL
SECRET_KEY = "999111"
SECRET_PHONE = "+353861234567"


def test_fr_1_9_parses_one_recipient_per_line():
    raw = f"{SECRET_PHONE}:{SECRET_KEY}\n\n +353870000000 : 42 \n"
    assert parse_recipients(raw) == [
        Recipient(SECRET_PHONE, SECRET_KEY),
        Recipient("+353870000000", "42"),
    ]


def test_fr_1_9_no_recipients_when_secret_is_empty():
    assert parse_recipients("") == []


def test_fr_1_9_bad_line_error_does_not_leak_the_secret():
    with pytest.raises(ValueError) as error:
        parse_recipients(f"{SECRET_PHONE}{SECRET_KEY}")
    assert SECRET_PHONE not in str(error.value)
    assert "line 1" in str(error.value)


def test_fr_1_9_recipient_repr_hides_the_secret():
    assert SECRET_KEY not in repr(Recipient(SECRET_PHONE, SECRET_KEY))


@respx.mock
def test_fr_1_6_sends_the_text_to_every_recipient():
    route = respx.get(URL).respond(text="Message queued")
    with httpx.Client() as http:
        CallMeBotSender(http, [Recipient("1", "a"), Recipient("2", "b")]).send("🪁 hi")
    sent = [call.request.url.params for call in route.calls]
    assert [(p["phone"], p["apikey"], p["text"]) for p in sent] == [
        ("1", "a", "🪁 hi"),
        ("2", "b", "🪁 hi"),
    ]


@respx.mock
@pytest.mark.parametrize(
    "outcome", [httpx.Response(500), httpx.ConnectError(f"apikey={SECRET_KEY}")]
)
def test_fr_1_9_delivery_errors_do_not_leak_the_secret(outcome):
    respx.get(URL).mock(side_effect=[outcome])
    with httpx.Client() as http, pytest.raises(DeliveryError) as error:
        CallMeBotSender(http, [Recipient(SECRET_PHONE, SECRET_KEY)]).send("hi")
    assert SECRET_KEY not in str(error.value)
    assert SECRET_PHONE not in str(error.value)
    assert error.value.__cause__ is None
