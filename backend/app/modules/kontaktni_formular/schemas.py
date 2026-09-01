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
