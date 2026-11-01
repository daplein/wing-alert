"""Send WhatsApp messages to individuals through CallMeBot (FR-1.6, FR-1.9).

Phone numbers and API keys are secrets: they never go into error messages or logs,
which is why errors below name the recipient by position only.
"""

from dataclasses import dataclass

import httpx


class DeliveryError(Exception):
    """A message could not be delivered."""


@dataclass(frozen=True)
class Recipient:
    phone: str
    api_key: str

    def __repr__(self) -> str:
        return "Recipient(***)"


def parse_recipients(raw: str) -> list[Recipient]:
    """One "phone:apikey" pair per line; blank lines are ignored."""
    recipients = []
    for number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        phone, separator, api_key = line.strip().partition(":")
        if not (separator and phone and api_key):
            raise ValueError(f"WHATSAPP_RECIPIENTS line {number} is not phone:apikey")
        recipients.append(Recipient(phone.strip(), api_key.strip()))
    return recipients


class CallMeBotSender:
    # https://www.callmebot.com/blog/free-api-whatsapp-messages/
    URL = "https://api.callmebot.com/whatsapp.php"

    def __init__(self, http: httpx.Client, recipients: list[Recipient]) -> None:
        self._http = http
        self._recipients = recipients

    def send(self, text: str) -> None:
        for number, recipient in enumerate(self._recipients, start=1):
            self._send_one(number, recipient, text)

    def _send_one(self, number: int, recipient: Recipient, text: str) -> None:
        params = {"phone": recipient.phone, "text": text, "apikey": recipient.api_key}
        try:
            response = self._http.get(self.URL, params=params)
        except httpx.HTTPError as error:
            raise DeliveryError(f"recipient {number}: {type(error).__name__}") from None
        if response.status_code != 200:
            raise DeliveryError(f"recipient {number}: HTTP {response.status_code}")


class DrySender:
    """Sends nothing: used when there are no recipients yet, or for a dry run.
    The job's output already shows the message."""

    def send(self, text: str) -> None:
        pass
