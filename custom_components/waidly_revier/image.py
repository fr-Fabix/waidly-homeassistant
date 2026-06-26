"""Image-Entity: Foto der letzten Erlegung (Signed-URL der API)."""

from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import WaidlyConfigEntry
from .entity import WaidlyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WaidlyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([WaidlyFotoEntity(entry.runtime_data)])


class WaidlyFotoEntity(WaidlyEntity, ImageEntity):
    """Zeigt das Foto der jüngsten Erlegung (sofern vorhanden)."""

    _attr_name = "Letztes Erlegungsfoto"

    def __init__(self, coordinator) -> None:
        WaidlyEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self._attr_unique_id = f"{coordinator.revier_id}_letztes_foto"
        self._current_url: str | None = coordinator.data.letztes_foto_url
        self._attr_image_url = self._current_url
        self._attr_image_last_updated = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        url = self.coordinator.data.letztes_foto_url
        if url != self._current_url:
            self._current_url = url
            self._attr_image_url = url
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()
