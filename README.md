# RTE éCO2mix for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Validate](https://github.com/Sinepel/ha-rte-eco2mix/actions/workflows/validate.yml/badge.svg)](https://github.com/Sinepel/ha-rte-eco2mix/actions/workflows/validate.yml)
[![Tests](https://github.com/Sinepel/ha-rte-eco2mix/actions/workflows/tests.yml/badge.svg)](https://github.com/Sinepel/ha-rte-eco2mix/actions/workflows/tests.yml)

Real-time French electricity data from [RTE éCO2mix](https://www.rte-france.com/eco2mix) in Home Assistant: **CO2 intensity**, production by source, consumption and exchanges, for **France or any of the 12 mainland regions**.

Its main purpose is to help you **run appliances when electricity is low-carbon**: a binary sensor and a 24-hour percentile tell your automations when it is a good time to start the washing machine, the dishwasher or the EV charger.

*🇫🇷 Version française plus bas.*

## Features

- France and/or any mainland region (one entry per perimeter), set up from the UI
- CO2 intensity of French electricity (gCO2eq/kWh)
- **Low-carbon electricity** binary sensor with a configurable threshold
- **CO2 intensity 24 h percentile**: 0 % means now is the cleanest moment of the last 24 hours
- Production by source (nuclear, wind, solar, hydro, bioenergy, gas, coal, oil or fossil thermal for regions), consumption, physical exchanges
- Low-carbon and renewable shares of production
- Regions: share of the regional consumption covered by each source (disabled by default)
- No API key, no account, updated every 15 minutes

## Installation

### HACS

1. In HACS, open the menu ⋮ → **Custom repositories**, add `https://github.com/Sinepel/ha-rte-eco2mix` as an **Integration**.
2. Download **RTE éCO2mix** and restart Home Assistant.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Sinepel&repository=ha-rte-eco2mix&category=integration)

### Manual

Copy `custom_components/rte_eco2mix` into your `config/custom_components/` folder and restart Home Assistant.

Requires Home Assistant 2026.3 or newer.

## Configuration

**Settings → Devices & services → Add integration → RTE éCO2mix**, then choose **France** or a region.
Add the integration again to follow another perimeter. CO2 intensity is only published for France, so add France if you want the low-carbon signal.

Options (France only): the CO2 intensity threshold of the low-carbon binary sensor, 50 gCO2eq/kWh by default.

## Entities

| Entity | France | Region | Unit |
|---|:-:|:-:|---|
| CO2 intensity | ✓ | | gCO2eq/kWh |
| CO2 intensity 24 h percentile | ✓ | | % |
| Low-carbon electricity (binary sensor) | ✓ | | on/off |
| Consumption | ✓ | ✓ | MW |
| Nuclear, wind, solar, hydro, bioenergy | ✓ | ✓ | MW |
| Gas, coal, oil | ✓ | | MW |
| Fossil thermal | | ✓ | MW |
| Physical exchanges (positive = import) | ✓ | ✓ | MW |
| Pumped storage *(disabled by default)* | ✓ | ✓ | MW |
| Low-carbon share, renewable share | ✓ | ✓ | % |
| Consumption covered by each source *(disabled by default)* | | ✓ | % |
| Data time (diagnostic) | ✓ | ✓ | timestamp |

RTE publishes data with a delay of about 30 minutes; *Data time* shows the 15-minute slot currently displayed.

## Automation example

Start the washing machine (here through a smart plug, with the machine in delayed-start mode) as soon as electricity is in the cleanest 20 % of the last 24 hours, but no later than 6 am:

```yaml
automation:
  - alias: "Washing machine on low-carbon electricity"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.eco2mix_france_co2_intensity_24_h_percentile
        below: 20
      - trigger: time
        at: "06:00:00"
    conditions:
      - condition: state
        entity_id: input_boolean.washing_machine_ready
        state: "on"
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.washing_machine_plug
      - action: input_boolean.turn_off
        target:
          entity_id: input_boolean.washing_machine_ready
```

A simpler alternative is to trigger on `binary_sensor.eco2mix_france_low_carbon_electricity` turning `on`.

## Data source

Data © [RTE](https://www.rte-france.com/), [éCO2mix](https://odre.opendatasoft.com/explore/dataset/eco2mix-national-tr/) real-time datasets published on the ODRÉ open data platform under the [Licence Ouverte v2.0 (Etalab)](https://www.etalab.gouv.fr/licence-ouverte-open-licence/).
This project is not affiliated with or endorsed by RTE.

The API allows 50,000 calls per month per dataset; this integration makes one call every 15 minutes per perimeter.

---

## 🇫🇷 En français

Données en temps réel de l'électricité française (RTE éCO2mix) : **taux de CO2**, production par filière, consommation et échanges, pour **la France ou l'une des 12 régions métropolitaines continentales**.

Objectif principal : **lancer vos appareils quand l'électricité est bas carbone**. Le capteur binaire « Électricité bas carbone » (seuil réglable) et le « Centile du taux de CO2 sur 24 h » (0 % = moment le plus propre des dernières 24 h) servent de déclencheurs pour vos automatisations : lave-linge, lave-vaisselle, recharge de voiture…

Installation : HACS → ⋮ → Dépôts personnalisés → `https://github.com/Sinepel/ha-rte-eco2mix` (Intégration), puis **Paramètres → Appareils et services → Ajouter une intégration → RTE éCO2mix**. Ajoutez la France pour le taux de CO2, et votre région si vous le souhaitez. Aucune clé d'API, mise à jour toutes les 15 minutes.

## License

[MIT](LICENSE)
