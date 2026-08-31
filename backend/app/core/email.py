"""
Email provider abstraction — same reasoning as core/payments.py:
which email service a business wants (SendGrid, SES, Postmark, etc.)
is a deployment decision, not a base-template one. What's universal
is the shape: "send this address this subject/body."

ConsoleEmailProvider is the default — it does NOT send anything, it
logs what would have been sent. This makes the whole system testable
with zero configuration, and is why request_password_reset can still
return the token directly today (see the CUSTOMIZING.md checklist —
that response field must be removed once a real provider is wired in
and actually delivering the email).

To integrate a real provider: implement EmailProvider in a new file,
swap the instance in get_email_provider(), store API keys via
app.core.config.settings.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("app.email")


class EmailProvider(ABC):
    @abstractmethod
    async def send(self, to: str, subject: str, body: str) -> bool:
        raise NotImplementedError


class ConsoleEmailProvider(EmailProvider):
    """Default provider — logs instead of sending. Real behavior until
    a deployment wires in an actual email service."""

    async def send(self, to: str, subject: str, body: str) -> bool:
        logger.info("EMAIL (not actually sent) to=%s subject=%r body=%r", to, subject, body)
        return True


def get_email_provider() -> EmailProvider:
    return ConsoleEmailProvider()
