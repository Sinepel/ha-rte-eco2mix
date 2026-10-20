"""Data update coordinators for RTE éCO2mix."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import Eco2mixClient, Eco2mixData, Eco2mixError, Eco2mixForecast
from .const import CONF_PERIMETER, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Forecasts are published once a day and the 7-day profile moves slowly.
FORECAST_INTERVAL = timedelta(hours=1)


@dataclass
class Eco2mixRuntimeData:
    """Coordinators of a config entry; forecast is None for regions."""

    realtime: Eco2mixCoordinator
    forecast: Eco2mixForecastCoordinator | None


type Eco2mixConfigEntry = ConfigEntry[Eco2mixRuntimeData]


class Eco2mixCoordinator(DataUpdateCoordinator[Eco2mixData]):
    """Poll the latest éCO2mix slot every 15 minutes."""

    config_entry: Eco2mixConfigEntry

    def __init__(self, hass: HomeAssistant, entry: Eco2mixConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.perimeter: str = entry.data[CONF_PERIMETER]
        self.client = Eco2mixClient(async_get_clientsession(hass), self.perimeter)

    async def _async_update_data(self) -> Eco2mixData:
        """Fetch the latest data."""
        try:
            return await self.client.async_get_data(dt_util.utcnow())
        except Eco2mixError as err:
            raise UpdateFailed(str(err)) from err


class Eco2mixForecastCoordinator(DataUpdateCoordinator[Eco2mixForecast]):
    """Poll consumption forecasts and the CO2 profile every hour (France only)."""

    config_entry: Eco2mixConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: Eco2mixConfigEntry, client: Eco2mixClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_forecast",
            update_interval=FORECAST_INTERVAL,
        )
        self.perimeter: str = entry.data[CONF_PERIMETER]
        self.client = client

    async def _async_update_data(self) -> Eco2mixForecast:
        """Fetch forecasts."""
        try:
            return await self.client.async_get_forecast(dt_util.utcnow())
        except Eco2mixError as err:
            raise UpdateFailed(str(err)) from err
