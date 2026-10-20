"""Base entity for RTE éCO2mix."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, perimeter_name
from .coordinator import Eco2mixCoordinator, Eco2mixForecastCoordinator


class Eco2mixEntity[CoordinatorT: (Eco2mixCoordinator, Eco2mixForecastCoordinator)](
    CoordinatorEntity[CoordinatorT]
):
    """An entity bound to one éCO2mix perimeter (France or a region)."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: CoordinatorT, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        perimeter = coordinator.perimeter
        self._attr_unique_id = f"{perimeter}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, perimeter)},
            name=f"éCO2mix {perimeter_name(perimeter)}",
            manufacturer="RTE",
            model="éCO2mix",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.rte-france.com/eco2mix",
        )
