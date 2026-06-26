"""Waidly Online-Revier — Home-Assistant-Integration (read-only)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import WaidlyCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.IMAGE,
]

type WaidlyConfigEntry = ConfigEntry[WaidlyCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: WaidlyConfigEntry) -> bool:
    """Revier-Eintrag einrichten."""
    coordinator = WaidlyCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    coordinator.async_setup_wind_tracking()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WaidlyConfigEntry) -> bool:
    """Revier-Eintrag entladen."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: WaidlyConfigEntry) -> None:
    """Bei Options-Änderung neu laden."""
    await hass.config_entries.async_reload(entry.entry_id)
