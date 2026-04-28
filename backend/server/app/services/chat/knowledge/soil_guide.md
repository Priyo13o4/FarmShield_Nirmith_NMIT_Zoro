# FarmShield Knowledge Base — Soil Health Guide
# Source: ICAR (Indian Council of Agricultural Research) crop management guidelines.
# This file is committed to the repo. The FAISS index built from it is gitignored.

## Soil pH Ranges by Crop

| Crop       | Optimal pH | Notes                                      |
|------------|------------|--------------------------------------------|
| Rice       | 5.5 – 6.5  | Tolerates slight acidity; avoid above 7.0  |
| Wheat      | 6.0 – 7.5  | Prefers near-neutral; sensitive to acidity |
| Tomato     | 5.8 – 6.8  | Slight acidity preferred                   |
| Sugarcane  | 6.0 – 7.5  | Wide range; avoid waterlogging             |
| Cotton     | 6.0 – 8.0  | Tolerates alkalinity better than most      |
| Potato     | 4.8 – 5.5  | Strongly acid-preferring                   |
| Maize      | 5.8 – 7.0  | Neutral preferred                          |
| Groundnut  | 5.5 – 6.5  | Same as rice; needs calcium at low pH      |
| Soybean    | 6.0 – 7.0  | Neutral preferred for nodule formation     |
| Onion      | 5.8 – 7.0  | Neutral; sensitive to acidic irrigation    |

## Interpreting pH Sensor Readings (FarmShield 0–14 scale)

- **Below 4.5** — Very strongly acidic. Apply lime immediately. Most crops will show iron/manganese toxicity.
- **4.5 – 5.5** — Strongly acidic. Apply dolomitic lime. Rice, potato can survive but most crops suffer.
- **5.5 – 6.5** — Slightly acidic. Ideal for rice, tomato, groundnut. Most nutrients are available.
- **6.5 – 7.5** — Neutral. Ideal for wheat, maize, soybean. Maximum nutrient availability.
- **7.5 – 8.5** — Slightly alkaline. Apply sulfur or acidifying fertilizers. Micronutrient deficiencies common.
- **Above 8.5** — Strongly alkaline. Serious nutrient lockout. Gypsum application required.

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
