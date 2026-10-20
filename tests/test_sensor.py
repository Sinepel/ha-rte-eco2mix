"""Tests for RTE éCO2mix entities."""

from __future__ import annotations

from datetime import UTC, datetime

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.rte_eco2mix.api import PARIS, Eco2mixData
from custom_components.rte_eco2mix.const import SCAN_INTERVAL
from custom_components.rte_eco2mix.sensor import (
    co2_percentile,
    next_typical_cleanest_hour,
)

from .conftest import NATIONAL_URL, load_fixture

LATEST_NATIONAL = load_fixture("national.json")["results"][0]
LATEST_REGIONAL = load_fixture("regional_32.json")["results"][0]


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_france_sensors(
    hass: HomeAssistant, mock_api, france_entry: MockConfigEntry
) -> None:
    """France exposes CO2 intensity, production and the low-carbon signal."""
    await _setup(hass, france_entry)

    co2 = hass.states.get("sensor.eco2mix_france_co2_intensity")
    assert float(co2.state) == LATEST_NATIONAL["taux_co2"]
    assert co2.attributes["unit_of_measurement"] == "gCO2eq/kWh"

    nuclear = hass.states.get("sensor.eco2mix_france_nuclear")
    assert float(nuclear.state) == LATEST_NATIONAL["nucleaire"]
    assert nuclear.attributes["unit_of_measurement"] == "MW"

    # Default threshold 50 g, fixture is 25 g.
    low_carbon = hass.states.get("binary_sensor.eco2mix_france_low_carbon_electricity")
    assert low_carbon.state == "on"
    assert low_carbon.attributes["threshold"] == 50

    share = float(hass.states.get("sensor.eco2mix_france_low_carbon_share").state)
    assert 0 < share <= 100

    assert hass.states.get("sensor.eco2mix_france_fossil_thermal") is None


async def test_region_sensors(
    hass: HomeAssistant,
    mock_api,
    region_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Regions expose production but no CO2 intensity."""
    await _setup(hass, region_entry)

    consumption = hass.states.get("sensor.eco2mix_hauts_de_france_consumption")
    assert float(consumption.state) == LATEST_REGIONAL["consommation"]
    assert hass.states.get("sensor.eco2mix_hauts_de_france_fossil_thermal") is not None
    assert hass.states.get("sensor.eco2mix_hauts_de_france_co2_intensity") is None
    assert (
        hass.states.get("binary_sensor.eco2mix_hauts_de_france_low_carbon_electricity")
        is None
    )

    coverage = entity_registry.async_get(
        "sensor.eco2mix_hauts_de_france_consumption_covered_by_nuclear"
    )
    assert coverage.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_update_failure_marks_unavailable(
    hass: HomeAssistant,
    mock_api,
    aioclient_mock: AiohttpClientMocker,
    france_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Entities become unavailable when the API fails, and recover."""
    await _setup(hass, france_entry)

    aioclient_mock.clear_requests()
    aioclient_mock.get(NATIONAL_URL, status=429)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.eco2mix_france_co2_intensity").state
        == STATE_UNAVAILABLE
    )

    aioclient_mock.clear_requests()
    aioclient_mock.get(NATIONAL_URL, json=load_fixture("national.json"))
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.eco2mix_france_co2_intensity").state
        != STATE_UNAVAILABLE
    )


async def test_setup_retry_on_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    france_entry: MockConfigEntry,
) -> None:
    """Setup is retried when the API is down."""
    aioclient_mock.get(NATIONAL_URL, status=500)
    france_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(france_entry.entry_id)
    assert france_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload(
    hass: HomeAssistant, mock_api, france_entry: MockConfigEntry
) -> None:
    """The entry unloads cleanly."""
    await _setup(hass, france_entry)
    assert await hass.config_entries.async_unload(france_entry.entry_id)
    assert france_entry.state is ConfigEntryState.NOT_LOADED


def test_co2_percentile() -> None:
    """0 % = cleanest slot of the last 24 h, 100 % excluded by strict comparison."""
    time = datetime(2026, 10, 20, tzinfo=UTC)
    history = [10, 20, 30, 40]
    assert co2_percentile(Eco2mixData(time, {"taux_co2": 10}, history)) == 0
    assert co2_percentile(Eco2mixData(time, {"taux_co2": 30}, history)) == 50
    assert co2_percentile(Eco2mixData(time, {"taux_co2": 40}, history)) == 75
    assert co2_percentile(Eco2mixData(time, {"taux_co2": None}, history)) is None
    assert co2_percentile(Eco2mixData(time, {"taux_co2": 10}, [])) is None


async def test_diagnostics(
    hass: HomeAssistant, mock_api, france_entry: MockConfigEntry
) -> None:
    """Diagnostics expose the latest slot and the CO2 history."""
    from custom_components.rte_eco2mix.diagnostics import (  # noqa: PLC0415
        async_get_config_entry_diagnostics,
    )

    await _setup(hass, france_entry)
    diag = await async_get_config_entry_diagnostics(hass, france_entry)
    assert diag["values"]["taux_co2"] == LATEST_NATIONAL["taux_co2"]
    assert len(diag["co2_history"]) > 0


async def test_forecast_sensors(
    hass: HomeAssistant, mock_api, france_entry: MockConfigEntry
) -> None:
    """France exposes consumption peak forecasts and the typical cleanest hour."""
    await _setup(hass, france_entry)

    peak_today = load_fixture("peak_today.json")["results"][0]
    state = hass.states.get("sensor.eco2mix_france_consumption_peak_forecast_today")
    assert float(state.state) == peak_today["prevision_j"]
    assert state.attributes["time"] == peak_today["date_heure"]

    peak_tomorrow = load_fixture("peak_tomorrow.json")["results"][0]
    state = hass.states.get("sensor.eco2mix_france_consumption_peak_forecast_tomorrow")
    assert float(state.state) == peak_tomorrow["prevision_j1"]

    state = hass.states.get("sensor.eco2mix_france_typical_cleanest_hour")
    profile = {r["h"]: r["co2"] for r in load_fixture("co2_profile.json")["results"]}
    best = min(profile, key=profile.get)
    cleanest = datetime.fromisoformat(state.state).astimezone(PARIS)
    assert cleanest.hour == best
    assert state.attributes["typical_co2_intensity"] == round(profile[best], 1)
    assert len(state.attributes["hourly_profile"]) == 24


async def test_no_forecast_for_regions(
    hass: HomeAssistant, mock_api, region_entry: MockConfigEntry
) -> None:
    """Regions have no forecast sensors."""
    await _setup(hass, region_entry)
    assert (
        hass.states.get("sensor.eco2mix_hauts_de_france_typical_cleanest_hour") is None
    )


def test_next_typical_cleanest_hour() -> None:
    """The next occurrence is today if the hour is not over, else tomorrow."""
    profile = {3: 20.0, 14: 22.0, 20: 45.0}
    at = datetime(2026, 10, 20, 2, 30, tzinfo=PARIS)
    assert next_typical_cleanest_hour(profile, at) == datetime(
        2026, 10, 20, 3, tzinfo=PARIS
    )
    at = datetime(2026, 10, 20, 3, 45, tzinfo=PARIS)
    assert next_typical_cleanest_hour(profile, at) == datetime(
        2026, 10, 20, 3, tzinfo=PARIS
    )
    at = datetime(2026, 10, 20, 4, 0, tzinfo=PARIS)
    assert next_typical_cleanest_hour(profile, at) == datetime(
        2026, 10, 21, 3, tzinfo=PARIS
    )
    assert next_typical_cleanest_hour({}, at) is None


async def test_forecast_missing_fields(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    france_entry: MockConfigEntry,
) -> None:
    """Empty or partial forecast answers give unknown sensors, not a failed setup."""
    # One minimal slot answers every query: no forecast fields, no profile rows.
    slot = {
        "date_heure": "2026-10-20T20:45:00+00:00",
        "consommation": 1,
        "taux_co2": 20,
    }
    aioclient_mock.get(NATIONAL_URL, json={"results": [slot]})
    await _setup(hass, france_entry)
    assert france_entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.get("sensor.eco2mix_france_consumption_peak_forecast_today").state
        == "unknown"
    )
    assert (
        hass.states.get("sensor.eco2mix_france_typical_cleanest_hour").state
        == "unknown"
    )
