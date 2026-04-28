"""
FarmShield Backend — Alert Endpoints.

GET /alerts — list recent alerts
PATCH /alerts/{alert_id}/acknowledge — mark alert as acknowledged
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_auth
from app.schemas.alert import AlertListResponse, AlertOut
from app.services import alert as alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"], dependencies=[Depends(require_auth)])


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    device_id: str = Query(default="farmshield_node1", description="Target device"),
    limit: int = Query(default=50, ge=1, le=500, description="Max alerts returned"),
    unacknowledged_only: bool = Query(default=False, description="Filter to unacked only"),
    db: AsyncSession = Depends(get_db),
):
    """List recent alerts for a device."""
    alerts = await alert_service.get_alerts(db, device_id, limit, unacknowledged_only)
    return AlertListResponse(
        count=len(alerts),
        alerts=[AlertOut.model_validate(a) for a in alerts],
    )


@router.patch("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Mark a specific alert as acknowledged."""
    alert = await alert_service.acknowledge_alert(db, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return AlertOut.model_validate(alert)
