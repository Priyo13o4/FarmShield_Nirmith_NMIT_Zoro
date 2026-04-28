"""
FarmShield Backend — Sensor Pydantic Schemas.

SensorPayload: inbound MQTT JSON from ESP32 (PRD §8.1)
SensorReadingOut: outbound API response (PRD §11)
SensorHistoryResponse: paginated history wrapper

Field naming note:
  The firmware publishes abbreviated / different field names from the DB
  column names. SensorPayload uses Field(alias=...) to accept the firmware
  names while the internal attribute names stay aligned with the DB schema.
  populate_by_name=True allows SensorPayload(**data) to work alongside
  SensorPayload.model_validate(data), keeping the ingestion call site unchanged.
"""

from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SensorPayload(BaseModel):
    """
    Raw MQTT payload from ESP32 firmware.

    All numeric sensor fields are optional to tolerate individual sensor
    failures. A payload where ALL numeric fields are None is rejected.

    Field aliases map firmware JSON keys → internal attribute names which
    match DB column names. The before-validator flattens the nested
    `color` and `npk` objects before field assignment.
    """

    model_config = ConfigDict(
        populate_by_name=True,  # allows SensorPayload(**data) AND model_validate(data)
    )

    # ── Identity ─────────────────────────────────────────────────────────
    device_id: str = Field(alias="device")  # firmware sends "device", DB column is "device_id"

    # ── Core sensor readings (aliases = firmware JSON keys) ───────────────
    temp_c: float | None = Field(default=None, alias="temperature")
    humidity_pct: float | None = Field(default=None, alias="humidity")
    soil_pct: float | None = Field(default=None, alias="soil")
    tds_ppm: float | None = Field(default=None, alias="tds")
    ph: float | None = None                   # same name in firmware and DB
    rain_raw: int | None = Field(default=None, alias="rain")
    motion: bool | None = None                # same name in firmware and DB

    # ── Color sensor (flattened from nested {"r":..,"g":..,"b":..}) ──────
    leaf_r: int | None = None
    leaf_g: int | None = None
    leaf_b: int | None = None

    # ── NPK sensor (flattened from nested {"n":..,"p":..,"k":..,"ok":..})
    npk_n: int | None = None
    npk_p: int | None = None
    npk_k: int | None = None
    npk_ok: bool | None = None               # whether Modbus read succeeded

    # ── Actuator / state fields ───────────────────────────────────────────
    pump_on: bool = Field(default=False, alias="pump")

    # ── New firmware fields ───────────────────────────────────────────────
    mode: str | None = None  # firmware operating mode field — safe in Pydantic v2, does not shadow model_validator mode kwarg
    uptime_s: int | None = None

    # ── Timestamp — firmware does NOT send this; always falls back to NOW()
    ts: int | None = None  # Unix epoch from ESP32 (not present in current firmware)

    # ── Firmware alert string — accepted to avoid validation rejection,
    #    but deliberately NOT stored or used for alert generation.
    #    The backend generates its own threshold-based alerts independently.
    alert: str | None = None

    # ── Pre-field validator: flatten nested objects ───────────────────────
    @model_validator(mode="before")
    @classmethod
    def flatten_nested_objects(cls, data: Any) -> Any:
        """
        Flatten firmware's nested `color` and `npk` dicts into top-level fields
        before Pydantic assigns them to attributes.

        Input:  {"color": {"r": 80, "g": 140, "b": 60}, "npk": {"n": 45, ...}}
        Output: {"leaf_r": 80, "leaf_g": 140, "leaf_b": 60, "npk_n": 45, ...}
        """
        if not isinstance(data, dict):
            return data

        color = data.pop("color", None)
        if isinstance(color, dict):
            data.setdefault("leaf_r", color.get("r"))
            data.setdefault("leaf_g", color.get("g"))
            data.setdefault("leaf_b", color.get("b"))

        npk = data.pop("npk", None)
        if isinstance(npk, dict):
            data.setdefault("npk_n", npk.get("n"))
            data.setdefault("npk_p", npk.get("p"))
            data.setdefault("npk_k", npk.get("k"))
            data.setdefault("npk_ok", npk.get("ok"))

        return data

    # ── Post-field validator: require at least one numeric reading ─────────
    @model_validator(mode="after")
    def at_least_one_numeric_field(self) -> Self:
        """
        Reject payloads where ALL numeric sensor fields are None.
        motion, leaf_r/g/b, pump_on, npk_ok, mode, uptime_s are excluded —
        they are boolean/state fields and alone don't constitute a live reading.
        """
        numeric_fields = [
            self.soil_pct,
            self.ph,
            self.tds_ppm,
            self.temp_c,
            self.humidity_pct,
            self.rain_raw,
            self.npk_n,
            self.npk_p,
            self.npk_k,
        ]
        if not any(v is not None for v in numeric_fields):
            raise ValueError(
                "Payload rejected: all numeric sensor fields are None. "
                "At least one of soil_pct, ph, tds_ppm, temp_c, humidity_pct, "
                "rain_raw, npk_n, npk_p, npk_k must be present."
            )
        return self


class SensorReadingOut(BaseModel):
    """API response shape for a single sensor reading (PRD §11).

    Field names reflect DB column names, but aliases are used for 
    serialization to match the frontend's expected keys.
    """

    time: datetime
    device_id: str = Field(serialization_alias="deviceid")
    soil_pct: float | None = Field(default=None, serialization_alias="soilpct")
    ph: float | None = None
    tds_ppm: float | None = Field(default=None, serialization_alias="tdsppm")
    temp_c: float | None = Field(default=None, serialization_alias="tempc")
    humidity_pct: float | None = Field(default=None, serialization_alias="humiditypct")
    rain_raw: int | None = Field(default=None, serialization_alias="rainraw")
    motion: bool | None = None
    npk_n: int | None = Field(default=None, serialization_alias="npkn")
    npk_p: int | None = Field(default=None, serialization_alias="npkp")
    npk_k: int | None = Field(default=None, serialization_alias="npkk")
    npk_ok: bool | None = None
    leaf_r: int | None = Field(default=None, serialization_alias="leafr")
    leaf_g: int | None = Field(default=None, serialization_alias="leafg")
    leaf_b: int | None = Field(default=None, serialization_alias="leafb")
    pump_on: bool = Field(default=False, serialization_alias="pumpon")
    mode: str | None = None
    uptime_s: int | None = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        serialize_by_alias=True  # Ensure aliases are used in JSON response
    )


class SensorHistoryResponse(BaseModel):
    """Paginated sensor history wrapper."""

    count: int
    device_id: str
    readings: list[SensorReadingOut]
