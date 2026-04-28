# FarmShield Knowledge Base — Irrigation Guide
# Source: FAO Irrigation and Drainage Paper No. 29, ICAR guidelines.
# This file is committed to the repo. The FAISS index built from it is gitignored.

## When to Irrigate — Soil Moisture Decision Rules

Use the FarmShield `soil_pct` reading (0–100%) as the primary trigger.

| Crop Stage        | Irrigate When soil_pct Falls Below | Target After Irrigation |
|-------------------|------------------------------------|-------------------------|
| Seedling / germination | 50%                          | 70–80%                  |
| Vegetative growth | 35%                                | 60–70%                  |
| Flowering         | 40% (critical stage — don't stress)| 65–75%                  |
| Grain filling     | 35%                                | 60–70%                  |
| Maturity / harvest| 20% (allow slight drying)          | No irrigation needed    |

### General Rule of Thumb

- **Dry alert threshold (FarmShield default):** `ALERT_SOIL_DRY_PCT = 30`  
  Irrigate immediately when `soil_pct < 30`.
- **Flood alert threshold:** `ALERT_SOIL_FLOOD_PCT = 85`  
  Stop irrigation and open drainage when `soil_pct > 85`.

## Rain Sensor Reading (rain_raw) Interpretation

FarmShield uses a capacitive rain sensor. Raw ADC output: 0–4095.

| rain_raw Range | Interpretation       | Recommended Action              |
|----------------|----------------------|---------------------------------|
| 0 – 500        | Heavy rain / sensor wet | Do NOT irrigate                |
| 500 – 1500     | Moderate rain        | Do NOT irrigate                 |
| 1500 – 2500    | Light rain / drizzle | Monitor; hold irrigation        |
| 2500 – 3500    | Dry conditions       | Evaluate soil_pct to decide     |
| 3500 – 4095    | Very dry             | Likely no rain; irrigate if soil_pct < threshold |

**FarmShield alert trigger:** `ALERT_RAIN_DRY_RAW = 2500` — alert fires when `rain_raw > 2500`.

Note: rain_raw is inverted — higher value = drier (more resistance = less water on sensor).

## TDS (Total Dissolved Solids) Water Quality Guide

FarmShield reads irrigation water TDS in ppm (mg/L). Sensor type: EC-based probe.

| TDS (ppm)  | Water Quality     | Suitable For                          |
|------------|-------------------|---------------------------------------|
| 0 – 300    | Excellent         | All crops, all stages                 |
| 300 – 600  | Good              | Most crops; optimal range             |
| 600 – 1000 | Acceptable        | Salt-tolerant crops only (cotton, sugarcane) |
| 1000 – 1500| Marginal          | Only halophytes; leach soil regularly |
| > 1500     | Poor / toxic      | FarmShield alert fires; do not use    |

### TDS and Nutrient Availability

High TDS often indicates:
- Excessive soluble salts from over-fertilization
- Contaminated bore well water (high Ca, Mg, Na)

Low TDS (< 50 ppm) is also problematic — rain or RO water lacks minerals; supplement with fertigation.

## Irrigation Timing Best Practices

1. **Early morning (5–8 AM):** Best time — low evaporation, leaf wetness dries before noon.
2. **Evening (6–8 PM):** Acceptable — but wet foliage overnight increases fungal risk.
3. **Midday:** Avoid — evaporative loss 30–40% higher than morning.

## Drip vs Flood Irrigation Decision

| Factor              | Drip                    | Flood                  |
|---------------------|-------------------------|------------------------|
| Water use efficiency| High (40–50% savings)   | Low                    |
| Capital cost        | High                    | Low                    |
| Salt buildup risk   | High (edge accumulation)| Low (leaching effect)  |
| FarmShield pump control | Suitable            | Suitable               |
| Soil type           | Sandy/loamy preferred   | Clay/flat fields       |

## Pump Control (FarmShield)

FarmShield can toggle pump state via MQTT topic `farmshield/control/pump`:
- Publish `{"state": "ON"}` to turn on  
- Publish `{"state": "OFF"}` to turn off  
- Auto-mode enables rule-based control using sensor thresholds
