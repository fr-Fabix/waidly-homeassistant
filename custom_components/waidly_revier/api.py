"""Async-Client für die Waidly `web-revier` Edge Function."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import ANON_KEY, API_URL

_LOGGER = logging.getLogger(__name__)


class WaidlyApiError(Exception):
    """Allgemeiner API-Fehler."""


class InvalidCode(WaidlyApiError):
    """Code ungültig, inaktiv oder Revier nicht verfügbar."""


class RateLimited(WaidlyApiError):
    """Zu viele Validierungs-Versuche (HTTP 429)."""


class SessionExpired(WaidlyApiError):
    """Session-Token abgelaufen/ungültig (HTTP 401) — neu validieren."""


class WebRevierClient:
    """Dünner Wrapper um die zwei Actions `validate` und `refresh`."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {ANON_KEY}",
            "apikey": ANON_KEY,
            "Content-Type": "application/json",
        }
        try:
            async with self._session.post(
                API_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                status = resp.status
                try:
                    data: dict[str, Any] = await resp.json()
                except (aiohttp.ContentTypeError, ValueError):
                    data = {}
        except aiohttp.ClientError as err:
            raise WaidlyApiError(f"Verbindungsfehler: {err}") from err

        if status == 200:
            return data

        message = (data or {}).get("error") or f"HTTP {status}"
        if status == 429:
            raise RateLimited(message)
        if status == 401:
            raise SessionExpired(message)
        if status in (403, 404):
            raise InvalidCode(message)
        raise WaidlyApiError(message)

    async def validate(self, code: str) -> dict[str, Any]:
        """Code prüfen und alle Daten + Session-Token laden."""
        return await self._post({"action": "validate", "code": code.strip().upper()})

    async def refresh(
        self, revier_id: str, session_token: str, last_load: str
    ) -> dict[str, Any]:
        """Delta seit `last_load` laden (kein Rate-Limit)."""
        return await self._post(
            {
                "action": "refresh",
                "revier_id": revier_id,
                "session_token": session_token,
                "last_load": last_load,
            }
        )
