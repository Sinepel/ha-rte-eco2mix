"""Constants for the RTE éCO2mix integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "rte_eco2mix"

CONF_PERIMETER: Final = "perimeter"
CONF_CO2_THRESHOLD: Final = "co2_threshold"

DEFAULT_CO2_THRESHOLD: Final = 50  # gCO2eq/kWh

PERIMETER_FRANCE: Final = "france"

# INSEE region code -> name, as published by RTE in eco2mix-regional-tr.
REGIONS: Final[dict[str, str]] = {
    "11": "Île-de-France",
    "24": "Centre-Val de Loire",
    "27": "Bourgogne-Franche-Comté",
    "28": "Normandie",
    "32": "Hauts-de-France",
    "44": "Grand Est",
    "52": "Pays de la Loire",
    "53": "Bretagne",
    "75": "Nouvelle-Aquitaine",
    "76": "Occitanie",
    "84": "Auvergne-Rhône-Alpes",
    "93": "Provence-Alpes-Côte d'Azur",
}

# RTE publishes a new 15-minute slot roughly every 15 minutes.
SCAN_INTERVAL: Final = timedelta(minutes=15)

ATTRIBUTION: Final = "Data provided by RTE éCO2mix (Licence Ouverte v2.0)"


def perimeter_name(perimeter: str) -> str:
    """Return the display name of a perimeter."""
    return "France" if perimeter == PERIMETER_FRANCE else REGIONS[perimeter]
