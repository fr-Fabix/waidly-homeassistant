"""DataUpdateCoordinator: hält Revier-Zustand, merged Deltas, feuert Events."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import InvalidCode, RateLimited, SessionExpired, WaidlyApiError, WebRevierClient
from .const import (
    CONF_CODE,
    CONF_INACTIVITY_DAYS,
    CONF_SCAN_INTERVAL,
    CONF_WIND_ENTITY,
    DEFAULT_INACTIVITY_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_EINRICHTUNG_WARTUNG,
    EVENT_NEUE_ERLEGUNG,
    EVENT_NEUER_ANBLICK,
)
from .data import Einrichtung, RevierState, compute_revier_state

_LOGGER = logging.getLogger(__name__)


class WaidlyCoordinator(DataUpdateCoordinator[RevierState]):
    """Pollt `web-revier`, hält die volle Datenbasis und feuert HA-Events."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        scan = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=scan),
        )
        self.entry = entry
        self._code: str = entry.data[CONF_CODE]
        self._client = WebRevierClient(async_get_clientsession(hass))

        # Volle Datenbasis (per id), wird über Deltas gepflegt.
        self._revier: dict[str, Any] = {}
        self._entries: dict[str, dict[str, Any]] = {}
        self._spots: dict[str, dict[str, Any]] = {}
        self._revier_id: str | None = None
        self._session_token: str | None = None
        self._last_load: str = "1970-01-01T00:00:00Z"

        # Für Event-Erkennung
        self._first_load = True
        self._spot_zustand: dict[str, bool] = {}  # spot_id -> needs_maintenance

    @property
    def inactivity_days(self) -> int:
        return self.entry.options.get(CONF_INACTIVITY_DAYS, DEFAULT_INACTIVITY_DAYS)

    @property
    def revier_id(self) -> str:
        return self._revier_id or self.entry.entry_id

    @property
    def revier_name(self) -> str:
        return self._revier.get("name") or "Revier"

    async def _async_update_data(self) -> RevierState:
        try:
            if self._session_token is None:
                await self._do_validate()
            else:
                try:
                    await self._do_refresh()
                except SessionExpired:
                    _LOGGER.debug("Session abgelaufen, validiere neu")
                    await self._do_validate()
        except InvalidCode as err:
            raise UpdateFailed(f"Code ungültig: {err}") from err
        except RateLimited as err:
            raise UpdateFailed(f"Rate-Limit: {err}") from err
        except WaidlyApiError as err:
            raise UpdateFailed(str(err)) from err

        state = compute_revier_state(self._build_raw(), current_wind=self._current_wind())
        self._first_load = False
        return state

    # ---- Wind-Eignung ----

    @callback
    def _current_wind(self) -> str | None:
        ent = self.entry.options.get(CONF_WIND_ENTITY)
        if not ent:
            return None
        st = self.hass.states.get(ent)
        if st is None or st.state in (None, "", "unknown", "unavailable"):
            return None
        return st.state

    @callback
    def async_setup_wind_tracking(self) -> None:
        """Bei Windrichtungs-Änderung die Eignung live neu berechnen (ohne API-Call)."""
        ent = self.entry.options.get(CONF_WIND_ENTITY)
        if not ent:
            return

        @callback
        def _wind_changed(event: Any) -> None:
            if self.data is not None:
                self.async_set_updated_data(
                    compute_revier_state(self._build_raw(), current_wind=self._current_wind())
                )

        self.entry.async_on_unload(
            async_track_state_change_event(self.hass, [ent], _wind_changed)
        )

    # ---- API-Aufrufe ----

    async def _do_validate(self) -> None:
        data = await self._client.validate(self._code)
        self._revier = data.get("revier") or {}
        self._revier_id = data.get("revier_id")
        self._session_token = data.get("session_token")
        self._last_load = data.get("server_time") or self._last_load

        new_entries = {e["id"]: e for e in (data.get("entries") or []) if e.get("id")}
        new_spots = {s["id"]: s for s in (data.get("spots") or []) if s.get("id")}

        if not self._first_load:
            self._detect_events(new_entries, new_spots)

        self._entries = new_entries
        self._spots = new_spots
        self._update_zustand_cache()

    async def _do_refresh(self) -> None:
        assert self._revier_id and self._session_token
        data = await self._client.refresh(
            self._revier_id, self._session_token, self._last_load
        )
        updates = data.get("updates") or {}

        # Kopien für Event-Vergleich anlegen
        merged_entries = dict(self._entries)
        merged_spots = dict(self._spots)

        for e in updates.get("entries") or []:
            if e.get("id"):
                merged_entries[e["id"]] = e
        for s in updates.get("spots") or []:
            if s.get("id"):
                merged_spots[s["id"]] = s
        if updates.get("revier"):
            self._revier = {**self._revier, **updates["revier"]}

        # Löschungen anwenden
        for d in data.get("deletions") or []:
            table, rec = d.get("table"), d.get("record_id")
            if table == "shared_entries":
                merged_entries.pop(rec, None)
            elif table == "shared_spots":
                merged_spots.pop(rec, None)

        if not self._first_load:
            self._detect_events(merged_entries, merged_spots)

        self._entries = merged_entries
        self._spots = merged_spots
        self._last_load = data.get("server_time") or self._last_load
        self._update_zustand_cache()

    # ---- Event-Erkennung ----

    def _detect_events(
        self,
        new_entries: dict[str, dict[str, Any]],
        new_spots: dict[str, dict[str, Any]],
    ) -> None:
        # Neue Einträge (id war vorher unbekannt)
        for eid, e in new_entries.items():
            if eid in self._entries:
                continue
            etype = e.get("entry_type")
            if etype == "Erlegung":
                self.hass.bus.async_fire(EVENT_NEUE_ERLEGUNG, self._erlegung_payload(e))
            elif etype == "Anblick":
                self.hass.bus.async_fire(EVENT_NEUER_ANBLICK, self._anblick_payload(e))

        # Einrichtung: Zustand verschlechtert (Wartung nötig, war vorher ok)
        for sid, s in new_spots.items():
            now_bad = Einrichtung(raw=s).needs_maintenance
            was_bad = self._spot_zustand.get(sid, False)
            if now_bad and not was_bad:
                self.hass.bus.async_fire(
                    EVENT_EINRICHTUNG_WARTUNG,
                    {
                        "revier_id": self.revier_id,
                        "revier_name": self.revier_name,
                        "einrichtung": s.get("name"),
                        "typ": s.get("type"),
                        "zustand": (s.get("zustand") or "").strip() or "Unbekannt",
                    },
                )

    def _erlegung_payload(self, e: dict[str, Any]) -> dict[str, Any]:
        return {
            "revier_id": self.revier_id,
            "revier_name": self.revier_name,
            "schuetze": e.get("schuetze"),
            "wildart": e.get("wildart"),
            "unterart": e.get("unterart"),
            "anzahl": e.get("anzahl"),
            "gewicht": e.get("gewicht"),
            "geschlecht": e.get("geschlecht"),
            "waffe": e.get("waffe"),
            "munition": e.get("munition"),
            "entfernung": e.get("entfernung"),
            "verwertung": e.get("verwertung"),
            "datum": e.get("datum"),
            "uhrzeit": e.get("uhrzeit"),
            "spot_id": e.get("spot_id"),
            "latitude": e.get("latitude"),
            "longitude": e.get("longitude"),
            "foto_url": e.get("photo_url"),
            "notizen": e.get("notizen"),
        }

    def _anblick_payload(self, e: dict[str, Any]) -> dict[str, Any]:
        return {
            "revier_id": self.revier_id,
            "revier_name": self.revier_name,
            "schuetze": e.get("schuetze"),
            "wildart": e.get("wildart"),
            "unterart": e.get("unterart"),
            "anzahl": e.get("anzahl"),
            "datum": e.get("datum"),
            "uhrzeit": e.get("uhrzeit"),
            "latitude": e.get("latitude"),
            "longitude": e.get("longitude"),
            "notizen": e.get("notizen"),
        }

    def _update_zustand_cache(self) -> None:
        self._spot_zustand = {
            sid: Einrichtung(raw=s).needs_maintenance for sid, s in self._spots.items()
        }

    def _build_raw(self) -> dict[str, Any]:
        return {
            "revier": self._revier,
            "spots": list(self._spots.values()),
            "entries": list(self._entries.values()),
        }
