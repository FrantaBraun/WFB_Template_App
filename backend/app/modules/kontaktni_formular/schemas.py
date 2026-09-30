# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from pydantic import BaseModel, EmailStr, Field


class ContactFormRequest(BaseModel):
    """reply_to is only actually required for an anonymous sender - enforced
    in the router, since that depends on whether a valid bearer token was
    sent, which the schema itself can't see."""

    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=5000)
    reply_to: EmailStr | None = None
    # The frontend's active i18n language; picks the confirmation email's
    # template (see config.ContactFormConfig.reply_template_for), falling
    # back to the configured default_language when absent or unconfigured.
    language: str | None = Field(default=None, max_length=35)
