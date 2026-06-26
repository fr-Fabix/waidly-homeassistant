"""Sensoren: Strecke, Anblicke, Wildbret, Einrichtungen + je Wildart/Einrichtung."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WaidlyConfigEntry
from .coordinator import WaidlyCoordinator
from .data import RevierState
from .entity import WaidlyEntity

# Icon je Wildart (Standard: Pfote)
WILDART_ICONS = {
    "Rehwild": "mdi:deer",
    "Rotwild": "mdi:deer",
    "Damwild": "mdi:deer",
    "Schwarzwild": "mdi:pig",
    "Fuchs": "mdi:paw",
    "Hase": "mdi:rabbit",
    "Dachs": "mdi:paw",
}

# Icon je Einrichtungstyp (HA-MDI-Annäherung an die App-Icons)
EINRICHTUNG_ICONS = {
    "Hochsitz": "mdi:tower-fire",
    "Kanzel": "mdi:home-roof",
    "Leitersitz": "mdi:ladder",
    "Kirrung": "mdi:bowl-mix",
    "Wildkamera": "mdi:cctv",
    "Falle": "mdi:select-place",
    "Salzlecke": "mdi:cube-outline",
    "Futterhaus": "mdi:home-variant",
    "Wildacker": "mdi:sprout",
    "Jagdhütte": "mdi:home",
}


def _slug(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "x"


@dataclass(frozen=True, kw_only=True)
class WaidlySensorDescription(SensorEntityDescription):
    """Sensor-Beschreibung mit Wert-/Attribut-Funktion auf dem RevierState."""

    value_fn: Callable[[RevierState], Any]
    attr_fn: Callable[[RevierState], dict[str, Any]] | None = None


def _letzte_erlegung_text(s: RevierState) -> str | None:
    e = s.letzte_erlegung
    if not e:
        return None
    parts = [e.get("wildart"), e.get("unterart")]
    return " ".join(p for p in parts if p) or e.get("wildart")


SENSORS: tuple[WaidlySensorDescription, ...] = (
    WaidlySensorDescription(
        key="strecke",
        name="Strecke",
        icon="mdi:target",
        native_unit_of_measurement="Stück",
        value_fn=lambda s: s.strecke_total,
        attr_fn=lambda s: {"jagdjahr": s.jagdjahr, "je_wildart": s.strecke_by_wildart},
    ),
    WaidlySensorDescription(
        key="anblicke",
        name="Anblicke",
        icon="mdi:binoculars",
        native_unit_of_measurement="Stück",
        value_fn=lambda s: s.anblicke_total,
        attr_fn=lambda s: {"jagdjahr": s.jagdjahr, "je_wildart": s.anblicke_by_wildart},
    ),
    WaidlySensorDescription(
        key="wildbret_kg",
        name="Wildbret",
        icon="mdi:scale",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        suggested_display_precision=1,
        value_fn=lambda s: round(s.wildbret_kg, 1),
    ),
    WaidlySensorDescription(
        key="erloes",
        name="Erlös",
        icon="mdi:cash",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        suggested_display_precision=2,
        value_fn=lambda s: round(s.erloes, 2),
    ),
    WaidlySensorDescription(
        key="letzte_erlegung",
        name="Letzte Erlegung",
        icon="mdi:bullseye-arrow",
        value_fn=_letzte_erlegung_text,
        attr_fn=lambda s: dict(s.letzte_erlegung) if s.letzte_erlegung else {},
    ),
    WaidlySensorDescription(
        key="letzte_aktivitaet",
        name="Letzte Aktivität",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda s: s.letzte_aktivitaet,
    ),
    WaidlySensorDescription(
        key="tage_seit_aktivitaet",
        name="Tage seit Aktivität",
        icon="mdi:calendar-clock",
        native_unit_of_measurement="d",
        value_fn=lambda s: s.tage_seit_aktivitaet,
    ),
    WaidlySensorDescription(
        key="einrichtungen",
        name="Einrichtungen",
        icon="mdi:map-marker-multiple",
        native_unit_of_measurement="Stück",
        value_fn=lambda s: len(s.einrichtungen),
        attr_fn=lambda s: {"je_typ": s.einrichtungen_by_type},
    ),
    WaidlySensorDescription(
        key="wartung",
        name="Wartung nötig",
        icon="mdi:wrench",
        native_unit_of_measurement="Stück",
        value_fn=lambda s: s.wartung_count,
        attr_fn=lambda s: {"einrichtungen": s.wartung_liste},
    ),
    WaidlySensorDescription(
        key="wildkameras",
        name="Wildkameras",
        icon="mdi:cctv",
        native_unit_of_measurement="Stück",
        value_fn=lambda s: s.wildkamera_count,
    ),
    WaidlySensorDescription(
        key="geeignete_einrichtungen",
        name="Geeignete Einrichtungen (Wind)",
        icon="mdi:weather-windy",
        value_fn=lambda s: (
            ", ".join(s.geeignete_einrichtungen)
            if s.geeignete_einrichtungen
            else ("—" if s.current_wind else "kein Wind konfiguriert")
        ),
        attr_fn=lambda s: {
            "aktueller_wind": s.current_wind,
            "anzahl": len(s.geeignete_einrichtungen),
            "einrichtungen": s.geeignete_einrichtungen,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WaidlyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    async_add_entities(WaidlyAggregateSensor(coordinator, d) for d in SENSORS)

    known_wildarten: set[str] = set()
    known_spots: set[str] = set()

    @callback
    def _add_dynamic() -> None:
        new: list[SensorEntity] = []
        state = coordinator.data
        for wildart in state.strecke_by_wildart:
            if wildart not in known_wildarten:
                known_wildarten.add(wildart)
                new.append(WaidlyWildartSensor(coordinator, wildart))
        for ein in state.einrichtungen:
            if ein.id not in known_spots:
                known_spots.add(ein.id)
                new.append(WaidlyEinrichtungSensor(coordinator, ein.id))
        if new:
            async_add_entities(new)

    _add_dynamic()
    entry.async_on_unload(coordinator.async_add_listener(_add_dynamic))


class WaidlyAggregateSensor(WaidlyEntity, SensorEntity):
    """Aggregat-Sensor (Strecke, Anblicke, Wildbret …)."""

    entity_description: WaidlySensorDescription

    def __init__(
        self, coordinator: WaidlyCoordinator, description: WaidlySensorDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.revier_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attr_fn:
            return self.entity_description.attr_fn(self.coordinator.data)
        return None


class WaidlyWildartSensor(WaidlyEntity, SensorEntity):
    """Strecke je Wildart (laufendes Jagdjahr)."""

    _attr_native_unit_of_measurement = "Stück"

    def __init__(self, coordinator: WaidlyCoordinator, wildart: str) -> None:
        super().__init__(coordinator)
        self._wildart = wildart
        self._attr_name = f"Strecke {wildart}"
        self._attr_icon = WILDART_ICONS.get(wildart, "mdi:paw")
        self._attr_unique_id = f"{coordinator.revier_id}_strecke_{_slug(wildart)}"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.strecke_by_wildart.get(self._wildart, 0)


class WaidlyEinrichtungSensor(WaidlyEntity, SensorEntity):
    """Eine Einrichtung; State = Zustand (Gut/Mittel/Schlecht/…)."""

    def __init__(self, coordinator: WaidlyCoordinator, spot_id: str) -> None:
        super().__init__(coordinator)
        self._spot_id = spot_id
        ein = self._find()
        name = ein.name if ein else "Einrichtung"
        typ = ein.typ if ein else "Sonstiges"
        self._attr_name = f"Einrichtung {name}"
        self._attr_icon = EINRICHTUNG_ICONS.get(typ, "mdi:map-marker")
        self._attr_unique_id = f"{coordinator.revier_id}_einrichtung_{spot_id}"

    def _find(self):
        for e in self.coordinator.data.einrichtungen:
            if e.id == self._spot_id:
                return e
        return None

    @property
    def available(self) -> bool:
        return super().available and self._find() is not None

    @property
    def native_value(self) -> str | None:
        ein = self._find()
        return ein.zustand if ein else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        ein = self._find()
        return ein.attributes() if ein else None
