"""Notifier registry."""

from __future__ import annotations

import logging

from ..config import NotifierConfig
from .base import Notifier
from .email_smtp import EmailNotifier
from .whatsapp_callmebot import WhatsAppCallMeBotNotifier

log = logging.getLogger("flight_tracker.notifiers")

_REGISTRY: dict[str, type[Notifier]] = {
    "email": EmailNotifier,
    "whatsapp_callmebot": WhatsAppCallMeBotNotifier,
}


def build_notifiers(configs: list[NotifierConfig]) -> list[Notifier]:
    notifiers: list[Notifier] = []
    for cfg in configs:
        if not cfg.enabled:
            continue
        cls = _REGISTRY.get(cfg.name)
        if cls is None:
            log.warning("unknown notifier '%s' in config; skipping", cfg.name)
            continue
        notifier = cls(cfg.options)
        if not notifier.ready():
            continue
        notifiers.append(notifier)
    return notifiers


__all__ = ["build_notifiers", "Notifier"]
