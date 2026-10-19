# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from pydantic import BaseModel


class ProviderInfo(BaseModel):
    """The provider's identification as the legal pages show it. Empty
    strings (and `effective_from` None) mean the value is not configured;
    `configured` says whether the minimum a published legal page needs - name,
    company ID, address and email - is there."""

    name: str = ""
    ico: str = ""
    dic: str = ""
    vat_payer: bool = False
    address: str = ""
    registration: str = ""
    email: str = ""
    phone: str = ""
    web: str = ""
    dpo_email: str = ""
    effective_from: str | None = None
    configured: bool = False
