"""The RTE éCO2mix integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_PERIMETER, PERIMETER_FRANCE
from .coordinator import (
    Eco2mixConfigEntry,
    Eco2mixCoordinator,
    Eco2mixForecastCoordinator,
    Eco2mixRuntimeData,
)

PLATFORMS_FRANCE = [Platform.BINARY_SENSOR, Platform.SENSOR]
PLATFORMS_REGION = [Platform.SENSOR]


def _platforms(entry: Eco2mixConfigEntry) -> list[Platform]:
    # CO2 intensity is only published nationally, so regions get no binary sensor.
    if entry.data[CONF_PERIMETER] == PERIMETER_FRANCE:
        return PLATFORMS_FRANCE
    return PLATFORMS_REGION


async def async_setup_entry(hass: HomeAssistant, entry: Eco2mixConfigEntry) -> bool:
    """Set up RTE éCO2mix from a config entry."""
    realtime = Eco2mixCoordinator(hass, entry)
    await realtime.async_config_entry_first_refresh()
    forecast = None
    if realtime.perimeter == PERIMETER_FRANCE:
        forecast = Eco2mixForecastCoordinator(hass, entry, realtime.client)
        await forecast.async_config_entry_first_refresh()
    entry.runtime_data = Eco2mixRuntimeData(realtime, forecast)
    await hass.config_entries.async_forward_entry_setups(entry, _platforms(entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Eco2mixConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _platforms(entry))
