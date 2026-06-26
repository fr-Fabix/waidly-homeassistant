"""Gemeinsame Basis-Entity (Geräte-Zuordnung)."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import WaidlyCoordinator


class WaidlyEntity(CoordinatorEntity[WaidlyCoordinator]):
    """Basis: ordnet alle Entities dem Revier-Gerät zu."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WaidlyCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.revier_id)},
            name=f"Revier {coordinator.revier_name}",
            manufacturer=MANUFACTURER,
            model=(coordinator.data.revier.get("revierart") or "Online-Revier"),
            configuration_url="https://app.waidly.de",
        )
