"""Binary sensor for RTE éCO2mix: is electricity low-carbon right now?"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_CO2_THRESHOLD, DEFAULT_CO2_THRESHOLD
from .coordinator import Eco2mixConfigEntry, Eco2mixCoordinator
from .entity import Eco2mixEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Eco2mixConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the low-carbon binary sensor (France only)."""
    threshold = entry.options.get(CONF_CO2_THRESHOLD, DEFAULT_CO2_THRESHOLD)
    async_add_entities([Eco2mixLowCarbonSensor(entry.runtime_data, threshold)])


class Eco2mixLowCarbonSensor(Eco2mixEntity, BinarySensorEntity):
    """On when the national CO2 intensity is at or below the threshold."""

    _attr_translation_key = "low_carbon"

    def __init__(self, coordinator: Eco2mixCoordinator, threshold: int) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, "low_carbon")
        self._threshold = threshold

    @property
    def is_on(self) -> bool | None:
        """Return True when electricity is low-carbon."""
        co2 = self.coordinator.data.values.get("taux_co2")
        return None if co2 is None else co2 <= self._threshold

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the threshold so automations and users can see it."""
        return {"threshold": self._threshold}
