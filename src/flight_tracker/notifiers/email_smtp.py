"""Email notifier over SMTP.

Works with any SMTP server. For Gmail / Google Workspace, create an *App
Password* (https://myaccount.google.com/apppasswords) and use:

    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=you@yourdomain.com
    SMTP_PASSWORD=<app password>

Recipients and the from-address are set in config; credentials come from env.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from ..config import env
from .base import Notifier

log = logging.getLogger("flight_tracker.notifier.email")


class EmailNotifier(Notifier):
    name = "email"

    def __init__(self, options: Optional[dict] = None):
        super().__init__(options)
        self.host = env(self.options.get("host_env", "SMTP_HOST"), "smtp.gmail.com")
        self.port = int(env(self.options.get("port_env", "SMTP_PORT"), "587") or 587)
        self.user = env(self.options.get("user_env", "SMTP_USER"))
        self.password = env(self.options.get("password_env", "SMTP_PASSWORD"))
        self.sender = self.options.get("from") or self.user
        recips = self.options.get("to", [])
        self.recipients = [recips] if isinstance(recips, str) else list(recips)
        self.use_tls = bool(self.options.get("use_tls", True))

    def ready(self) -> bool:
        if not (self.user and self.password and self.recipients):
            log.info("email notifier not ready: missing SMTP creds or recipients")
            return False
        return True

    def send(self, subject: str, text_body: str, html_body: Optional[str] = None) -> bool:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = ", ".join(self.recipients)
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            if self.port == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=30) as s:
                    s.login(self.user, self.password)
                    s.sendmail(self.sender, self.recipients, msg.as_string())
            else:
                with smtplib.SMTP(self.host, self.port, timeout=30) as s:
                    if self.use_tls:
                        s.starttls(context=ssl.create_default_context())
                    s.login(self.user, self.password)
                    s.sendmail(self.sender, self.recipients, msg.as_string())
            log.info("email sent to %s", ", ".join(self.recipients))
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("email send failed: %s", exc)
            return False
