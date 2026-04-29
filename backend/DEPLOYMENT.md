# FarmShield — Deployment Guide

> **Stack:** FastAPI · TimescaleDB · Mosquitto — all containerised via Docker Compose.
> No Python, Postgres, or MQTT broker installation needed on the host — only Docker.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [How Configuration Works](#2-how-configuration-works)
3. [Laptop Development Setup](#3-laptop-development-setup)
4. [Raspberry Pi Production Setup](#4-raspberry-pi-production-setup)
5. [Config Reference — Laptop vs Pi](#5-config-reference--laptop-vs-pi)
6. [ESP32 Firmware Config](#6-esp32-firmware-config)
7. [Running the Stack](#7-running-the-stack)
8. [Health Verification](#8-health-verification)
9. [Data Management](#9-data-management)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

### Both environments

| Dependency | Min version | Check |
|---|---|---|
| Docker Engine | 24.x | `docker --version` |
| Docker Compose (plugin) | 2.x | `docker compose version` |
| Git | any | `git --version` |

**Raspberry Pi — install Docker via the official script** (the `apt` version is usually outdated):

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in
docker run --rm hello-world   # verify
```

---

## 2. How Configuration Works

All runtime config lives in one file: **`.env`**

- `docker-compose.yml` loads `.env` via `env_file: - .env`
- `server/app/config.py` reads the same variables via `pydantic-settings`
- You never edit `docker-compose.yml` or Python source to change config — only `.env`
- `.env.example` is the canonical reference with inline comments for every variable

**Key principle:** `.env` defaults are always the safe/production values. `docker-compose.override.yml` layers dev conveniences (live reload, source bind mounts) on top and is only merged when you run `docker compose up` without `-f`.

---

## 3. Laptop Development Setup

### First-time setup

```bash
git clone <repo-url>
cd NIRMITH26_NMIT

# Create your local .env — laptop defaults are already correct, no edits needed
cp .env.example .env

# Build and start (override file merged automatically → live reload enabled)
docker compose up --build -d

# Verify
docker compose ps
# Expected: all three containers show (healthy)
curl http://localhost:8000/api/v1/health
```

### Daily workflow

```bash
docker compose up -d                  # start
docker compose logs -f fastapi        # stream logs
docker compose down                   # stop, data preserved in volumes
docker compose down -v                # stop + wipe all data (clean slate)
docker compose up --build -d          # rebuild after code changes
```

Code changes inside `server/app/` automatically restart uvicorn (live reload via override).

### Running tests

```bash
cd server
pip install -e ".[dev]"
pytest tests/ -v
```

---

## 4. Raspberry Pi Production Setup

### First-time Pi setup

```bash
ssh pi@<pi-ip>

git clone <repo-url>
cd NIRMITH26_NMIT

cp .env.example .env
nano .env   # see Section 5 for required changes

# Start with BASE file only — no override, no live reload
docker compose -f docker-compose.yml up --build -d

# Verify
docker compose -f docker-compose.yml ps
curl http://localhost:8000/api/v1/health
```

> **Why `-f docker-compose.yml`?** The override file adds bind mounts (requires source code on host) and `--reload` (wasteful on Pi). Passing `-f` explicitly loads only the base file.

### Start on boot (systemd)

```bash
sudo nano /etc/systemd/system/farmshield.service
```

```ini
[Unit]
Description=FarmShield Docker Stack
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/pi/NIRMITH26_NMIT
ExecStart=/usr/bin/docker compose -f docker-compose.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.yml down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable farmshield.service
sudo systemctl start farmshield.service
```

---

## 5. Config Reference — Laptop vs Pi

### Variables you MUST change for Pi

| Variable | Laptop | Pi | Notes |
|---|---|---|---|
| `TARGET_ENV` | `laptop` | `pi` | Documentation only |
| `ESP32_MQTT_TARGET_IP` | Laptop LAN IP | **Pi LAN IP** | Reminder only — not read by backend |
| `AUTH_ENABLED` | `false` | **`true`** | Always enable in production |
| `API_KEY` | `dev-key-not-for-production` | **`openssl rand -hex 32`** | Must be strong random string |
| `DB_PASSWORD` | `farmshield123` | **strong password** | Change before first run |
| `MQTT_PASSWORD` | `farmshield123` | **strong password** | Must match `mosquitto/config/passwd` |
| `LOG_JSON` | `false` | `true` | JSON logs for systemd journal |
| `LOG_LEVEL` | `DEBUG` | `INFO` | Reduce noise |
| `FASTAPI_RELOAD` | `false` | `false` | Never enable on Pi |

### After changing MQTT password on Pi

```bash
# Regenerate the hashed passwd file inside the container
docker exec -it farmshield-mosquitto \
  mosquitto_passwd -b /mosquitto/config/passwd farmshield <new-password>

docker compose -f docker-compose.yml restart mosquitto
```

---

## 6. ESP32 Firmware Config

In `Hardware/farmshield.ino`, edit the USER CONFIG block:

```cpp
const char *WIFI_SSID  = "YOUR_WIFI_SSID";
const char *WIFI_PASS  = "YOUR_WIFI_PASSWORD";
const char *MQTT_HOST  = "192.168.1.106"; // ← Laptop or Pi LAN IP
const char *MQTT_USER  = "farmshield";
const char *MQTT_PASS  = "farmshield123"; // ← Must match MQTT_PASSWORD in .env
```

The firmware:
- **Publishes** to `farmshield/data` every 5 seconds
- **Subscribes** to `farmshield/control/pump`, `farmshield/control/mode`, `farmshield/control/buzzer`

---

## 7. Running the Stack

### Laptop

```bash
docker compose up -d                  # start (with override = live reload)
docker compose up --build -d          # rebuild + start
docker compose down                   # stop
docker compose down -v                # stop + delete all data
docker compose restart fastapi        # restart only the API container
```

### Pi

```bash
docker compose -f docker-compose.yml up -d
docker compose -f docker-compose.yml up --build -d   # after git pull
docker compose -f docker-compose.yml down
docker compose -f docker-compose.yml logs -f fastapi
```

> **Alembic migrations run automatically** at every startup via `entrypoint.sh`. You never run migrations manually.

---

## 8. Health Verification

Run these in order after starting:

```bash
# 1. All three containers show (healthy)
docker compose ps

# 2. API health check
curl http://localhost:8000/api/v1/health
# {"status":"ok","mqtt_connected":true,"db_connected":true,"ml_enabled":false,"version":"1.0.0"}

# 3. Simulate an ESP32 message
docker exec farmshield-mosquitto mosquitto_pub \
  -h localhost -u farmshield -P farmshield123 \
  -t farmshield/data -q 1 \
  -m '{"device":"farmshield_node1","temperature":29.1,"humidity":58.0,"soil":42.5,"tds":410.0,"rain":3200,"motion":false,"color":{"r":80,"g":140,"b":60},"npk":{"n":45,"p":30,"k":60,"ok":true},"pump":false,"mode":"AUTO","alert":"","uptime_s":100}'

# 4. Confirm reading in DB
docker exec farmshield-timescaledb psql -U farmshield -d farmshield \
  -c "SELECT device_id, temp_c, soil_pct, mode, uptime_s FROM sensor_readings ORDER BY time DESC LIMIT 1;"

# 5. Test from LAN (replace IP with your machine's IP)
curl http://192.168.1.106:8000/api/v1/health
```

### LAN reachability (verified on current setup)

| Service | Port | LAN address | Status |
|---|---|---|---|
| FastAPI REST + WebSocket | 8000 | `http://<host-ip>:8000` | ✅ |
| Mosquitto MQTT | 1883 | `<host-ip>:1883` | ✅ |
| TimescaleDB (PostgreSQL) | 5432 | `<host-ip>:5432` | ✅ |

> Port 5432 should be firewalled from external networks in production — only the FastAPI container needs it.

---

## 9. Data Management

### Retention policy

Sensor readings older than `RETENTION_DAYS` (default 7) are auto-dropped by TimescaleDB.

```dotenv
# in .env
RETENTION_DAYS=30   # keep 30 days; set to 0 to disable
```

Restart FastAPI after changing: `docker compose up -d fastapi`

### Backup

```bash
docker exec farmshield-timescaledb pg_dump \
  -U farmshield -d farmshield --format=custom \
  > backup_$(date +%Y%m%d).dump
```

### Restore

```bash
docker exec -i farmshield-timescaledb pg_restore \
  -U farmshield -d farmshield --clean < backup_20260427.dump
```

### Export CSV

```bash
curl "http://localhost:8000/api/v1/sensors/export?hours=168" \
  -o export_$(date +%Y%m%d).csv
```

---

## 10. Troubleshooting

### FastAPI container exits immediately

```bash
docker logs farmshield-fastapi
```

Common causes:
- `.env` missing or malformed — `MQTT_USERNAME`, `DB_USER`, `DB_PASSWORD` must be set
- TimescaleDB not yet healthy — wait 30 s then `docker compose up -d fastapi`
- Alembic migration failed — look for `alembic.runtime.migration` errors

### MQTT messages not ingested

```bash
docker logs farmshield-fastapi | grep "mqtt_connected"
# Must show: topic=farmshield/data (not farmshield/sensors)

docker logs farmshield-fastapi | grep "mqtt_message_received"
```

Check firmware: `MQTT_HOST` must be your machine's LAN IP, not `localhost`.

### API returning 401

When `AUTH_ENABLED=true`, every request (except `/api/v1/health`) needs:
```
Authorization: Bearer <API_KEY>
```

### Cannot reach from LAN

1. Check firewall: `sudo ufw status` — ports 8000 and 1883 must be `ALLOW`
2. Confirm Docker binds to `0.0.0.0`: `docker compose ps` should show `0.0.0.0:8000->8000/tcp`
3. ESP32 and backend must be on the same WiFi network / VLAN

### Pi disk full

```bash
docker system df -v          # show volume usage
docker image prune -f        # remove unused images after updates
```
