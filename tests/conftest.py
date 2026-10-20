"""Fixtures for RTE éCO2mix tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.rte_eco2mix.api import (
    API_URL,
    DATASET_NATIONAL,
    DATASET_REGIONAL,
)
from custom_components.rte_eco2mix.const import CONF_PERIMETER, DOMAIN, PERIMETER_FRANCE

FIXTURES = Path(__file__).parent / "fixtures"
NATIONAL_URL = API_URL.format(dataset=DATASET_NATIONAL)
REGIONAL_URL = API_URL.format(dataset=DATASET_REGIONAL)


def load_fixture(name: str) -> dict:
    """Load a JSON fixture."""
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in every test."""
    return


@pytest.fixture
def mock_api(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock both éCO2mix datasets with real recorded responses."""
    aioclient_mock.get(NATIONAL_URL, json=load_fixture("national.json"))
    aioclient_mock.get(REGIONAL_URL, json=load_fixture("regional_32.json"))
    return aioclient_mock


@pytest.fixture
def france_entry() -> MockConfigEntry:
    """Config entry for France."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="France",
        unique_id=PERIMETER_FRANCE,
        data={CONF_PERIMETER: PERIMETER_FRANCE},
    )


@pytest.fixture
def region_entry() -> MockConfigEntry:
    """Config entry for Hauts-de-France."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Hauts-de-France",
        unique_id="32",
        data={CONF_PERIMETER: "32"},
    )
