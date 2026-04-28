"""
FarmShield Backend — Control Pydantic Schemas.

Request bodies for pump, mode, and buzzer commands.
Inferred from PRD §10.3 payload examples (confirmed in Q2 answers).
"""

from typing import Literal

from pydantic import BaseModel


class PumpCommand(BaseModel):
    """POST /control/pump request body."""

    state: Literal["ON", "OFF"]


class ModeCommand(BaseModel):
    """POST /control/mode request body."""

    state: Literal["AUTO", "MANUAL"]


class BuzzerCommand(BaseModel):
    """POST /control/buzzer request body. Only silencing is supported from the API."""

    state: Literal["OFF"]


class ControlResponse(BaseModel):
    """Response shape for all control endpoints."""

    command: str
    state: str
    published: bool
    ts: int
