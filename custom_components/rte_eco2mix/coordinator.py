"""Data update coordinator for RTE éCO2mix."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import Eco2mixClient, Eco2mixData, Eco2mixError
from .const import CONF_PERIMETER, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type Eco2mixConfigEntry = ConfigEntry[Eco2mixCoordinator]


class Eco2mixCoordinator(DataUpdateCoordinator[Eco2mixData]):
    """Poll the éCO2mix API every 15 minutes."""

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
