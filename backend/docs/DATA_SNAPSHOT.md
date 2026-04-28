# FarmShield — Data Snapshot & ML Feature Guide

This document provides a live snapshot of the data currently being ingested from the ESP32 hardware and stored in the TimescaleDB database. It serves as a reference for data scientists and developers building ML training models.

---

## 1. Data Interception (Live ESP32 to Database)

### What the ESP32 Broadcasts (MQTT JSON Payload)
This is the raw JSON structure published by the ESP32 to the `farmshield/data` MQTT topic every 5 seconds.

```json
{
  "device": "farmshield_node1",
  "temperature": 33.8,
  "humidity": 45.0,
  "soil": 11.9,
  "tds": 0.0,
  "ph": 14.0,
  "rain": 4095,
  "motion": true,
  "color": {
    "r": 170,
    "g": 277,
    "b": 280
  },
  "npk": {
    "n": 0,
    "p": 0,
    "k": 0,
    "ok": false
  },
  "pump": true,
  "mode": "AUTO",
  "alert": "Soil pH out of range",
  "uptime_s": 334
}
```

### What the Backend Stores (TimescaleDB `sensor_readings` table)
The backend intercepts this JSON, validates it via Pydantic, flattens the nested objects (`color` and `npk`), and stores it in the `sensor_readings` table. 

Here is an actual live row pulled from the database:

| Column Name | Data Type | Live Value | Notes for ML Training |
| :--- | :--- | :--- | :--- |
| `time` | TIMESTAMPTZ | `2026-04-28 18:30:09` | Primary index (Time-series). Use for temporal features (hour_of_day). |
| `device_id` | TEXT | `farmshield_node1` | Categorical feature if training across multiple nodes. |
| `soil_pct` | FLOAT8 | `11.93888` | Soil Moisture %. Extremely critical for irrigation models. |
| `ph` | FLOAT8 | `14.0` | Soil/Water pH. (Note: A value of 14 indicates sensor needs calibration/is disconnected). |
| `tds_ppm` | FLOAT8 | `0.0` | Total Dissolved Solids. Indicator of nutrient concentration. |
| `temp_c` | FLOAT8 | `33.8` | Ambient Temperature in Celsius. |
| `humidity_pct`| FLOAT8 | `45.0` | Ambient Humidity %. |
| `rain_raw` | INT4 | `4095` | Analog value. ~0 is soaking wet, 4095 is bone dry. |
| `motion` | BOOLEAN | `t` (true) | PIR sensor flag. Generally exclude from agronomic models. |
| `npk_n` | INT4 | `0` | Nitrogen level. |
| `npk_p` | INT4 | `0` | Phosphorus level. |
| `npk_k` | INT4 | `0` | Potassium level. |
| `npk_ok` | BOOLEAN | `f` (false) | **CRITICAL for ML:** If `false`, the NPK readings (0) are invalid and should be masked/dropped during training. |
| `leaf_r` | INT4 | `170` | TCS3200 Red frequency. Use to calculate color ratios for disease/chlorosis. |
| `leaf_g` | INT4 | `277` | TCS3200 Green frequency. |
| `leaf_b` | INT4 | `280` | TCS3200 Blue frequency. |
| `pump_on` | BOOLEAN | `t` (true) | The *target* variable for predictive irrigation models. |
| `mode` | TEXT | `AUTO` | `AUTO` or `MANUAL`. Exclude from training (leakage risk). |
| `uptime_s` | INT4 | `334` | Hardware diagnostic. Exclude from ML models. |

---

## 2. Important Notes for ML Implementation

If you are pulling data from the `/api/v1/sensors/export` endpoint (CSV download) to train your `scikit-learn` or `TensorFlow` models, keep the following quirks in mind:

### Missing Data & Hardware Anomalies
1. **The `npk_ok` Flag:** Modbus communication with the NPK probe can occasionally fail due to RS485 noise. The ESP32 will send `N=0, P=0, K=0` and set `npk_ok=false`. Your ML preprocessing pipeline **must** check `npk_ok` and impute/drop those rows. Do not train the model thinking the soil suddenly lost all nutrients.
2. **Rain Sensor is Inverted:** The `rain_raw` feature is an raw ADC value from `0` to `4095`. **4095 means completely dry.** 
3. **Color Sensor Normalization:** The `leaf_r`, `leaf_g`, and `leaf_b` values are raw pulse frequencies, not 0-255 RGB values. You must normalize them (e.g., `r_ratio = r / (r + g + b)`) before feeding them into a model, as the absolute values change with ambient sunlight.

### Feature Selection
For an **Irrigation Prediction Model**, your feature vector `X` should look like this:
`[soil_pct, temp_c, humidity_pct, rain_raw]`

For a **Crop Health / Fertilizer Model**, your feature vector `X` should look like this:
`[ph, tds_ppm, npk_n, npk_p, npk_k, leaf_r_norm, leaf_g_norm, leaf_b_norm]`

### Field Name Mapping Reference
If you interact with the REST API instead of the raw database, remember that the backend serializes the data with frontend-friendly aliases:
* `soil_pct` → `soilpct`
* `temp_c` → `tempc`
* `pump_on` → `pumpon`
* `rain_raw` → `rainraw`
