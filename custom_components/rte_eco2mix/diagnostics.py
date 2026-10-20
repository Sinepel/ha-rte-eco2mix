"""Diagnostics for RTE éCO2mix."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import Eco2mixConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: Eco2mixConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry (public data only, nothing to redact)."""
    data = entry.runtime_data.data
    return {
        "entry_data": dict(entry.data),
        "entry_options": dict(entry.options),
        "time": data.time.isoformat(),
        "values": data.values,
        "co2_history": data.co2_history,
    }
