"""Notifier interface.

A notifier delivers an alert through one channel (email, WhatsApp, ...). Like
providers, notifiers self-report readiness and never raise on a delivery
failure — they log and return False so one broken channel doesn't stop the
others.
"""

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("flight_tracker.notifier")


class Notifier:
    name: str = "base"

    def __init__(self, options: Optional[dict] = None):
        self.options = options or {}

    def ready(self) -> bool:
        return True

    def send(self, subject: str, text_body: str, html_body: Optional[str] = None) -> bool:
        raise NotImplementedError
