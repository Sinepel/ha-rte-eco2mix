"""Fixtures for RTE éCO2mix tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from yarl import URL

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
    mock_forecast(aioclient_mock)
    aioclient_mock.get(NATIONAL_URL, json=load_fixture("national.json"))
    aioclient_mock.get(REGIONAL_URL, json=load_fixture("regional_32.json"))
    return aioclient_mock


def mock_forecast(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock forecast queries; they share the national URL, so match on the query.

    Register before the catch-all national mock: the first match wins.
    """
    for query, fixture in (
        ({"order_by": "prevision_j desc"}, "peak_today.json"),
        ({"order_by": "prevision_j1 desc"}, "peak_tomorrow.json"),
        ({"group_by": "hour(date_heure) as h"}, "co2_profile.json"),
    ):
        aioclient_mock.get(
            URL(NATIONAL_URL).with_query(query), json=load_fixture(fixture)
        )


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
