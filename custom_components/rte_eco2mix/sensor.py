"""Sensors for RTE éCO2mix."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import Eco2mixData
from .const import PERIMETER_FRANCE
from .coordinator import Eco2mixConfigEntry
from .entity import Eco2mixEntity

PARALLEL_UPDATES = 0

UNIT_CO2_INTENSITY = "gCO2eq/kWh"

RENEWABLE = ("eolien", "solaire", "hydraulique", "bioenergies")
LOW_CARBON = ("nucleaire", *RENEWABLE)
FOSSIL_NATIONAL = ("gaz", "charbon", "fioul")
FOSSIL_REGIONAL = ("thermique",)


def _num(values: dict[str, Any], key: str) -> float | None:
    """Return a numeric field; the API sometimes sends numbers as strings."""
    value = values.get(key)
    return None if value is None else float(value)


def _share(
    values: dict[str, Any], part: tuple[str, ...], fossil: tuple[str, ...]
) -> float | None:
    """Return the share of `part` in total production, in percent."""
    sources = {k: _num(values, k) for k in {*LOW_CARBON, *fossil}}
    if any(v is None for v in sources.values()):
        return None
    total = sum(sources.values())
    if total <= 0:
        return None
    return round(100 * sum(sources[k] for k in part) / total, 1)


def co2_percentile(data: Eco2mixData) -> float | None:
    """Return the share of the last 24 h slots that were cleaner than now.

    0 % means the current slot is the cleanest of the last 24 hours.
    """
    current = data.values.get("taux_co2")
    if current is None or not data.co2_history:
        return None
    cleaner = sum(1 for v in data.co2_history if v < current)
    return round(100 * cleaner / len(data.co2_history))


@dataclass(frozen=True, kw_only=True)
class Eco2mixSensorDescription(SensorEntityDescription):
    """Describe an éCO2mix sensor."""

    value_fn: Callable[[Eco2mixData], float | datetime | None]


def _power(key: str, field: str, **kwargs: Any) -> Eco2mixSensorDescription:
    return Eco2mixSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.MEGA_WATT,
        suggested_display_precision=0,
        value_fn=lambda d: _num(d.values, field),
        **kwargs,
    )


def _percent(
    key: str, value_fn: Callable[[Eco2mixData], float | None], **kwargs: Any
) -> Eco2mixSensorDescription:
    return Eco2mixSensorDescription(
        key=key,
        translation_key=key,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=value_fn,
        **kwargs,
    )


DATA_TIME = Eco2mixSensorDescription(
    key="data_time",
    translation_key="data_time",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda d: d.time,
)

COMMON = (
    _power("consumption", "consommation"),
    _power("nuclear", "nucleaire"),
    _power("wind", "eolien"),
    _power("solar", "solaire"),
    _power("hydro", "hydraulique"),
    _power("bioenergy", "bioenergies"),
    _power("pumped_storage", "pompage", entity_registry_enabled_default=False),
    _power("physical_exchanges", "ech_physiques"),
    DATA_TIME,
)

NATIONAL = (
    Eco2mixSensorDescription(
        key="co2_intensity",
        translation_key="co2_intensity",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UNIT_CO2_INTENSITY,
        suggested_display_precision=0,
        value_fn=lambda d: _num(d.values, "taux_co2"),
    ),
    _percent("co2_intensity_percentile", co2_percentile),
    _power("gas", "gaz"),
    _power("coal", "charbon"),
    _power("oil", "fioul"),
    _percent(
        "low_carbon_share",
        lambda d: _share(d.values, LOW_CARBON, FOSSIL_NATIONAL),
    ),
    _percent("renewable_share", lambda d: _share(d.values, RENEWABLE, FOSSIL_NATIONAL)),
)

REGIONAL = (
    _power("thermal", "thermique"),
    _percent(
        "low_carbon_share",
        lambda d: _share(d.values, LOW_CARBON, FOSSIL_REGIONAL),
    ),
    _percent("renewable_share", lambda d: _share(d.values, RENEWABLE, FOSSIL_REGIONAL)),
    # Share of the regional consumption covered by each source (RTE "TCO").
    *(
        _percent(
            f"coverage_{key}",
            lambda d, f=f"tco_{field}": _num(d.values, f),
            entity_registry_enabled_default=False,
        )
        for key, field in (
            ("nuclear", "nucleaire"),
            ("wind", "eolien"),
            ("solar", "solaire"),
            ("hydro", "hydraulique"),
            ("bioenergy", "bioenergies"),
            ("thermal", "thermique"),
        )
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Eco2mixConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up éCO2mix sensors."""
    coordinator = entry.runtime_data
    specific = NATIONAL if coordinator.perimeter == PERIMETER_FRANCE else REGIONAL
    async_add_entities(
        Eco2mixSensor(coordinator, description) for description in (*COMMON, *specific)
    )


class Eco2mixSensor(Eco2mixEntity, SensorEntity):
    """An éCO2mix sensor."""

    entity_description: Eco2mixSensorDescription

    def __init__(self, coordinator, description: Eco2mixSensorDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | datetime | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
