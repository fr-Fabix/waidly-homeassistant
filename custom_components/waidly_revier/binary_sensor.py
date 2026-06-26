"""Binary-Sensor: Inaktivitäts-Warnung (lange kein Eintrag)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WaidlyConfigEntry
from .entity import WaidlyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WaidlyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([WaidlyInaktivSensor(entry.runtime_data)])


class WaidlyInaktivSensor(WaidlyEntity, BinarySensorEntity):
    """An, wenn seit > Schwelle Tagen kein Eintrag kam."""

    _attr_name = "Inaktiv"
    _attr_icon = "mdi:sleep"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.revier_id}_inaktiv"

    @property
    def is_on(self) -> bool | None:
        tage = self.coordinator.data.tage_seit_aktivitaet
        if tage is None:
            return None
        return tage >= self.coordinator.inactivity_days

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "tage_seit_aktivitaet": self.coordinator.data.tage_seit_aktivitaet,
            "schwelle_tage": self.coordinator.inactivity_days,
        }
