from __future__ import annotations

import json as _json
import time

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MLInference
from app.dependencies import get_db, require_auth
from app.schemas.audio import AudioInferenceOut, DemoTriggerRequest, DemoTriggerResponse
from app.services.audio_inference import (
    DEMO_PAYLOADS,
    process_audio,
    publish_demo_payload,
)

router = APIRouter(prefix="/audio", tags=["Audio Pest Detection"])
logger = structlog.get_logger(__name__)


@router.get(
    "/latest",
    response_model=AudioInferenceOut | None,
    summary="Latest audio inference result",
)
async def get_latest_audio(
    deviceid: str = Query(default="farmshield_node1"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_auth),
):
    stmt = (
        select(MLInference)
        .where(
            MLInference.device_id == deviceid,
            MLInference.model_name == "audio_rule_v1",
        )
        .order_by(MLInference.time.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return _row_to_out(row)


@router.get(
    "/history",
    response_model=list[AudioInferenceOut],
    summary="Paginated audio inference history",
)
async def get_audio_history(
    deviceid: str = Query(default="farmshield_node1"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_auth),
):
    stmt = (
        select(MLInference)
        .where(
            MLInference.device_id == deviceid,
            MLInference.model_name == "audio_rule_v1",
        )
        .order_by(MLInference.time.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [_row_to_out(r) for r in rows]


@router.post(
    "/demo",
    response_model=DemoTriggerResponse,
    summary="Trigger demo pest detection (judge demo endpoint)",
)
async def trigger_demo(
    body: DemoTriggerRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_auth),
):
    """
    Publishes a pre-crafted MQTT audio payload that runs through
    the full inference pipeline end-to-end.
    Use during live demo to guarantee detection fires on command.
    """
    published = await publish_demo_payload(body.pest_class)

    # Also directly process it so the response returns the result immediately
    raw = dict(DEMO_PAYLOADS[body.pest_class])
    raw["ts"] = int(time.time())
    raw["deviceid"] = body.deviceid

    out = await process_audio(raw, db)

    return DemoTriggerResponse(
        status="ok",
        pest_class=out.pest_class,
        confidence=out.confidence,
        alert_triggered=out.alert_triggered,
        mqtt_payload_published=published,
    )


def _row_to_out(row: MLInference) -> AudioInferenceOut:
    """Convert an ORM MLInference row to AudioInferenceOut schema."""
    all_scores: dict[str, float] = {}
    db_level = 0.0
    dominant_freq_hz = 0.0
    try:
        parsed = _json.loads(row.raw_output or "{}")
        db_level = parsed.pop("_db_level", 0.0)
        dominant_freq_hz = parsed.pop("_dominant_freq_hz", 0.0)
        all_scores = parsed
    except Exception:
        pass
    return AudioInferenceOut(
        id=row.id,
        time=row.time,
        deviceid=row.device_id,
        pest_class=row.prediction or "unknown",
        confidence=row.confidence or 0.0,
        db_level=db_level,
        dominant_freq_hz=dominant_freq_hz,
        all_scores=all_scores,
        alert_triggered=False,  # historical — not re-evaluated
    )
