from fastapi import APIRouter
from app.models.schemas import ZonesResponse, ZoneInfo
from app.services.zones import list_enabled_zones

router = APIRouter(prefix="/api", tags=["zones"])


@router.get("/zones", response_model=ZonesResponse)
def get_zones():
    return ZonesResponse(zones=[
        ZoneInfo(id=z["id"], display_name=z["display_name"],
                 bbox=z["bbox"], enabled=z["enabled"])
        for z in list_enabled_zones()
    ])