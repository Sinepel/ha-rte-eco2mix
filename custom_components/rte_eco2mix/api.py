"""Client for the RTE éCO2mix open data API (ODRÉ)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from .const import PERIMETER_FRANCE

API_URL = (
    "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/{dataset}/records"
)
DATASET_NATIONAL = "eco2mix-national-tr"
DATASET_REGIONAL = "eco2mix-regional-tr"

# 24 hours of 15-minute slots fit in one page (API maximum is 100 records).
HISTORY = timedelta(hours=24)
TIMEOUT = aiohttp.ClientTimeout(total=30)


class Eco2mixError(Exception):
    """Raised when the API cannot be reached or returns an error."""


class Eco2mixRateLimitError(Eco2mixError):
    """Raised when the API quota is exhausted."""


@dataclass(frozen=True, slots=True)
class Eco2mixData:
    """Latest published slot plus the CO2 intensities of the last 24 hours."""

    time: datetime
    values: dict[str, Any]
    co2_history: list[int]


class Eco2mixClient:
    """Fetch éCO2mix real-time data for France or one region."""

    def __init__(self, session: aiohttp.ClientSession, perimeter: str) -> None:
        """Initialize the client."""
        self._session = session
        self._perimeter = perimeter

    async def async_get_data(self, now: datetime) -> Eco2mixData:
        """Return the latest slot with data and the last 24 hours of CO2 values."""
        national = self._perimeter == PERIMETER_FRANCE
        dataset = DATASET_NATIONAL if national else DATASET_REGIONAL
        # Future slots exist with empty values, so only keep published ones.
        where = (
            f"date_heure >= date'{(now - HISTORY).isoformat()}'"
            " and consommation is not null"
        )
        if not national:
            where += f" and code_insee_region = '{self._perimeter}'"
        params = {
            "where": where,
            "order_by": "date_heure desc",
            "limit": 100,
        }
        try:
            async with self._session.get(
                API_URL.format(dataset=dataset), params=params, timeout=TIMEOUT
            ) as resp:
                if resp.status == 429:
                    raise Eco2mixRateLimitError("API quota exceeded")
                if resp.status != 200:
                    raise Eco2mixError(f"Unexpected HTTP status {resp.status}")
                payload = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise Eco2mixError(f"Cannot reach the éCO2mix API: {err}") from err

        records = payload.get("results") or []
        if not records:
            raise Eco2mixError("No published data in the last 24 hours")

        latest = records[0]
        return Eco2mixData(
            time=datetime.fromisoformat(latest["date_heure"]),
            values=latest,
            co2_history=[
                r["taux_co2"] for r in records if r.get("taux_co2") is not None
            ],
        )
