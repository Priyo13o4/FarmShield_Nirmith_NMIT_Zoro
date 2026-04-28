# FarmShield — Issues and Fixes Log

This document tracks technical hurdles encountered during local development and the solutions implemented to resolve them.

---

## 1. Frontend/Backend Field Name Mismatch (Schema Mapping)

**Issue:** 
The backend was sending sensor data using database-aligned `snake_case` (e.g., `soil_pct`, `temp_c`, `pump_on`), but the frontend's dashboard components were expecting "flat" or `camelCase` keys (e.g., `soilpct`, `tempc`, `pumpon`). This caused the dashboard to show "No Data" even when the database was populated.

**Fix:**
Configured the `SensorReadingOut` Pydantic schema in the backend to use **serialization aliases**. The backend still uses clean snake_case internally, but automatically renames the fields in the JSON response to match the frontend's expectations.

- **File:** `backend/server/app/schemas/sensor.py`
- **Keys Mapped:** `deviceid`, `soilpct`, `tdsppm`, `tempc`, `humiditypct`, `rainraw`, `npkn`, `npkp`, `npkk`, `leafr`, `leafg`, `leafb`, `pumpon`.

---

## 2. CORS (Cross-Origin Resource Sharing)

**Issue:**
The frontend (running on `localhost:5173`) was unable to communicate with the backend (`localhost:8000`) because the browser blocked the requests. The backend logs showed `405 Method Not Allowed` for preflight `OPTIONS` requests.

**Fix:**
Added `CORSMiddleware` to the FastAPI application to allow all origins and methods during local development.

- **File:** `backend/server/app/main.py`

---

## 3. Health Check Path Mismatch

**Issue:**
The frontend was hardcoded to check health at `http://localhost:8000/health`, but the backend API followed a versioned structure at `http://localhost:8000/api/v1/health`, resulting in a `404 Not Found`.

**Fix:**
Added a root-level redirect in the backend that forwards any request from `/health` to `/api/v1/health`.

- **File:** `backend/server/app/main.py`

---

## 4. Query Parameter Mismatch (`deviceid` vs `device_id`)

**Issue:**
The frontend sent the target device as a query parameter named `deviceid`, but the backend endpoint expected `device_id`.

**Fix:**
Updated the `/sensors/latest` endpoint to accept both `device_id` and `deviceid` parameters, with a fallback logic to ensure compatibility.

- **File:** `backend/server/app/api/v1/sensors.py`

---

## 5. Slow Startup due to Chat Dependencies

**Issue:**
Setting `CHAT_ENABLED=true` caused the backend to take ~2 minutes to start because it was downloading heavy libraries (LangChain, FAISS) at runtime every time the container was created.

**Fix:**
Modified the `Dockerfile` to install these dependencies during the image build process (via the `[chat]` optional dependency in `pyproject.toml`) and removed the runtime installation from `entrypoint.sh`.

- **Files:** `backend/server/Dockerfile`, `backend/server/entrypoint.sh`, `backend/server/pyproject.toml`

---

## 6. Docker Container Name Conflicts

**Issue:**
Manual restarts sometimes caused Docker to complain that a container name (e.g., `/farmshield-mosquitto`) was already in use by a "ghost" container.

**Fix:**
Recommended a cleanup command to force-remove existing containers before running compose:
`docker rm -f farmshield-mosquitto farmshield-fastapi farmshield-timescaledb`
