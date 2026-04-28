# FarmShield — Issues & Fixes Log

This document tracks technical hurdles encountered during the setup and development of FarmShield, along with their resolutions.

## 1. Frontend-Backend Naming Mismatch (Schema Mapping)
- **Issue:** The backend was using `snake_case` (e.g., `soil_pct`, `temp_c`) while the React frontend expected flat or aliased names (e.g., `soilpct`, `tempc`). This resulted in "No Data" being displayed in the dashboard despite a populated database.
- **Fix:** Updated the backend `SensorReadingOut` schema in `app/schemas/sensor.py` to use `serialization_alias`. The backend now exports data using the keys the frontend expects (e.g., `soilpct`).
- **Evidence:** `backend/server/app/schemas/sensor.py`, `farmshield-frontend/src/context/FarmContext.jsx`.

## 2. CORS (Cross-Origin Resource Sharing)
- **Issue:** The browser blocked the frontend (localhost:5173) from talking to the backend (localhost:8000) due to missing CORS headers.
- **Fix:** Added `CORSMiddleware` to `backend/server/app/main.py`.

## 3. Health Check Path Mismatch
- **Issue:** The frontend was hardcoded to check `/health`, but the backend API versioned its health check at `/api/v1/health`.
- **Fix:** Added a root-level redirect in `main.py` from `/health` to `/api/v1/health`.

## 4. Docker Container Name Conflict
- **Issue:** Manual container runs or previous crashed sessions left "ghost" containers (e.g., `farmshield-mosquitto`) that blocked `docker compose up`.
- **Fix:** Users should run `docker rm -f farmshield-mosquitto farmshield-fastapi farmshield-timescaledb` before restarting if conflicts occur.

## 5. Slow Cold-Start (AI Dependencies)
- **Issue:** Installing `langchain`, `faiss`, and `google-genai` at runtime in `entrypoint.sh` took ~2 minutes every time the container was recreated.
- **Fix:** Moved these dependencies into the `Dockerfile` so they are baked into the image during build. Startup is now near-instant regardless of the `CHAT_ENABLED` setting.
