# ETDS Hardware Integration

The repository you provided contains only the website; it does not contain the meter firmware, circuit diagram, sensor models, pin mapping, or communication protocol. Therefore this release provides a real production-style **hardware ingestion contract** rather than pretending to know your exact electronics.

## Recommended physical signal path

For theft detection that can be defended technically, use a source/feeder measurement plus downstream meter measurement(s):

`Grid/Feeder CT + Voltage sensor → ESP32/MCU → HTTPS → ETDS backend`

and either:

`Downstream meter/CT → same MCU`  or  `Downstream smart meter → Modbus/RS-485 gateway → ESP32`

The backend compares source and load power. Add a tamper input for enclosure/bypass events.

## Required device contract

Every device posts to:

`POST /api/hardware/telemetry`

with `Authorization: Bearer DEVICE_API_KEY`.

At minimum send:

- `meter_id`
- `voltage`
- `current`
- `power_kw`
- `tamper`
- `latitude` / `longitude` (or configure coordinates once in the database)

For theft imbalance detection also send:

- `source_power_kw`
- `load_power_kw`

The included `firmware/esp32_etds/esp32_etds.ino` is an example and must be calibrated for the actual electrical sensors before field use.
