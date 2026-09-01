"""WhatsApp notifier via CallMeBot (free, personal use).

One-time activation (per phone number that should *receive* alerts):

1. Add the CallMeBot number **+34 644 51 95 23** to your contacts.
2. Send it this WhatsApp message: ``I allow callmebot to send me messages``
3. You'll get an ``apikey`` back. Put the phone (international format, e.g.
   ``+5511999999999``) and the apikey in env:

       CALLMEBOT_PHONE
       CALLMEBOT_APIKEY

CallMeBot only sends plain text, so HTML bodies are ignored and messages are
truncated to a sane length.

Docs: https://www.callmebot.com/blog/free-api-whatsapp-messages/
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import quote

import requests

from ..config import env
from .base import Notifier

log = logging.getLogger("flight_tracker.notifier.whatsapp")

_ENDPOINT = "https://api.callmebot.com/whatsapp.php"
_MAX_LEN = 900


class WhatsAppCallMeBotNotifier(Notifier):
    name = "whatsapp_callmebot"

    def __init__(self, options: Optional[dict] = None):
        super().__init__(options)
        self.phone = env(self.options.get("phone_env", "CALLMEBOT_PHONE"))
        self.apikey = env(self.options.get("apikey_env", "CALLMEBOT_APIKEY"))

    def ready(self) -> bool:
        if not (self.phone and self.apikey):
            log.info("whatsapp notifier not ready: CALLMEBOT_PHONE/APIKEY not set")
            return False
        return True

    def send(self, subject: str, text_body: str, html_body: Optional[str] = None) -> bool:
        message = f"{subject}\n\n{text_body}".strip()
        if len(message) > _MAX_LEN:
            message = message[: _MAX_LEN - 3] + "..."
        params = {
            "phone": self.phone,
            "text": message,
            "apikey": self.apikey,
        }
        try:
            resp = requests.get(_ENDPOINT, params=params, timeout=30)
            # CallMeBot returns 200 with an HTML body on success; non-200 or a
            # body mentioning an error means it didn't go through.
            ok = resp.status_code == 200 and "error" not in resp.text.lower()
            if ok:
                log.info("whatsapp sent to %s", self.phone)
            else:
                log.warning(
                    "whatsapp send failed HTTP %s: %s",
                    resp.status_code,
                    resp.text[:200],
                )
            return ok
        except Exception as exc:  # noqa: BLE001
            log.warning("whatsapp send error: %s", exc)
            return False


# Build a phone number into a CallMeBot URL without spaces/plus issues.
def _encode(text: str) -> str:  # pragma: no cover - kept for reference/manual use
    return quote(text)
