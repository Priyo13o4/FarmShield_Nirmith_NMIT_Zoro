"""
FarmShield Backend — Alert Pydantic Schemas.

AlertOut: API response shape (PRD §11).
AlertListResponse: paginated alert list wrapper.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlertOut(BaseModel):
    """API response shape for a single alert (PRD §11)."""

    id: UUID
    time: datetime
    device_id: str
    type: str
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    message: str
    acknowledged: bool

    model_config = ConfigDict(from_attributes=True)


class AlertListResponse(BaseModel):
    """Paginated alert list wrapper."""

    count: int
    alerts: list[AlertOut]
