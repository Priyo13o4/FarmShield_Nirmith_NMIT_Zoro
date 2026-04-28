"""
FarmShield Backend — Sensor Endpoints.

GET /sensors/latest — most recent reading for a device
GET /sensors/history — paginated historical readings
GET /sensors/export — CSV download of historical readings
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_auth
from app.schemas.sensor import SensorHistoryResponse, SensorReadingOut
from app.services import sensor as sensor_service

router = APIRouter(prefix="/sensors", tags=["sensors"], dependencies=[Depends(require_auth)])


@router.get("/latest", response_model=SensorReadingOut)
async def get_latest_reading(
    device_id: str | None = Query(default=None, description="Target device (snake_case)"),
    deviceid: str | None = Query(default=None, description="Target device (camelCase/aliased)"),
    db: AsyncSession = Depends(get_db),
):
    """Return the most recent sensor reading for a device."""
    # Fallback logic to support frontend 'deviceid' param
    final_device_id = device_id or deviceid or "farmshield_node1"
    
    reading = await sensor_service.get_latest(db, final_device_id)
    if reading is None:
        raise HTTPException(
            status_code=404, 
            detail=f"No readings found for device '{final_device_id}'"
        )
    return reading


@router.get("/history", response_model=SensorHistoryResponse)
async def get_sensor_history(
    device_id: str = Query(default="farmshield_node1", description="Target device"),
    hours: int = Query(default=24, ge=1, le=168, description="Lookback window (max 168 = 7 days)"),
    limit: int = Query(default=500, ge=1, le=5000, description="Max rows returned"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
):
    """Return paginated historical sensor readings within a lookback window."""
    readings, total = await sensor_service.get_history(db, device_id, hours, limit, offset)
    return SensorHistoryResponse(
        count=total,
        device_id=device_id,
        readings=[SensorReadingOut.model_validate(r) for r in readings],
    )


@router.get("/export")
async def export_sensor_data(
    device_id: str = Query(default="farmshield_node1", description="Target device"),
    hours: int = Query(default=24, ge=1, le=168, description="Lookback window"),
    limit: int = Query(default=500, ge=1, le=5000, description="Max rows"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
):
    """Download sensor readings as CSV for external ML training."""
    csv_data = await sensor_service.export_csv_data(db, device_id, hours, limit, offset)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=farmshield_export.csv"},
    )
