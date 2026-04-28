"""
FarmShield Backend — Control Endpoints.

POST /control/pump — turn pump ON or OFF
POST /control/mode — switch AUTO / MANUAL
POST /control/buzzer — silence buzzer
"""

from fastapi import APIRouter, Depends

from app.dependencies import require_auth
from app.schemas.control import (
    BuzzerCommand,
    ControlResponse,
    ModeCommand,
    PumpCommand,
)
from app.services import control as control_service

router = APIRouter(prefix="/control", tags=["control"], dependencies=[Depends(require_auth)])


@router.post("/pump", response_model=ControlResponse)
async def pump_control(cmd: PumpCommand):
    """Turn the irrigation pump ON or OFF."""
    result = await control_service.send_pump_command(cmd.state)
    return ControlResponse(**result)


@router.post("/mode", response_model=ControlResponse)
async def mode_control(cmd: ModeCommand):
    """Switch between AUTO and MANUAL operation modes."""
    result = await control_service.send_mode_command(cmd.state)
    return ControlResponse(**result)


@router.post("/buzzer", response_model=ControlResponse)
async def buzzer_control(cmd: BuzzerCommand):
    """Silence the buzzer. Only OFF is supported from the API."""
    result = await control_service.send_buzzer_command(cmd.state)
    return ControlResponse(**result)
