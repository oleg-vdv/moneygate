"""What an assistant proposes to do on the person's behalf.

Action types are Kepil action names, so the same mandate patterns apply:
  pay:transfer   — send money to a card, phone or account
  share:card     — give out a card number, CVV or expiry
  share:code     — give out an SMS/OTP code or a password (never allowed)
  share:id       — give out an IIN, passport or ID card number
  message:send   — send a message on the person's behalf
  link:open      — open a link or install an app from a message
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

ACTION_TYPES = ("pay:transfer", "share:card", "share:code", "share:id",
                "message:send", "link:open")


@dataclass(frozen=True)
class ProposedAction:
    type: str
    recipient: str | None = None   # card, phone, handle or domain as written
    amount_kzt: float = 0.0
    text: str | None = None        # the message the assistant wants to send, if any

    def __post_init__(self) -> None:
        if self.type not in ACTION_TYPES:
            raise ValueError(f"unknown action type: {self.type!r}")
        if self.amount_kzt < 0:
            raise ValueError("amount_kzt must not be negative")

    def masked_recipient(self) -> str | None:
        """What the journal may show: domains as is, cards and phones as their last 4 digits."""
        if not self.recipient:
            return None
        digits = "".join(ch for ch in self.recipient if ch.isdigit())
        if len(digits) >= 15:
            return "card:*" + digits[-4:]
        if len(digits) >= 10:
            return "tel:*" + digits[-4:]
        return self.recipient

    def ref(self) -> str:
        """Hash of the action: the journal keeps this, never the card number itself."""
        raw = f"{self.type}|{self.recipient or ''}|{self.amount_kzt}|{self.text or ''}"
        return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
