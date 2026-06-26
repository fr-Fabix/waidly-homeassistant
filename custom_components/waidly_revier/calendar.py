"""Kalender: alle Erlegungen/Anblicke auf ihrem Datum."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WaidlyConfigEntry
from .entity import WaidlyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WaidlyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([WaidlyCalendar(entry.runtime_data)])


class WaidlyCalendar(WaidlyEntity, CalendarEntity):
    """Jagdkalender — Ganztages-Events je Eintrag."""

    _attr_name = "Jagdkalender"
    _attr_icon = "mdi:calendar-star"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.revier_id}_kalender"

    def _build_events(self) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        for e in self.coordinator.data.all_entries:
            raw = e.get("datum")
            if not raw:
                continue
            try:
                day = date.fromisoformat(str(raw)[:10])
            except ValueError:
                continue
            typ = e.get("entry_type") or "Eintrag"
            wild = " ".join(p for p in (e.get("wildart"), e.get("unterart")) if p)
            anzahl = e.get("anzahl") or 1
            prefix = "🦌" if typ == "Erlegung" else "👁"
            summary = f"{prefix} {wild or typ}"
            if isinstance(anzahl, (int, float)) and anzahl > 1:
                summary += f" ×{int(anzahl)}"
            desc = [
                f"Typ: {typ}",
                f"Schütze: {e['schuetze']}" if e.get("schuetze") else None,
                f"Gewicht: {e['gewicht']} kg" if e.get("gewicht") else None,
                f"Waffe: {e['waffe']}" if e.get("waffe") else None,
                e.get("notizen") or None,
            ]
            loc = (
                f"{e['latitude']},{e['longitude']}"
                if e.get("latitude") is not None and e.get("longitude") is not None
                else None
            )
            events.append(
                CalendarEvent(
                    start=day,
                    end=day + timedelta(days=1),
                    summary=summary,
                    description="\n".join(p for p in desc if p),
                    location=loc,
                )
            )
        return events

    @property
    def event(self) -> CalendarEvent | None:
        evs = sorted(self._build_events(), key=lambda x: x.start)
        return evs[-1] if evs else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        sd, ed = start_date.date(), end_date.date()
        return [e for e in self._build_events() if e.start < ed and e.end > sd]
