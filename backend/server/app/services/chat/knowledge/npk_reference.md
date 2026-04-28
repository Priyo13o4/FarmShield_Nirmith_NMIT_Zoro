# FarmShield Knowledge Base — NPK Reference
# Source: ICAR Crop Production & Protection Guidelines, Soil Health Card scheme.
# This file is committed to the repo. The FAISS index built from it is gitignored.

## What Is NPK?

NPK refers to the three primary macronutrients in plant nutrition:
- **N — Nitrogen:** Leaf growth, chlorophyll, protein synthesis
- **P — Phosphorus:** Root development, flowering, energy transfer (ATP)
- **K — Potassium:** Water regulation, disease resistance, fruit quality

FarmShield measures NPK in **mg/kg (ppm)** using an RS-485 Modbus soil sensor.

## NPK Optimal Ranges by Crop

| Crop      | N (mg/kg) | P (mg/kg) | K (mg/kg) |
|-----------|-----------|-----------|-----------|
| Rice      | 280 – 560 | 10 – 25   | 110 – 280 |
| Wheat     | 280 – 560 | 20 – 40   | 140 – 280 |
| Maize     | 280 – 420 | 25 – 50   | 140 – 280 |
| Tomato    | 210 – 420 | 20 – 40   | 200 – 350 |
| Sugarcane | 280 – 420 | 15 – 30   | 200 – 350 |
| Cotton    | 210 – 420 | 15 – 30   | 140 – 280 |
| Groundnut | 140 – 280 | 25 – 50   | 140 – 280 |
| Soybean   | 140 – 280 | 20 – 40   | 140 – 280 |
| Potato    | 280 – 420 | 25 – 50   | 200 – 400 |
| Onion     | 210 – 350 | 20 – 40   | 175 – 280 |

*Note: These are indicative ranges. Optimal values vary with soil type and growth stage.*

## NPK Deficiency Symptoms

### Nitrogen (N) Deficiency
- **Symptom:** Yellowing of older/lower leaves (chlorosis), starting at leaf tips
- **Cause:** N is mobile — plant scavenges it from older tissue
- **FarmShield indicator:** Low N mg/kg reading from sensor
- **Fix:** Apply urea (46-0-0), ammonium sulphate, or organic compost
- **Caution:** Excess N causes excessive vegetative growth, delays fruiting

### Phosphorus (P) Deficiency
- **Symptom:** Purplish/reddish discolouration of leaves and stems; poor root growth
- **Cause:** P is important for ATP synthesis; deficiency limits energy metabolism
- **FarmShield indicator:** Low P mg/kg reading
- **Fix:** Apply DAP (18-46-0), SSP (Single Super Phosphate)
- **Caution:** P is immobile in soil; apply before planting for best root uptake

### Potassium (K) Deficiency
- **Symptom:** Scorching/browning of leaf edges (marginal leaf scorch); weak stems
- **Cause:** K regulates stomatal opening; deficiency causes water stress symptoms
- **FarmShield indicator:** Low K mg/kg reading
- **Fix:** Apply MOP (Muriate of Potash, 0-0-60), SOP (Sulphate of Potash)
- **Caution:** Excess K can antagonize Mg and Ca uptake

## Recommended NPK Ratios for Common Crops

| Crop      | N : P : K Ratio | Application Notes                         |
|-----------|-----------------|-------------------------------------------|
| Rice      | 4 : 2 : 1      | Split N in 3 doses (basal, tillering, PI) |
| Wheat     | 4 : 2 : 1      | 50% N at sowing, 50% at 1st irrigation   |
| Maize     | 4 : 2 : 2      | Apply K with P at sowing                 |
| Tomato    | 3 : 2 : 3      | High K for fruit quality and shelf life  |
| Sugarcane | 4 : 2 : 2      | Ratoon crop needs extra K                |
| Potato    | 3 : 2 : 4      | Highest K requirement of common crops    |

## Interpreting Modbus NPK Sensor Output

FarmShield uses a 3-parameter or 7-parameter RS-485 sensor:
- **Register format:** Each nutrient is one 16-bit register (raw integer)
- **Conversion:** raw value × 0.1 = mg/kg in most common sensors
- **Calibration:** Values may need factory calibration constant (see sensor datasheet)
- **Units:** Always mg/kg (= ppm by weight in soil)

### Reading Consistency

NPK sensors give **point-in-time readings** — values fluctuate based on:
- Recent rainfall (dilution effect lowers apparent values)
- Temperature (low temp reduces microbial N mineralization)
- Sampling depth (usually 0–30 cm topsoil layer)

For reliable diagnosis, average 3+ readings taken at different times of day.

## Secondary and Micronutrients (not measured by FarmShield)

| Nutrient  | Deficiency Sign           | Fix                    |
|-----------|---------------------------|------------------------|
| Calcium   | Tip burn, blossom end rot | Lime, gypsum           |
| Magnesium | Interveinal chlorosis     | Dolomite, Epsom salt   |
| Sulphur   | Uniform yellowing         | Elemental S, gypsum    |
| Zinc      | Small leaves, shortened internodes | ZnSO4 spray |
| Iron      | Interveinal chlorosis (new leaves) | Chelated Fe spray |
| Boron     | Hollow heart, poor pollination | Borax at 0.2% |
