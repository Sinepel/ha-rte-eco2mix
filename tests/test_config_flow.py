"""Tests for the RTE éCO2mix config and options flows."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.rte_eco2mix.const import (
    CONF_CO2_THRESHOLD,
    CONF_PERIMETER,
    DOMAIN,
    PERIMETER_FRANCE,
)

from .conftest import NATIONAL_URL, REGIONAL_URL


async def test_create_france(hass: HomeAssistant, mock_api) -> None:
    """France can be added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PERIMETER: PERIMETER_FRANCE}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "France"
    assert result["data"] == {CONF_PERIMETER: PERIMETER_FRANCE}
    assert result["result"].unique_id == PERIMETER_FRANCE


async def test_create_region(hass: HomeAssistant, mock_api) -> None:
    """A region can be added and is titled with its name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PERIMETER: "32"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hauts-de-France"


async def test_already_configured(
    hass: HomeAssistant, mock_api, france_entry: MockConfigEntry
) -> None:
    """The same perimeter cannot be added twice."""
    france_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PERIMETER: PERIMETER_FRANCE}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_cannot_connect_then_recover(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An API error shows an error and the user can retry."""
    aioclient_mock.get(NATIONAL_URL, status=500)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PERIMETER: PERIMETER_FRANCE}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        NATIONAL_URL,
        json={
            "results": [{"date_heure": "2026-10-20T20:45:00+00:00", "consommation": 1}]
        },
    )
    aioclient_mock.get(REGIONAL_URL, json={"results": []})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PERIMETER: PERIMETER_FRANCE}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow(
    hass: HomeAssistant, mock_api, france_entry: MockConfigEntry
) -> None:
    """The CO2 threshold can be changed and the entry reloads with it."""
    france_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(france_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(france_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CO2_THRESHOLD: 20}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert france_entry.options == {CONF_CO2_THRESHOLD: 20}

    state = hass.states.get("binary_sensor.eco2mix_france_low_carbon_electricity")
    assert state.attributes["threshold"] == 20
    assert state.state == "off"  # fixture CO2 intensity is 25 g


async def test_no_options_for_regions(
    hass: HomeAssistant, region_entry: MockConfigEntry
) -> None:
    """Regions have no CO2 data, so no options."""
    region_entry.add_to_hass(hass)
    assert not region_entry.supports_options
