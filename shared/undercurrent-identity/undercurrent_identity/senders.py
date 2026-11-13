"""How invite and recovery links reach people.

All sending goes through `Sender`. Today there is no email service
(owner-approved 2026-11-13): `LinkOnlySender` sends nothing and the owner
passes the link on by hand. #80 adds a Resend implementation behind this
same interface; nothing else should need to change.
"""
from typing import Protocol


class Sender(Protocol):
    def send(self, to: str, subject: str, text: str, html: str | None = None) -> bool:
        """Send a message. Returns True if it was actually sent."""
        ...


class LinkOnlySender:
    """Sends nothing. Callers print the link for the owner to pass on."""

    def send(self, to: str, subject: str, text: str, html: str | None = None) -> bool:
        return False
