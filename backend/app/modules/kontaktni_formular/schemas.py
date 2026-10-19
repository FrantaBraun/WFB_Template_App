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


class ContactDetails(BaseModel):
    """The public contact details of the deployment; each is None unless it
    is configured (and, for the email, switched on by show_email)."""

    email: str | None = None
    address: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None


class ContactInfoResponse(BaseModel):
    """What the contact page shows around the form. Empty strings and a
    details object with no values mean there is nothing to show."""

    title: str = ""
    intro: str = ""
    aside: str = ""
    details: ContactDetails
