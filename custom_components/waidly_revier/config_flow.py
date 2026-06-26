"""Config- und Options-Flow für Waidly Online-Revier."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .api import InvalidCode, RateLimited, WaidlyApiError, WebRevierClient
from .const import (
    CONF_CODE,
    CONF_INACTIVITY_DAYS,
    CONF_SCAN_INTERVAL,
    CONF_WIND_ENTITY,
    DEFAULT_INACTIVITY_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class WaidlyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Code eingeben, gegen die API prüfen, Revier-Eintrag anlegen."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            code = user_input[CONF_CODE].strip().upper()
            client = WebRevierClient(async_get_clientsession(self.hass))
            try:
                data = await client.validate(code)
            except InvalidCode:
                errors["base"] = "invalid_code"
            except RateLimited:
                errors["base"] = "rate_limited"
            except WaidlyApiError:
                errors["base"] = "cannot_connect"
            else:
                revier_id = data.get("revier_id")
                if not revier_id:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(revier_id)
                    self._abort_if_unique_id_configured()
                    name = (data.get("revier") or {}).get("name") or "Revier"
                    return self.async_create_entry(
                        title=f"Revier {name}", data={CONF_CODE: code}
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_CODE): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return WaidlyOptionsFlow()


class WaidlyOptionsFlow(OptionsFlow):
    """Poll-Intervall und Inaktivitäts-Schwelle einstellen."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=120, max=86400)),
                    vol.Optional(
                        CONF_INACTIVITY_DAYS,
                        default=opts.get(
                            CONF_INACTIVITY_DAYS, DEFAULT_INACTIVITY_DAYS
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=365)),
                    vol.Optional(
                        CONF_WIND_ENTITY,
                        description={"suggested_value": opts.get(CONF_WIND_ENTITY)},
                    ): EntitySelector(EntitySelectorConfig(domain=["sensor", "weather"])),
                }
            ),
        )
