"""
Newsletter/discount email capture — retail-vertical addition, not a
base-build concept. A storefront wants a lightweight way to collect
an email for marketing outreach without requiring a full account
(register/login); this table exists purely so an email can be
recorded and later exported/synced to whatever ESP (Mailchimp, etc.)
a real deployment wires up. No account_id — a signup isn't tied to
an Account and shouldn't require someone to register just to get on
a mailing list.
"""

from datetime import datetime

from pydantic import EmailStr
from sqlmodel import Field, SQLModel


class NewsletterSignupBase(SQLModel):
    email: EmailStr = Field(index=True, unique=True, max_length=255)


class NewsletterSignup(NewsletterSignupBase, table=True):
    __tablename__ = "newsletter_signup"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class NewsletterSignupCreate(NewsletterSignupBase):
    pass


class NewsletterSignupRead(NewsletterSignupBase):
    id: int
    created_at: datetime
