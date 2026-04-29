from fastapi import APIRouter, Depends, HTTPException
from app.config import settings
from app.schemas.dev import NPKOverrideRequest, NPKOverrideResponse

router = APIRouter(prefix="/dev", tags=["dev"])

def require_dev_enabled():
    if not settings.npk_override_enabled:
        raise HTTPException(status_code=403, detail={
            "detail": "Dev override endpoints are disabled on this deployment.",
            "type": "FEATURE_DISABLED"
        })

@router.post("/npk-override", response_model=NPKOverrideResponse,
             dependencies=[Depends(require_dev_enabled)])
async def set_npk_override(body: NPKOverrideRequest):
    if settings.npk_override_enabled:
        from app.services.dev.npk_override import npk_override, NPK_PROFILES
        npk_override.set(body.profile)
        profile_data = NPK_PROFILES.get(body.profile)
        return NPKOverrideResponse(
            active_profile=body.profile,
            label=profile_data["label"] if profile_data else "Override OFF",
            ranges=profile_data
        )

@router.get("/npk-override", response_model=NPKOverrideResponse,
            dependencies=[Depends(require_dev_enabled)])
async def get_npk_override():
    if settings.npk_override_enabled:
        from app.services.dev.npk_override import npk_override, NPK_PROFILES
        active = npk_override.get()
        profile_data = NPK_PROFILES.get(active)
        return NPKOverrideResponse(
            active_profile=active,
            label=profile_data["label"] if profile_data else "Override OFF",
            ranges=profile_data
        )
