"""Client for the RTE éCO2mix open data API (ODRÉ)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from .const import PERIMETER_FRANCE

API_URL = (
    "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/{dataset}/records"
)
DATASET_NATIONAL = "eco2mix-national-tr"
DATASET_REGIONAL = "eco2mix-regional-tr"

# 24 hours of 15-minute slots fit in one page (API maximum is 100 records).
HISTORY = timedelta(hours=24)
# Window used to build the typical hourly CO2 profile.
PROFILE_HISTORY = timedelta(days=7)
TIMEOUT = aiohttp.ClientTimeout(total=30)
PARIS = ZoneInfo("Europe/Paris")


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


@dataclass(frozen=True, slots=True)
class Eco2mixPeak:
    """Forecast consumption peak of a day."""

    time: datetime
    power: int


@dataclass(frozen=True, slots=True)
class Eco2mixForecast:
    """RTE consumption forecasts and the typical hourly CO2 profile."""

    peak_today: Eco2mixPeak | None
    peak_tomorrow: Eco2mixPeak | None
    # Local hour (Europe/Paris) -> average CO2 intensity over the last 7 days.
    co2_profile: dict[int, float]


class Eco2mixClient:
    """Fetch éCO2mix real-time data for France or one region."""

    def __init__(self, session: aiohttp.ClientSession, perimeter: str) -> None:
        """Initialize the client."""
        self._session = session
        self._perimeter = perimeter

    async def _async_get(self, dataset: str, params: dict[str, Any]) -> list[dict]:
        """Query a dataset and return its records."""
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
        return payload.get("results") or []

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
        records = await self._async_get(
            dataset, {"where": where, "order_by": "date_heure desc", "limit": 100}
        )
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

    async def _async_get_peak(self, day: str, field: str) -> Eco2mixPeak | None:
        """Return the highest forecast slot of a local day (YYYY-MM-DD)."""
        records = await self._async_get(
            DATASET_NATIONAL,
            {
                "where": f"date = '{day}' and {field} is not null",
                "order_by": f"{field} desc",
                "select": f"date_heure, {field}",
                "limit": 1,
            },
        )
        if not records or records[0].get(field) is None:
            return None
        return Eco2mixPeak(
            time=datetime.fromisoformat(records[0]["date_heure"]),
            power=records[0][field],
        )

    async def async_get_forecast(self, now: datetime) -> Eco2mixForecast:
        """Return consumption peak forecasts and the 7-day hourly CO2 profile.

        Only available for France: regional data has neither forecasts nor CO2.
        """
        today = now.astimezone(PARIS).date()
        profile = await self._async_get(
            DATASET_NATIONAL,
            {
                "where": (
                    f"date_heure >= date'{(now - PROFILE_HISTORY).isoformat()}'"
                    " and taux_co2 is not null"
                ),
                "select": "avg(taux_co2) as co2",
                "group_by": "hour(date_heure) as h",
                "timezone": "Europe/Paris",
                "limit": 24,
            },
        )
        return Eco2mixForecast(
            peak_today=await self._async_get_peak(today.isoformat(), "prevision_j"),
            peak_tomorrow=await self._async_get_peak(
                (today + timedelta(days=1)).isoformat(), "prevision_j1"
            ),
            co2_profile={
                int(r["h"]): round(r["co2"], 1)
                for r in profile
                if r.get("h") is not None and r.get("co2") is not None
            },
        )
