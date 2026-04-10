import time

import httpx

from wow_ah.exceptions.base import APIError
from wow_ah.exceptions.messages import APIErrorMessages

_TOKEN_URL = "https://oauth.battle.net/token"


class TokenManager:
    """Manages OAuth2 client credentials tokens with caching."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._expires_at: float = 0

    def get_token(self) -> str:
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        self._refresh()
        return self._token  # type: ignore[return-value]

    def _refresh(self) -> None:
        try:
            resp = httpx.post(
                _TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
                timeout=30,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise APIError(APIErrorMessages.AUTH_FAILED.format(error=str(e))) from e

        data = resp.json()
        self._token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 86400)
