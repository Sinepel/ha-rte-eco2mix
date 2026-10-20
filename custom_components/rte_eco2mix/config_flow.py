"""Config flow for RTE éCO2mix."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util

from .api import Eco2mixClient, Eco2mixError
from .const import (
    CONF_CO2_THRESHOLD,
    CONF_PERIMETER,
    DEFAULT_CO2_THRESHOLD,
    DOMAIN,
    PERIMETER_FRANCE,
    REGIONS,
    perimeter_name,
)
from .coordinator import Eco2mixConfigEntry

_LOGGER = logging.getLogger(__name__)

PERIMETER_OPTIONS = [
    SelectOptionDict(value=PERIMETER_FRANCE, label="France"),
    *(
        SelectOptionDict(value=code, label=name)
        for code, name in sorted(REGIONS.items(), key=lambda item: item[1])
    ),
]


class Eco2mixConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RTE éCO2mix."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick France or a region."""
        errors: dict[str, str] = {}
        if user_input is not None:
            perimeter = user_input[CONF_PERIMETER]
            await self.async_set_unique_id(perimeter)
            self._abort_if_unique_id_configured()
            client = Eco2mixClient(async_get_clientsession(self.hass), perimeter)
            try:
                await client.async_get_data(dt_util.utcnow())
            except Eco2mixError as err:
                _LOGGER.debug("Cannot fetch éCO2mix data: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=perimeter_name(perimeter), data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PERIMETER, default=PERIMETER_FRANCE
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=PERIMETER_OPTIONS,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Eco2mixConfigEntry) -> Eco2mixOptionsFlow:
        """Return the options flow."""
        return Eco2mixOptionsFlow()

    @classmethod
    @callback
    def async_supports_options_flow(cls, config_entry: Eco2mixConfigEntry) -> bool:
        """Only France has options: the CO2 threshold."""
        return config_entry.data[CONF_PERIMETER] == PERIMETER_FRANCE


class Eco2mixOptionsFlow(OptionsFlowWithReload):
    """Set the CO2 threshold of the low-carbon binary sensor."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_CO2_THRESHOLD: int(user_input[CONF_CO2_THRESHOLD])}
            )

        current = self.config_entry.options.get(
            CONF_CO2_THRESHOLD, DEFAULT_CO2_THRESHOLD
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CO2_THRESHOLD, default=current): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=200,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="gCO2eq/kWh",
                        )
                    )
                }
            ),
        )
