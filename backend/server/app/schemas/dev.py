from pydantic import BaseModel
from typing import Literal

ProfileKey = Literal["sample1", "sample2", "sample3", "random", "null"]

class NPKOverrideRequest(BaseModel):
    profile: ProfileKey

class NPKOverrideResponse(BaseModel):
    active_profile: ProfileKey
    label: str
    ranges: dict | None
