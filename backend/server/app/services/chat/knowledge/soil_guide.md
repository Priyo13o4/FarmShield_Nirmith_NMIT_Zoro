# FarmShield Knowledge Base — Soil Health Guide
# Source: ICAR (Indian Council of Agricultural Research) crop management guidelines.
# This file is committed to the repo. The FAISS index built from it is gitignored.


## Soil Moisture % Interpretation (FarmShield sensor)

The FarmShield sensor reports soil moisture as a percentage (0–100%).

| Range     | Interpretation                  | Action                              |
|-----------|---------------------------------|-------------------------------------|
| 0 – 10%   | Bone dry — critical drought     | Irrigate immediately                |
| 10 – 30%  | Dry — plant stress likely       | Irrigate soon (< 24 h)              |
| 30 – 60%  | Adequate — most crops healthy   | No action; monitor daily            |
| 60 – 80%  | Moist — good for rice           | Monitor for waterlogging            |
| 80 – 95%  | Waterlogged — most crop stress  | Stop irrigation; open drainage      |
| 95 – 100% | Saturation — likely flooding    | Emergency drainage; root rot risk   |

The alert thresholds (configurable) default to:
- `ALERT_SOIL_DRY_PCT = 30` — triggers "dry soil" alert below this
- `ALERT_SOIL_FLOOD_PCT = 85` — triggers "waterlogging" alert above this

## NPK Reading Units

FarmShield reads NPK via RS-485 Modbus sensor (4-in-1 or 7-in-1 type):
- **N (Nitrogen):** mg/kg (ppm)  
- **P (Phosphorus):** mg/kg (ppm)  
- **K (Potassium):** mg/kg (ppm)  

## Soil Classification by Texture

- **Sandy:** Drains fast, low water retention. Needs frequent light irrigation.
- **Clay:** Retains water well, compacts easily. Risk of waterlogging.
- **Loamy:** Balanced drainage and retention. Ideal for most crops.
- **Black cotton soil (Vertisol):** High clay, swells when wet. Common in Deccan Plateau.

## Salinity and TDS

Soil salinity is indirectly indicated by irrigation water TDS (Total Dissolved Solids, ppm):
- **< 300 ppm:** Excellent — all crops
- **300 – 600 ppm:** Good — most crops
- **600 – 1000 ppm:** Tolerable — salt-tolerant crops (sugarcane, cotton)
- **1000 – 1500 ppm:** Marginal — only halophytes
- **> 1500 ppm:** Toxic — FarmShield default alert threshold
