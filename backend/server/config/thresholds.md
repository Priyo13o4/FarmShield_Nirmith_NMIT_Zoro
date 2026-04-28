# FarmShield Threshold Registry

**THIS IS THE SINGLE SOURCE OF TRUTH.**
Any change to these thresholds must be reflected in BOTH the backend (`.env`) and the ESP32 firmware (`farmshield.ino`).

| Parameter      | Value  | Firmware Constant (`farmshield.ino`) | Backend Variable (`.env`) |
|----------------|--------|--------------------------------------|---------------------------|
| Soil dry       | 30.0%  | `TH_SOIL_LOW`                        | `ALERT_SOIL_DRY_PCT`      |
| Soil flood     | 85.0%  | *(Not in firmware)*                  | `ALERT_SOIL_FLOOD_PCT`    |
| Temp high      | 38.0°C | `TH_TEMP_HIGH`                       | `ALERT_TEMP_HIGH_C`       |
| pH low         | 5.5    | `TH_PH_LO`                           | `ALERT_PH_LOW`            |
| pH high        | 7.5    | `TH_PH_HI`                           | `ALERT_PH_HIGH`           |
| TDS high       | 1500   | `TH_TDS_HI`                          | `ALERT_TDS_HIGH_PPM`      |
| Rain dry       | 2500   | `TH_RAIN_DRY`                        | `ALERT_RAIN_DRY_RAW`      |

> **Note on Firmware Auto-Irrigation:**
> The firmware also has a `TH_SOIL_OK` (currently `60.0%`) which is used to stop the pump when in AUTO mode. This is an operational threshold, not an alert threshold, which is why it doesn't have a matching `.env` alert variable.

---

### Why does the backend evaluate these independently?
The ESP32 firmware includes a basic `alertMsg` string, but it suffers from structural limitations:
1. It uses an `else-if` chain, meaning if multiple conditions are met (e.g. Temp High AND pH Low), only one alert is generated.
2. Soil moisture is completely absent from the firmware's alert string logic.

Therefore, the backend **completely ignores the ESP32's alert string** and evaluates all raw sensor readings against the `.env` variables independently to ensure no alerts are missed.
