# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import httpx

from app.config import Settings, get_settings


class AuthClient:
    """Async client for auth.withfbraun.com, the shared authorization service.

    X-Api-Key is required on every request - the auth service uses it to
    identify which application group is calling. Every method except `login`
    raises via response.raise_for_status() on a non-2xx response. `login` is
    the one call that must NOT raise on 403: the caller needs to distinguish
    "200 with tokens" from "403 consent_required" itself, and raising would
    collapse that distinction.
    """

    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        self._api_key = settings.auth_api_key
        self._http = httpx.AsyncClient(
            base_url=settings.auth_url,
            headers={"X-Api-Key": self._api_key},
            timeout=15,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    def _require_api_key(self) -> None:
        if not self._api_key:
            # An empty/missing X-Api-Key isn't rejected by the auth service -
            # it's silently treated as "no application context", which skips
            # the consent check entirely. Failing loudly here beats a silent
            # security-relevant misconfiguration (e.g. a stale process that
            # never picked up AUTH_API_KEY after it was added to .env - the
            # Settings singleton is cached for the process lifetime).
            raise RuntimeError(
                "AUTH_API_KEY is not configured - every request to the auth "
                "service requires it. Set it in backend/.env and restart the "
                "backend process."
            )

    async def register(
        self,
        *,
        email: str,
        login: str,
        password: str,
        first_name: str,
        last_name: str,
        **extra: object,
    ) -> dict:
        self._require_api_key()
        r = await self._http.post(
            "/api/auth/register",
            json={
                "email": email,
                "login": login,
                "password": password,
                "first_name": first_name,
                "last_name": last_name,
                **extra,
            },
        )
        r.raise_for_status()
        return r.json()

    async def login(self, *, identifier: str, password: str) -> httpx.Response:
        """Returns the raw response - inspect .status_code: 200 = tokens in
        body, 403 = consent_required, anything else = a real error."""
        self._require_api_key()
        return await self._http.post(
            "/api/auth/login", json={"identifier": identifier, "password": password}
        )

    async def refresh(self, *, refresh_token: str) -> dict:
        self._require_api_key()
        r = await self._http.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        r.raise_for_status()
        return r.json()

    async def logout(self, *, access_token: str, refresh_token: str) -> None:
        self._require_api_key()
        r = await self._http.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()

    async def get_me(self, *, access_token: str) -> dict:
        """Returns {consent_required, application_group_id, user}. `user` is
        only populated once consent_required is false."""
        self._require_api_key()
        r = await self._http.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {access_token}"}
        )
        r.raise_for_status()
        return r.json()

    async def update_me(self, *, access_token: str, payload: dict) -> dict:
        """PATCH /api/auth/me - updates core profile fields (UserUpdate),
        returns the updated UserOut."""
        self._require_api_key()
        r = await self._http.patch(
            "/api/auth/me", json=payload, headers={"Authorization": f"Bearer {access_token}"}
        )
        r.raise_for_status()
        return r.json()

    async def get_group_attributes(self, *, access_token: str, group_id: str) -> dict:
        """{application_group_id, user_data, updated_at} - user_data only,
        system_data is never included (hidden by the auth service itself)."""
        self._require_api_key()
        r = await self._http.get(
            f"/api/auth/me/group-attributes/{group_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()
        return r.json()

    async def update_group_attributes(
        self, *, access_token: str, group_id: str, user_data: dict
    ) -> dict:
        """PATCH .../group-attributes/{group_id} - replaces the ENTIRE
        user_data object, it is not a partial merge. Callers must send the
        full desired object, merging with the existing one themselves."""
        self._require_api_key()
        r = await self._http.patch(
            f"/api/auth/me/group-attributes/{group_id}",
            json={"user_data": user_data},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()
        return r.json()

    async def request_password_reset(
        self, *, email: str, reset_url: str | None = None
    ) -> None:
        """POST /api/auth/password-reset/request - the auth service mails a
        reset link; reset_url is where that link leads (its ?token= is added
        upstream). Omitted, the service uses its own configured default."""
        self._require_api_key()
        payload: dict = {"email": email}
        if reset_url:
            payload["reset_url"] = reset_url
        r = await self._http.post("/api/auth/password-reset/request", json=payload)
        r.raise_for_status()

    async def confirm_password_reset(self, *, token: str, new_password: str) -> None:
        self._require_api_key()
        r = await self._http.post(
            "/api/auth/password-reset/confirm",
            json={"token": token, "new_password": new_password},
        )
        r.raise_for_status()

    async def change_password(
        self, *, access_token: str, current_password: str, new_password: str
    ) -> None:
        self._require_api_key()
        r = await self._http.post(
            "/api/auth/me/change-password",
            json={"current_password": current_password, "new_password": new_password},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()

    async def get_public_key(self) -> str:
        self._require_api_key()
        r = await self._http.get("/api/auth/public-key")
        r.raise_for_status()
        return r.json()["public_key"]

    async def get_group_info(self) -> dict:
        """{id, name, description, scopes} for the group identified by our
        own X-Api-Key - no user token needed, used to render the consent page."""
        self._require_api_key()
        r = await self._http.get("/api/auth/group-info")
        r.raise_for_status()
        return r.json()

    async def get_consent_info(self, *, group_id: str, access_token: str) -> dict:
        self._require_api_key()
        r = await self._http.get(
            f"/api/auth/consent-info/{group_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()
        return r.json()

    async def grant_consent(self, *, group_id: str, access_token: str) -> None:
        self._require_api_key()
        r = await self._http.post(
            f"/api/auth/consent/{group_id}/grant",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()

    async def reject_consent(self, *, group_id: str, access_token: str) -> None:
        self._require_api_key()
        r = await self._http.post(
            f"/api/auth/consent/{group_id}/reject",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()


auth_client = AuthClient()
