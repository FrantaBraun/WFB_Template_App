# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from pydantic import BaseModel, EmailStr, Field


class EmailParams(BaseModel):
    """Matches auth.withfbraun.com's EmailTemplateParams - any field left
    unset uses the service's default (English) text."""

    title: str | None = None
    greeting: str | None = None
    message: str | None = None
    expire_units: str | None = None
    button_text: str | None = None
    instructions: str | None = None
    footer_text: str | None = None


class RegisterRequest(BaseModel):
    """Matches auth.withfbraun.com's registration body - POST /api/auth/register."""

    email: EmailStr
    login: str
    password: str
    first_name: str
    last_name: str
    language_code: str | None = None
    verify_url: str | None = None
    send_verify_email: bool = True
    email_params: EmailParams | None = None


class LoginRequest(BaseModel):
    """Matches auth.withfbraun.com's login body - identifier accepts either
    email or login/username, per the upstream contract."""

    identifier: str
    password: str


class RefreshRequest(BaseModel):
    """Body for POST /api/auth/refresh - exchanges a refresh token for a new
    access/refresh pair."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Body for POST /api/auth/logout - the refresh token to revoke; the
    access token itself travels in the Authorization header instead."""

    refresh_token: str


class UserUpdate(BaseModel):
    """Matches auth.withfbraun.com's UserUpdate - PATCH /api/auth/me body."""

    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None
    language_code: str | None = None
    birth_date: str | None = None
    country_code: str | None = None


class UserDataUpdate(BaseModel):
    """PATCH .../me/group-attributes/{group_id} body - replaces the entire
    user_data object, not a partial merge."""

    user_data: dict | None = None


class PasswordResetRequestBody(BaseModel):
    """Body for POST /api/auth/password-reset/request - the auth service mails
    a link to this app's reset page, which carries the token."""

    email: EmailStr


class PasswordResetConfirmBody(BaseModel):
    """Body for POST /api/auth/password-reset/confirm - the token from the
    e-mail link and the new password chosen on this app's reset page."""

    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordBody(BaseModel):
    """Body for POST /api/auth/me/change-password - the signed-in user's
    current password, then the new one."""

    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
