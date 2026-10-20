"""Sensors for RTE éCO2mix."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
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
from homeassistant.util import dt as dt_util

from .api import PARIS, Eco2mixData, Eco2mixForecast, Eco2mixPeak
from .const import PERIMETER_FRANCE
from .coordinator import (
    Eco2mixConfigEntry,
    Eco2mixCoordinator,
    Eco2mixForecastCoordinator,
)
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


def next_typical_cleanest_hour(
    profile: dict[int, float], now: datetime
) -> datetime | None:
    """Return the start of the next occurrence of the typically cleanest hour.

    The current hour counts as "next" while it is still running.
    """
    if not profile:
        return None
    best = min(profile, key=lambda hour: profile[hour])
    local = now.astimezone(PARIS)
    day = local.date() if best >= local.hour else local.date() + timedelta(days=1)
    return datetime.combine(day, time(best), tzinfo=PARIS)


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


@dataclass(frozen=True, kw_only=True)
class Eco2mixForecastSensorDescription(SensorEntityDescription):
    """Describe an éCO2mix forecast sensor."""

    value_fn: Callable[[Eco2mixForecast], float | datetime | None]
    attributes_fn: Callable[[Eco2mixForecast], dict[str, Any]] = lambda _: {}


def _peak_attributes(peak: Eco2mixPeak | None) -> dict[str, Any]:
    return {"time": peak.time.isoformat()} if peak else {}


def _peak(key: str, attr: str) -> Eco2mixForecastSensorDescription:
    return Eco2mixForecastSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.MEGA_WATT,
        suggested_display_precision=0,
        value_fn=lambda f: getattr(f, attr).power if getattr(f, attr) else None,
        attributes_fn=lambda f: _peak_attributes(getattr(f, attr)),
    )


FORECAST = (
    _peak("consumption_peak_today", "peak_today"),
    _peak("consumption_peak_tomorrow", "peak_tomorrow"),
    Eco2mixForecastSensorDescription(
        key="typical_cleanest_hour",
        translation_key="typical_cleanest_hour",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda f: next_typical_cleanest_hour(f.co2_profile, dt_util.now()),
        attributes_fn=lambda f: {
            "typical_co2_intensity": min(f.co2_profile.values(), default=None),
            "hourly_profile": f.co2_profile,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Eco2mixConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up éCO2mix sensors."""
    coordinator = entry.runtime_data.realtime
    specific = NATIONAL if coordinator.perimeter == PERIMETER_FRANCE else REGIONAL
    entities: list[SensorEntity] = [
        Eco2mixSensor(coordinator, description) for description in (*COMMON, *specific)
    ]
    if forecast := entry.runtime_data.forecast:
        entities.extend(
            Eco2mixForecastSensor(forecast, description) for description in FORECAST
        )
    async_add_entities(entities)


class Eco2mixSensor(Eco2mixEntity[Eco2mixCoordinator], SensorEntity):
    """An éCO2mix sensor."""

    entity_description: Eco2mixSensorDescription

    def __init__(
        self, coordinator: Eco2mixCoordinator, description: Eco2mixSensorDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | datetime | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)


class Eco2mixForecastSensor(Eco2mixEntity[Eco2mixForecastCoordinator], SensorEntity):
    """An éCO2mix forecast sensor (France only)."""

    entity_description: Eco2mixForecastSensorDescription

    def __init__(
        self,
        coordinator: Eco2mixForecastCoordinator,
        description: Eco2mixForecastSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | datetime | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return self.entity_description.attributes_fn(self.coordinator.data)
